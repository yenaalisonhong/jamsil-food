"""
신규 오픈 탐지 크롤러.

Naver 검색 API(블로그·뉴스)로 '잠실 신규오픈' 키워드 게시물을 수집하고,
지역 검색 API로 실제 장소와 매칭합니다.
"""

import html
import re
from datetime import date, datetime
from typing import Any

import httpx

from config.settings import Settings, get_settings
from models.place import Place, PlaceType
from providers.naver_local import NaverLocalProvider
from utils.errors import ConfigurationError, PlaceProviderError
from utils.logger import get_logger

logger = get_logger(__name__)

_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

_NEW_OPENING_QUERIES = [
    "잠실 신규오픈 맛집",
    "잠실 신규 오픈 카페",
    "송파구 잠실 새로오픈",
    "잠실역 신상 맛집",
]

# 블로그 제목에서 상호명 후보 추출 (따옴표·대괄호 안 텍스트)
_NAME_PATTERNS = [
    re.compile(r"['\"『「]([^'\"』」]{2,20})['\"』」]"),
    re.compile(r"\[([^\]]{2,20})\]"),
    re.compile(r"신규\s*오픈\s*[|:]\s*([^\s,|]{2,15})"),
]


class NewOpeningCrawler:
    """Naver 블로그/뉴스 검색 기반 신규 오픈 후보 수집."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.naver_client_id:
            raise ConfigurationError("신규 오픈 검색에 NAVER_CLIENT_ID가 필요합니다.")

    def fetch_candidates(self) -> list[Place]:
        """
        블로그·뉴스에서 상호명 후보를 추출하고 지역 검색으로 Place를 만듭니다.
        """
        names: set[str] = set()
        for query in _NEW_OPENING_QUERIES:
            names.update(self._search_titles(_BLOG_URL, query))
            names.update(self._search_titles(_NEWS_URL, query))

        logger.info("신규 오픈 상호명 후보 %d건", len(names))

        try:
            local_provider = NaverLocalProvider(self._settings)
        except ConfigurationError:
            return []

        places: list[Place] = []
        for name in sorted(names)[:12]:
            matched = self._match_place_by_name(local_provider, name)
            if matched:
                if matched.opened_at is None:
                    matched = matched.model_copy(
                        update={"opened_at": date.today(), "source": "naver_blog"},
                    )
                places.append(matched)

        return places

    def _search_titles(self, api_url: str, query: str) -> set[str]:
        headers = {
            "X-Naver-Client-Id": self._settings.naver_client_id,
            "X-Naver-Client-Secret": self._settings.naver_client_secret,
        }
        params = {"query": query, "display": 10, "sort": "date"}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(api_url, headers=headers, params=params)
                response.raise_for_status()
                items = response.json().get("items", [])
        except (httpx.HTTPError, PlaceProviderError) as exc:
            logger.warning("Naver 검색 실패 (%s): %s", query, exc)
            return set()

        names: set[str] = set()
        for item in items:
            title = html.unescape(re.sub(r"<[^>]+>", "", item.get("title", "")))
            for pattern in _NAME_PATTERNS:
                for match in pattern.finditer(title):
                    candidate = match.group(1).strip()
                    if len(candidate) >= 2:
                        names.add(candidate)
        return names

    def _match_place_by_name(
        self,
        provider: NaverLocalProvider,
        name: str,
    ) -> Place | None:
        """상호명으로 지역 검색해 첫 번째 일치 장소 반환."""
        headers = {
            "X-Naver-Client-Id": self._settings.naver_client_id,
            "X-Naver-Client-Secret": self._settings.naver_client_secret,
        }
        params = {"query": f"잠실 {name}", "display": 3, "sort": "random"}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    "https://openapi.naver.com/v1/search/local.json",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                items = response.json().get("items", [])
        except httpx.HTTPError:
            return None

        if not items:
            return None

        place_type = (
            PlaceType.CAFE if "카페" in name or "커피" in name else PlaceType.RESTAURANT
        )
        place = provider._parse_item(items[0], place_type)
        office_lat = self._settings.fraunhofer_office_lat
        office_lng = self._settings.fraunhofer_office_lng
        max_m = self._settings.max_walk_minutes * 80
        dist = provider._haversine_m(office_lat, office_lng, place.lat, place.lng)
        if dist > max_m:
            return None
        return place
