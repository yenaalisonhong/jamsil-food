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
from models.place import Place, PlaceCategory, PlaceType
from providers.naver_local import NaverLocalProvider
from services.naver_blog_review import NaverBlogReviewFetcher
from services.manual_data_store import ManualDataStore
from services.naver_place_crawler import NaverPlaceCrawler
from services.category_classifier import refine_category, refine_place_type
from services.place_defaults import is_generic_menu, resolve_price_fields
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
        self._blog_fetcher: NaverBlogReviewFetcher | None = None
        if enable_crawl:
            try:
                self._blog_fetcher = NaverBlogReviewFetcher(get_settings())
            except ConfigurationError:
                self._blog_fetcher = None

    def enrich_all(self, places: list[Place]) -> list[Place]:
        """전체 목록 보강 후 중복 병합."""
        enriched: list[Place] = []
        for place in places:
            try:
                enriched.append(self.enrich_one(place))
            except Exception as exc:
                logger.warning("장소 보강 실패 (%s): %s", place.name, exc)
                enriched.append(place)
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
            needs_menu = is_generic_menu(place.representative_menu)
            needs_crawl = (
                place.rating is None
                or place.price_per_person_krw is None
                or needs_menu
                or place.representative_review is None
                or place.opened_at is None
            )
            if needs_crawl:
                light_crawl = (
                    place.source in {"naver_trending", "naver_blog"}
                    and place.opened_at is not None
                    and not needs_menu
                )
                detail = self._crawler.fetch_detail(
                    naver_id,
                    place.place_type,
                    light=light_crawl,
                )
                if place.rating is None and detail.rating is not None and detail.rating > 0:
                    updates["rating"] = detail.rating
                    updates["rating_source"] = "naver_crawl"
                if place.review_count is None and detail.review_count is not None:
                    updates["review_count"] = detail.review_count
                if place.price_per_person_krw is None and detail.price_per_person_krw is not None:
                    updates["price_per_person_krw"] = detail.price_per_person_krw
                if needs_menu and detail.representative_menu:
                    updates["representative_menu"] = detail.representative_menu
                if place.representative_review is None and detail.representative_review:
                    updates["representative_review"] = detail.representative_review
                if not place.representative_reviews and detail.representative_reviews:
                    updates["representative_reviews"] = detail.representative_reviews
                if place.opened_at is None and detail.opened_at is not None:
                    updates["opened_at"] = detail.opened_at
                elif (
                    place.opened_at is not None
                    and detail.opened_at is not None
                    and detail.is_new_opening
                    and detail.opened_at < place.opened_at
                ):
                    updates["opened_at"] = detail.opened_at
                if detail.price_range_min_krw is not None:
                    updates["price_range_min_krw"] = detail.price_range_min_krw
                if detail.price_range_max_krw is not None:
                    updates["price_range_max_krw"] = detail.price_range_max_krw

            if naver_id and place.naver_place_id is None:
                updates["naver_place_id"] = naver_id

        merged = place.model_copy(update=updates) if updates else place

        if naver_id:
            cached = self._store.get_cached_detail(naver_id) or {}
            cached_menu = cached.get("representative_menu")
            if (
                is_generic_menu(merged.representative_menu)
                and cached_menu
                and not is_generic_menu(cached_menu)
            ):
                merged = merged.model_copy(update={"representative_menu": cached_menu})

        refined_type = refine_place_type(merged)
        if refined_type != merged.place_type:
            merged = merged.model_copy(update={"place_type": refined_type})

        refined = refine_category(merged)
        if refined != merged.category:
            merged = merged.model_copy(update={"category": refined})

        if (
            merged.representative_review is None
            and merged.rating is None
            and self._blog_fetcher
        ):
            blog_review = self._blog_fetcher.fetch_review_snippet(merged.name)
            if blog_review:
                merged = merged.model_copy(update={"representative_review": blog_review})

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
            resolved = self._crawler.resolve_place_id_by_map_search(
                place.name,
                place.lat,
                place.lng,
                place.place_type,
            )
            if resolved:
                return resolved

        return None

    @staticmethod
    def _apply_display_defaults(place: Place) -> Place:
        """메뉴·가격 범위가 비어 있지 않도록 기본값을 채웁니다."""
        updates: dict = {}
        if is_generic_menu(place.representative_menu):
            updates["representative_menu"] = None
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
            if field == "category":
                other_cat = other.get("category")
                if (
                    other_cat
                    and other_cat != PlaceCategory.OTHER.value
                    and data.get("category") in (None, PlaceCategory.OTHER.value)
                ):
                    data["category"] = other_cat
            if field == "place_type":
                other_type = other.get("place_type")
                if other_type == PlaceType.CAFE.value and data.get("place_type") != PlaceType.CAFE.value:
                    data["place_type"] = other_type
            if field == "naver_place_id" and other.get("naver_place_id"):
                if not data.get("naver_place_id") or not str(data["naver_place_id"]).isdigit():
                    data["naver_place_id"] = other["naver_place_id"]
        data["source"] = f"{a.source}+{b.source}" if a.source != b.source else a.source
        merged = Place(**data)
        return PlaceEnricher._apply_display_defaults(merged)
