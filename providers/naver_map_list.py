"""
Naver Place 목록 페이지 크롤링 Provider.

지역 검색 API보다 더 많은 주변 맛집·카페를 수집합니다.
좌표 기준 목록 페이지를 파싱하며, 요청 간격을 두어 rate limit을 피합니다.
"""

import math
import urllib.parse

from config.settings import Settings, get_settings
from models.place import Place, PlaceType
from providers.base import PlaceProvider
from providers.jamsil_commercial import map_searches
from services.category_classifier import guess_category, is_food_place
from services.naver_place_crawler import NaverListPlaceHit, NaverPlaceCrawler
from utils.logger import get_logger

logger = get_logger(__name__)

# 상권 일반 검색 (상가 앵커는 jamsil_commercial에서 생성)
_BASE_RESTAURANT_SEARCHES: list[tuple[str, float, float]] = [
    ("맛집", 37.51692, 127.10282),
    ("음식점", 37.51692, 127.10282),
    ("한식", 37.51692, 127.10282),
    ("중식", 37.51692, 127.10282),
    ("일식", 37.51692, 127.10282),
    ("양식", 37.51692, 127.10282),
    ("분식", 37.51692, 127.10282),
    ("신천동 맛집", 37.51692, 127.10282),
    ("올림픽로35가길 맛집", 37.51692, 127.10282),
    ("잠실역 맛집", 37.5135, 127.0998),
    ("잠실새내 맛집", 37.5117, 127.0864),
    ("송리단길 맛집", 37.5102, 127.1088),
    ("석촌호수 맛집", 37.5092, 127.1068),
    ("롯데월드몰 맛집", 37.5113, 127.0986),
    ("백제고분로 맛집", 37.5125, 127.1055),
    ("방이동 맛집", 37.5148, 127.1105),
    ("치킨", 37.51692, 127.10282),
    ("피자", 37.51692, 127.10282),
    ("패스트푸드", 37.5135, 127.0998),
    ("현대백화점 잠실점 맛집", 37.5135, 127.0998),
]

_BASE_CAFE_SEARCHES: list[tuple[str, float, float]] = [
    ("카페", 37.51692, 127.10282),
    ("커피", 37.51692, 127.10282),
    ("디저트", 37.51692, 127.10282),
    ("베이커리", 37.51692, 127.10282),
    ("브런치", 37.51692, 127.10282),
    ("신천동 카페", 37.51692, 127.10282),
    ("올림픽로35가길 카페", 37.51692, 127.10282),
    ("잠실역 카페", 37.5135, 127.0998),
    ("잠실새내 카페", 37.5117, 127.0864),
    ("송리단길 카페", 37.5102, 127.1088),
    ("석촌호수 카페", 37.5092, 127.1068),
    ("롯데월드몰 카페", 37.5113, 127.0986),
    ("백제고분로 카페", 37.5125, 127.1055),
    ("방이동 카페", 37.5148, 127.1105),
    ("스타벅스 잠실", 37.5135, 127.0998),
    ("비엔나커피센트럴", 37.51345, 127.10015),
    ("잠실역 근처 카페", 37.51345, 127.10015),
]


def _merge_searches(
    base: list[tuple[str, float, float]],
    place_type: PlaceType,
) -> list[tuple[str, float, float]]:
    """상가 전용 검색을 앞에 두고 일반 상권 검색과 합칩니다."""
    seen: set[tuple[str, float, float]] = set()
    merged: list[tuple[str, float, float]] = []
    for batch in (map_searches(place_type), base):
        for query, lat, lng in batch:
            key = (query, round(lat, 5), round(lng, 5))
            if key in seen:
                continue
            seen.add(key)
            merged.append((query, lat, lng))
    return merged


class NaverMapListProvider(PlaceProvider):
    """Naver Place 목록 페이지 기반 장소 조회."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._crawler = NaverPlaceCrawler(
            request_delay_sec=max(2.0, self._settings.crawl_request_delay_sec),
        )
        self._office = (
            self._settings.fraunhofer_office_lat,
            self._settings.fraunhofer_office_lng,
        )
        self._max_dist_m = self._settings.max_walk_radius_meters * 1.15

    @property
    def source_name(self) -> str:
        return "naver_map"

    def fetch_places(self, place_type: PlaceType) -> list[Place]:
        """여러 키워드·상권으로 목록 검색 후 중복 제거."""
        searches = _merge_searches(
            _BASE_RESTAURANT_SEARCHES
            if place_type == PlaceType.RESTAURANT
            else _BASE_CAFE_SEARCHES,
            place_type,
        )
        seen_ids: set[str] = set()
        results: list[Place] = []

        for query, lat, lng in searches:
            items = self._crawler.search_list_places(
                query,
                place_type,
                lng=lng,
                lat=lat,
            )
            added = 0
            for hit in items:
                if hit.place_id in seen_ids:
                    continue
                if not is_food_place(
                    name=hit.name,
                    category_text=hit.category_text,
                    business_category=hit.business_category,
                ):
                    continue
                dist = self._haversine_m(
                    self._office[0],
                    self._office[1],
                    hit.lat,
                    hit.lng,
                )
                if dist > self._max_dist_m:
                    continue
                anchor_dist = self._haversine_m(lat, lng, hit.lat, hit.lng)
                if anchor_dist > 600:
                    continue
                seen_ids.add(hit.place_id)
                results.append(self._to_place(hit, place_type, query))
                added += 1
            logger.debug(
                "Naver 목록 '%s' → %d건 (누적 %d)",
                query,
                added,
                len(results),
            )

        logger.info("Naver Place 목록 %d건 (중복·거리 필터 후)", len(results))
        return results

    @staticmethod
    def _to_place(
        hit: NaverListPlaceHit,
        place_type: PlaceType,
        search_query: str,
    ) -> Place:
        category = guess_category(
            hit.category_text,
            place_type,
            name=hit.name,
            search_query=search_query,
            business_category=hit.business_category,
        )
        enc_name = urllib.parse.quote(hit.name)
        url = f"https://map.naver.com/p/search/{enc_name}/place/{hit.place_id}"
        return Place(
            id=f"naver:{hit.place_id}",
            name=hit.name,
            place_type=place_type,
            category=category,
            address="",
            lat=hit.lat,
            lng=hit.lng,
            rating=None,
            rating_source=None,
            url=url,
            source="naver_map",
            naver_place_id=hit.place_id,
        )

    @staticmethod
    def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))
