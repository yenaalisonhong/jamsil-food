"""jamsil_commercial 상가 앵커·심층 검색 테스트."""

from models.place import PlaceType
from providers.jamsil_commercial import (
    NEAREST_COMMERCIAL_COUNT,
    deep_commercial_searches,
    is_deep_commercial_anchor,
    jangmi_searches,
    map_searches,
    nearest_commercial_anchors,
    nearest_commercial_names,
)


def test_nearest_five_anchors_order() -> None:
    anchors = nearest_commercial_anchors()
    assert len(anchors) == NEAREST_COMMERCIAL_COUNT
    names = [a.name for a in anchors]
    assert names[0] == "잠실더샵스타파크"
    assert "장미상가" in names
    assert "홈플러스 잠실점" in names
    assert "르엘 잠실" in names


def test_is_deep_commercial_anchor() -> None:
    assert is_deep_commercial_anchor("장미상가")
    assert is_deep_commercial_anchor("잠실더샵스타파크")
    assert not is_deep_commercial_anchor("트리지움")


def test_deep_searches_include_named_seeds() -> None:
    queries = [q for q, _, _ in deep_commercial_searches(PlaceType.RESTAURANT)]
    assert "가보자식당" in queries
    assert "삼청동식탁" in queries
    assert "왁버거" in queries
    assert "장미상가 음식점" in queries


def test_deep_searches_include_cafe_named_seeds() -> None:
    queries = [q for q, _, _ in deep_commercial_searches(PlaceType.CAFE)]
    assert "비엔나커피센트럴" in queries
    assert "리사르커피" in queries
    assert "푸가커피" in queries
    assert "하삼동커피" in queries
    assert "장미상가 카페" in queries


def test_deep_searches_include_cuisine_variants() -> None:
    queries = [q for q, _, _ in deep_commercial_searches(PlaceType.RESTAURANT)]
    assert any("장미상가" in q and "한식" in q for q in queries)
    assert any("홈플러스" in q and "일식" in q for q in queries)


def test_map_searches_puts_deep_first() -> None:
    all_queries = map_searches(PlaceType.RESTAURANT)
    deep_queries = deep_commercial_searches(PlaceType.RESTAURANT)
    assert all_queries[: len(deep_queries)] == deep_queries


def test_jangmi_searches_alias() -> None:
    assert jangmi_searches(PlaceType.RESTAURANT) == deep_commercial_searches(
        PlaceType.RESTAURANT,
    )


def test_nearest_names_matches_count() -> None:
    assert len(nearest_commercial_names()) == NEAREST_COMMERCIAL_COUNT
