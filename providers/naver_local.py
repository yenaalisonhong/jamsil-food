"""
Naver 지역 검색 API Provider.

공식 Search Local API로 장소 목록·링크·좌표를 수집합니다.
평점/가격/개업일은 PlaceEnricher(크롤링·수동 DB)에서 보강합니다.
문서: https://developers.naver.com/docs/serviceapi/search/local/local.md
"""

import html
import math
import re
import time
from typing import Any

import httpx

from config.settings import Settings, get_settings
from models.place import Place, PlaceCategory, PlaceType
from providers.base import PlaceProvider
from utils.coordinates import naver_map_to_wgs84
from utils.errors import ConfigurationError, PlaceProviderError
from utils.logger import get_logger
from utils.naver_urls import extract_naver_place_id

logger = get_logger(__name__)

_BASE_URL = "https://openapi.naver.com/v1/search/local.json"
_DISPLAY = 5
_MAX_START = 50
_REQUEST_DELAY_SEC = 0.35

_RESTAURANT_QUERIES = [
    "잠실역 맛집",
    "잠실 한식",
    "잠실 중식",
    "잠실 일식",
    "잠실 양식",
    "잠실 분식",
    "잠실 패스트푸드",
    "송파구 잠실 음식점",
    "올림픽로 음식점",
    "석촌호수 맛집",
    "롯데월드몰 맛집",
    "잠실새내 맛집",
]
_CAFE_QUERIES = [
    "잠실역 카페",
    "잠실 카페",
    "송파구 잠실 카페",
    "잠실 디저트",
    "석촌호수 카페",
    "롯데월드몰 카페",
    "잠실새내 카페",
]


class NaverLocalProvider(PlaceProvider):
    """Naver 지역 검색 API 기반 장소 조회."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.naver_client_id or not self._settings.naver_client_secret:
            raise ConfigurationError(
                "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 설정되지 않았습니다.",
            )
        self._last_request_at: float = 0.0

    @property
    def source_name(self) -> str:
        return "naver"

    def fetch_places(self, place_type: PlaceType) -> list[Place]:
        """여러 키워드·페이지로 지역 검색 후 중복 제거."""
        queries = _RESTAURANT_QUERIES if place_type == PlaceType.RESTAURANT else _CAFE_QUERIES
        seen_ids: set[str] = set()
        results: list[Place] = []

        for query in queries:
            for item in self._search_all_pages(query):
                place = self._parse_item(item, place_type)
                if place.id in seen_ids:
                    continue
                seen_ids.add(place.id)
                results.append(place)

        logger.info("Naver 지역 검색 %d건 (중복 제거 후)", len(results))
        return results

    def resolve_place_id(self, name: str, lat: float, lng: float) -> str | None:
        """상호명·좌표로 Naver Place 숫자 ID를 찾습니다."""
        queries = [f"잠실 {name}", name]
        best_id: str | None = None
        best_dist = float("inf")

        for query in queries:
            for item in self._search(query, start=1):
                candidate = self._parse_item(item, PlaceType.RESTAURANT)
                naver_id = candidate.naver_place_id
                if not naver_id or not naver_id.isdigit():
                    continue
                dist = self._haversine_m(lat, lng, candidate.lat, candidate.lng)
                if dist < best_dist:
                    best_dist = dist
                    best_id = naver_id

        if best_id and best_dist <= 500:
            return best_id
        return None

    def _search_all_pages(self, query: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for start in range(1, _MAX_START + 1, _DISPLAY):
            batch = self._search(query, start=start)
            if not batch:
                break
            items.extend(batch)
            if len(batch) < _DISPLAY:
                break
        return items

    def _search(self, query: str, start: int = 1) -> list[dict[str, Any]]:
        """단일 키워드 지역 검색."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _REQUEST_DELAY_SEC:
            time.sleep(_REQUEST_DELAY_SEC - elapsed)

        headers = {
            "X-Naver-Client-Id": self._settings.naver_client_id,
            "X-Naver-Client-Secret": self._settings.naver_client_secret,
        }
        params = {"query": query, "display": _DISPLAY, "start": start, "sort": "comment"}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(_BASE_URL, headers=headers, params=params)
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise PlaceProviderError(
                f"Naver Local API HTTP 오류: {exc.response.status_code}",
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise PlaceProviderError("Naver Local API 네트워크 오류", cause=exc) from exc

        return data.get("items", [])

    def _parse_item(self, item: dict[str, Any], place_type: PlaceType) -> Place:
        """Naver local item → Place."""
        try:
            raw_title = item.get("title", "")
            name = html.unescape(re.sub(r"<[^>]+>", "", raw_title))
            link = item.get("link", "")
            place_id = extract_naver_place_id(link)
            if not place_id:
                place_id = f"naver-{abs(hash(name + item.get('address', '')))}"

            mapx = item.get("mapx", "")
            mapy = item.get("mapy", "")
            lat, lng = naver_map_to_wgs84(mapx, mapy)

            category_raw = item.get("category", "")
            numeric_id = place_id if str(place_id).isdigit() else None
            return Place(
                id=f"naver:{place_id}",
                name=name,
                place_type=place_type,
                category=self._guess_category(category_raw, place_type),
                address=item.get("roadAddress") or item.get("address", ""),
                lat=lat,
                lng=lng,
                rating=None,
                rating_source=None,
                review_count=None,
                price_per_person_krw=None,
                phone=item.get("telephone") or None,
                url=link or None,
                source=self.source_name,
                naver_place_id=numeric_id,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise PlaceProviderError(f"Naver 응답 파싱 실패: {item}", cause=exc) from exc

    @staticmethod
    def _guess_category(category_name: str, place_type: PlaceType) -> PlaceCategory:
        if place_type == PlaceType.CAFE:
            return PlaceCategory.CAFE
        name = category_name.lower()
        if "한식" in name:
            return PlaceCategory.KOREAN
        if "중식" in name or "중국" in name:
            return PlaceCategory.CHINESE
        if "일식" in name or "일본" in name:
            return PlaceCategory.JAPANESE
        if "양식" in name:
            return PlaceCategory.WESTERN
        if "분식" in name:
            return PlaceCategory.BUNSIK
        if "패스트" in name:
            return PlaceCategory.FAST_FOOD
        if "디저트" in name or "베이커리" in name:
            return PlaceCategory.DESSERT
        return PlaceCategory.OTHER

    @staticmethod
    def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))
