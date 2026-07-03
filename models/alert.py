"""
신규 오픈 알림 데이터 모델 (기능 C).

한 달 이내 오픈한 식당/카페를 사용자에게 전달할 때 사용합니다.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from models.place import Place, PlaceType


class NewOpeningAlert(BaseModel):
    """신규 오픈 장소 알림 단위."""

    place: Place
    opened_at: date = Field(description="확인된 개업일")
    days_since_opening: int = Field(ge=0, description="오픈 후 경과 일수")
    alert_type: PlaceType
    created_at: datetime = Field(default_factory=datetime.now)
    message: str = Field(description="사용자에게 보여줄 알림 문구")

    @classmethod
    def from_place(cls, place: Place, *, today: date | None = None) -> "NewOpeningAlert":
        """
        Place 객체로부터 알림 메시지를 생성합니다.

        opened_at이 없으면 ValueError를 발생시킵니다.
        """
        if place.opened_at is None:
            raise ValueError(f"개업일 정보가 없습니다: {place.name}")

        reference = today or date.today()
        days = (reference - place.opened_at).days

        type_label = "식당" if place.place_type == PlaceType.RESTAURANT else "카페"
        message = (
            f"[신규 오픈] {place.name} ({type_label}) - "
            f"{place.address} | 개업 {days}일차 | 평점 {place.rating or 'N/A'}"
        )

        return cls(
            place=place,
            opened_at=place.opened_at,
            days_since_opening=days,
            alert_type=place.place_type,
            message=message,
        )
