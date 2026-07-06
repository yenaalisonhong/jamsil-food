"""메뉴 검색용 menu_names 동기화 테스트."""

from scripts.refresh_menus_in_places_json import (
    _menu_names_from_cache_data,
    _sync_menu_names,
)


def test_menu_names_from_cache_data_dedupes() -> None:
    cached = {
        "menu_items": [
            {"name": "아인슈페너", "price": 6500},
            {"name": "아인슈페너", "price": 6500},
            {"name": "카페라떼", "price": 5500},
        ]
    }
    assert _menu_names_from_cache_data(cached) == ["아인슈페너", "카페라떼"]


def test_sync_menu_names_writes_field() -> None:
    raw: dict = {}
    cached = {"menu_items": [{"name": "아인슈페너", "price": 6500}]}
    assert _sync_menu_names(raw, cached) is True
    assert raw["menu_names"] == ["아인슈페너"]
