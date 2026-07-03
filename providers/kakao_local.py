"""
Kakao Local API Provider.

키워드 검색 API로 주변 식당/카페를 조회합니다.
문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide
"""

from datetime import date
from typing import Any

import httpx

from config.settings import Settings, get_settings
from models.place import Place, PlaceCategory, PlaceType
from providers.base import PlaceProvider
from utils.errors import ConfigurationError, PlaceProviderError
from utils.logger import get_logger

logger = get_logger(__name__)

# Kakao category_group_code: FD6=음식점, CE7=카페
_CATEGORY_MAP = {
    PlaceType.RESTAURANT: "FD6",
    PlaceType.CAFE: "CE7",
}

_SEARCH_KEYWORDS = {
    PlaceType.RESTAURANT: "음식점",
    PlaceType.CAFE: "카페",
}


class KakaoLocalProvider(PlaceProvider):
    """Kakao Local API 기반 장소 조회."""

    BASE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.kakao_rest_api_key:
            raise ConfigurationError(
                "KAKAO_REST_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.",
            )

    @property
    def source_name(self) -> str:
        return "kakao"

    def fetch_places(self, place_type: PlaceType) -> list[Place]:
        """Kakao 키워드 검색으로 주변 장소를 조회합니다."""
        headers = {
            "Authorization": f"KakaoAK {self._settings.kakao_rest_api_key}",
        }
        params = {
            "query": _SEARCH_KEYWORDS[place_type],
            "x": self._settings.fraunhofer_office_lng,
            "y": self._settings.fraunhofer_office_lat,
            "radius": int(self._settings.max_walk_radius_meters),
            "category_group_code": _CATEGORY_MAP[place_type],
            "size": 15,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.BASE_URL, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise PlaceProviderError(
                f"Kakao API HTTP 오류: {exc.response.status_code}",
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise PlaceProviderError(
                "Kakao API 네트워크 오류",
                cause=exc,
            ) from exc

        documents = data.get("documents", [])
        return [self._parse_document(doc, place_type) for doc in documents]

    def _parse_document(self, doc: dict[str, Any], place_type: PlaceType) -> Place:
        """Kakao API 응답 document → Place 모델 변환."""
        try:
            return Place(
                id=doc["id"],
                name=doc["place_name"],
                place_type=place_type,
                category=self._guess_category(doc.get("category_name", "")),
                address=doc.get("road_address_name") or doc.get("address_name", ""),
                lat=float(doc["y"]),
                lng=float(doc["x"]),
                distance_meters=float(doc.get("distance", 0)),
                rating=None,  # Kakao Local API는 평점 미제공 → Naver 등 보완 필요
                rating_source=None,
                price_per_person_krw=None,
                phone=doc.get("phone") or None,
                url=doc.get("place_url") or None,
                source=self.source_name,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise PlaceProviderError(
                f"Kakao 응답 파싱 실패: {doc}",
                cause=exc,
            ) from exc

    @staticmethod
    def _guess_category(category_name: str) -> PlaceCategory:
        """Kakao category_name 문자열에서 PlaceCategory 추정."""
        name = category_name.lower()
        if "카페" in name or "coffee" in name:
            return PlaceCategory.CAFE
        if "한식" in name:
            return PlaceCategory.KOREAN
        if "중식" in name or "중국" in name:
            return PlaceCategory.CHINESE
        if "일식" in name or "일본" in name:
            return PlaceCategory.JAPANESE
        if "양식" in name or "이탈" in name:
            return PlaceCategory.WESTERN
        if "패스트" in name or "버거" in name:
            return PlaceCategory.FAST_FOOD
        return PlaceCategory.OTHER
