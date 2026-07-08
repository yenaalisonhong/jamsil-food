"""
식사 기록(다이어리) 데이터 모델.

브라우저 localStorage(`jamsil_meal_diary`)와 동일한 JSON 형식을
Python 서비스 레이어에서 사용할 수 있게 정규화합니다.
"""

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


_DATE_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_diary_name(name: str) -> str:
    """상호명 정규화 (diary-shared.js normalizeName과 동일)."""
    return re.sub(r"\s+", " ", str(name or "").strip())


class DiaryEntry(BaseModel):
    """하루 중 한 건의 식사 기록."""

    name: str
    rating: int = Field(default=4, ge=1, le=5)
    memo: str = ""
    price_min_krw: int | None = None
    price_max_krw: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    place_id: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        normalized = normalize_diary_name(value)
        if not normalized:
            raise ValueError("name은 비어 있을 수 없습니다.")
        return normalized

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "DiaryEntry":
        """localStorage 항목 또는 export JSON 한 건을 파싱합니다."""
        created_raw = raw.get("createdAt") or raw.get("created_at")
        if isinstance(created_raw, str):
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                created_at = datetime.now()
        else:
            created_at = datetime.now()

        rating = max(1, min(5, round(float(raw.get("rating", 4)))))

        price_min = cls._parse_optional_price(raw.get("price_min_krw"))
        price_max = cls._parse_optional_price(raw.get("price_max_krw"))
        if price_min is not None and price_max is not None and price_min > price_max:
            price_min, price_max = price_max, price_min
        if price_min is None and price_max is not None:
            price_min = price_max
        if price_max is None and price_min is not None:
            price_max = price_min

        return cls(
            name=str(raw.get("name", "")),
            rating=rating,
            memo=str(raw.get("memo", "") or "").strip(),
            price_min_krw=price_min,
            price_max_krw=price_max,
            created_at=created_at,
            place_id=raw.get("place_id") or raw.get("placeId"),
        )

    @staticmethod
    def _parse_optional_price(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            n = round(float(value))
        except (TypeError, ValueError):
            return None
        return n if n >= 0 else None


class DiaryDay(BaseModel):
    """특정 날짜의 식사 기록 묶음."""

    date: date
    entries: list[DiaryEntry] = Field(default_factory=list)


class DiaryStore(BaseModel):
    """전체 식사 기록 저장소."""

    days: dict[str, list[DiaryEntry]] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "DiaryStore":
        """localStorage/export JSON 전체를 파싱합니다."""
        days: dict[str, list[DiaryEntry]] = {}
        if not isinstance(raw, dict):
            return cls(days=days)

        for key, value in raw.items():
            if not _DATE_KEY_RE.match(key) or not isinstance(value, list):
                continue
            entries: list[DiaryEntry] = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                try:
                    entries.append(DiaryEntry.from_raw(item))
                except ValueError:
                    continue
            if entries:
                days[key] = entries
        return cls(days=days)

    def entries_for_month(self, year: int, month: int) -> list[tuple[date, DiaryEntry]]:
        """해당 월의 (날짜, 기록) 목록을 날짜순으로 반환합니다."""
        prefix = f"{year:04d}-{month:02d}-"
        result: list[tuple[date, DiaryEntry]] = []
        for key, entries in self.days.items():
            if not key.startswith(prefix):
                continue
            day = date.fromisoformat(key)
            for entry in entries:
                result.append((day, entry))
        result.sort(key=lambda item: (item[0], item[1].created_at))
        return result

    def first_visit_dates(self) -> dict[str, date]:
        """식당 이름(정규화)별 최초 방문일."""
        first: dict[str, date] = {}
        for key in sorted(self.days.keys()):
            day = date.fromisoformat(key)
            for entry in self.days[key]:
                norm = normalize_diary_name(entry.name)
                if norm not in first:
                    first[norm] = day
        return first

    def visit_counts_before(self, before: date) -> dict[str, int]:
        """특정 날짜 이전까지 식당별 방문 횟수."""
        counts: dict[str, int] = {}
        for key, entries in self.days.items():
            day = date.fromisoformat(key)
            if day >= before:
                continue
            for entry in entries:
                norm = normalize_diary_name(entry.name)
                counts[norm] = counts.get(norm, 0) + 1
        return counts

    def total_count(self) -> int:
        return sum(len(entries) for entries in self.days.values())
