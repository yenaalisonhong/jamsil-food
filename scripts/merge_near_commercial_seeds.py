"""near_commercial_seeds.json 항목을 places.json에 병합."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.place import Place, PlaceCategory, PlaceType
from scripts.export_places import build_payload
from scripts.supplement_near_commercial import TARGETS, load_existing
from services.geolocation import GeolocationService
from services.place_enricher import PlaceEnricher

SEEDS_PATH = ROOT / "data" / "near_commercial_seeds.json"
LEGACY_SEEDS_PATH = ROOT / "data" / "jangmi_place_seeds.json"


def _seed_paths() -> list[Path]:
    paths: list[Path] = []
    if SEEDS_PATH.exists():
        paths.append(SEEDS_PATH)
    if LEGACY_SEEDS_PATH.exists():
        paths.append(LEGACY_SEEDS_PATH)
    return paths


def _seed_to_place(raw: dict) -> Place | None:
    name = (raw.get("name") or "").strip()
    if not name:
        return None
    lat = raw.get("lat")
    lng = raw.get("lng")
    if lat is None or lng is None:
        return None

    naver_id = str(raw.get("naver_place_id") or "").strip()
    place_id = f"naver:{naver_id}" if naver_id else f"seed:{name.replace(' ', '_')}"
    category = PlaceCategory(raw.get("category", "korean"))
    place_type = (
        PlaceType.CAFE
        if category in {PlaceCategory.CAFE, PlaceCategory.DESSERT}
        else PlaceType.RESTAURANT
    )
    enc_name = urllib.parse.quote(name)
    url = (
        f"https://map.naver.com/p/search/{enc_name}/place/{naver_id}"
        if naver_id
        else None
    )
    return Place(
        id=place_id,
        name=name,
        place_type=place_type,
        category=category,
        address=raw.get("address", ""),
        lat=float(lat),
        lng=float(lng),
        url=url,
        source="manual_seed",
        naver_place_id=naver_id or None,
    )


def merge_seeds(*, enable_crawl: bool = True) -> int:
    paths = _seed_paths()
    if not paths:
        print("No seed files found.")
        return 0

    all_seeds: list[dict] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        all_seeds.extend(payload.get("seeds", []))

    if not all_seeds:
        return 0

    geo = GeolocationService()
    enricher = PlaceEnricher(enable_crawl=enable_crawl)
    path = TARGETS[0]
    existing = load_existing(path)
    seen = {p.id for p in existing}
    seen_names = {p.name for p in existing}
    added: list[Place] = []

    for raw in all_seeds:
        name = raw.get("name", "")
        if name in seen_names:
            print(f"  skip existing name: {name}")
            continue
        place = _seed_to_place(raw)
        if place is None:
            continue
        if place.id in seen:
            continue
        seen.add(place.id)
        seen_names.add(place.name)
        anchor = raw.get("anchor", "")
        added.append(geo.enrich_place(place))
        label = f" [{anchor}]" if anchor else ""
        print(f"  + {place.name}{label}")

    if not added:
        print("No new seed places to add.")
        return 0

    merged = enricher.merge_duplicates(existing + enricher.enrich_all(added))
    within = [
        geo.enrich_place(p)
        for p in merged
        if geo.is_within_walk_range(geo.enrich_place(p))
    ]
    out = build_payload(within)
    from scripts.reclassify_places import finalize_places_data

    finalize_places_data(out)

    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated {target} (+{len(added)} seeds, total {len(within)})")

    return len(added)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="근접 상가 수동 시드 병합")
    parser.add_argument("--no-crawl", action="store_true")
    args = parser.parse_args()
    merge_seeds(enable_crawl=not args.no_crawl)
