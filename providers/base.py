"""
장소 데이터 Provider 추상 인터페이스.

Kakao, Naver 등 외부 API를 동일한 인터페이스로 교체 가능하게 합니다.
(Strategy 패턴)
"""

from abc import ABC, abstractmethod

from models.place import Place, PlaceType


class PlaceProvider(ABC):
    """외부 API에서 장소 목록을 가져오는 Provider 기본 클래스."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """데이터 출처 이름 (로깅/Place.source 필드용)."""

    @abstractmethod
    def fetch_places(self, place_type: PlaceType) -> list[Place]:
        """
        지정 유형의 장소 목록을 반환합니다.

        Raises:
            PlaceProviderError: API 호출 또는 파싱 실패 시
        """
