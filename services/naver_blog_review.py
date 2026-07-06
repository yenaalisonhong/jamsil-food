"""Naver 블로그 검색으로 대표 리뷰 스니펫을 가져옵니다."""

from __future__ import annotations

import html
import re
import time

import httpx

from config.settings import Settings, get_settings
from utils.errors import ConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)

_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"


class NaverBlogReviewFetcher:
    """Naver Search Blog API 기반 리뷰 문장 추출."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        request_delay_sec: float = 1.0,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.naver_client_id or not self._settings.naver_client_secret:
            raise ConfigurationError("Naver API 키가 없습니다.")
        self._delay = request_delay_sec
        self._last_request_at = 0.0

    def fetch_review_snippet(self, place_name: str) -> str | None:
        for query in (f"잠실 {place_name} 맛집", f"잠실 {place_name}"):
            snippet = self._search_snippet(query)
            if snippet:
                return snippet
        return None

    def _search_snippet(self, query: str, *, retries: int = 3) -> str | None:
        headers = {
            "X-Naver-Client-Id": self._settings.naver_client_id,
            "X-Naver-Client-Secret": self._settings.naver_client_secret,
        }
        params = {
            "query": query,
            "display": 5,
            "sort": "sim",
        }
        for attempt in range(retries):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)

            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(_BLOG_URL, headers=headers, params=params)
                    self._last_request_at = time.monotonic()
                    if response.status_code == 429:
                        wait = self._delay * (2 ** attempt) + 2.0
                        logger.warning(
                            "Naver Blog rate limit (429), %.1fs 후 재시도 (%d/%d)",
                            wait,
                            attempt + 1,
                            retries,
                        )
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPError as exc:
                logger.debug("블로그 리뷰 검색 실패 (%s): %s", query, exc)
                return None

            for item in data.get("items", []):
                description = html.unescape(
                    re.sub(r"<[^>]+>", "", item.get("description", ""))
                )
                description = re.sub(r"\s+", " ", description).strip()
                if len(description) >= 15:
                    return description[:200]
            return None
        return None
