"""
신규 오픈 알림 서비스 (기능 C).

최근 오픈 장소를 탐지하고 콘솔/이메일 등으로 알림을 전달합니다.
"""

import smtplib
from email.mime.text import MIMEText

from models.alert import NewOpeningAlert
from models.place import Place
from services.filter_service import FilterService
from services.new_opening_discovery import NewOpeningDiscovery
from services.place_enricher import PlaceEnricher
from services.recommendation_service import RecommendationService
from config.settings import Settings, get_settings
from utils.errors import AlertDeliveryError, ConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)


class AlertService:
    """신규 오픈 탐지 및 알림 발송."""

    def __init__(
        self,
        recommendation_service: RecommendationService,
        filter_service: FilterService | None = None,
        settings: Settings | None = None,
        *,
        use_blog_crawler: bool = True,
    ) -> None:
        self._recommendation = recommendation_service
        self._filter = filter_service or FilterService()
        self._settings = settings or get_settings()
        self._use_blog_crawler = use_blog_crawler
        self._enricher = PlaceEnricher(enable_crawl=False)

    def detect_new_openings(self) -> list[NewOpeningAlert]:
        """
        주변 신규 오픈 장소를 탐지해 알림 객체 목록을 반환합니다.

        1) Provider + Enricher(크롤링/수동 DB)로 opened_at 보강
        2) Naver 블로그/뉴스 신규오픈 검색 결과 병합
        """
        places = self._recommendation.fetch_all_nearby()

        if self._use_blog_crawler:
            try:
                blog_places = NewOpeningDiscovery(self._settings).fetch_candidates()
                places = self._enricher.merge_duplicates(places + blog_places)
            except Exception as exc:
                logger.warning("신규 오픈 후보 수집 스킵: %s", exc)

        new_places = self._filter.filter_new_openings(places)

        alerts: list[NewOpeningAlert] = []
        for place in new_places:
            try:
                alerts.append(NewOpeningAlert.from_place(place))
            except ValueError as exc:
                logger.debug("알림 생성 스킵: %s", exc)
        return alerts

    def send_console_alerts(self, alerts: list[NewOpeningAlert]) -> None:
        """개발/테스트용: 콘솔에 알림 출력."""
        if not alerts:
            logger.info("신규 오픈 알림 없음.")
            return
        for alert in alerts:
            print(alert.message)

    def send_email_alerts(self, alerts: list[NewOpeningAlert]) -> None:
        """
        SMTP로 이메일 알림을 발송합니다.

        SMTP 설정이 없으면 ConfigurationError를 발생시킵니다.
        """
        if not alerts:
            logger.info("발송할 신규 오픈 알림 없음.")
            return

        if not all(
            [
                self._settings.smtp_host,
                self._settings.smtp_user,
                self._settings.alert_recipient_email,
            ]
        ):
            raise ConfigurationError(
                "이메일 알림을 위해 SMTP_HOST, SMTP_USER, ALERT_RECIPIENT_EMAIL을 설정하세요.",
            )

        body = "\n\n".join(a.message for a in alerts)
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = f"[맛집탐방] 신규 오픈 {len(alerts)}건"
        msg["From"] = self._settings.smtp_user
        msg["To"] = self._settings.alert_recipient_email

        try:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
            ) as server:
                server.starttls()
                if self._settings.smtp_password:
                    server.login(
                        self._settings.smtp_user,
                        self._settings.smtp_password,
                    )
                server.send_message(msg)
            logger.info("이메일 알림 %d건 발송 완료", len(alerts))
        except smtplib.SMTPException as exc:
            raise AlertDeliveryError(
                "이메일 발송에 실패했습니다.",
                cause=exc,
            ) from exc

    def run_alert_check(self, *, use_email: bool = False) -> list[NewOpeningAlert]:
        """
        알림 파이프라인 전체 실행: 탐지 → 출력/발송.

        Returns:
            생성된 알림 목록
        """
        alerts = self.detect_new_openings()
        self.send_console_alerts(alerts)
        if use_email:
            self.send_email_alerts(alerts)
        return alerts
