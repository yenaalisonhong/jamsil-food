"""
CLI 진입점 (User Flow 1~3단계).

Typer 기반 명령어:
  - restaurants: 맛집 추천 (기능 A)
  - cafes: 카페 추천 (기능 B)
  - alerts: 신규 오픈 알림 (기능 C)
  - crawl: Naver Place 크롤링·캐시 갱신
"""

import sys

import typer
from rich.console import Console
from rich.table import Table

from config.settings import get_settings
from models.place import Cafe, Place, Restaurant
from providers.kakao_local import KakaoLocalProvider
from providers.mock_provider import MockPlaceProvider
from providers.naver_local import NaverLocalProvider
from providers.naver_map_list import NaverMapListProvider
from services.alert_service import AlertService
from services.wrapped_delivery import WrappedDelivery
from services.manual_data_store import ManualDataStore
from services.naver_place_crawler import NaverPlaceCrawler
from services.recommendation_service import RecommendationService
from utils.console_encoding import configure_utf8_console
from utils.errors import ConfigurationError, FoodFinderError
from utils.logger import get_logger, setup_logging

# Windows 한글 깨짐 방지 — 모든 명령보다 먼저 실행
configure_utf8_console()

app = typer.Typer(
    name="fraunhofer-food",
    help="프라운호퍼 한국사무소 근처 맛집/카페 추천 도구",
)
console = Console(force_terminal=True)
logger = get_logger(__name__)


def _build_providers(use_mock: bool) -> list:
    """
    사용 가능한 Provider 목록을 구성합니다.

    Kakao(위치) + Naver(목록·링크)를 함께 사용하고,
    use_mock=True면 Mock만 사용합니다.
    """
    if use_mock:
        return [MockPlaceProvider()]

    settings = get_settings()
    providers = []

    if settings.kakao_rest_api_key:
        try:
            providers.append(KakaoLocalProvider(settings))
        except ConfigurationError as exc:
            logger.warning("Kakao Provider 초기화 실패: %s", exc)

    if settings.naver_client_id and settings.naver_client_secret:
        try:
            providers.append(NaverLocalProvider(settings))
        except ConfigurationError as exc:
            logger.warning("Naver Provider 초기화 실패: %s", exc)

    # Naver Place 목록 크롤링 — API보다 많은 주변 장소 수집
    try:
        providers.append(NaverMapListProvider(settings))
    except Exception as exc:
        logger.warning("Naver Map List Provider 초기화 실패: %s", exc)

    if not providers:
        console.print(
            "[yellow]API 키가 없어 Mock 데이터를 사용합니다. "
            ".env에 KAKAO_REST_API_KEY, NAVER_CLIENT_ID를 설정하세요.[/yellow]",
        )
        providers.append(MockPlaceProvider())

    return providers


def _build_recommendation_service(use_mock: bool, enable_crawl: bool) -> RecommendationService:
    return RecommendationService(
        _build_providers(use_mock),
        enable_crawl=enable_crawl,
    )


