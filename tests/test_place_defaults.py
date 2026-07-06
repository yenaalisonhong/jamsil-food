"""place_defaults 단위 테스트."""

from models.place import Place, PlaceCategory, PlaceType
from services.place_defaults import default_menu, is_generic_menu


def test_is_generic_menu_detects_placeholders() -> None:
    assert is_generic_menu("점심 특선") is True
    assert is_generic_menu("시그니처 메뉴") is True
    assert is_generic_menu("된장찌개") is False


def test_default_menu_ignores_generic_placeholder() -> None:
    place = Place(
        id="1",
        name="테스트",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="서울",
        lat=37.5,
        lng=127.0,
        source="test",
        representative_menu="점심 특선",
    )
    assert default_menu(place) == "한정식 / 제육볶음"


def test_adjust_restaurant_price_range_raises_low_min() -> None:
    from services.place_defaults import adjust_restaurant_price_range

    lo, hi = adjust_restaurant_price_range(11500, 4800, 22500)
    assert lo == 8500
    assert hi == 22500


def test_resolve_price_fields_uses_crawled_range() -> None:
    from services.place_defaults import resolve_price_fields

    place = Place(
        id="1",
        name="테스트",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.WESTERN,
        address="서울",
        lat=37.5,
        lng=127.0,
        source="test",
        price_per_person_krw=11500,
        price_range_min_krw=4800,
        price_range_max_krw=22500,
    )
    mid, lo, hi = resolve_price_fields(place)
    assert mid == 11500
    assert lo == 8500
    assert hi == 22500
