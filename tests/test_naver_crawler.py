"""NaverPlaceCrawler 파싱 단위 테스트 (HTTP 없이)."""

from datetime import date

from models.place import PlaceType
from services.naver_place_crawler import NaverPlaceCrawler


def test_extract_rating_from_html() -> None:
    html = '{"__typename":"VisitorReviewStats","avgRating":4.32,"totalCount":128}'
    assert NaverPlaceCrawler._extract_rating(html) == 4.32
    assert NaverPlaceCrawler._extract_review_count(html) == 128


def test_extract_rating_from_apollo_state() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "VisitorReviewStats:123": {
        "__typename": "VisitorReviewStats",
        "avgRating": 4.15,
        "totalCount": 88
      }
    };
    window.__PLACE_STATE__ = {};
    """
    assert NaverPlaceCrawler._extract_rating(html) == 4.15


def test_extract_rating_from_apollo_visitor_review_score() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "PlaceListBusinessesItem:1": {
        "id": "1",
        "visitorReviewScore": 4.52,
        "visitorReviewCount": 245
      }
    };
    window.__PLACE_STATE__ = {};
    """
    assert NaverPlaceCrawler._extract_rating(html) == 4.52


def test_estimate_price_from_menu() -> None:
    html = '{"__typename":"Menu","name":"김치찌개","price":"12000"}'
    price = NaverPlaceCrawler._estimate_price_from_menu(html)
    assert price == 12000


def test_menu_prices_for_range_excludes_drinks_for_restaurant() -> None:
    menus = [
        ("김치찌개", 12000, True),
        ("아메리카노", 4500, False),
        ("케이크", 6500, False),
        ("된장찌개", 9000, False),
    ]
    prices = NaverPlaceCrawler._menu_prices_for_range(menus, PlaceType.RESTAURANT)
    assert prices == [12000, 9000]
    price_range = NaverPlaceCrawler._price_range_from_prices(prices)
    assert price_range == (9000, 12000)


def test_menu_prices_for_range_includes_all_for_cafe() -> None:
    menus = [
        ("아메리카노", 4500, True),
        ("케이크", 6500, False),
    ]
    prices = NaverPlaceCrawler._menu_prices_for_range(menus, PlaceType.CAFE)
    assert prices == [4500, 6500]


def test_extract_menu_items() -> None:
    html = '{"__typename":"Menu","name":"된장찌개","price":"9000","recommend":true}'
    items = NaverPlaceCrawler._extract_menu_items(html)
    assert items[0] == ("된장찌개", 9000, True)


def test_format_representative_menu_prefers_recommended() -> None:
    html = (
        '{"__typename":"Menu","name":"김치찌개","price":"9000","recommend":false}'
        '{"__typename":"Menu","name":"된장찌개","price":"9000","recommend":true}'
        '{"__typename":"Menu","name":"순두부찌개","price":"8000","recommend":true}'
        '{"__typename":"Menu","name":"부대찌개","price":"10000","recommend":false}'
    )
    items = NaverPlaceCrawler._extract_menu_items(html)
    menu = NaverPlaceCrawler._format_representative_menu(items)
    assert menu == "된장찌개 · 순두부찌개 · 김치찌개"


def test_extract_review_text() -> None:
    html = '{"body":"맛있고 양도 푸짐해서 다음에 또 올 것 같아요"}'
    text = NaverPlaceCrawler._extract_review_text(html)
    assert text is not None
    assert "맛있고" in text


def test_extract_review_texts_returns_up_to_two_unique() -> None:
    html = (
        '{"body":"첫 번째 리뷰입니다"}'
        'other'
        '{"body":"두 번째 리뷰입니다"}'
        '{"body":"첫 번째 리뷰입니다"}'
        '{"body":"세 번째 리뷰입니다"}'
    )
    texts = NaverPlaceCrawler._extract_review_texts(html, limit=2)
    assert texts == ["첫 번째 리뷰입니다", "두 번째 리뷰입니다"]


def test_extract_opening_date_from_legacy_field() -> None:
    html = '{"openingDate":"2026-06-01","newOpening":false}'
    assert NaverPlaceCrawler._extract_opening_date(html, "123") == date(2026, 6, 1)


def test_extract_new_opening_from_apollo_state() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "ROOT_QUERY": {
        "placeDetail({\\"input\\":{\\"deviceType\\":\\"pcmap\\",\\"id\\":\\"2041123621\\",\\"isNx\\":false}})": {
          "__typename": "PlaceDetail",
          "newOpening": true,
          "topPhotos": {
            "__typename": "PlaceDetailTopPhotos",
            "items": [
              {"date": "2026.06.17.", "origin": "https://video-phinf.pstatic.net/20260617_60/x.jpg"}
            ]
          }
        }
      }
    };
    window.__PLACE_STATE__ = {};
    """
    assert NaverPlaceCrawler._extract_new_opening_flag(html, "2041123621") is True
    assert NaverPlaceCrawler._extract_opening_date(html, "2041123621") == date(2026, 6, 17)


def test_extract_opening_date_ignores_old_places_without_flag() -> None:
    html = """
    window.__APOLLO_STATE__ = {
      "ROOT_QUERY": {
        "placeDetail({\\"input\\":{\\"deviceType\\":\\"pcmap\\",\\"id\\":\\"999\\",\\"isNx\\":false}})": {
          "newOpening": false,
          "topPhotos": {"items": [{"date": "2026.06.17."}]}
        }
      }
    };
    window.__PLACE_STATE__ = {};
    """
    assert NaverPlaceCrawler._extract_opening_date(html, "999") is None


def test_fetch_detail_supplements_menu_from_cache_hit(monkeypatch) -> None:
    from services.manual_data_store import ManualDataStore

    store = ManualDataStore()
    store.set_cached_detail(
        "12345",
        {
            "rating": 4.5,
            "review_count": 10,
            "representative_review": "맛있어요",
            "opened_at": "2020-01-01",
        },
    )

    menu_html = (
        '{"__typename":"Menu","name":"된장찌개","price":"9000","recommend":true}'
        '{"__typename":"Menu","name":"김치찌개","price":"9000","recommend":false}'
    )

    def fake_get_page(url: str, *, retries: int = 3) -> str:
        if "/menu" in url:
            return menu_html
        return '{"visitorReviewScore":4.5,"visitorReviewCount":10}'

    crawler = NaverPlaceCrawler(store, request_delay_sec=0)
    monkeypatch.setattr(crawler, "_get_page", fake_get_page)

    detail = crawler.fetch_detail("12345", PlaceType.RESTAURANT)
    assert detail.representative_menu == "된장찌개 · 김치찌개"
