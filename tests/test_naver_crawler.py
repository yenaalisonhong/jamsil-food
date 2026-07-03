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
