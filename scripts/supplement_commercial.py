"""상가·건물 전용 보충 수집 후 places.json에 병합."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from models.place import Place, PlaceCategory, PlaceType
from providers.jamsil_commercial import map_searches, search_radius_m
from providers.naver_map_list import NaverMapListProvider
from scripts.export_places import build_payload
from services.category_classifier import is_food_place
from services.geolocation import GeolocationService
from services.place_enricher import PlaceEnricher

TARGETS = (
    ROOT / "site" / "data" / "places.json",
    ROOT / "docs" / "data" / "places.json",
)

_ANCHOR_RADIUS_M = 600  # fallback; prefer search_radius_m(lat, lng)


def load_existing(path: Path) -> list[Place]:
    data = json.loads(path.read_text(encoding="utf-8"))
    places: list[Place] = []
    for raw in data.get("places", []):
        places.append(
            Place(
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
            ),
        )
    return places


def supplement_commercial(
    *,
    enable_crawl: bool = False,
    request_delay_sec: float = 8.0,
) -> int:
    settings = get_settings()
    geo = GeolocationService(settings)
    enricher = PlaceEnricher(enable_crawl=enable_crawl)
    provider = NaverMapListProvider(settings)
    provider._crawler._delay = max(
        request_delay_sec,
        settings.crawl_request_delay_sec,
    )

    path = TARGETS[0]
    existing = load_existing(path)
    seen = {p.id for p in existing}
    added: list[Place] = []
    crawler = provider._crawler
    office = provider._office
    max_dist = provider._max_dist_m

    for place_type in (PlaceType.RESTAURANT, PlaceType.CAFE):
        for query, lat, lng in map_searches(place_type):
            items = crawler.search_list_places(query, place_type, lng=lng, lat=lat)
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
                if anchor_dist > search_radius_m(lat, lng):
                    continue
                seen.add(pid)
                place = NaverMapListProvider._to_place(hit, place_type, query)
                added.append(geo.enrich_place(place))
                print(f"  + {hit.name} ({query})")

    if not added:
        print("No new commercial places to add.")
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
        if target.parent.exists() or target == TARGETS[0]:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Updated {target} (+{len(added)} new, total {len(within)})")

    return len(added)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="전체 상가 보충 수집")
    parser.add_argument("--no-crawl", action="store_true")
    parser.add_argument("--delay", type=float, default=8.0)
    args = parser.parse_args()
    supplement_commercial(
        enable_crawl=not args.no_crawl,
        request_delay_sec=args.delay,
    )
