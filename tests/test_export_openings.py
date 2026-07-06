"""export_places 신규오픈 보존·플래그 동기화 테스트."""

from datetime import date, timedelta

from scripts.export_places import (
    is_new_opening_raw,
    preserve_opened_at_from_snapshots,
    sync_opening_flags_in_places,
    sync_new_openings_from_places,
)


def test_preserve_opened_at_from_snapshots() -> None:
    places = [{"id": "naver:1", "name": "A", "opened_at": None}]
    previous = [{"id": "naver:1", "name": "A", "opened_at": "2026-06-10"}]
    assert preserve_opened_at_from_snapshots(places, previous) == 1
    assert places[0]["opened_at"] == "2026-06-10"


def test_sync_opening_flags_within_window() -> None:
    recent = (date.today() - timedelta(days=5)).isoformat()
    old = (date.today() - timedelta(days=40)).isoformat()
    places = [
        {"id": "naver:1", "opened_at": recent},
        {"id": "naver:2", "opened_at": old},
        {"id": "naver:3", "opened_at": None},
    ]
    sync_opening_flags_in_places(places, within_days=30)
    assert places[0]["is_new_opening"] is True
    assert places[1]["is_new_opening"] is False
    assert places[2]["is_new_opening"] is False


def test_sync_new_openings_from_places_filters_by_date() -> None:
    recent = (date.today() - timedelta(days=3)).isoformat()
    places = [
        {"id": "naver:1", "opened_at": recent, "walk_minutes": 5},
        {"id": "naver:2", "opened_at": None, "walk_minutes": 3},
    ]
    openings = sync_new_openings_from_places(places, within_days=30)
    assert len(openings) == 1
    assert openings[0]["id"] == "naver:1"
    assert is_new_opening_raw({"opened_at": recent}, 30) is True
