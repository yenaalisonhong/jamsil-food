"""
Mock Place Provider.

API 키 없이 로컬 개발·테스트를 위한 샘플 데이터를 제공합니다.
잠실/프라운호퍼 사무소 주변 가상 장소입니다.
"""

from datetime import date, timedelta

from models.place import Place, PlaceCategory, PlaceType
from providers.base import PlaceProvider


class MockPlaceProvider(PlaceProvider):
    """개발용 더미 데이터 Provider."""

    @property
    def source_name(self) -> str:
        return "mock"

    def fetch_places(self, place_type: PlaceType) -> list[Place]:
        """유형별 샘플 장소 반환."""
        if place_type == PlaceType.RESTAURANT:
            return self._sample_restaurants()
        return self._sample_cafes()

    def _sample_restaurants(self) -> list[Place]:
        """기능 A 테스트용 식당 샘플."""
        today = date.today()
        return [
            Place(
                id="mock-r1",
                name="잠실맛집 한식당",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.KOREAN,
                address="서울 송파구 올림픽로 300",
                lat=37.5145,
                lng=127.1010,
                rating=4.3,
                rating_source="mock",
                price_per_person_krw=12_000,
                opened_at=today - timedelta(days=5),  # 신규 오픈 테스트용
                source=self.source_name,
            ),
            Place(
                id="mock-r2",
                name="가성비 중식당",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.CHINESE,
                address="서울 송파구 신천동",
                lat=37.5120,
                lng=127.0990,
                rating=4.1,
                rating_source="mock",
                price_per_person_krw=9_000,
                source=self.source_name,
            ),
            Place(
                id="mock-r3",
                name="비싼 스테이크하우스",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.WESTERN,
                address="서울 송파구 잠실동",
                lat=37.5150,
                lng=127.1020,
                rating=4.8,
                rating_source="mock",
                price_per_person_krw=45_000,  # 가격 필터 제외 대상
                source=self.source_name,
            ),
            Place(
                id="mock-r4",
                name="평점낮은 분식",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.KOREAN,
                address="서울 송파구 석촌동",
                lat=37.5110,
                lng=127.0980,
                rating=3.2,  # 평점 필터 제외 대상
                rating_source="mock",
                price_per_person_krw=8_000,
                source=self.source_name,
            ),
        ]

    def _sample_cafes(self) -> list[Place]:
        """기능 B 테스트용 카페 샘플."""
        today = date.today()
        return [
            Place(
                id="mock-c1",
                name="스타파크 카페",
                place_type=PlaceType.CAFE,
                category=PlaceCategory.CAFE,
                address="서울 송파구 올림픽로35가길 10",
                lat=37.5140,
                lng=127.1008,
                rating=4.5,
                rating_source="mock",
                opened_at=today - timedelta(days=10),
                source=self.source_name,
            ),
            Place(
                id="mock-c2",
                name="잠실 브런치 카페",
                place_type=PlaceType.CAFE,
                category=PlaceCategory.CAFE,
                address="서울 송파구 잠실동",
                lat=37.5130,
                lng=127.0995,
                rating=4.2,
                rating_source="mock",
                source=self.source_name,
            ),
        ]
