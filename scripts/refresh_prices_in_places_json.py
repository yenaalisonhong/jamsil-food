"""places.json 가격·가격대를 네이버 메뉴 페이지로 재계산합니다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.place import PlaceType  # noqa: E402
from services.manual_data_store import ManualDataStore  # noqa: E402
from services.naver_place_crawler import NaverPlaceCrawler  # noqa: E402
from utils.naver_urls import extract_naver_place_id  # noqa: E402


def _naver_id(raw: dict) -> str | None:
    from_url = extract_naver_place_id(str(raw.get("url") or ""))
    if from_url:
        return from_url
    place_id = str(raw.get("id") or "")
    if place_id.startswith("naver:"):
        candidate = place_id.split(":", 1)[1]
        if candidate.isdigit():
            return candidate
    return None


def _save_data(path: Path, data: dict) -> None:
    from scripts.reclassify_places import _atomic_write_json, finalize_places_data

    finalize_places_data(data)
    _atomic_write_json(path, data)


def _apply_price_fields(raw: dict, fields: dict[str, Any]) -> bool:
    updated = False
    for field in (
        "price_per_person_krw",
        "price_range_min_krw",
        "price_range_max_krw",
    ):
        value = fields.get(field)
        if value is not None and raw.get(field) != value:
            raw[field] = value
            updated = True
    return updated


def _heuristic_restaurant_fields(raw: dict) -> dict[str, int] | None:
    from services.place_defaults import adjust_restaurant_price_range

    if raw.get("place_type") != PlaceType.RESTAURANT.value:
        return None
    lo = raw.get("price_range_min_krw")
    hi = raw.get("price_range_max_krw")
    if lo is None or hi is None or lo >= 6_000:
        return None
    new_lo, new_hi = adjust_restaurant_price_range(
        raw.get("price_per_person_krw"),
        lo,
        hi,
    )
    if new_lo == lo and new_hi == hi:
        return None
    return {"price_range_min_krw": new_lo, "price_range_max_krw": new_hi}


def _recompute_from_cache(
    store: ManualDataStore,
    places: list[dict],
    *,
    restaurants_only: bool,
) -> int:
    cache = store._load_json(store._cache_path)
    by_naver_id = {_naver_id(raw): raw for raw in places if _naver_id(raw)}
    updates = 0

    for naver_id, entry in cache.items():
        raw = by_naver_id.get(naver_id)
        if not raw:
            continue
        if restaurants_only and raw.get("place_type") != PlaceType.RESTAURANT.value:
            continue

        menu_items = entry.get("data", {}).get("menu_items")
        if not menu_items:
            continue

        place_type = PlaceType(raw.get("place_type", "restaurant"))
        fields = NaverPlaceCrawler._price_fields_from_menu_items(menu_items, place_type)
        if _apply_price_fields(raw, fields):
            updates += 1

        cached_data = dict(entry.get("data", {}))
        cached_data.update(
            {
                k: fields[k]
                for k in (
                    "price_per_person_krw",
                    "price_range_min_krw",
                    "price_range_max_krw",
                    "menu_prices",
                )
                if fields.get(k) is not None
            }
        )
        store.set_cached_detail(naver_id, cached_data)

    return updates


def refresh(
    path: Path,
    *,
    crawl_limit: int | None = None,
    save_every: int = 10,
    request_delay_sec: float = 3.0,
    restaurants_only: bool = True,
    crawl: bool = True,
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    store = ManualDataStore()
    crawler = NaverPlaceCrawler(store, request_delay_sec=request_delay_sec)
    places = data.get("places", [])

    cache_updates = _recompute_from_cache(
        store,
        places,
        restaurants_only=restaurants_only,
    )
    heuristic_updates = 0
    for raw in places:
        if restaurants_only and raw.get("place_type") != PlaceType.RESTAURANT.value:
            continue
        fields = _heuristic_restaurant_fields(raw)
        if fields and _apply_price_fields(raw, fields):
            heuristic_updates += 1

    if cache_updates or heuristic_updates:
        _save_data(path, data)
        print(
            f"offline updates: cache={cache_updates}, heuristic={heuristic_updates}"
        )

    crawl_attempts = 0
    crawl_updates = 0
    crawl_failures = 0

    if not crawl:
        print(f"{path.name}: cache={cache_updates}, crawl=0, total={len(places)}")
        return

    for raw in places:
        if restaurants_only and raw.get("place_type") != PlaceType.RESTAURANT.value:
            continue

        naver_id = _naver_id(raw)
        if not naver_id:
            continue

        cached = store.get_cached_detail(naver_id, ttl_hours=24 * 365)
        if cached and cached.get("menu_items"):
            continue

        if crawl_limit is not None and crawl_attempts >= crawl_limit:
            break

        place_type = PlaceType(raw.get("place_type", "restaurant"))
        crawler.fetch_representative_menu(naver_id, place_type)
        crawl_attempts += 1

        cached = store.get_cached_detail(naver_id, ttl_hours=24 * 365)
        if not cached:
            crawl_failures += 1
            continue

        if _apply_price_fields(raw, cached):
            crawl_updates += 1
            crawl_failures = 0
            if crawl_updates % save_every == 0:
                _save_data(path, data)
                print(
                    f"  ... saved progress ({crawl_updates} updated / {crawl_attempts} crawled)"
                )
        else:
            crawl_failures += 1
            if crawl_failures >= 5:
                wait = min(120, 30 + crawl_failures * 10)
                print(f"  ... rate limit backoff {wait}s")
                time.sleep(wait)
                crawl_failures = 0

    _save_data(path, data)
    print(
        f"{path.name}: cache={cache_updates}, crawled={crawl_attempts}, "
        f"crawl_updated={crawl_updates}, total={len(places)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="places.json 가격·가격대 갱신")
    parser.add_argument(
        "--no-crawl",
        action="store_true",
        help="캐시 재계산만 수행 (네이버 요청 없음)",
    )
    parser.add_argument(
        "--crawl-limit",
        type=int,
        default=None,
        help="메뉴 크롤 최대 건수",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=8.0,
        help="네이버 요청 간격(초)",
    )
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="카페 포함 전체 장소 갱신",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
    )
    args = parser.parse_args()

    refresh(
        args.path,
        crawl_limit=args.crawl_limit,
        request_delay_sec=args.delay,
        restaurants_only=not args.all_types,
        crawl=not args.no_crawl,
    )

    docs_path = ROOT / "docs" / "data" / "places.json"
    if docs_path != args.path and docs_path.exists():
        docs_path.write_text(
            args.path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print(f"copied → {docs_path}")


if __name__ == "__main__":
    main()
