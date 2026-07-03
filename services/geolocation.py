"""
지리 위치 서비스.

프라운호퍼 사무소 기준 거리·도보 시간을 계산합니다.
"""

from geopy.distance import geodesic

from config.settings import Settings, get_settings
from models.place import Place
from utils.logger import get_logger

logger = get_logger(__name__)


class GeolocationService:
    """좌표 기반 거리/도보 시간 계산."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._origin = (
            self._settings.fraunhofer_office_lat,
            self._settings.fraunhofer_office_lng,
        )

    @property
    def origin(self) -> tuple[float, float]:
        """프라운호퍼 한국사무소 (위도, 경도)."""
        return self._origin

    def distance_meters(self, lat: float, lng: float) -> float:
        """두 좌표 간 직선 거리(미터)를 반환합니다."""
        return geodesic(self._origin, (lat, lng)).meters

    def estimate_walk_minutes(self, distance_meters: float) -> float:
        """
        거리로부터 도보 시간(분)을 추정합니다.

        walk_speed_kmh 설정값을 사용합니다.
        """
        if distance_meters < 0:
            raise ValueError("distance_meters는 0 이상이어야 합니다.")
        km = distance_meters / 1000
        hours = km / self._settings.walk_speed_kmh
        return round(hours * 60, 1)

    def enrich_place(self, place: Place) -> Place:
        """
        Place에 distance_meters, walk_minutes를 채워 반환합니다.

        원본 객체는 변경하지 않고 복사본을 반환합니다 (불변성 유지).
        """
        dist = self.distance_meters(place.lat, place.lng)
        walk = self.estimate_walk_minutes(dist)
        return place.model_copy(
            update={"distance_meters": round(dist, 1), "walk_minutes": walk},
        )

    def is_within_walk_range(self, place: Place) -> bool:
        """PRD 기준: 걸어서 max_walk_minutes 이내인지 확인."""
        enriched = self.enrich_place(place)
        if enriched.walk_minutes is None:
            return False
        return enriched.walk_minutes <= self._settings.max_walk_minutes
