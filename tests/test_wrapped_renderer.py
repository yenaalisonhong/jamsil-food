"""WrappedRenderer 단위 테스트."""

from pathlib import Path

import pytest

from adapters.diary_adapter import FileDiaryAdapter
from adapters.place_catalog_adapter import PlaceCatalogAdapter
from services.wrapped_generator import WrappedGenerator
from services.wrapped_renderer import ConsoleWrappedRenderer

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def renderer() -> ConsoleWrappedRenderer:
    return ConsoleWrappedRenderer()


def test_console_render_contains_cards(renderer: ConsoleWrappedRenderer) -> None:
    gen = WrappedGenerator(
        FileDiaryAdapter(_FIXTURES / "sample_diary.json"),
        PlaceCatalogAdapter(_FIXTURES / "sample_places.json"),
    )
    report = gen.generate(2026, 7)
    text = renderer.render(report)

    assert "맛집 Wrapped" in text
    assert "총 5곳 탐방" in text
    assert "최애 카테고리" in text
    assert "총평" in text


def test_empty_month_render(renderer: ConsoleWrappedRenderer) -> None:
    gen = WrappedGenerator(
        FileDiaryAdapter(_FIXTURES / "sample_diary.json"),
        PlaceCatalogAdapter(_FIXTURES / "sample_places.json"),
    )
    report = gen.generate(2025, 1)
    text = renderer.render(report)

    assert "휴식" in text
    assert "[1/1]" in text
