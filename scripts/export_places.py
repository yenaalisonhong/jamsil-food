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
from models.place import Place, PlaceCategory, PlaceType  # noqa: E402
from services.filter_service import FilterService  # noqa: E402
from services.geolocation import GeolocationService  # noqa: E402
from services.place_enricher import PlaceEnricher  # noqa: E402
from services.recommendation_service import RecommendationService  # noqa: E402

_CATEGORY_MENUS: dict[PlaceCategory, str] = {
    PlaceCategory.KOREAN: "한정식 / 제육볶음",
    PlaceCategory.CHINESE: "짜장면 / 탕수육",
    PlaceCategory.JAPANESE: "초밥 / 돈카츠",
    PlaceCategory.WESTERN: "파스타 / 스테이크",
    PlaceCategory.FAST_FOOD: "버거 / 샌드위치",
    PlaceCategory.BUNSIK: "떡볶이 / 김밥",
    PlaceCategory.CAFE: "아메리카노 / 라떼",
    PlaceCategory.DESSERT: "케이크 / 마카롱",
    PlaceCategory.OTHER: "시그니처 메뉴",
}

_CATEGORY_LABELS: dict[PlaceCategory, str] = {
    PlaceCategory.KOREAN: "한식",
    PlaceCategory.CHINESE: "중식",
    PlaceCategory.JAPANESE: "일식",
    PlaceCategory.WESTERN: "양식",
    PlaceCategory.FAST_FOOD: "패스트푸드",
    PlaceCategory.BUNSIK: "분식",
    PlaceCategory.CAFE: "카페",
    PlaceCategory.DESSERT: "디저트",
    PlaceCategory.OTHER: "기타",
}


def _default_menu(place: Place) -> str:
    if place.representative_menu:
        return place.representative_menu
    return _CATEGORY_MENUS.get(place.category, "시그니처 메뉴")


def _place_to_dict(place: Place) -> dict:
    return {
        "id": place.id,
        "name": place.name,
        "place_type": place.place_type.value,
        "category": place.category.value,
        "category_label": _CATEGORY_LABELS.get(place.category, "기타"),
        "address": place.address,
        "lat": place.lat,
        "lng": place.lng,
        "distance_meters": place.distance_meters,
        "walk_minutes": place.walk_minutes,
        "rating": place.rating,
        "rating_source": place.rating_source,
        "review_count": place.review_count,
        "price_per_person_krw": place.price_per_person_krw,
        "representative_menu": _default_menu(place),
        "opened_at": place.opened_at.isoformat() if place.opened_at else None,
        "is_new_opening": _is_new_opening(place),
        "phone": place.phone,
        "url": str(place.url) if place.url else None,
        "source": place.source,
    }


def _is_new_opening(place: Place, within_days: int = 30) -> bool:
    if place.opened_at is None:
        return False
    cutoff = date.today() - timedelta(days=within_days)
    return place.opened_at >= cutoff


def collect_places(*, use_mock: bool = False, enable_crawl: bool = False) -> list[Place]:
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

    enriched = enricher.merge_duplicates(enricher.enrich_all(collected))
    within_range: list[Place] = []
    for place in enriched:
        with_geo = geo.enrich_place(place)
        if geo.is_within_walk_range(with_geo):
            within_range.append(with_geo)
    return within_range


def build_payload(places: list[Place]) -> dict:
    settings = get_settings()
    filter_svc = FilterService(settings, GeolocationService(settings))
    new_openings = filter_svc.filter_new_openings(places)

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
        },
        "new_openings": [_place_to_dict(p) for p in new_openings],
        "places": [_place_to_dict(p) for p in places],
    }


def export_to(path: Path, *, use_mock: bool = False, enable_crawl: bool = False) -> int:
    places = collect_places(use_mock=use_mock, enable_crawl=enable_crawl)
    payload = build_payload(places)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(places)} places → {path}")
    return len(places)


def main() -> None:
    parser = argparse.ArgumentParser(description="맛집 데이터 JSON보내기")
    parser.add_argument("--mock", action="store_true", help="Mock 데이터 사용")
    parser.add_argument("--crawl", action="store_true", help="Naver 크롤링 활성화")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
        help="출력 경로",
    )
    args = parser.parse_args()
    export_to(args.output, use_mock=args.mock, enable_crawl=args.crawl)


if __name__ == "__main__":
    main()
