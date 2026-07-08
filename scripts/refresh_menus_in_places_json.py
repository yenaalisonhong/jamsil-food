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


def _menu_names_from_cache_data(cached: dict) -> list[str] | None:
    """캐시 menu_items에서 검색용 메뉴명 목록을 추출합니다."""
    items = cached.get("menu_items")
    if not items:
        return None
    names: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names or None


def _sync_menu_names(raw: dict, cached: dict) -> bool:
    names = _menu_names_from_cache_data(cached)
    if not names:
        return False
    raw["menu_names"] = names
    return True


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


def _save_data(path: Path, data: dict, *, finalize: bool = True) -> None:
    if finalize:
        from scripts.reclassify_places import finalize_places_data

        finalize_places_data(data)
    else:
        from scripts.export_places import sync_new_openings_from_places

        data["generated_at"] = datetime.now().isoformat()
        data["new_openings"] = sync_new_openings_from_places(data.get("places", []))
    from scripts.reclassify_places import _atomic_write_json

    _atomic_write_json(path, data)


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
    menu_names_updates = 0
    crawl_updates = 0
    crawl_attempts = 0
    crawl_failures = 0
    places = data.get("places", [])

    for index, raw in enumerate(places, start=1):
        menu = raw.get("representative_menu")
        naver_id = _naver_id(raw)
        cached: dict = {}

        if naver_id:
            entry = cache.get(naver_id)
            cached = entry.get("data", {}) if entry else {}
            if _sync_menu_names(raw, cached):
                menu_names_updates += 1
            cached_menu = cached.get("representative_menu")
            if _should_use_cached_menu(menu, cached_menu):
                raw["representative_menu"] = cached_menu
                cache_updates += 1
                menu = cached_menu

        needs_menu_names = not raw.get("menu_names")
        needs_rep_menu = is_generic_menu(menu)
        if not needs_menu_names and not needs_rep_menu:
            continue

        if not crawl or not crawler or not naver_id:
            continue
        if crawl_limit is not None and crawl_updates >= crawl_limit:
            break
        max_attempts = (crawl_limit * 4) if crawl_limit is not None else None
        if max_attempts is not None and crawl_attempts >= max_attempts:
            print(f"  ... stopping after {crawl_attempts} failed/skip attempts")
            break

        place_type = PlaceType(raw.get("place_type", "restaurant"))
        crawled = crawler.fetch_representative_menu(naver_id, place_type)
        crawl_attempts += 1
        updated = crawler._store.get_cached_detail(naver_id) or {}
        if _sync_menu_names(raw, updated):
            menu_names_updates += 1
        if crawled and not is_generic_menu(crawled):
            raw["representative_menu"] = crawled
        if (crawled and not is_generic_menu(crawled)) or updated.get("menu_items"):
            crawl_updates += 1
            crawl_failures = 0
            if crawl_updates % save_every == 0:
                _save_data(path, data, finalize=False)
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
        f"{path.name}: cache={cache_updates}, menu_names={menu_names_updates}, "
        f"crawl={crawl_updates}, real_menus={real_menus}/{len(places)}"
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
        help="성공적으로 가져온 메뉴 최대 건수",
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
