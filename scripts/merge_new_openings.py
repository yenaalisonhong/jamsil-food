"""기존 places.json에 신규 오픈 후보만 병합합니다."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import date

from models.place import Place, PlaceCategory, PlaceType  # noqa: E402
from scripts.export_places import _fetch_new_opening_candidates, build_payload  # noqa: E402
from services.geolocation import GeolocationService  # noqa: E402
from services.place_enricher import PlaceEnricher  # noqa: E402


def merge(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    enricher = PlaceEnricher(enable_crawl=True)
    geo = GeolocationService()

    existing: list[Place] = []
    for raw in data.get("places", []):
        existing.append(
            Place(
                id=raw["id"],
                name=raw["name"],
                place_type=PlaceType(raw["place_type"]),
                category=PlaceCategory(raw.get("category", "other")),
                address=raw["address"],
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
                opened_at=(
                    date.fromisoformat(raw["opened_at"]) if raw.get("opened_at") else None
                ),
                phone=raw.get("phone"),
                url=raw.get("url"),
                source=raw.get("source", "naver"),
            )
        )

    extras = _fetch_new_opening_candidates(use_mock=False, enable_crawl=True)
    merged = enricher.merge_duplicates(existing + extras)
    existing_ids = {p.id for p in existing}
    enriched: list[Place] = []
    for place in merged:
        if place.id in existing_ids:
            enriched.append(place)
        else:
            enriched.append(enricher.enrich_one(place))
    within = [geo.enrich_place(p) for p in enriched if geo.is_within_walk_range(geo.enrich_place(p))]

    payload = build_payload(within)
    from scripts.reclassify_places import finalize_places_data

    finalize_places_data(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {path} — places={len(within)}, new_openings={len(payload['new_openings'])}")


if __name__ == "__main__":
    for rel in ("site/data/places.json", "docs/data/places.json"):
        target = ROOT / rel
        if target.exists():
            merge(target)
