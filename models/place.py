"""
장소(맛집/카페) 데이터 모델.

Pydantic 모델로 API 응답과 내부 로직 간 데이터 형식을 통일합니다.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class PlaceType(str, Enum):
    """장소 유형 (기능 A: 식당, 기능 B: 카페)."""

    RESTAURANT = "restaurant"
    CAFE = "cafe"


class PlaceCategory(str, Enum):
    """세부 음식/업종 카테고리 (API별 매핑용)."""

    KOREAN = "korean"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    WESTERN = "western"
    FAST_FOOD = "fast_food"
    CAFE = "cafe"
    DESSERT = "dessert"
    OTHER = "other"


class Place(BaseModel):
    """
    맛집/카페 공통 기본 모델.

    모든 외부 API 응답은 이 스키마로 정규화(normalize)한 뒤
    필터링·추천·알림 로직에 전달합니다.
    """

    id: str = Field(description="외부 API 또는 내부 고유 ID")
    name: str = Field(description="상호명")
    place_type: PlaceType
    category: PlaceCategory = PlaceCategory.OTHER

    # 위치 정보
    address: str = Field(description="도로명/지번 주소")
    lat: float
    lng: float
    distance_meters: Optional[float] = Field(
        default=None,
        description="프라운호퍼 사무소 기준 직선 거리(미터)",
    )
    walk_minutes: Optional[float] = Field(
        default=None,
        description="추정 도보 시간(분)",
    )

    # 평점 (여러 사이트 평점 중 대표값 또는 평균)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    rating_source: Optional[str] = Field(
        default=None,
        description="평점 출처 (kakao, naver, google 등)",
    )
    review_count: Optional[int] = Field(default=None, ge=0)

    # 가격 (인당, 원) - API에서 없을 수 있어 Optional
    price_per_person_krw: Optional[int] = Field(
        default=None,
        ge=0,
        description="인당 예상 가격(원)",
    )

    # 신규 오픈 추적 (기능 C)
    opened_at: Optional[date] = Field(
        default=None,
        description="개업일 (알 수 있는 경우)",
    )

    # 메타
    phone: Optional[str] = None
    url: Optional[HttpUrl] = None
    naver_place_id: Optional[str] = Field(
        default=None,
        description="Naver Place 숫자 ID (크롤링·수동 DB 매칭용)",
    )
    source: str = Field(description="데이터 제공 API 이름")
    fetched_at: datetime = Field(default_factory=datetime.now)


class Restaurant(Place):
    """식당 전용 모델 (기능 A)."""

    place_type: PlaceType = PlaceType.RESTAURANT


class Cafe(Place):
    """카페 전용 모델 (기능 B)."""

    place_type: PlaceType = PlaceType.CAFE
    category: PlaceCategory = PlaceCategory.CAFE
