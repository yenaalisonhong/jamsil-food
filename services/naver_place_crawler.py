"""
Naver Place 페이지 크롤러.

평점(visitorRating), 리뷰 수, 메뉴 가격, 개업일 등을 HTML/임베디드 JSON에서 추출합니다.
API 키 없이 pcmap.place.naver.com 페이지를 파싱합니다.

주의: 요청 간격을 두어 rate limit(429)을 피합니다.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from models.place import PlaceType
from services.manual_data_store import ManualDataStore
from utils.errors import PlaceProviderError
from utils.logger import get_logger
from utils.naver_urls import build_place_home_url, build_place_menu_url

logger = get_logger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://map.naver.com/",
}

# HTML/JSON 내 패턴
_RATING_PATTERN = re.compile(r'"visitorRating":([\d.]+)')
_REVIEW_COUNT_PATTERN = re.compile(r'"visitorReviewCount":(\d+)')
_OPENING_PATTERN = re.compile(r'"openingDate":"(\d{4}-\d{2}-\d{2})"')
_NEW_OPENING_PATTERN = re.compile(r'"newOpening":(true|false)')
_MENU_PRICE_PATTERN = re.compile(r'"price":(\d+)')


@dataclass
class NaverPlaceDetail:
    """크롤링으로 추출한 Naver Place 상세 정보."""

    rating: float | None = None
    review_count: int | None = None
    price_per_person_krw: int | None = None
    opened_at: date | None = None
    is_new_opening: bool = False


class NaverPlaceCrawler:
    """Naver Place 상세·메뉴 페이지 크롤러."""

    def __init__(
        self,
        store: ManualDataStore | None = None,
        request_delay_sec: float = 1.5,
    ) -> None:
        self._store = store or ManualDataStore()
        self._delay = request_delay_sec
        self._last_request_at: float = 0.0

    def fetch_detail(
        self,
        naver_place_id: str,
        place_type: PlaceType = PlaceType.RESTAURANT,
    ) -> NaverPlaceDetail:
        """
        place ID로 상세 정보를 수집합니다.

        캐시 → 홈 페이지 → 메뉴 페이지 순으로 시도합니다.
        """
        cached = self._store.get_cached_detail(naver_place_id)
        if cached:
            return self._detail_from_dict(cached)

        detail = NaverPlaceDetail()
        category = "cafe" if place_type == PlaceType.CAFE else "restaurant"

        try:
            home_html = self._get_page(build_place_home_url(naver_place_id, category))
            detail.rating = self._extract_rating(home_html)
            detail.review_count = self._extract_review_count(home_html)
            detail.opened_at = self._extract_opening_date(home_html)
            detail.is_new_opening = self._extract_new_opening_flag(home_html)

            if place_type == PlaceType.RESTAURANT and detail.price_per_person_krw is None:
                menu_html = self._get_page(build_place_menu_url(naver_place_id, category))
                detail.price_per_person_krw = self._estimate_price_from_menu(menu_html)

            self._store.set_cached_detail(naver_place_id, self._detail_to_dict(detail))
        except PlaceProviderError as exc:
            logger.warning("Naver Place 크롤링 실패 (id=%s): %s", naver_place_id, exc)

        return detail

    def _get_page(self, url: str) -> str:
        """Rate limit을 지키며 HTTP GET."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                response = client.get(url, headers=_BROWSER_HEADERS)
                self._last_request_at = time.monotonic()

                if response.status_code == 429:
                    raise PlaceProviderError("Naver rate limit (429)")
                if response.status_code >= 400:
                    raise PlaceProviderError(f"HTTP {response.status_code}")

                return response.text
        except httpx.RequestError as exc:
            raise PlaceProviderError("Naver Place 네트워크 오류", cause=exc) from exc

    @staticmethod
    def _extract_rating(html: str) -> float | None:
        match = _RATING_PATTERN.search(html)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_review_count(html: str) -> int | None:
        match = _REVIEW_COUNT_PATTERN.search(html)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_opening_date(html: str) -> date | None:
        match = _OPENING_PATTERN.search(html)
        if match:
            return date.fromisoformat(match.group(1))
        return None

    @staticmethod
    def _extract_new_opening_flag(html: str) -> bool:
        match = _NEW_OPENING_PATTERN.search(html)
        return match.group(1) == "true" if match else False

    @staticmethod
    def _estimate_price_from_menu(html: str) -> int | None:
        """
        메뉴 페이지에서 가격 목록을 추출해 중앙값을 인당 가격으로 추정.

        일식·코스 등 고가 메뉴가 섞일 수 있어 1만~3만 원 구간만 사용합니다.
        """
        prices = [int(p) for p in _MENU_PRICE_PATTERN.findall(html)]
        lunch_range = [p for p in prices if 5_000 <= p <= 30_000]
        if not lunch_range:
            return None
        lunch_range.sort()
        mid = len(lunch_range) // 2
        return lunch_range[mid]

    @staticmethod
    def _detail_to_dict(detail: NaverPlaceDetail) -> dict[str, Any]:
        return {
            "rating": detail.rating,
            "review_count": detail.review_count,
            "price_per_person_krw": detail.price_per_person_krw,
            "opened_at": detail.opened_at.isoformat() if detail.opened_at else None,
            "is_new_opening": detail.is_new_opening,
        }

    @staticmethod
    def _detail_from_dict(data: dict[str, Any]) -> NaverPlaceDetail:
        opened = data.get("opened_at")
        return NaverPlaceDetail(
            rating=data.get("rating"),
            review_count=data.get("review_count"),
            price_per_person_krw=data.get("price_per_person_krw"),
            opened_at=date.fromisoformat(opened) if opened else None,
            is_new_opening=bool(data.get("is_new_opening")),
        )
