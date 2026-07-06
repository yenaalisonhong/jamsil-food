"""카테고리별 기본 메뉴·가격 범위 (크롤링/API 미제공 시 사용)."""

from __future__ import annotations

from models.place import Place, PlaceCategory, PlaceType

GENERIC_MENU_HINTS: frozenset[str] = frozenset(
    {
        "점심 특선",
        "시그니처 메뉴",
        "한정식 / 제육볶음",
        "짜장면 / 탕수육",
        "초밥 / 돈카츠",
        "파스타 / 스테이크",
        "버거 / 샌드위치",
        "떡볶이 / 김밥",
        "아메리카노 / 라떼",
        "케이크 / 마카롱",
    }
)

_CATEGORY_MENUS: dict[PlaceCategory, str] = {
    PlaceCategory.KOREAN: "한정식 / 제육볶음",
    PlaceCategory.CHINESE: "짜장면 / 탕수육",
    PlaceCategory.JAPANESE: "초밥 / 돈카츠",
    PlaceCategory.WESTERN: "파스타 / 스테이크",
    PlaceCategory.FAST_FOOD: "버거 / 샌드위치",
    PlaceCategory.BUNSIK: "떡볶이 / 김밥",
    PlaceCategory.CAFE: "아메리카노 / 라떼",
    PlaceCategory.DESSERT: "케이크 / 마카롱",
    PlaceCategory.OTHER: "점심 특선",
}

_CATEGORY_LABELS: dict[PlaceCategory, str] = {
    PlaceCategory.KOREAN: "한식",
    PlaceCategory.CHINESE: "중식",
    PlaceCategory.JAPANESE: "일식",
    PlaceCategory.WESTERN: "양식",
    PlaceCategory.FAST_FOOD: "패스트푸드",
    PlaceCategory.BUNSIK: "분식",
    PlaceCategory.CAFE: "카페",
    PlaceCategory.DESSERT: "디저트",
    PlaceCategory.OTHER: "기타",
}

# (min, max) 인당 가격 범위 — 항상 표시용
_CATEGORY_PRICE_RANGES: dict[PlaceCategory, tuple[int, int]] = {
    PlaceCategory.KOREAN: (8_000, 15_000),
    PlaceCategory.CHINESE: (7_000, 14_000),
    PlaceCategory.JAPANESE: (9_000, 18_000),
    PlaceCategory.WESTERN: (10_000, 20_000),
    PlaceCategory.FAST_FOOD: (6_000, 12_000),
    PlaceCategory.BUNSIK: (5_000, 10_000),
    PlaceCategory.CAFE: (4_500, 8_000),
    PlaceCategory.DESSERT: (5_000, 12_000),
    PlaceCategory.OTHER: (8_000, 15_000),
}

_CAFE_PRICE_RANGE = (4_500, 8_000)
_RESTAURANT_PRICE_RANGE = (8_000, 15_000)


def category_label(category: PlaceCategory) -> str:
    return _CATEGORY_LABELS.get(category, "기타")


def is_generic_menu(menu: str | None) -> bool:
    """크롤링·분류에 쓸 수 없는 카테고리 기본값·플레이스홀더 메뉴."""
    if not menu:
        return True
    return menu.strip() in GENERIC_MENU_HINTS


def category_from_menu_template(menu: str | None) -> PlaceCategory | None:
    """카테고리별 표시용 기본 메뉴 문자열 → PlaceCategory."""
    if not menu:
        return None
    normalized = menu.strip()
    for category, template in _CATEGORY_MENUS.items():
        if normalized == template:
            return category
    return None


def default_menu(place: Place) -> str:
    if place.representative_menu and not is_generic_menu(place.representative_menu):
        return place.representative_menu
    return _CATEGORY_MENUS.get(place.category, "점심 특선")


def default_price_range(place: Place) -> tuple[int, int]:
    if place.place_type == PlaceType.CAFE:
        return _CATEGORY_PRICE_RANGES.get(PlaceCategory.CAFE, _CAFE_PRICE_RANGE)
    return _CATEGORY_PRICE_RANGES.get(place.category, _RESTAURANT_PRICE_RANGE)


def adjust_restaurant_price_range(
    price_per_person_krw: int | None,
    min_krw: int | None,
    max_krw: int | None,
) -> tuple[int | None, int | None]:
    """음료·디저트가 min을 끌어내린 구 데이터를 인당가 기준으로 보정합니다."""
    if min_krw is None or max_krw is None:
        return min_krw, max_krw
    if min_krw >= 6_000:
        return min_krw, max_krw
    if price_per_person_krw is None:
        return min_krw, max_krw
    floor = max(6_000, price_per_person_krw - 3_000)
    if floor >= max_krw:
        return min_krw, max_krw
    return floor, max_krw


def resolve_price_fields(place: Place) -> tuple[int, int, int]:
    """
    인당 가격·범위를 반환합니다.

    크롤링 가격 범위가 있으면 우선 사용하고, 인당가만 있으면 ±15%로 잡습니다.
    """
    lo, hi = default_price_range(place)

    if place.price_range_min_krw is not None and place.price_range_max_krw is not None:
        lo, hi = place.price_range_min_krw, place.price_range_max_krw
        if place.place_type == PlaceType.RESTAURANT:
            lo, hi = adjust_restaurant_price_range(place.price_per_person_krw, lo, hi)
        mid = place.price_per_person_krw or (lo + hi) // 2
        return mid, lo, hi

    if place.price_per_person_krw is not None:
        mid = place.price_per_person_krw
        margin = max(1_000, int(mid * 0.15))
        return mid, max(0, mid - margin), mid + margin

    mid = (lo + hi) // 2
    return mid, lo, hi
