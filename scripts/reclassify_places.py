"""places.json의 카테고리만 빠르게 재분류합니다 (크롤링 없음)."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.place import Place, PlaceCategory, PlaceType  # noqa: E402
from scripts.export_places import (  # noqa: E402
    sync_new_openings_from_places,
    sync_opening_flags_in_places,
)
from scripts.refresh_menus_in_places_json import (  # noqa: E402
    _naver_id,
    _should_use_cached_menu,
    _sync_menu_names,
)
from services.category_classifier import (  # noqa: E402
    _menu_names_from_parts,
    is_food_place,
    refine_category,
    refine_place_type,
)
from services.manual_data_store import ManualDataStore  # noqa: E402
from services.place_defaults import category_label  # noqa: E402


def _parse_opened_at(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _apply_cache_fields(places: list[dict], cache: dict) -> int:
    updated = 0
    for raw in places:
        naver_id = _naver_id(raw)
        if not naver_id:
            continue
        entry = cache.get(naver_id)
        cached = entry.get("data", {}) if entry else {}
        if not cached:
            continue

        cached_menu = cached.get("representative_menu")
        if _should_use_cached_menu(raw.get("representative_menu"), cached_menu):
            raw["representative_menu"] = cached_menu
            updated += 1

        if _sync_menu_names(raw, cached):
            updated += 1

        cached_opened_at = cached.get("opened_at")
        if cached_opened_at and not raw.get("opened_at"):
            raw["opened_at"] = cached_opened_at
            updated += 1
    return updated


def _apply_manual_openings(places: list[dict], store: ManualDataStore) -> int:
    updated = 0
    for raw in places:
        if raw.get("opened_at"):
            continue
        naver_id = _naver_id(raw)
        manual = store.get_opening_date(
            place_id=raw.get("id"),
            naver_place_id=naver_id,
            name=raw.get("name"),
        )
        if manual:
            raw["opened_at"] = manual.isoformat()
            updated += 1
    return updated


def _place_from_raw(raw: dict) -> Place:
    return Place(
        id=raw["id"],
        name=raw["name"],
        place_type=PlaceType(raw["place_type"]),
        category=PlaceCategory(raw.get("category", "other")),
        address=raw.get("address", ""),
        lat=raw["lat"],
        lng=raw["lng"],
        distance_meters=raw.get("distance_meters"),
        walk_minutes=raw.get("walk_minutes"),
        rating=raw.get("rating"),
        rating_source=raw.get("rating_source"),
        review_count=raw.get("review_count"),
        price_per_person_krw=raw.get("price_per_person_krw"),
        representative_menu=raw.get("representative_menu"),
        representative_review=raw.get("representative_review"),
        price_range_min_krw=raw.get("price_range_min_krw"),
        price_range_max_krw=raw.get("price_range_max_krw"),
        phone=raw.get("phone"),
        url=raw.get("url"),
        source=raw.get("source", "naver"),
        naver_place_id=raw.get("naver_place_id"),
        opened_at=_parse_opened_at(raw.get("opened_at")),
    )


def _menu_text_from_raw(raw: dict) -> str:
    """대표메뉴·menu_names·캐시 메뉴를 분류용 문자열로 합칩니다."""
    from services.place_defaults import is_generic_menu

    parts: list[str] = []
    menu = (raw.get("representative_menu") or "").strip()
    if menu and not is_generic_menu(menu):
        parts.append(menu)
    names = raw.get("menu_names")
    if isinstance(names, list):
        for name in names[:6]:
            text = str(name or "").strip()
            if text and text not in parts:
                parts.append(text)
    return " · ".join(parts)


def _menu_names_from_raw(raw: dict) -> list[str]:
    names = raw.get("menu_names")
    if isinstance(names, list):
        return [str(name).strip() for name in names if str(name or "").strip()]
    return _menu_names_from_parts(_menu_text_from_raw(raw))


def reclassify_raw_place(raw: dict) -> bool:
    """단일 places.json 항목의 place_type·category를 갱신합니다."""
    place = _place_from_raw(raw)
    menu_text = _menu_text_from_raw(raw)
    menu_names = _menu_names_from_raw(raw)
    if menu_text and menu_text != (place.representative_menu or ""):
        place = place.model_copy(update={"representative_menu": menu_text})

    place_type = refine_place_type(place, menu_names=menu_names)
    if place_type != place.place_type:
        place = place.model_copy(update={"place_type": place_type})
    category = refine_category(place, menu_names=menu_names)
    changed = place_type != PlaceType(raw["place_type"]) or category != PlaceCategory(
        raw.get("category", "other")
    )
    raw["place_type"] = place.place_type.value
    raw["category"] = category.value
    raw["category_label"] = category_label(category)
    return changed


def reclassify_places_list(places: list[dict]) -> int:
    return sum(1 for raw in places if reclassify_raw_place(raw))


def finalize_places_data(data: dict, *, cache: dict | None = None) -> tuple[int, int, int]:
    """캐시 메뉴 복원 → 재분류 → 비음식 제거 후 places 목록을 갱신합니다."""
    if cache is None:
        cache = ManualDataStore()._load_json(ManualDataStore()._cache_path)
    places = data.get("places", [])
    store = ManualDataStore()
    cache_updates = _apply_cache_fields(places, cache)
    manual_updates = _apply_manual_openings(places, store)
    changed = reclassify_places_list(places)

    food_places: list[dict] = []
    for raw in places:
        place = _place_from_raw(raw)
        if is_food_place(
            name=place.name,
            representative_review=place.representative_review or "",
            place_category=place.category,
        ):
            food_places.append(raw)
    removed = len(places) - len(food_places)
    data["places"] = food_places
    data["generated_at"] = datetime.now().isoformat()
    within_days = (data.get("defaults") or {}).get("new_opening_days")
    sync_opening_flags_in_places(food_places, within_days=within_days)
    data["new_openings"] = sync_new_openings_from_places(
        food_places,
        within_days=within_days,
    )
    return cache_updates + manual_updates, changed, removed


def _atomic_write_json(path: Path, data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def save_places_file(path: Path, data: dict | None = None) -> tuple[int, int, int]:
    """places.json을 캐시 복원·재분류·비음식 제거 후 저장합니다."""
    if data is None:
        data = json.loads(path.read_text(encoding="utf-8"))
    stats = finalize_places_data(data)
    _atomic_write_json(path, data)
    return stats


def reclassify(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    cache_updates, changed, removed = finalize_places_data(data)
    _atomic_write_json(path, data)

    counts = Counter(p["category"] for p in data["places"])
    print(
        f"Saved {path} (cache menus: {cache_updates}, reclassified: {changed}, "
        f"removed non-food: {removed}, new_openings: {len(data['new_openings'])})"
    )
    for key in sorted(counts):
        print(f"  {category_label(PlaceCategory(key))} ({key}): {counts[key]}")


if __name__ == "__main__":
    for rel in ("site/data/places.json", "docs/data/places.json"):
        target = ROOT / rel
        if target.exists():
            reclassify(target)
