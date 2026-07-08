"""영업일 유틸 단위 테스트."""

from datetime import date

from utils.business_calendar import is_last_business_day_of_month, last_business_day_of_month


def test_last_business_day_july_2026() -> None:
    # 2026-07-31 is Friday
    assert last_business_day_of_month(2026, 7) == date(2026, 7, 31)


def test_last_business_day_when_month_ends_on_weekend() -> None:
    # 2026-08-31 is Monday → last business day is Aug 31
    assert last_business_day_of_month(2026, 8) == date(2026, 8, 31)
    # 2025-11-30 is Sunday → last business day is Nov 28 (Friday)
    assert last_business_day_of_month(2025, 11) == date(2025, 11, 28)


def test_is_last_business_day() -> None:
    assert is_last_business_day_of_month(date(2026, 7, 31)) is True
    assert is_last_business_day_of_month(date(2026, 7, 30)) is False
