"""
추천 오케스트레이션 서비스.

여러 Place Provider에서 데이터를 수집하고,
PlaceEnricher로 평점·가격·개업일을 보강한 뒤 필터를 적용합니다.
"""

from models.place import Cafe, Place, PlaceType, Restaurant
from providers.base import PlaceProvider
from services.filter_service import FilterService
from services.place_enricher import PlaceEnricher
from utils.errors import PlaceProviderError
from utils.logger import get_logger

logger = get_logger(__name__)


class RecommendationService:
    """기능 A/B 통합 추천 진입점."""

    def __init__(
        self,
        providers: list[PlaceProvider],
        filter_service: FilterService | None = None,
        enricher: PlaceEnricher | None = None,
        *,
        enable_crawl: bool = True,
    ) -> None:
        if not providers:
            raise ValueError("최소 1개의 PlaceProvider가 필요합니다.")
        self._providers = providers
        self._filter = filter_service or FilterService()
        self._enricher = enricher or PlaceEnricher(enable_crawl=enable_crawl)

    def _fetch_all(self, place_type: PlaceType) -> list[Place]:
        """
        Provider 수집 → Enricher 보강 → 반환.

        개별 Provider 실패 시 로그만 남기고 나머지는 계속 시도합니다.
        """
        collected: list[Place] = []
        for provider in self._providers:
            try:
                places = provider.fetch_places(place_type)
                collected.extend(places)
                logger.info("%s에서 %d건 수집", provider.source_name, len(places))
            except PlaceProviderError as exc:
                logger.warning(
                    "Provider '%s' 실패 (건너뜀): %s",
                    provider.source_name,
                    exc,
                )

        return self._enricher.enrich_all(collected)

    def recommend_restaurants(self) -> list[Restaurant]:
        """기능 A: 가성비 맛집 추천."""
        raw = self._fetch_all(PlaceType.RESTAURANT)
        filtered = self._filter.filter_restaurants(raw)
        return [Restaurant(**p.model_dump()) for p in filtered]

    def recommend_cafes(self) -> list[Cafe]:
        """기능 B: 카페 추천."""
        raw = self._fetch_all(PlaceType.CAFE)
        filtered = self._filter.filter_cafes(raw)
        return [Cafe(**p.model_dump()) for p in filtered]

    def fetch_all_nearby(self) -> list[Place]:
        """알림 서비스 등에서 사용: 식당+카페 전체 수집·보강."""
        restaurants = self._fetch_all(PlaceType.RESTAURANT)
        cafes = self._fetch_all(PlaceType.CAFE)
        return self._enricher.merge_duplicates(restaurants + cafes)
