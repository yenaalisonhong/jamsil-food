"""WrappedGenerator 단위 테스트."""

from datetime import date
from pathlib import Path

import pytest

from adapters.diary_adapter import FileDiaryAdapter
from adapters.place_catalog_adapter import PlaceCatalogAdapter
from services.wrapped_generator import WrappedGenerator

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def generator() -> WrappedGenerator:
    return WrappedGenerator(
        FileDiaryAdapter(_FIXTURES / "sample_diary.json"),
        PlaceCatalogAdapter(_FIXTURES / "sample_places.json"),
    )


def test_generate_july_stats(generator: WrappedGenerator) -> None:
    report = generator.generate(2026, 7)

    assert report.is_empty is False
    assert report.stats is not None
    stats = report.stats
    assert stats.total_visits == 5
    assert stats.unique_places == 3
    assert stats.top_category in ("한식", "카페")
    assert stats.new_discoveries == 2
    assert stats.revisit_visits == 3
    assert stats.average_rating == 4.2
    assert stats.best_rated_place == "잠실맛집 한식당"
    assert stats.best_rating == 5
    assert stats.cheapest_place == "잠실 카페 라떼"
    assert stats.cheapest_price_krw == 4500
    assert stats.max_streak_days == 3
    assert stats.active_days == 4
    assert len(report.cards) >= 5


def test_top_places_order(generator: WrappedGenerator) -> None:
    report = generator.generate(2026, 7)
    assert report.stats is not None
    names = [name for name, _ in report.stats.top_places]
    assert names[0] == "잠실맛집 한식당"
    assert names[1] == "잠실 카페 라떼"


def test_empty_month(generator: WrappedGenerator) -> None:
    report = generator.generate(2025, 1)

    assert report.is_empty is True
    assert len(report.cards) == 1
    assert "휴식" in report.cards[0].title


def test_missing_diary_file(tmp_path: Path) -> None:
    gen = WrappedGenerator(
        FileDiaryAdapter(tmp_path / "missing.json"),
        PlaceCatalogAdapter(_FIXTURES / "sample_places.json"),
    )
    report = gen.generate(2026, 7)
    assert report.is_empty is True


def test_june_has_one_visit(generator: WrappedGenerator) -> None:
    report = generator.generate(2026, 6)
    assert report.stats is not None
    assert report.stats.total_visits == 1
    assert report.stats.new_discoveries == 1
    assert report.stats.revisit_visits == 0
