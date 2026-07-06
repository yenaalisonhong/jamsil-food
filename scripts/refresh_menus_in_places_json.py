"""places.json 대표메뉴를 캐시·네이버 메뉴 페이지로 갱신합니다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.place import PlaceType  # noqa: E402
from services.manual_data_store import ManualDataStore  # noqa: E402
from services.naver_place_crawler import NaverPlaceCrawler  # noqa: E402
from services.place_defaults import is_generic_menu  # noqa: E402
from utils.naver_urls import extract_naver_place_id  # noqa: E402


def _menu_richness(menu: str | None) -> int:
    if not menu:
        return 0
    return menu.count(" · ") + 1


def _should_use_cached_menu(current: str | None, cached_menu: str | None) -> bool:
    if not cached_menu or is_generic_menu(cached_menu):
        return False
    if is_generic_menu(current):
        return True
    return _menu_richness(cached_menu) > _menu_richness(current)


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
    from scripts.reclassify_places import finalize_places_data

    finalize_places_data(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh(
    path: Path,
    *,
    crawl: bool = False,
    crawl_limit: int | None = None,
    save_every: int = 10,
    request_delay_sec: float = 3.0,
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    store = ManualDataStore()
    cache = store._load_json(store._cache_path)
    crawler = (
        NaverPlaceCrawler(store, request_delay_sec=request_delay_sec) if crawl else None
    )

    cache_updates = 0
    crawl_updates = 0
    crawl_attempts = 0
    crawl_failures = 0
    places = data.get("places", [])

    for index, raw in enumerate(places, start=1):
        menu = raw.get("representative_menu")
        naver_id = _naver_id(raw)

        if naver_id:
            entry = cache.get(naver_id)
            cached_menu = entry.get("data", {}).get("representative_menu") if entry else None
            if _should_use_cached_menu(menu, cached_menu):
                raw["representative_menu"] = cached_menu
                cache_updates += 1
                menu = cached_menu

        if not is_generic_menu(menu):
            continue

        if naver_id:
            entry = cache.get(naver_id)
            cached_menu = entry.get("data", {}).get("representative_menu") if entry else None
            if _should_use_cached_menu(menu, cached_menu):
                raw["representative_menu"] = cached_menu
                cache_updates += 1
                continue

        if not crawl or not crawler or not naver_id:
            continue
        if crawl_limit is not None and crawl_attempts >= crawl_limit:
            break

        place_type = PlaceType(raw.get("place_type", "restaurant"))
        crawled = crawler.fetch_representative_menu(naver_id, place_type)
        crawl_attempts += 1
        if crawled and not is_generic_menu(crawled):
            raw["representative_menu"] = crawled
            crawl_updates += 1
            crawl_failures = 0
            if crawl and crawl_updates % save_every == 0:
                _save_data(path, data)
                print(f"  ... saved progress ({crawl_updates} crawled)")
        else:
            crawl_failures += 1
            if crawl_failures >= 5:
                wait = min(120, 30 + crawl_failures * 10)
                print(f"  ... rate limit backoff {wait}s")
                time.sleep(wait)
                crawl_failures = 0

    _save_data(path, data)

    real_menus = sum(
        1 for p in places if not is_generic_menu(p.get("representative_menu"))
    )
    print(
        f"{path.name}: cache={cache_updates}, crawl={crawl_updates}, "
        f"real_menus={real_menus}/{len(places)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="places.json 대표메뉴 갱신")
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="캐시에 없는 장소는 네이버 메뉴 페이지를 조회합니다",
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
        "--path",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
    )
    args = parser.parse_args()

    refresh(
        args.path,
        crawl=args.crawl,
        crawl_limit=args.crawl_limit,
        request_delay_sec=args.delay,
    )

    docs_path = ROOT / "docs" / "data" / "places.json"
    if docs_path != args.path and docs_path.exists():
        refresh(docs_path, crawl=False)


if __name__ == "__main__":
    main()