def _render_places_table(title: str, places: list[Place]) -> None:
    """Rich 테이블로 추천 결과 출력."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("이름", style="green")
    table.add_column("주소")
    table.add_column("평점", justify="right")
    table.add_column("도보(분)", justify="right")
    table.add_column("인당(원)", justify="right")

    for p in places:
        table.add_row(
            p.name,
            p.address[:30] + ("..." if len(p.address) > 30 else ""),
            f"{p.rating:.1f}" if p.rating else "-",
            f"{p.walk_minutes:.0f}" if p.walk_minutes else "-",
            f"{p.price_per_person_krw:,}" if p.price_per_person_krw else "-",
        )

    if not places:
        console.print(f"[dim]{title}: 조건에 맞는 결과가 없습니다.[/dim]")
    else:
        console.print(table)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 로그 출력"),
) -> None:
    """전역 옵션: 로깅 레벨 설정."""
    import logging

    setup_logging(logging.DEBUG if verbose else logging.INFO)


@app.command("restaurants")
def cmd_restaurants(
    mock: bool = typer.Option(False, "--mock", help="Mock 데이터 사용"),
    no_crawl: bool = typer.Option(False, "--no-crawl", help="Naver 크롤링 비활성화"),
) -> None:
    """
    기능 A: 프라운호퍼 근처 가성비 맛집 추천.

    조건: 평점 4+, 인당 1.5만원 이하, 도보 15분 이내
    """
    try:
        service = _build_recommendation_service(mock, enable_crawl=not no_crawl)
        results: list[Restaurant] = service.recommend_restaurants()
        _render_places_table("맛집 추천 (기능 A)", results)
    except FoodFinderError as exc:
        console.print(f"[red]오류: {exc}[/red]")
        sys.exit(1)


@app.command("cafes")
def cmd_cafes(
    mock: bool = typer.Option(False, "--mock", help="Mock 데이터 사용"),
    no_crawl: bool = typer.Option(False, "--no-crawl", help="Naver 크롤링 비활성화"),
) -> None:
    """
    기능 B: 프라운호퍼 근처 카페 추천.

    조건: 평점 4+, 도보 15분 이내
    """
    try:
        service = _build_recommendation_service(mock, enable_crawl=not no_crawl)
        results: list[Cafe] = service.recommend_cafes()
        _render_places_table("카페 추천 (기능 B)", results)
    except FoodFinderError as exc:
        console.print(f"[red]오류: {exc}[/red]")
        sys.exit(1)


@app.command("alerts")
def cmd_alerts(
    mock: bool = typer.Option(False, "--mock", help="Mock 데이터 사용"),
    email: bool = typer.Option(False, "--email", help="이메일로도 발송"),
    no_crawl: bool = typer.Option(False, "--no-crawl", help="Naver 크롤링 비활성화"),
    no_blog: bool = typer.Option(False, "--no-blog", help="블로그 신규오픈 검색 비활성화"),
) -> None:
    """
    기능 C: 최근 한 달 내 신규 오픈 식당/카페 알림.
    """
    try:
        rec = _build_recommendation_service(mock, enable_crawl=not no_crawl)
        alert_svc = AlertService(rec, use_blog_crawler=not no_blog)
        alerts = alert_svc.run_alert_check(use_email=email)
        if alerts:
            console.print(f"\n[green]총 {len(alerts)}건의 신규 오픈 알림[/green]")
    except FoodFinderError as exc:
        console.print(f"[red]오류: {exc}[/red]")
        sys.exit(1)


@app.command("crawl")
def cmd_crawl(
    place_id: str = typer.Argument(..., help="Naver Place ID (숫자)"),
    save_price: bool = typer.Option(False, "--save-price", help="추정 가격을 수동 DB에 저장"),
) -> None:
    """
    Naver Place 페이지를 크롤링해 평점·메뉴가·개업일을 조회/캐시합니다.

    정기 실행(cron/Task Scheduler)으로 data/cache를 갱신할 수 있습니다.
    """
    try:
        crawler = NaverPlaceCrawler()
        detail = crawler.fetch_detail(place_id)
        console.print(f"[bold]Place ID:[/bold] {place_id}")
        console.print(f"  평점: {detail.rating or '-'}")
        console.print(f"  리뷰 수: {detail.review_count or '-'}")
        console.print(f"  인당 추정가: {detail.price_per_person_krw or '-'}원")
        console.print(f"  개업일: {detail.opened_at or '-'}")
        console.print(f"  신규오픈 플래그: {detail.is_new_opening}")

        if save_price and detail.price_per_person_krw:
            ManualDataStore().upsert_price(
                place_id,
                detail.price_per_person_krw,
                notes="crawl 명령으로 자동 저장",
            )
            console.print("[green]수동 가격 DB에 저장했습니다.[/green]")
    except FoodFinderError as exc:
        console.print(f"[red]오류: {exc}[/red]")
        sys.exit(1)


@app.command("add-price")
def cmd_add_price(
    key: str = typer.Argument(..., help="place_id 또는 naver_place_id"),
    price: int = typer.Argument(..., help="인당 가격(원)"),
    notes: str = typer.Option("", "--notes", help="메모"),
) -> None:
    """인당 가격을 수동 DB(data/manual_prices.json)에 등록합니다."""
    ManualDataStore().upsert_price(key, price, notes=notes)
    console.print(f"[green]{key} → {price:,}원 저장 완료[/green]")


@app.command("wrapped")
def cmd_wrapped(
    year: int = typer.Option(None, "--year", "-y", help="연도 (기본: 올해)"),
    month: int = typer.Option(None, "--month", "-m", help="월 1-12 (기본: 이번 달)"),
    diary: str = typer.Option(
        "data/diary/default.json",
        "--diary",
        help="식사 기록 JSON (브라우저 export)",
    ),
    places: str = typer.Option(
        "site/data/places.json",
        "--places",
        help="맛집 카탈로그 JSON",
    ),
    email: bool = typer.Option(False, "--email", help="이메일로도 발송"),
) -> None:
    """
    Monthly Wrapped: 이번 달 나의 맛집 탐방 리포트.

    식사 기록 JSON이 필요합니다. 브라우저 개발자 도구에서
    localStorage.getItem('jamsil_meal_diary') 내용을 data/diary/default.json으로 저장하세요.
    """
    from datetime import date

    try:
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month

        delivery = WrappedDelivery.from_paths(diary, places)
        report = delivery.generate_for_month(target_year, target_month)
        delivery.send_console(report)
        if email:
            delivery.send_email(report)
    except FoodFinderError as exc:
        console.print(f"[red]오류: {exc}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
