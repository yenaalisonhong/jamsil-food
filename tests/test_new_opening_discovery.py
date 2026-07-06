"""신규 오픈 탐지 단위 테스트."""

from datetime import date

from models.place import PlaceType
from services.naver_place_crawler import NaverPlaceCrawler


def test_parse_new_openings_from_list_apollo() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "PlaceListBusinessesItem:2041123621:2041123621": {
        "__typename": "PlaceListBusinessesItem",
        "id": "2041123621",
        "name": "상구네돼지구이 잠실새내점",
        "businessCategory": "restaurant",
        "category": "돼지고기구이",
        "x": "127.0842954",
        "y": "37.5100704",
        "roadAddress": "서울 송파구 백제고분로9길 47",
        "address": "서울 송파구 방이동",
        "phone": "02-000-0000",
        "newOpening": true,
        "imageUrl": "https://ldb-phinf.pstatic.net/20260520_170/x.jpg"
      },
      "PlaceListBusinessesItem:999:999": {
        "id": "999",
        "name": "오래된식당",
        "businessCategory": "restaurant",
        "x": "127.1",
        "y": "37.5",
        "newOpening": false
      }
    };
    window.__PLACE_STATE__ = {};
    """
    places = NaverPlaceCrawler._parse_new_openings_from_list_html(html, PlaceType.RESTAURANT)
    assert len(places) == 1
    assert places[0].name == "상구네돼지구이 잠실새내점"
    assert places[0].naver_place_id == "2041123621"
    assert places[0].opened_at == date(2026, 5, 20)
    assert places[0].source == "naver_trending"
