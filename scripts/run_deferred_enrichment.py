"""Merge site/docs places.json and run deferred Naver enrichment."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reclassify_places import _atomic_write_json, finalize_places_data  # noqa: E402

SITE = ROOT / "site" / "data" / "places.json"
DOCS = ROOT / "docs" / "data" / "places.json"
DELAY = "12"


def _richness(raw: dict) -> int:
    score = 0
    if raw.get("rating") is not None:
        score += 4
    if raw.get("representative_review"):
        score += 3
    if raw.get("menu_names"):
        score += 2
    menu = raw.get("representative_menu") or ""
    if menu and menu not in ("아메리카노 / 라떼", "대표 메뉴"):
        score += 2
    if raw.get("review_count") is not None:
        score += 1
    return score


def merge_places() -> dict:
    site_data = json.loads(SITE.read_text(encoding="utf-8"))
    docs_data = json.loads(DOCS.read_text(encoding="utf-8"))
    by_id: dict[str, dict] = {}

    for raw in docs_data.get("places", []):
        by_id[raw["id"]] = raw
    for raw in site_data.get("places", []):
        existing = by_id.get(raw["id"])
        if existing is None or _richness(raw) > _richness(existing):
            by_id[raw["id"]] = raw

    merged = dict(docs_data)
    merged["places"] = list(by_id.values())
    finalize_places_data(merged)
    for path in (SITE, DOCS):
        _atomic_write_json(path, merged)
    print(f"merged {len(merged['places'])} places -> site + docs")
    return merged


def run_step(label: str, args: list[str]) -> None:
    print(f"\n=== {label} ===", flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=False)


def main() -> None:
    merge_places()
    run_step(
        "ratings",
        [
            "scripts/refresh_ratings_in_places_json.py",
            "--crawl",
            "--delay",
            DELAY,
            "--path",
            str(SITE),
        ],
    )
    run_step(
        "menus",
        [
            "scripts/refresh_menus_in_places_json.py",
            "--crawl",
            "--delay",
            DELAY,
            "--path",
            str(SITE),
        ],
    )
    run_step(
        "prices",
        [
            "scripts/refresh_prices_in_places_json.py",
            "--all-types",
            "--delay",
            DELAY,
            "--path",
            str(SITE),
        ],
    )
    run_step(
        "reviews",
        [
            "scripts/backfill_reviews_in_places_json.py",
            "--crawl",
            "--delay",
            DELAY,
            "--path",
            str(SITE),
        ],
    )
    run_step("reclassify", ["scripts/reclassify_places.py"])
    docs_data = json.loads(SITE.read_text(encoding="utf-8"))
    docs_data["generated_at"] = datetime.now().isoformat()
    _atomic_write_json(DOCS, docs_data)
    print(f"\nDone. synced docs ({len(docs_data['places'])} places)", flush=True)


if __name__ == "__main__":
    main()
