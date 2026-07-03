"""카테고리별 기본 메뉴·가격 범위 (크롤링/API 미제공 시 사용)."""

from __future__ import annotations

from models.place import Place, PlaceCategory, PlaceType

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


def default_menu(place: Place) -> str:
    if place.representative_menu:
        return place.representative_menu
    return _CATEGORY_MENUS.get(place.category, "점심 특선")


def default_price_range(place: Place) -> tuple[int, int]:
    if place.place_type == PlaceType.CAFE:
        return _CATEGORY_PRICE_RANGES.get(PlaceCategory.CAFE, _CAFE_PRICE_RANGE)
    return _CATEGORY_PRICE_RANGES.get(place.category, _RESTAURANT_PRICE_RANGE)


def resolve_price_fields(place: Place) -> tuple[int, int, int]:
    """
    인당 가격·범위를 반환합니다.

    크롤링/수동 가격이 있으면 범위를 ±15%로 잡고, 없으면 카테고리 기본 범위를 씁니다.
    """
    lo, hi = default_price_range(place)
    if place.price_per_person_krw is not None:
        mid = place.price_per_person_krw
        margin = max(1_000, int(mid * 0.15))
        return mid, max(0, mid - margin), mid + margin
    mid = (lo + hi) // 2
    return mid, lo, hi
