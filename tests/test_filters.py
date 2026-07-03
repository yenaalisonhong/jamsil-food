"""FilterService 단위 테스트."""

from datetime import date, timedelta

import pytest

from config.settings import Settings
from models.place import Place, PlaceCategory, PlaceType
from providers.mock_provider import MockPlaceProvider
from services.filter_service import FilterService
from services.geolocation import GeolocationService


@pytest.fixture
def filter_service() -> FilterService:
    settings = Settings(max_walk_minutes=15, min_rating=4.0, max_price_per_person_krw=15_000)
    return FilterService(settings, GeolocationService(settings))


def test_filter_restaurants_excludes_expensive(filter_service: FilterService) -> None:
    places = MockPlaceProvider().fetch_places(PlaceType.RESTAURANT)
    result = filter_service.filter_restaurants(places)
    names = {p.name for p in result}
    assert "비싼 스테이크하우스" not in names
    assert "평점낮은 분식" not in names
    assert "잠실맛집 한식당" in names


def test_filter_cafes_rating_and_distance(filter_service: FilterService) -> None:
    places = MockPlaceProvider().fetch_places(PlaceType.CAFE)
    result = filter_service.filter_cafes(places)
    assert len(result) >= 1
    for cafe in result:
        assert cafe.rating is not None
        assert cafe.rating >= 4.0


def test_filter_new_openings(filter_service: FilterService) -> None:
    places = MockPlaceProvider().fetch_places(PlaceType.RESTAURANT)
    places += MockPlaceProvider().fetch_places(PlaceType.CAFE)
    result = filter_service.filter_new_openings(places, within_days=30)
    assert all(p.opened_at is not None for p in result)
    assert all(p.opened_at >= date.today() - timedelta(days=30) for p in result)
