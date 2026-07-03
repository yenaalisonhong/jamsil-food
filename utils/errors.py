"""
커스텀 예외 정의.

에러 유형별로 구분해 상위 레이어(CLI, 알림 서비스)에서
적절한 사용자 메시지와 복구 전략을 선택할 수 있게 합니다.
"""


class FoodFinderError(Exception):
    """애플리케이션 전역 기본 예외."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class ConfigurationError(FoodFinderError):
    """API 키 누락, 잘못된 설정값 등 환경 설정 오류."""


class PlaceProviderError(FoodFinderError):
    """외부 장소 API 호출 실패 (네트워크, 인증, 응답 파싱 등)."""


class FilterError(FoodFinderError):
    """필터링 로직 처리 중 발생한 오류."""


class AlertDeliveryError(FoodFinderError):
    """신규 오픈 알림 전송 실패."""
