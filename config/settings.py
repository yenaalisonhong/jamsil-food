"""
전역 설정 모듈.

프라운호퍼 한국사무소 좌표, 필터 기준(평점/가격/도보 시간),
외부 API 키 등을 한곳에서 관리합니다.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 및 기본값을 담는 설정 클래스."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 프라운호퍼 한국사무소 (잠실 더샵 스타파크) ---
    # 주소: 서울시 송파구 올림픽로 35가길 10, A동 202호 (신천동, 잠실더샵스타파크)
    fraunhofer_office_lat: float = Field(
        default=37.51692,
        description="프라운호퍼 한국사무소 위도",
    )
    fraunhofer_office_lng: float = Field(
        default=127.10282,
        description="프라운호퍼 한국사무소 경도",
    )

    # --- 추천 필터 기준 (PRD 2장) ---
    min_rating: float = Field(default=4.0, description="최소 평점 (4점 이상)")
    max_price_per_person_krw: int = Field(
        default=15_000,
        description="인당 최대 가격 (원)",
    )
    max_walk_minutes: int = Field(
        default=15,
        description="최대 도보 시간 (분)",
    )
    # 평균 도보 속도 4.8km/h 기준 15분 ≈ 1.2km
    walk_speed_kmh: float = Field(default=4.8, description="도보 속도 (km/h)")

    # --- 신규 오픈 알림 (기능 C) ---
    new_opening_days: int = Field(
        default=30,
        description="신규 오픈으로 간주할 기간 (일)",
    )

    # --- 크롤링 ---
    crawl_request_delay_sec: float = Field(
        default=1.5,
        description="Naver Place 크롤링 요청 간격(초)",
    )
    crawl_cache_ttl_hours: int = Field(
        default=24,
        description="크롤링 캐시 TTL(시간)",
    )

    # --- 외부 API 키 ---
    kakao_rest_api_key: str = Field(default="", description="Kakao REST API 키")
    naver_client_id: str = Field(default="", description="Naver API Client ID")
    naver_client_secret: str = Field(default="", description="Naver API Client Secret")

    # --- 알림 (SMTP) ---
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    alert_recipient_email: str = Field(default="")

    @property
    def max_walk_radius_meters(self) -> float:
        """도보 시간 기준으로 최대 반경(미터)을 계산합니다."""
        hours = self.max_walk_minutes / 60
        km = self.walk_speed_kmh * hours
        return km * 1000


@lru_cache
def get_settings() -> Settings:
    """
    설정 싱글톤을 반환합니다.

    lru_cache로 앱 전체에서 동일한 Settings 인스턴스를 재사용합니다.
    """
    return Settings()
