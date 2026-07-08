"""
잠실 프라운호퍼 사무소 근처 상가·건물 검색 앵커.

홈플러스, 장미상가 등 밀집 상권을 좌표·별칭으로 지정해
Provider마다 동일한 키워드·앵커를 재사용합니다.

사무실에서 가장 가까운 5개 상가는 deep_commercial_searches()로
키워드·상호명 시드·업종별 쿼리를 추가 실행합니다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from models.place import PlaceType

# 프라운호퍼 한국사무소 (잠실더샵스타파크)
_OFFICE_LAT = 37.51692
_OFFICE_LNG = 127.10282

NEAREST_COMMERCIAL_COUNT = 5
DEFAULT_ANCHOR_RADIUS_M = 600
DEEP_ANCHOR_RADIUS_M = 750


@dataclass(frozen=True)
class CommercialAnchor:
    """상가/건물 이름, 중심 좌표, 검색 별칭."""

    name: str
    lat: float
    lng: float
    aliases: tuple[str, ...] = ()
    radius_m: float = DEFAULT_ANCHOR_RADIUS_M
    # 넓은 상가·인접 건물 식당 검색용 보조 중심 (lat, lng)
    extra_centers: tuple[tuple[float, float], ...] = ()


# 도보 15분 이내 주요 상가·건물 (사무실: 37.51692, 127.10282)
COMMERCIAL_ANCHORS: list[CommercialAnchor] = [
    CommercialAnchor(
        "홈플러스 잠실점",
        37.51623,
        127.10301,
        (
            "홈플러스 상가",
            "홈플러스 잠실",
            "송파펀스타디움",
            "잠실홈플러스",
            "푸르지오월드마크",
            "잠실 푸르지오 월드마크",
        ),
        radius_m=850,
        # 홈플러스 건너편·인접 상가 식당 (나루스시, BHC 등)
        extra_centers=((37.51655, 127.10175),),
    ),
    CommercialAnchor(
        "장미상가",
        37.51785,
        127.10185,
        (
            "잠실 장미상가",
            "장미상가 지하",
            "장미상가 지하식당",
            "올림픽로35길 장미상가",
            "장미상가 A동",
            "장미상가 B동",
        ),
        radius_m=DEEP_ANCHOR_RADIUS_M,
    ),
    CommercialAnchor(
        "장미아파트 지하상가",
        37.51825,
        127.10095,
        ("장미아파트 맛집", "장미아파트 지하상가", "잠실나루 장미아파트"),
        radius_m=DEEP_ANCHOR_RADIUS_M,
    ),
    CommercialAnchor(
        "잠실더샵스타파크",
        37.51692,
        127.10282,
        (
            "더샵스타파크",
            "스타파크 상가",
            "잠실더샵 상가",
            "올림픽로35가길 스타파크",
            "스타파크 지하",
            "스타파크 지하식당",
        ),
        radius_m=DEEP_ANCHOR_RADIUS_M,
    ),
    CommercialAnchor(
        "잠실역 상권",
        37.51345,
        127.10015,
        (
            "잠실역 카페",
            "현대타워 카페",
            "올림픽로 카페",
            "잠실역 근처 카페",
        ),
    ),
    CommercialAnchor(
        "파크리오 상가",
        37.5191,
        127.1070,
        ("잠실 파크리오",),
    ),
    CommercialAnchor(
        "잠실리센츠 상가",
        37.5140,
        127.1080,
        ("잠실 리센츠",),
    ),
    CommercialAnchor(
        "르엘 잠실",
        37.5155,
        127.1060,
        ("르엘 상가", "잠실르엘", "잠실 르엘"),
        radius_m=DEEP_ANCHOR_RADIUS_M,
    ),
    CommercialAnchor(
        "잠실엘스",
        37.5138,
        127.1055,
        ("잠실 엘스",),
    ),
    CommercialAnchor(
        "트리지움",
        37.5138,
        127.0895,
        ("잠실 트리지움",),
    ),
    CommercialAnchor(
        "GS타워 잠실",
        37.5145,
        127.1050,
        (),
    ),
]

_ANCHOR_BY_NAME: dict[str, CommercialAnchor] = {a.name: a for a in COMMERCIAL_ANCHORS}

# 상가별 핵심 검색어
_PRIORITY_RESTAURANT: dict[str, tuple[str, ...]] = {
    "잠실더샵스타파크": (
        "잠실더샵스타파크 음식점",
        "잠실더샵스타파크",
        "스타파크 상가 맛집",
        "더샵스타파크 음식점",
        "올림픽로35가길 스타파크 맛집",
        "스타파크 지하 맛집",
        "스타파크 지하식당",
        "올림픽로35가길 10 맛집",
    ),
    "홈플러스 잠실점": (
        "홈플러스 잠실점 음식점",
        "홈플러스 잠실점",
        "홈플러스 상가 맛집",
        "홈플러스 잠실 푸드코트",
        "홈플러스 잠실 식당가",
        "송파펀스타디움 맛집",
        "홈플러스 잠실 1층 식당",
        "홈플러스 잠실 3층 식당",
        "홈플러스 잠실 4층 식당",
        "푸르지오월드마크 맛집",
        "잠실 푸르지오 월드마크 음식점",
    ),
    "장미상가": (
        "장미상가 음식점",
        "장미상가 맛집",
        "잠실 장미상가",
        "장미상가 지하",
        "장미상가 지하식당",
        "장미상가 A동",
        "장미상가 B동",
        "올림픽로35길 장미상가",
    ),
    "장미아파트 지하상가": (
        "장미아파트 지하상가 음식점",
        "장미아파트 지하상가 맛집",
        "장미아파트 맛집",
        "잠실나루 장미아파트 맛집",
        "장미아파트 B상가 맛집",
    ),
    "르엘 잠실": (
        "르엘 잠실 음식점",
        "르엘 잠실 맛집",
        "잠실르엘 맛집",
        "잠실 르엘 상가 맛집",
        "르엘 상가 음식점",
    ),
    "파크리오 상가": ("파크리오 상가 맛집", "잠실 파크리오 맛집"),
    "잠실리센츠 상가": ("잠실리센츠 상가 맛집", "리센츠 상가 맛집"),
    "잠실엘스": ("잠실엘스 맛집", "엘스 상가 맛집"),
    "트리지움": ("트리지움 맛집",),
    "GS타워 잠실": ("GS타워 잠실 맛집",),
}

_PRIORITY_CAFE: dict[str, tuple[str, ...]] = {
    "잠실더샵스타파크": (
        "더샵스타파크 카페",
        "스타파크 상가 카페",
        "잠실더샵스타파크 카페",
    ),
    "홈플러스 잠실점": (
        "홈플러스 잠실점 카페",
        "홈플러스 상가 카페",
    ),
    "장미상가": (
        "장미상가 카페",
        "잠실 장미상가 카페",
        "장미상가 디저트",
        "장미상가 베이커리",
    ),
    "장미아파트 지하상가": (
        "장미아파트 카페",
        "장미아파트 지하상가 카페",
    ),
    "르엘 잠실": (
        "르엘 잠실 카페",
        "잠실르엘 카페",
    ),
    "잠실역 상권": (
        "잠실역 카페",
        "현대타워 카페",
        "올림픽로 카페",
        "잠실역 근처 카페",
    ),
    "파크리오 상가": ("파크리오 상가 카페",),
    "잠실리센츠 상가": ("잠실리센츠 카페",),
    "잠실엘스": ("잠실엘스 카페",),
    "트리지움": ("트리지움 카페",),
    "GS타워 잠실": ("GS타워 잠실 카페",),
}

# 심층 조사: 업종별 보조 검색 (가까운 5개 상가만)
_DEEP_CUISINE_SUFFIXES: tuple[str, ...] = (
    "한식",
    "중식",
    "일식",
    "분식",
    "치킨",
)

# 심층 조사: 일반 키워드 검색에 누락되기 쉬운 상호명 (상가별)
_DEEP_NAMED_SEEDS: dict[str, tuple[str, ...]] = {
    "홈플러스 잠실점": (
        "삼청동식탁",
        "모스버거",
        "북촌손만두",
        "좋은날한우",
        "테루카츠",
        "두끼",
        "두촌가마솥밥",
        "메밀꽃필무렵",
        "락앤웍",
        "명동칼국수",
        "우리콩순두부",
        "오호이박스",
    ),
    "잠실더샵스타파크": (
        "크래프트아일랜드",
        "더타코부스",
        "복호두",
        "식물원김밥",
        "샐러디",
        "진전복삼계탕",
        "서커스래빗",
        "본죽",
        "맥도날드 잠실",
    ),
    "장미상가": (
        "가보자식당",
        "태양의집",
        "알뜰식당",
        "치마오",
        "정순함박",
        "한뭉티기",
        "할아버지돈까스",
        "라멘쨩",
        "뽀빠이분식",
        "후또로마또로",
        "한국수",
        "제주도야지판",
        "송가네감자탕",
    ),
    "장미아파트 지하상가": (
        "깜닭치킨",
        "장미시장국밥",
        "30년전통 송가네감자탕",
        "나루스시",
    ),
    "르엘 잠실": (
        "왁버거",
        "신선미미사리우동",
        "푸에르코",
        "하삼동커피",
    ),
}

# 심층 조사: 카페 상호명 시드 (일반 키워드 검색 누락 방지)
_DEEP_CAFE_NAMED_SEEDS: dict[str, tuple[str, ...]] = {
    "장미상가": (
        "리사르커피",
        "푸가커피",
        "커피나인",
        "나이스카페인클럽",
        "매머드익스프레스",
    ),
    "잠실역 상권": (
        "비엔나커피센트럴",
        "비엔나커피하우스",
        "파스쿠찌 잠실역",
        "봄날의서재",
    ),
    "르엘 잠실": (
        "하삼동커피",
    ),
    "홈플러스 잠실점": (
        "스타벅스 홈플러스",
        "이디야 홈플러스",
        "어라운드홈",
        "마호가니",
        "차타임",
        "차타임라운지",
    ),
    "잠실더샵스타파크": (
        "스타벅스 스타파크",
        "이디야 스타파크",
    ),
}

# 상가별 고수율 1순위 쿼리 (rate limit 시 우선 실행)
_DEEP_PRIMARY_QUERY: dict[str, str] = {
    "잠실더샵스타파크": "스타파크 상가 맛집",
    "홈플러스 잠실점": "홈플러스 잠실점 음식점",
    "장미상가": "장미상가 음식점",
    "장미아파트 지하상가": "장미아파트 지하상가 음식점",
    "르엘 잠실": "르엘 잠실 음식점",
}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _anchor_for_search_center(lat: float, lng: float) -> CommercialAnchor | None:
    """검색 중심 좌표에 대응하는 상가 앵커 (보조 중심 포함)."""
    best: CommercialAnchor | None = None
    best_dist = 80.0
    for anchor in COMMERCIAL_ANCHORS:
        dist = _haversine_m(lat, lng, anchor.lat, anchor.lng)
        if dist < best_dist:
            best = anchor
            best_dist = dist
            continue
        for elat, elng in anchor.extra_centers:
            edist = _haversine_m(lat, lng, elat, elng)
            if edist < best_dist:
                best = anchor
                best_dist = edist
    return best


def search_radius_m(lat: float, lng: float) -> float:
    """검색 중심 좌표 기준 허용 반경(미터)."""
    anchor = _anchor_for_search_center(lat, lng)
    if anchor is None:
        return DEFAULT_ANCHOR_RADIUS_M
    if anchor.name in nearest_commercial_names():
        return anchor.radius_m
    return DEFAULT_ANCHOR_RADIUS_M


def _search_centers_for_anchor(anchor: CommercialAnchor) -> list[tuple[float, float]]:
    centers = [(anchor.lat, anchor.lng)]
    centers.extend(anchor.extra_centers)
    return centers


def nearest_commercial_anchors(
    *,
    count: int = NEAREST_COMMERCIAL_COUNT,
    office_lat: float = _OFFICE_LAT,
    office_lng: float = _OFFICE_LNG,
) -> list[CommercialAnchor]:
    """사무실에서 가장 가까운 상가 N개."""
    ranked = sorted(
        COMMERCIAL_ANCHORS,
        key=lambda a: _haversine_m(office_lat, office_lng, a.lat, a.lng),
    )
    return ranked[:count]


def nearest_commercial_names(
    *,
    count: int = NEAREST_COMMERCIAL_COUNT,
) -> frozenset[str]:
    """심층 조사 대상 상가 이름 집합."""
    return frozenset(a.name for a in nearest_commercial_anchors(count=count))


def is_deep_commercial_anchor(name: str) -> bool:
    return name in nearest_commercial_names()


def _priority_queries(place_type: PlaceType) -> dict[str, tuple[str, ...]]:
    return _PRIORITY_RESTAURANT if place_type == PlaceType.RESTAURANT else _PRIORITY_CAFE


def _anchor_queries(anchor: CommercialAnchor, place_type: PlaceType) -> tuple[str, ...]:
    priorities = _priority_queries(place_type)
    default = (
        (f"{anchor.name} 맛집",)
        if place_type == PlaceType.RESTAURANT
        else (f"{anchor.name} 카페",)
    )
    return priorities.get(anchor.name, default)


def deep_commercial_searches(place_type: PlaceType) -> list[tuple[str, float, float]]:
    """
    가장 가까운 5개 상가 심층 검색 목록.

    우선순위: 고수율 쿼리 → 상가별 키워드 → 업종별 → 상호명 시드.
    """
    searches: list[tuple[str, float, float]] = []
    seen: set[tuple[str, float, float]] = set()

    def _add(query: str, anchor_lat: float, anchor_lng: float) -> None:
        key = (query, round(anchor_lat, 5), round(anchor_lng, 5))
        if key in seen:
            return
        seen.add(key)
        searches.append((query, anchor_lat, anchor_lng))

    for anchor in nearest_commercial_anchors():
        centers = _search_centers_for_anchor(anchor)
        for center_lat, center_lng in centers:
            if place_type == PlaceType.RESTAURANT:
                primary = _DEEP_PRIMARY_QUERY.get(anchor.name)
                if primary:
                    _add(primary, center_lat, center_lng)

            for query in _anchor_queries(anchor, place_type):
                _add(query, center_lat, center_lng)

            if place_type == PlaceType.RESTAURANT:
                label = anchor.aliases[0] if anchor.aliases else anchor.name
                for suffix in _DEEP_CUISINE_SUFFIXES:
                    _add(f"{label} {suffix}", center_lat, center_lng)
                for name in _DEEP_NAMED_SEEDS.get(anchor.name, ()):
                    _add(name, center_lat, center_lng)
            elif place_type == PlaceType.CAFE:
                for name in _DEEP_CAFE_NAMED_SEEDS.get(anchor.name, ()):
                    _add(name, center_lat, center_lng)

    if place_type == PlaceType.CAFE:
        deep_names = nearest_commercial_names()
        for anchor in COMMERCIAL_ANCHORS:
            if anchor.name in deep_names:
                continue
            for name in _DEEP_CAFE_NAMED_SEEDS.get(anchor.name, ()):
                _add(name, anchor.lat, anchor.lng)

    return searches


def jangmi_searches(place_type: PlaceType) -> list[tuple[str, float, float]]:
    """하위 호환 — deep_commercial_searches()와 동일."""
    return deep_commercial_searches(place_type)


def map_searches(place_type: PlaceType) -> list[tuple[str, float, float]]:
    """Naver Place 목록용 (검색어, 위도, 경도) 목록."""
    searches: list[tuple[str, float, float]] = []
    seen: set[tuple[str, float, float]] = set()
    deep_names = nearest_commercial_names()

    def _merge(batch: list[tuple[str, float, float]]) -> None:
        for query, lat, lng in batch:
            key = (query, round(lat, 5), round(lng, 5))
            if key in seen:
                continue
            seen.add(key)
            searches.append((query, lat, lng))

    _merge(deep_commercial_searches(place_type))

    for anchor in COMMERCIAL_ANCHORS:
        if anchor.name in deep_names:
            continue
        for query in _anchor_queries(anchor, place_type):
            key = (query, round(anchor.lat, 5), round(anchor.lng, 5))
            if key in seen:
                continue
            seen.add(key)
            searches.append((query, anchor.lat, anchor.lng))

    return searches


def api_queries(place_type: PlaceType) -> list[str]:
    """Naver 지역 검색 API용 키워드."""
    priorities = _priority_queries(place_type)
    queries: list[str] = []
    seen: set[str] = set()

    for query, _, _ in deep_commercial_searches(place_type):
        if query in seen:
            continue
        seen.add(query)
        queries.append(query)

    for anchor in COMMERCIAL_ANCHORS:
        if anchor.name in nearest_commercial_names():
            continue
        for query in priorities.get(anchor.name, ()):
            if query in seen:
                continue
            seen.add(query)
            queries.append(query)
    return queries


def kakao_anchors() -> list[tuple[str, float, float]]:
    """Kakao 앵커 검색 중심 (가까운 상가 우선)."""
    deep = nearest_commercial_anchors()
    deep_coords = {(a.lat, a.lng) for a in deep}
    rest = [a for a in COMMERCIAL_ANCHORS if (a.lat, a.lng) not in deep_coords]
    return [(a.name, a.lat, a.lng) for a in [*deep, *rest]]


def kakao_keywords(place_type: PlaceType) -> list[str]:
    """Kakao 키워드 검색용 상가별 키워드."""
    keywords: list[str] = []
    seen: set[str] = set()

    for query, _, _ in deep_commercial_searches(place_type):
        if query in seen:
            continue
        seen.add(query)
        keywords.append(query)

    priorities = _priority_queries(place_type)
    for anchor in COMMERCIAL_ANCHORS:
        if anchor.name in nearest_commercial_names():
            continue
        for query in priorities.get(anchor.name, ()):
            if query in seen:
                continue
            seen.add(query)
            keywords.append(query)
    return keywords
