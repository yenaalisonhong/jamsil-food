"""
장소 데이터 보강(Enrichment) 서비스.

Kakao/Naver Provider 수집 결과에 대해:
  1. 수동 DB (가격·개업일)
  2. Naver Place 크롤링 (평점·메뉴가·개업일)
  3. 중복 장소 병합
을 적용합니다.
"""

import re
from typing import Iterable

from models.place import Place
from services.manual_data_store import ManualDataStore
from services.naver_place_crawler import NaverPlaceCrawler
from utils.logger import get_logger
from utils.naver_urls import extract_naver_place_id

logger = get_logger(__name__)


class PlaceEnricher:
    """Place 목록 보강 및 병합."""

    def __init__(
        self,
        store: ManualDataStore | None = None,
        crawler: NaverPlaceCrawler | None = None,
        *,
        enable_crawl: bool = True,
    ) -> None:
        self._store = store or ManualDataStore()
        self._crawler = crawler or NaverPlaceCrawler(self._store)
        self._enable_crawl = enable_crawl

    def enrich_all(self, places: list[Place]) -> list[Place]:
        """전체 목록 보강 후 중복 병합."""
        enriched = [self.enrich_one(p) for p in places]
        return self.merge_duplicates(enriched)

    def enrich_one(self, place: Place) -> Place:
        """단일 Place에 평점·가격·개업일을 채웁니다."""
        updates: dict = {}

        naver_id = place.naver_place_id or extract_naver_place_id(str(place.url or ""))

        # 1) 수동 DB
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

        # 2) Naver Place 크롤링 (naver_place_id 있을 때)
        if naver_id and self._enable_crawl:
            if place.rating is None or place.price_per_person_krw is None or place.opened_at is None:
                detail = self._crawler.fetch_detail(naver_id, place.place_type)
                if place.rating is None and detail.rating is not None:
                    updates["rating"] = detail.rating
                    updates["rating_source"] = "naver_crawl"
                if place.review_count is None and detail.review_count is not None:
                    updates["review_count"] = detail.review_count
                if place.price_per_person_krw is None and detail.price_per_person_krw is not None:
                    updates["price_per_person_krw"] = detail.price_per_person_krw
                if place.opened_at is None and detail.opened_at is not None:
                    updates["opened_at"] = detail.opened_at
                if naver_id and place.naver_place_id is None:
                    updates["naver_place_id"] = naver_id

        if updates:
            return place.model_copy(update=updates)
        return place

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
            # 평점은 naver_crawl 우선
            if field == "rating" and other.get("rating_source") == "naver_crawl":
                data["rating"] = other["rating"]
                data["rating_source"] = "naver_crawl"
        data["source"] = f"{a.source}+{b.source}" if a.source != b.source else a.source
        return Place(**data)
