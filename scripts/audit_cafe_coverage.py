"""근처 카페 커버리지 감사 — 알려진 시드 대비 places.json 포함 여부."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.place import PlaceType
from providers.jamsil_commercial import COMMERCIAL_ANCHORS, _DEEP_CAFE_NAMED_SEEDS

PLACES_PATH = ROOT / "site" / "data" / "places.json"


def _normalize(name: str) -> str:
    return name.replace(" ", "").lower()


def main() -> None:
    data = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    places = data.get("places", [])
    cafes = [p for p in places if p.get("place_type") == "cafe"]
    all_names = {_normalize(p.get("name", "")) for p in places}

    print(f"places.json: {len(places)}곳 (카페 {len(cafes)}곳)")
    print()

    missing: list[str] = []
    found: list[str] = []
    for anchor, seeds in _DEEP_CAFE_NAMED_SEEDS.items():
        for seed in seeds:
            key = _normalize(seed)
            matched = any(key in n or n in key for n in all_names)
            if matched:
                found.append(f"{seed} ({anchor})")
            else:
                missing.append(f"{seed} ({anchor})")

    print(f"카페 시드 {len(found) + len(missing)}개 중 포함 {len(found)}개, 누락 {len(missing)}개")
    if missing:
        print("\n[누락]")
        for item in missing:
            print(f"  - {item}")
    if found:
        print("\n[포함]")
        for item in found:
            print(f"  - {item}")

    # 비음식 카페로 잘못 분류된 항목
    bad_markers = (
        "올리브영",
        "프린트카페",
        "화장실",
        "은행",
        "편의점",
        "캐리박스",
        "총각네야채",
    )
    bad = [p["name"] for p in cafes if any(m in p.get("name", "") for m in bad_markers)]
    if bad:
        print(f"\n[비음식 항목이 카페로 남아 있음: {len(bad)}곳]")
        for name in bad:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
