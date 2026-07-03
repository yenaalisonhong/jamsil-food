"""
장소 데이터 보강(Enrichment) 서비스.

Kakao/Naver Provider 수집 결과에 대해:
  1. 수동 DB (가격·개업일)
  2. Naver Place ID 해석 및 크롤링 (평점·메뉴·가격·리뷰·개업일)
  3. 카테고리 기본값 (메뉴·가격 범위)
  4. 중복 장소 병합
을 적용합니다.
"""

import re
from typing import Iterable

from config.settings import get_settings
from models.place import Place
from providers.naver_local import NaverLocalProvider
from services.manual_data_store import ManualDataStore
from services.naver_place_crawler import NaverPlaceCrawler
from services.place_defaults import default_menu, resolve_price_fields
from utils.errors import ConfigurationError
from utils.logger import get_logger
from utils.naver_urls import extract_naver_place_id

logger = get_logger(__name__)


class PlaceEnricher:
    """Place 목록 보강 및 병합."""

    def __init__(
        self,
        store: ManualDataStore | None = None,
        crawler: NaverPlaceCrawler | None = None,
        naver_provider: NaverLocalProvider | None = None,
        *,
        enable_crawl: bool = True,
    ) -> None:
        self._store = store or ManualDataStore()
        self._crawler = crawler or NaverPlaceCrawler(self._store)
        self._enable_crawl = enable_crawl
        self._naver_provider = naver_provider
        if enable_crawl and naver_provider is None:
            try:
                self._naver_provider = NaverLocalProvider(get_settings())
            except ConfigurationError:
                self._naver_provider = None

    def enrich_all(self, places: list[Place]) -> list[Place]:
        """전체 목록 보강 후 중복 병합."""
        enriched = [self.enrich_one(p) for p in places]
        return self.merge_duplicates(enriched)

    def enrich_one(self, place: Place) -> Place:
        """단일 Place에 평점·가격·메뉴·리뷰·개업일을 채웁니다."""
        updates: dict = {}

        naver_id = self._resolve_naver_place_id(place)

        manual_price = self._store.get_price(
            place_id=place.id,
            naver_place_id=naver_id,
            name=place.name,
        )
        manual_opening = self._store.get_opening_date(
            place_id=place.id,
            naver_place_id=naver_id,
            name=place.name,
        )

        if place.price_per_person_krw is None and manual_price is not None:
            updates["price_per_person_krw"] = manual_price
        if place.opened_at is None and manual_opening is not None:
            updates["opened_at"] = manual_opening

        if naver_id and self._enable_crawl:
            needs_crawl = (
                place.rating is None
                or place.price_per_person_krw is None
                or place.representative_menu is None
                or place.representative_review is None
                or place.opened_at is None
            )
            if needs_crawl:
                detail = self._crawler.fetch_detail(naver_id, place.place_type)
                if place.rating is None and detail.rating is not None:
                    updates["rating"] = detail.rating
                    updates["rating_source"] = "naver_crawl"
                if place.review_count is None and detail.review_count is not None:
                    updates["review_count"] = detail.review_count
                if place.price_per_person_krw is None and detail.price_per_person_krw is not None:
                    updates["price_per_person_krw"] = detail.price_per_person_krw
                if place.representative_menu is None and detail.representative_menu:
                    updates["representative_menu"] = detail.representative_menu
                if place.representative_review is None and detail.representative_review:
                    updates["representative_review"] = detail.representative_review
                if place.opened_at is None and detail.opened_at is not None:
                    updates["opened_at"] = detail.opened_at
                if detail.price_range_min_krw is not None:
                    updates["price_range_min_krw"] = detail.price_range_min_krw
                if detail.price_range_max_krw is not None:
                    updates["price_range_max_krw"] = detail.price_range_max_krw

            if naver_id and place.naver_place_id is None:
                updates["naver_place_id"] = naver_id

        merged = place.model_copy(update=updates) if updates else place
        return self._apply_display_defaults(merged)

    def _resolve_naver_place_id(self, place: Place) -> str | None:
        """URL·기존 ID·검색 API·지도 검색으로 Naver Place ID를 찾습니다."""
        existing = place.naver_place_id or extract_naver_place_id(str(place.url or ""))
        if existing and str(existing).isdigit():
            return str(existing)

        if self._naver_provider:
            resolved = self._naver_provider.resolve_place_id(place.name, place.lat, place.lng)
            if resolved:
                return resolved

        if self._enable_crawl:
            resolved = self._crawler.resolve_place_id_by_map_search(place.name)
            if resolved:
                return resolved

        return None

    @staticmethod
    def _apply_display_defaults(place: Place) -> Place:
        """메뉴·가격 범위가 비어 있지 않도록 기본값을 채웁니다."""
        updates: dict = {}
        if not place.representative_menu:
            updates["representative_menu"] = default_menu(place)
        mid, lo, hi = resolve_price_fields(place.model_copy(update=updates))
        if place.price_per_person_krw is None:
            updates["price_per_person_krw"] = mid
        if place.price_range_min_krw is None:
            updates["price_range_min_krw"] = lo
        if place.price_range_max_krw is None:
            updates["price_range_max_krw"] = hi
        return place.model_copy(update=updates) if updates else place

    def merge_duplicates(self, places: list[Place]) -> list[Place]:
        """
        이름·좌표 기준 중복 병합.

        동일 장소가 Kakao/Naver 양쪽에서 오면 필드가 채워진 쪽을 우선 병합합니다.
        """
        buckets: dict[str, Place] = {}

        for place in places:
            key = self._dedupe_key(place)
            if key not in buckets:
                buckets[key] = place
            else:
                buckets[key] = self._merge_two(buckets[key], place)

        return list(buckets.values())

    @staticmethod
    def _dedupe_key(place: Place) -> str:
        norm_name = re.sub(r"\s+", "", place.name.lower())
        lat_round = round(place.lat, 4)
        lng_round = round(place.lng, 4)
        return f"{norm_name}|{lat_round}|{lng_round}"

    @staticmethod
    def _merge_two(a: Place, b: Place) -> Place:
        """두 Place 중 비어 있지 않은 필드를 합칩니다."""
        data = a.model_dump()
        other = b.model_dump()
        for field, value in other.items():
            if data.get(field) is None and value is not None:
                data[field] = value
            if field == "rating" and other.get("rating_source") == "naver_crawl":
                data["rating"] = other["rating"]
                data["rating_source"] = "naver_crawl"
            if field == "naver_place_id" and other.get("naver_place_id"):
                if not data.get("naver_place_id") or not str(data["naver_place_id"]).isdigit():
                    data["naver_place_id"] = other["naver_place_id"]
        data["source"] = f"{a.source}+{b.source}" if a.source != b.source else a.source
        merged = Place(**data)
        return PlaceEnricher._apply_display_defaults(merged)
