"""
신규 오픈 장소 통합 탐지.

1. Naver Place '요즘뜨는' 목록 (newOpening 플래그)
2. Naver 블로그/뉴스 검색 (NewOpeningCrawler)
"""

from config.settings import Settings, get_settings
from models.place import Place
from services.naver_place_crawler import NaverPlaceCrawler
from services.new_opening_crawler import NewOpeningCrawler
from utils.errors import ConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)


class NewOpeningDiscovery:
    """여러 소스에서 신규 오픈 후보를 수집합니다."""

    def __init__(
        self,
        settings: Settings | None = None,
        crawler: NaverPlaceCrawler | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._crawler = crawler or NaverPlaceCrawler()

    def fetch_candidates(self) -> list[Place]:
        """중복 제거된 신규 오픈 후보 Place 목록."""
        seen: set[str] = set()
        results: list[Place] = []

        for place in self._from_trending() + self._from_blog():
            key = place.naver_place_id or place.id
            if key in seen:
                continue
            seen.add(key)
            results.append(place)

        logger.info("신규 오픈 후보 통합 %d건", len(results))
        return results

    def _from_trending(self) -> list[Place]:
        return self._crawler.fetch_trending_new_openings(
            self._settings.fraunhofer_office_lat,
            self._settings.fraunhofer_office_lng,
        )

    def _from_blog(self) -> list[Place]:
        try:
            return NewOpeningCrawler(self._settings).fetch_candidates()
        except ConfigurationError as exc:
            logger.warning("신규 오픈 블로그 검색 스킵: %s", exc)
            return []
