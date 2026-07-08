"""누락 카페 시드만 빠르게 보충 수집."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from models.place import PlaceType
from providers.jamsil_commercial import (
    COMMERCIAL_ANCHORS,
    _DEEP_CAFE_NAMED_SEEDS,
    nearest_commercial_names,
)
from providers.naver_map_list import NaverMapListProvider
from scripts.supplement_commercial import TARGETS, load_existing
from scripts.export_places import build_payload
from services.category_classifier import is_food_place
from services.geolocation import GeolocationService
from services.place_enricher import PlaceEnricher

_ANCHOR_RADIUS_M = 600


def cafe_seed_searches() -> list[tuple[str, float, float]]:
    searches: list[tuple[str, float, float]] = []
    seen: set[tuple[str, float, float]] = set()
    deep_names = nearest_commercial_names()
    anchor_by_name = {a.name: a for a in COMMERCIAL_ANCHORS}

    for anchor_name, seeds in _DEEP_CAFE_NAMED_SEEDS.items():
        anchor = anchor_by_name.get(anchor_name)
        if anchor is None:
            continue
        for seed in seeds:
            key = (seed, round(anchor.lat, 5), round(anchor.lng, 5))
            if key in seen:
                continue
            seen.add(key)
            searches.append(key)

    # 잠실역 상권은 deep 5 밖이어도 시드 검색은 위에서 처리됨
    return searches


def supplement_cafe_seeds(*, enable_crawl: bool = True, delay: float = 4.0) -> int:
    settings = get_settings()
    geo = GeolocationService(settings)
    enricher = PlaceEnricher(enable_crawl=enable_crawl)
    provider = NaverMapListProvider(settings)
    provider._crawler._delay = max(delay, settings.crawl_request_delay_sec)

    path = TARGETS[0]
    existing = load_existing(path)
    seen = {p.id for p in existing}
    added = []
    office = provider._office
    max_dist = provider._max_dist_m
    crawler = provider._crawler

    for query, lat, lng in cafe_seed_searches():
        items = crawler.search_list_places(query, PlaceType.CAFE, lng=lng, lat=lat)
        for hit in items:
            if not is_food_place(
                name=hit.name,
                category_text=hit.category_text,
                business_category=hit.business_category,
            ):
                continue
            pid = f"naver:{hit.place_id}"
            if pid in seen:
                continue
            dist = provider._haversine_m(office[0], office[1], hit.lat, hit.lng)
            if dist > max_dist:
                continue
            anchor_dist = provider._haversine_m(lat, lng, hit.lat, hit.lng)
            if anchor_dist > _ANCHOR_RADIUS_M:
                continue
            seen.add(pid)
            place = NaverMapListProvider._to_place(hit, PlaceType.CAFE, query)
            added.append(geo.enrich_place(place))
            print(f"  + {hit.name} ({query})")

    if not added:
        print("No new cafe seed places.")
        return 0

    merged = enricher.merge_duplicates(existing + enricher.enrich_all(added))
    within = [
        geo.enrich_place(p)
        for p in merged
        if geo.is_within_walk_range(geo.enrich_place(p))
    ]
    payload = build_payload(within)
    from scripts.reclassify_places import finalize_places_data

    finalize_places_data(payload)

    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        cafes = sum(1 for p in payload["places"] if p.get("place_type") == "cafe")
        print(f"Updated {target} (+{len(added)}, total {len(within)}, cafes {cafes})")

    return len(added)


if __name__ == "__main__":
    supplement_cafe_seeds()
