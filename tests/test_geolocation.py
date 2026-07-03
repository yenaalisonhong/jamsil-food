"""GeolocationService 단위 테스트."""

import pytest

from config.settings import Settings
from models.place import Place, PlaceCategory, PlaceType
from services.geolocation import GeolocationService


@pytest.fixture
def geo_service() -> GeolocationService:
    settings = Settings(
        fraunhofer_office_lat=37.51395,
        fraunhofer_office_lng=127.10055,
        max_walk_minutes=15,
        walk_speed_kmh=4.8,
    )
    return GeolocationService(settings)


def test_distance_meters_positive(geo_service: GeolocationService) -> None:
    dist = geo_service.distance_meters(37.5145, 127.1010)
    assert dist > 0
    assert dist < 500  # 가까운 지점


def test_is_within_walk_range_near(geo_service: GeolocationService) -> None:
    place = Place(
        id="t1",
        name="가까운 식당",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="테스트",
        lat=37.5145,
        lng=127.1010,
        source="test",
    )
    assert geo_service.is_within_walk_range(place) is True


def test_is_within_walk_range_far(geo_service: GeolocationService) -> None:
    place = Place(
        id="t2",
        name="먼 식당",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="테스트",
        lat=37.55,
        lng=127.15,
        source="test",
    )
    assert geo_service.is_within_walk_range(place) is False


def test_estimate_walk_minutes_invalid(geo_service: GeolocationService) -> None:
    with pytest.raises(ValueError):
        geo_service.estimate_walk_minutes(-1)
