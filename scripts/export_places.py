"""맛집·카페 데이터를 JSON으로보내 웹 UI에서 사용합니다."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.main import _build_providers  # noqa: E402
from config.settings import get_settings  # noqa: E402
from models.place import Place, PlaceType  # noqa: E402
from services.geolocation import GeolocationService  # noqa: E402
from services.new_opening_discovery import NewOpeningDiscovery  # noqa: E402
from services.place_defaults import (  # noqa: E402
    category_label,
    is_generic_menu,
    resolve_price_fields,
)
from services.category_classifier import is_food_place  # noqa: E402
from services.place_enricher import PlaceEnricher  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def _place_to_dict(place: Place) -> dict:
    settings = get_settings()
    mid, lo, hi = resolve_price_fields(place)
    return {
        "id": place.id,
        "name": place.name,
        "place_type": place.place_type.value,
        "category": place.category.value,
        "category_label": category_label(place.category),
        "address": place.address,
        "lat": place.lat,
        "lng": place.lng,
        "distance_meters": place.distance_meters,
        "walk_minutes": place.walk_minutes,
        "rating": place.rating,
        "rating_source": place.rating_source,
        "review_count": place.review_count,
        "representative_review": place.representative_review,
        "representative_reviews": place.representative_reviews,
        "price_per_person_krw": place.price_per_person_krw or mid,
        "price_range_min_krw": place.price_range_min_krw or lo,
        "price_range_max_krw": place.price_range_max_krw or hi,
        "representative_menu": place.representative_menu,
        "opened_at": place.opened_at.isoformat() if place.opened_at else None,
        "is_new_opening": _is_new_opening(place, settings.new_opening_days),
        "phone": place.phone,
        "url": str(place.url) if place.url else None,
        "source": place.source,
    }


def _is_new_opening(place: Place, within_days: int = 30) -> bool:
    if place.opened_at is None:
        return False
    cutoff = date.today() - timedelta(days=within_days)
    return place.opened_at >= cutoff


def is_new_opening_raw(raw: dict, within_days: int) -> bool:
    opened = raw.get("opened_at")
    if not opened:
        return False
    cutoff = date.today() - timedelta(days=within_days)
    return date.fromisoformat(opened) >= cutoff


def sync_opening_flags_in_places(
    place_dicts: list[dict],
    *,
    within_days: int | None = None,
) -> None:
    """opened_at 기준으로 각 항목의 is_new_opening 플래그를 갱신합니다."""
    days = within_days if within_days is not None else get_settings().new_opening_days
    for raw in place_dicts:
        raw["is_new_opening"] = is_new_opening_raw(raw, days)


def preserve_opened_at_from_snapshots(
    place_dicts: list[dict],
    *snapshots: list[dict],
) -> int:
    """이전 places.json·new_openings 스냅샷에서 opened_at을 복원합니다."""
    by_id: dict[str, str] = {}
    for snapshot in snapshots:
        for raw in snapshot:
            opened = raw.get("opened_at")
            if opened:
                by_id[raw["id"]] = opened
    restored = 0
    for raw in place_dicts:
        if not raw.get("opened_at") and raw["id"] in by_id:
            raw["opened_at"] = by_id[raw["id"]]
            restored += 1
    return restored


def sync_new_openings_from_places(
    place_dicts: list[dict],
    *,
    within_days: int | None = None,
) -> list[dict]:
    """신규 오픈 팝업용 — places와 동일한 분류·메뉴 스냅샷을 유지합니다."""
    sync_opening_flags_in_places(place_dicts, within_days=within_days)
    openings = [place for place in place_dicts if place.get("is_new_opening")]
    return sorted(
        openings,
        key=lambda place: (
            place.get("opened_at") or "",
            -(place.get("walk_minutes") if place.get("walk_minutes") is not None else 999),
        ),
        reverse=True,
    )


def _fetch_new_opening_candidates(*, use_mock: bool, enable_crawl: bool) -> list[Place]:
    if use_mock or not enable_crawl:
        return []
    try:
        settings = get_settings()
        geo = GeolocationService(settings)
        extras = NewOpeningDiscovery().fetch_candidates()
        within_range: list[Place] = []
        for place in extras:
            enriched = geo.enrich_place(place)
            if geo.is_within_walk_range(enriched):
                within_range.append(enriched)
        logger.info("도보 범위 내 신규 오픈 후보 %d건", len(within_range))
        return within_range
    except Exception as exc:
        logger.warning("신규 오픈 후보 수집 실패: %s", exc)
        return []


def collect_places(*, use_mock: bool = False, enable_crawl: bool = True) -> list[Place]:
    """주변 장소를 수집·보강하고 도보 범위 내 항목만 반환합니다."""
    settings = get_settings()
    geo = GeolocationService(settings)
    enricher = PlaceEnricher(enable_crawl=enable_crawl)
    providers = _build_providers(use_mock)

    collected: list[Place] = []
    for provider in providers:
        for place_type in (PlaceType.RESTAURANT, PlaceType.CAFE):
            try:
                places = provider.fetch_places(place_type)
                collected.extend(places)
            except Exception:
                continue

    collected.extend(_fetch_new_opening_candidates(use_mock=use_mock, enable_crawl=enable_crawl))
    enriched = enricher.merge_duplicates(enricher.enrich_all(collected))
    within_range: list[Place] = []
    for place in enriched:
        with_geo = geo.enrich_place(place)
        if geo.is_within_walk_range(with_geo):
            within_range.append(with_geo)
    return within_range


def build_payload(places: list[Place]) -> dict:
    settings = get_settings()
    food_places = [
        p
        for p in places
        if is_food_place(
            name=p.name,
            representative_review=p.representative_review or "",
            place_category=p.category,
        )
    ]
    place_dicts = [_place_to_dict(p) for p in food_places]

    return {
        "generated_at": datetime.now().isoformat(),
        "office": {
            "name": "Fraunhofer 한국사무소",
            "address": "서울시 송파구 올림픽로 35가길 10, A동 202호",
            "lat": settings.fraunhofer_office_lat,
            "lng": settings.fraunhofer_office_lng,
        },
        "defaults": {
            "min_rating": settings.min_rating,
            "max_price_per_person_krw": settings.max_price_per_person_krw,
            "max_walk_minutes": settings.max_walk_minutes,
            "new_opening_days": settings.new_opening_days,
            "highlight_rating_min": 4.5,
            "highlight_review_count_min": 10,
        },
        "new_openings": sync_new_openings_from_places(place_dicts),
        "places": place_dicts,
    }


def _previous_opening_snapshots(path: Path) -> list[list[dict]]:
    snapshots: list[list[dict]] = []
    if path.exists():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            snapshots.append(prev.get("places", []))
            snapshots.append(prev.get("new_openings", []))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("기존 places.json opened_at 보존 스킵: %s", exc)
    docs_path = ROOT / "docs" / "data" / "places.json"
    if docs_path.exists() and docs_path.resolve() != path.resolve():
        try:
            docs = json.loads(docs_path.read_text(encoding="utf-8"))
            snapshots.append(docs.get("places", []))
            snapshots.append(docs.get("new_openings", []))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("docs places.json opened_at 보존 스킵: %s", exc)
    return snapshots


def export_to(path: Path, *, use_mock: bool = False, enable_crawl: bool = True) -> int:
    places = collect_places(use_mock=use_mock, enable_crawl=enable_crawl)
    payload = build_payload(places)
    path.parent.mkdir(parents=True, exist_ok=True)
    from scripts.reclassify_places import finalize_places_data

    restored = preserve_opened_at_from_snapshots(
        payload["places"],
        *_previous_opening_snapshots(path),
    )
    if restored:
        logger.info("재export 시 opened_at %d건 복원", restored)
    finalize_places_data(payload)
    from scripts.reclassify_places import _atomic_write_json

    _atomic_write_json(path, payload)
    print(f"Exported {len(payload['places'])} places → {path}")
    return len(payload["places"])


def main() -> None:
    parser = argparse.ArgumentParser(description="맛집 데이터 JSON보내기")
    parser.add_argument("--mock", action="store_true", help="Mock 데이터 사용")
    parser.add_argument(
        "--no-crawl",
        action="store_true",
        help="Naver 크롤링 비활성화",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
        help="출력 경로",
    )
    args = parser.parse_args()
    export_to(args.output, use_mock=args.mock, enable_crawl=not args.no_crawl)


if __name__ == "__main__":
    main()
