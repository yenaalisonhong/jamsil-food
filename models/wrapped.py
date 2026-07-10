"""
Monthly Wrapped 리포트 모델.

집계 결과와 슬라이드형 카드 데이터를 담습니다.
"""

from pydantic import BaseModel, Field


class WrappedStats(BaseModel):
    """월별 집계 수치 (카드 생성 전 원시 통계)."""

    year: int
    month: int
    total_visits: int = 0
    unique_places: int = 0
    top_categories: list[str] = Field(default_factory=list)
    top_category_count: int = 0
    top_places: list[tuple[str, int]] = Field(default_factory=list)
    new_discoveries: int = 0
    revisit_visits: int = 0
    average_rating: float | None = None
    best_rated_places: list[str] = Field(default_factory=list)
    best_rating: int | None = None
    cheapest_places: list[str] = Field(default_factory=list)
    cheapest_price_krw: int | None = None
    avg_walk_minutes: float | None = None
    avg_distance_meters: float | None = None
    max_streak_days: int = 0
    active_days: int = 0


class WrappedCard(BaseModel):
    """슬라이드 한 장."""

    title: str
    subtitle: str
    emoji: str = "🍽️"
    stat_value: str | int | float = ""
    stat_label: str = ""


class WrappedReport(BaseModel):
    """월간 Wrapped 전체 리포트."""

    year: int
    month: int
    month_label: str
    is_empty: bool = False
    stats: WrappedStats | None = None
    cards: list[WrappedCard] = Field(default_factory=list)
