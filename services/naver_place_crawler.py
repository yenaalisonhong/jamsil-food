"""
Naver Place 페이지 크롤러.

평점(visitorRating), 리뷰 수, 메뉴 가격, 개업일 등을 HTML/임베디드 JSON에서 추출합니다.
API 키 없이 pcmap.place.naver.com 페이지를 파싱합니다.

주의: 요청 간격을 두어 rate limit(429)을 피합니다.
"""

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
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

_RATING_PATTERN = re.compile(r'"visitorRating":([\d.]+)')
_REVIEW_COUNT_PATTERN = re.compile(r'"visitorReviewCount":(\d+)')
_OPENING_PATTERN = re.compile(r'"openingDate":"(\d{4}-\d{2}-\d{2})"')
_NEW_OPENING_PATTERN = re.compile(r'"newOpening":(true|false)')
_MENU_PRICE_PATTERN = re.compile(r'"price":(\d+)')
_MENU_ITEM_PATTERN = re.compile(
    r'"name":"([^"]{2,40})"[^}]{0,120}?"price":(\d+)',
)
_REVIEW_TEXT_PATTERN = re.compile(
    r'"review":"((?:\\.|[^"\\]){10,300})"',
)
_PLACE_ID_IN_HTML = re.compile(r"/(?:restaurant|cafe)/(\d+)(?:/|$|\?)")
_APOLLO_STATE_PATTERN = re.compile(
    r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});',
    re.DOTALL,
)


@dataclass
class NaverPlaceDetail:
    """크롤링으로 추출한 Naver Place 상세 정보."""

    rating: float | None = None
    review_count: int | None = None
    price_per_person_krw: int | None = None
    price_range_min_krw: int | None = None
    price_range_max_krw: int | None = None
    representative_menu: str | None = None
    representative_review: str | None = None
    opened_at: date | None = None
    is_new_opening: bool = False
    menu_prices: list[int] = field(default_factory=list)


class NaverPlaceCrawler:
    """Naver Place 상세·메뉴·리뷰 페이지 크롤러."""

    def __init__(
        self,
        store: ManualDataStore | None = None,
        request_delay_sec: float = 1.0,
    ) -> None:
        self._store = store or ManualDataStore()
        self._delay = request_delay_sec
        self._last_request_at: float = 0.0

    def resolve_place_id_by_map_search(self, name: str) -> str | None:
        """Naver 지도 검색 페이지에서 place ID를 추출합니다."""
        query = urllib.parse.quote(name)
        url = f"https://map.naver.com/p/search/{query}"
        try:
            html = self._get_page(url)
        except PlaceProviderError:
            return None

        ids = _PLACE_ID_IN_HTML.findall(html)
        for place_id in ids:
            if place_id.isdigit():
                return place_id
        return None

    def fetch_detail(
        self,
        naver_place_id: str,
        place_type: PlaceType = PlaceType.RESTAURANT,
    ) -> NaverPlaceDetail:
        """
        place ID로 상세 정보를 수집합니다.

        캐시 → 홈 페이지 → 메뉴 페이지 → 리뷰 페이지 순으로 시도합니다.
        """
        if not naver_place_id.isdigit():
            return NaverPlaceDetail()

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

            menu_html = self._get_page(build_place_menu_url(naver_place_id, category))
            menus = self._extract_menu_items(menu_html)
            if menus:
                detail.representative_menu = menus[0][0]
                prices = [price for _, price in menus]
                detail.menu_prices = prices
                detail.price_per_person_krw = self._estimate_price_from_prices(prices)
                lunch = [p for p in prices if 4_000 <= p <= 35_000]
                if lunch:
                    detail.price_range_min_krw = min(lunch)
                    detail.price_range_max_krw = max(lunch)

            if detail.representative_review is None:
                review_url = (
                    f"https://pcmap.place.naver.com/{category}/{naver_place_id}/review/visitor"
                )
                review_html = self._get_page(review_url)
                detail.representative_review = self._extract_review_text(review_html)
                if detail.rating is None:
                    detail.rating = self._extract_rating(review_html)

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
    def _extract_menu_items(html: str) -> list[tuple[str, int]]:
        items: list[tuple[str, int]] = []
        seen: set[str] = set()
        for name, price_str in _MENU_ITEM_PATTERN.findall(html):
            name = json.loads(f'"{name}"') if "\\" in name else name
            if name in seen:
                continue
            seen.add(name)
            items.append((name, int(price_str)))
        return items

    @staticmethod
    def _extract_review_text(html: str) -> str | None:
        match = _REVIEW_TEXT_PATTERN.search(html)
        if not match:
            return None
        raw = match.group(1)
        try:
            text = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            text = raw.replace("\\n", " ").strip()
        text = re.sub(r"\s+", " ", text).strip()
        return text[:200] if text else None

    @staticmethod
    def _estimate_price_from_menu(html: str) -> int | None:
        prices = [int(p) for p in _MENU_PRICE_PATTERN.findall(html)]
        return NaverPlaceCrawler._estimate_price_from_prices(prices)

    @staticmethod
    def _estimate_price_from_prices(prices: list[int]) -> int | None:
        lunch_range = [p for p in prices if 5_000 <= p <= 30_000]
        if not lunch_range:
            lunch_range = [p for p in prices if 4_000 <= p <= 35_000]
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
            "price_range_min_krw": detail.price_range_min_krw,
            "price_range_max_krw": detail.price_range_max_krw,
            "representative_menu": detail.representative_menu,
            "representative_review": detail.representative_review,
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
            price_range_min_krw=data.get("price_range_min_krw"),
            price_range_max_krw=data.get("price_range_max_krw"),
            representative_menu=data.get("representative_menu"),
            representative_review=data.get("representative_review"),
            opened_at=date.fromisoformat(opened) if opened else None,
            is_new_opening=bool(data.get("is_new_opening")),
        )
