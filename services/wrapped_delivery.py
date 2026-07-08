"""
Monthly Wrapped 알림 발송.

AlertService와 동일한 콘솔/이메일 채널 패턴을 따릅니다.
"""

import smtplib
from datetime import date
from pathlib import Path

from adapters.diary_adapter import FileDiaryAdapter
from adapters.place_catalog_adapter import PlaceCatalogAdapter
from config.settings import Settings, get_settings
from email.mime.text import MIMEText

from models.wrapped import WrappedReport
from services.wrapped_generator import WrappedGenerator
from services.wrapped_renderer import ConsoleWrappedRenderer
from utils.business_calendar import is_last_business_day_of_month
from utils.errors import AlertDeliveryError, ConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_DIARY_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "diary" / "default.json"
)


class WrappedDelivery:
    """Wrapped 생성 및 전달."""

    def __init__(
        self,
        generator: WrappedGenerator | None = None,
        renderer: ConsoleWrappedRenderer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._generator = generator or WrappedGenerator(
            FileDiaryAdapter(_DEFAULT_DIARY_PATH),
            PlaceCatalogAdapter(),
        )
        self._renderer = renderer or ConsoleWrappedRenderer()

    def generate_for_month(self, year: int, month: int) -> WrappedReport:
        return self._generator.generate(year, month)

    def generate_for_previous_month(self, today: date | None = None) -> WrappedReport:
        """전월 Wrapped를 생성합니다 (월말 배치용)."""
        ref = today or date.today()
        if ref.month == 1:
            year, month = ref.year - 1, 12
        else:
            year, month = ref.year, ref.month - 1
        return self.generate_for_month(year, month)

    def send_console(self, report: WrappedReport) -> None:
        self._renderer.print(report)

    def send_email(self, report: WrappedReport) -> None:
        if not all(
            [
                self._settings.smtp_host,
                self._settings.smtp_user,
                self._settings.alert_recipient_email,
            ],
        ):
            raise ConfigurationError(
                "이메일 발송을 위해 SMTP_HOST, SMTP_USER, ALERT_RECIPIENT_EMAIL을 설정하세요.",
            )

        body = self._renderer.render(report)
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = f"[맛집 Wrapped] {report.month_label} 탐방 리포트"
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
            logger.info("Wrapped 이메일 발송 완료: %s", report.month_label)
        except smtplib.SMTPException as exc:
            raise AlertDeliveryError(
                "Wrapped 이메일 발송에 실패했습니다.",
                cause=exc,
            ) from exc

    def run_monthly(
        self,
        *,
        use_email: bool = False,
        force: bool = False,
        today: date | None = None,
    ) -> WrappedReport | None:
        """
        월말 영업일에만 Wrapped를 생성·전달합니다.

        force=True면 날짜 조건을 무시합니다 (테스트/수동 실행용).
        """
        ref = today or date.today()
        if not force and not is_last_business_day_of_month(ref):
            logger.info(
                "오늘은 월말 영업일이 아닙니다 — Wrapped 배치 스킵 (%s)",
                ref.isoformat(),
            )
            return None

        report = self.generate_for_previous_month(ref)
        self.send_console(report)
        if use_email:
            self.send_email(report)
        return report

    @staticmethod
    def from_paths(
        diary_path: str,
        places_path: str | None = None,
        settings: Settings | None = None,
    ) -> "WrappedDelivery":
        generator = WrappedGenerator(
            FileDiaryAdapter(diary_path),
            PlaceCatalogAdapter(places_path) if places_path else PlaceCatalogAdapter(),
        )
        return WrappedDelivery(generator=generator, settings=settings)
