"""
장소 필터링 서비스.

PRD 조건(평점 4+, 인당 1.5만원 이하, 도보 15분)을 적용합니다.
"""

from config.settings import Settings, get_settings
from models.place import Place, PlaceType
from services.geolocation import GeolocationService
from utils.logger import get_logger

logger = get_logger(__name__)


class FilterService:
    """추천 조건에 맞는 장소만 선별."""

    def __init__(
        self,
        settings: Settings | None = None,
        geo_service: GeolocationService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._geo = geo_service or GeolocationService(self._settings)

    def passes_rating(self, place: Place) -> bool:
        """평점이 min_rating 이상인지 (평점 미제공 시 False)."""
        if place.rating is None:
            logger.debug("평점 없음 → 제외: %s", place.name)
            return False
        return place.rating >= self._settings.min_rating

    def passes_price(self, place: Place) -> bool:
        """
        인당 가격이 기준 이하인지.

        가격 정보가 없으면 식당은 제외, 카페는 가격 조건 생략 가능(정책).
        """
        if place.price_per_person_krw is None:
            if place.place_type == PlaceType.RESTAURANT:
                logger.debug("가격 정보 없음(식당) → 제외: %s", place.name)
                return False
            # 카페는 PRD에 가격 조건 없음
            return True
        return place.price_per_person_krw <= self._settings.max_price_per_person_krw

    def passes_distance(self, place: Place) -> bool:
        """도보 max_walk_minutes 이내인지."""
        return self._geo.is_within_walk_range(place)

    def filter_restaurants(self, places: list[Place]) -> list[Place]:
        """기능 A: 식당 추천 필터."""
        result: list[Place] = []
        for place in places:
            if place.place_type != PlaceType.RESTAURANT:
                continue
            enriched = self._geo.enrich_place(place)
            if (
                self.passes_distance(enriched)
                and self.passes_rating(enriched)
                and self.passes_price(enriched)
            ):
                result.append(enriched)
        return sorted(result, key=lambda p: (p.walk_minutes or 999, -(p.rating or 0)))

    def filter_cafes(self, places: list[Place]) -> list[Place]:
        """기능 B: 카페 추천 필터 (가격 조건 없음)."""
        result: list[Place] = []
        for place in places:
            if place.place_type != PlaceType.CAFE:
                continue
            enriched = self._geo.enrich_place(place)
            if self.passes_distance(enriched) and self.passes_rating(enriched):
                result.append(enriched)
        return sorted(result, key=lambda p: (p.walk_minutes or 999, -(p.rating or 0)))

    def filter_new_openings(
        self,
        places: list[Place],
        *,
        within_days: int | None = None,
    ) -> list[Place]:
        """
        기능 C: 최근 N일 이내 오픈 + 도보 범위 내 장소.

        opened_at이 없는 항목은 제외합니다.
        """
        from datetime import date, timedelta

        days = within_days or self._settings.new_opening_days
        cutoff = date.today() - timedelta(days=days)

        result: list[Place] = []
        for place in places:
            if place.opened_at is None or place.opened_at < cutoff:
                continue
            enriched = self._geo.enrich_place(place)
            if self.passes_distance(enriched) and self.passes_rating(enriched):
                result.append(enriched)
        return sorted(result, key=lambda p: p.opened_at or date.min, reverse=True)
