"""
맛집 카탈로그 어댑터.

export된 places.json을 읽어 diary 항목과 조인합니다.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models.diary import normalize_diary_name
from services.place_defaults import category_label
from models.place import PlaceCategory
from utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_PLACES_PATH = (
    Path(__file__).resolve().parent.parent / "site" / "data" / "places.json"
)


@dataclass(frozen=True)
class PlaceRecord:
    """Wrapped 집계에 필요한 장소 필드."""

    id: str
    name: str
    category_label: str
    walk_minutes: float | None
    distance_meters: float | None
    price_per_person_krw: int | None
    rating: float | None


class PlaceCatalogAdapter:
    """places.json 기반 장소 조회."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DEFAULT_PLACES_PATH
        self._by_id: dict[str, PlaceRecord] = {}
        self._by_name: dict[str, PlaceRecord] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            logger.warning("places.json 없음: %s", self._path)
            return

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("places.json 읽기 실패: %s (%s)", self._path, exc)
            return

        places = raw.get("places", raw) if isinstance(raw, dict) else raw
        if not isinstance(places, list):
            return

        for item in places:
            if not isinstance(item, dict):
                continue
            record = self._parse_place(item)
            if record is None:
                continue
            self._by_id[record.id] = record
            norm = normalize_diary_name(record.name)
            if norm and norm not in self._by_name:
                self._by_name[norm] = record

    def _parse_place(self, raw: dict[str, Any]) -> PlaceRecord | None:
        place_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "")).strip()
        if not place_id or not name:
            return None

        label = raw.get("category_label")
        if not label:
            cat_raw = raw.get("category", "other")
            try:
                label = category_label(PlaceCategory(str(cat_raw)))
            except ValueError:
                label = "기타"

        walk = raw.get("walk_minutes")
        dist = raw.get("distance_meters")
        price = raw.get("price_per_person_krw")
        rating = raw.get("rating")

        return PlaceRecord(
            id=place_id,
            name=name,
            category_label=str(label),
            walk_minutes=float(walk) if walk is not None else None,
            distance_meters=float(dist) if dist is not None else None,
            price_per_person_krw=int(price) if price is not None else None,
            rating=float(rating) if rating is not None else None,
        )

    def lookup(self, name: str, place_id: str | None = None) -> PlaceRecord | None:
        """place_id 우선, 없으면 이름으로 조회 (diary-shared.js와 동일 전략)."""
        self._ensure_loaded()
        if place_id and place_id in self._by_id:
            return self._by_id[place_id]

        norm = normalize_diary_name(name)
        if not norm:
            return None

        found = self._by_name.get(norm)
        if found:
            return found

        for key, record in self._by_name.items():
            if key in norm or norm in key:
                return record
        return None

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._by_id)
