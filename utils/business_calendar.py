"""
영업일(비즈니스 데이) 유틸리티.

월간 Wrapped 배치 잡 스케줄링에 사용합니다.
"""

from datetime import date, timedelta


def last_business_day_of_month(year: int, month: int) -> date:
    """
    해당 월의 마지막 영업일(월~금)을 반환합니다.

    한국 공휴일은 MVP에서 제외합니다.
    """
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    current = next_month - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def is_last_business_day_of_month(day: date | None = None) -> bool:
    """오늘이 해당 월의 마지막 영업일인지 확인합니다."""
    today = day or date.today()
    return today == last_business_day_of_month(today.year, today.month)
