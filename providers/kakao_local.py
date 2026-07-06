"""
Kakao Local API Provider.

키워드·카테고리 검색 API로 주변 식당/카페를 조회합니다.
문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide
"""

from datetime import date
from typing import Any

import httpx

from config.settings import Settings, get_settings
from models.place import Place, PlaceCategory, PlaceType
from services.category_classifier import guess_category
from providers.base import PlaceProvider
from providers.jamsil_commercial import kakao_anchors, kakao_keywords
from utils.errors import ConfigurationError, PlaceProviderError
from utils.logger import get_logger

logger = get_logger(__name__)

# Kakao category_group_code: FD6=음식점, CE7=카페
_CATEGORY_MAP = {
    PlaceType.RESTAURANT: "FD6",
    PlaceType.CAFE: "CE7",
}

_SEARCH_KEYWORDS = {
    PlaceType.RESTAURANT: [
        "음식점",
        "맛집",
        "잠실 맛집",
        "잠실역 맛집",
        "송파구 음식점",
        "신천동 맛집",
        "올림픽로35가길 맛집",
        "잠실 한식",
        "잠실 중식",
        "잠실 일식",
        "잠실 양식",
        "잠실 분식",
        "잠실 치킨",
        "잠실 피자",
        "장미상가 맛집",
        "장미상가 음식점",
        "송리단길 맛집",
        "백제고분로 맛집",
        "신천동 맛집",
        "올림픽로35가길 맛집",
        "석촌호수 맛집",
        "롯데월드몰 맛집",
        "잠실새내 맛집",
        "방이동 맛집",
    ],
    PlaceType.CAFE: [
        "카페",
        "커피",
        "잠실 카페",
        "잠실역 카페",
        "송파구 카페",
        "신천동 카페",
        "올림픽로35가길 카페",
        "잠실 디저트",
        "잠실 베이커리",
        "장미상가 카페",
        "송리단길 카페",
        "백제고분로 카페",
        "신천동 카페",
        "올림픽로35가길 카페",
        "석촌호수 카페",
        "롯데월드몰 카페",
        "잠실새내 카페",
        "방이동 카페",
    ],
}

# 상권별 보조 검색 중심 — API 결과 상한·거리순 편향으로 밀집 상가가 누락되는 것을 보완
_SEARCH_ANCHORS: list[tuple[str, float, float]] = [
    ("사무실", 37.51692, 127.10282),
    ("송리단길", 37.5102, 127.1088),
    ("잠실역", 37.5135, 127.0998),
    ("석촌호수", 37.5092, 127.1068),
    ("롯데월드몰", 37.5113, 127.0986),
    ("잠실새내", 37.5117, 127.0864),
    ("신천동", 37.5165, 127.1035),
    ("방이동", 37.5148, 127.1105),
    *kakao_anchors(),
]

_ANCHOR_KEYWORDS = {
    PlaceType.RESTAURANT: ("맛집", "음식점", "한식"),
    PlaceType.CAFE: ("카페", "디저트", "베이커리"),
}

_MAX_PAGE = 45
_PAGE_SIZE = 15


class KakaoLocalProvider(PlaceProvider):
    """Kakao Local API 기반 장소 조회."""

    KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
    CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"

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
        """키워드·카테고리 검색으로 반경 내 장소를 최대한 수집합니다."""
        seen_ids: set[str] = set()
        results: list[Place] = []

        for query in _SEARCH_KEYWORDS[place_type] + kakao_keywords(place_type):
            for doc in self._search_keyword(query, place_type):
                place = self._parse_document(doc, place_type)
                if place.id in seen_ids:
                    continue
                seen_ids.add(place.id)
                results.append(place)

        for doc in self._search_category(place_type):
            place = self._parse_document(doc, place_type)
            if place.id in seen_ids:
                continue
            seen_ids.add(place.id)
            results.append(place)

        for anchor_name, lat, lng in _SEARCH_ANCHORS:
            anchor_radius = self._settings.max_walk_radius_meters
            for doc in self._search_category(
                place_type,
                lat=lat,
                lng=lng,
                radius_m=anchor_radius,
            ):
                place = self._parse_document(doc, place_type)
                if place.id in seen_ids:
                    continue
                seen_ids.add(place.id)
                results.append(place)

            for keyword in _ANCHOR_KEYWORDS[place_type]:
                for doc in self._search_keyword(
                    keyword,
                    place_type,
                    lat=lat,
                    lng=lng,
                    radius_m=anchor_radius,
                ):
                    place = self._parse_document(doc, place_type)
                    if place.id in seen_ids:
                        continue
                    seen_ids.add(place.id)
                    results.append(place)

            logger.debug("Kakao 앵커 '%s' 수집 후 누적 %d건", anchor_name, len(results))

        logger.info("Kakao 수집 %d건 (중복 제거 후)", len(results))
        return results

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"KakaoAK {self._settings.kakao_rest_api_key}"}

    def _base_params(
        self,
        *,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: float | None = None,
    ) -> dict[str, Any]:
        return {
            "x": lng if lng is not None else self._settings.fraunhofer_office_lng,
            "y": lat if lat is not None else self._settings.fraunhofer_office_lat,
            "radius": int(radius_m if radius_m is not None else self._settings.max_walk_radius_meters),
            "size": _PAGE_SIZE,
        }

    def _search_keyword(
        self,
        query: str,
        place_type: PlaceType,
        *,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: float | None = None,
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for page in range(1, _MAX_PAGE + 1):
            params = {
                **self._base_params(lat=lat, lng=lng, radius_m=radius_m),
                "query": query,
                "category_group_code": _CATEGORY_MAP[place_type],
                "page": page,
            }
            batch, is_end = self._request(self.KEYWORD_URL, params)
            documents.extend(batch)
            if is_end or not batch:
                break
        return documents

    def _search_category(
        self,
        place_type: PlaceType,
        *,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: float | None = None,
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for page in range(1, _MAX_PAGE + 1):
            params = {
                **self._base_params(lat=lat, lng=lng, radius_m=radius_m),
                "category_group_code": _CATEGORY_MAP[place_type],
                "page": page,
            }
            batch, is_end = self._request(self.CATEGORY_URL, params)
            documents.extend(batch)
            if is_end or not batch:
                break
        return documents

    def _request(self, url: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=self._headers(), params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise PlaceProviderError(
                f"Kakao API HTTP 오류: {exc.response.status_code}",
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise PlaceProviderError("Kakao API 네트워크 오류", cause=exc) from exc

        meta = data.get("meta", {})
        return data.get("documents", []), bool(meta.get("is_end", True))

    def _parse_document(self, doc: dict[str, Any], place_type: PlaceType) -> Place:
        """Kakao API 응답 document → Place 모델 변환."""
        try:
            return Place(
                id=doc["id"],
                name=doc["place_name"],
                place_type=place_type,
                category=guess_category(
                    doc.get("category_name", ""),
                    place_type,
                    name=doc.get("place_name", ""),
                ),
                address=doc.get("road_address_name") or doc.get("address_name", ""),
                lat=float(doc["y"]),
                lng=float(doc["x"]),
                distance_meters=float(doc.get("distance", 0)),
                rating=None,
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

