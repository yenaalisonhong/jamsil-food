"""기존 places.json을 크롤링·기본값으로 다시 보강합니다."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.place import Place, PlaceCategory, PlaceType  # noqa: E402
from scripts.export_places import build_payload  # noqa: E402
from services.place_defaults import GENERIC_MENU_HINTS  # noqa: E402
from services.place_enricher import PlaceEnricher  # noqa: E402


def upgrade(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    enricher = PlaceEnricher(enable_crawl=True)
    upgraded: list[Place] = []
    total = len(data.get("places", []))

    for index, raw in enumerate(data.get("places", []), start=1):
        print(f"[{index}/{total}] {raw['name']}")
        place = Place(
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
            representative_menu=(
                None
                if raw.get("representative_menu") in (None, *GENERIC_MENU_HINTS)
                else raw.get("representative_menu")
            ),
            representative_review=raw.get("representative_review"),
            price_range_min_krw=raw.get("price_range_min_krw"),
            price_range_max_krw=raw.get("price_range_max_krw"),
            phone=raw.get("phone"),
            url=raw.get("url"),
            source=raw.get("source", "naver"),
        )
        menu = raw.get("representative_menu")
        already_enriched = raw.get("rating") is not None and (
            raw.get("representative_review")
            or (menu and menu not in GENERIC_MENU_HINTS)
        )
        if already_enriched:
            upgraded.append(place)
            continue

        upgraded.append(enricher.enrich_one(place))
        if index % 10 == 0 or index == total:
            payload = build_payload(upgraded + [
                Place(
                    id=r["id"],
                    name=r["name"],
                    place_type=PlaceType(r["place_type"]),
                    category=PlaceCategory(r.get("category", "other")),
                    address=r["address"],
                    lat=r["lat"],
                    lng=r["lng"],
                    distance_meters=r.get("distance_meters"),
                    walk_minutes=r.get("walk_minutes"),
                    rating=r.get("rating"),
                    rating_source=r.get("rating_source"),
                    review_count=r.get("review_count"),
                    price_per_person_krw=r.get("price_per_person_krw"),
                    representative_menu=r.get("representative_menu"),
                    representative_review=r.get("representative_review"),
                    price_range_min_krw=r.get("price_range_min_krw"),
                    price_range_max_krw=r.get("price_range_max_krw"),
                    phone=r.get("phone"),
                    url=r.get("url"),
                    source=r.get("source", "naver"),
                )
                for r in data["places"][index:]
            ])
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    payload = build_payload(upgraded)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ratings = sum(1 for p in payload["places"] if p.get("rating"))
    reviews = sum(1 for p in payload["places"] if p.get("representative_review"))
    print(f"Saved {path} — ratings={ratings}, reviews={reviews}")


if __name__ == "__main__":
    for rel in ("site/data/places.json", "docs/data/places.json"):
        target = ROOT / rel
        if target.exists():
            upgrade(target)
