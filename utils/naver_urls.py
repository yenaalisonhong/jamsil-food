"""Naver Place URL 파싱."""

import re
from typing import Optional

_PLACE_ID_PATTERNS = [
    re.compile(r"/place/(\d+)"),
    re.compile(r"/entry/place/(\d+)"),
    re.compile(r"placeId=(\d+)"),
]


def extract_naver_place_id(url: str) -> Optional[str]:
    """Naver Place URL에서 숫자 place ID를 추출합니다."""
    if not url:
        return None
    for pattern in _PLACE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _pcmap_category(_place_type: str = "restaurant") -> str:
    """pcmap.place.naver.com은 cafe/ 경로가 404 — restaurant 경로를 사용합니다."""
    return "restaurant"


def build_place_home_url(place_id: str, place_type: str = "restaurant") -> str:
    """크롤링용 Naver Place 홈 URL."""
    return f"https://pcmap.place.naver.com/{_pcmap_category(place_type)}/{place_id}/home"


def build_place_menu_url(place_id: str, place_type: str = "restaurant") -> str:
    """메뉴 가격 크롤링용 URL."""
    return f"https://pcmap.place.naver.com/{_pcmap_category(place_type)}/{place_id}/menu"
