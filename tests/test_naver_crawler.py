"""NaverPlaceCrawler 파싱 단위 테스트 (HTTP 없이)."""

from services.naver_place_crawler import NaverPlaceCrawler


def test_extract_rating_from_html() -> None:
    html = '{"visitorRating":4.32,"visitorReviewCount":128}'
    assert NaverPlaceCrawler._extract_rating(html) == 4.32
    assert NaverPlaceCrawler._extract_review_count(html) == 128


def test_estimate_price_from_menu() -> None:
    html = '"price":8000,"name":"김치찌개","price":12000,"price":45000'
    price = NaverPlaceCrawler._estimate_price_from_menu(html)
    assert price == 12000


def test_extract_menu_items() -> None:
    html = '{"name":"된장찌개","price":9000},{"name":"김치찌개","price":10000}'
    items = NaverPlaceCrawler._extract_menu_items(html)
    assert items[0] == ("된장찌개", 9000)


def test_extract_review_text() -> None:
    html = '{"review":"맛있고 양도 푸짐해서 다음에 또 올 것 같아요"}'
    text = NaverPlaceCrawler._extract_review_text(html)
    assert text is not None
    assert "맛있고" in text
