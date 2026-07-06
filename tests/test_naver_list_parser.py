"""Naver 목록 파싱 단위 테스트 (HTTP 없이)."""

from services.naver_place_crawler import NaverPlaceCrawler


def test_parse_list_hits_from_apollo_state() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "PlaceListBusinessesItem:123": {
        "id": "123",
        "name": "한식당",
        "x": "127.10",
        "y": "37.51",
        "category": "음식점>한식>백반",
        "businessCategory": "restaurant"
      },
      "PlaceListBusinessesItem:456": {
        "id": "456",
        "name": "스타벅스 잠실",
        "x": "127.11",
        "y": "37.52",
        "category": "음식점>카페",
        "businessCategory": "cafe"
      }
    };
    window.__PLACE_STATE__ = {};
  """
    hits = NaverPlaceCrawler._parse_list_hits_from_html(html)
    by_id = {hit.place_id: hit for hit in hits}
    assert by_id["123"].category_text == "음식점>한식>백반"
    assert by_id["456"].business_category == "cafe"
