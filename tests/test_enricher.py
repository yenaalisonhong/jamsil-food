"""PlaceEnricher 단위 테스트."""

from datetime import date

from models.place import Place, PlaceCategory, PlaceType
from services.manual_data_store import ManualDataStore
from services.place_enricher import PlaceEnricher


def test_enrich_from_manual_db(tmp_path) -> None:
    """수동 DB에서 가격·개업일을 보강합니다."""
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "place_details.json").write_text("{}", encoding="utf-8")
    (tmp_path / "manual_prices.json").write_text(
        '{"test-1": {"price_per_person_krw": 13000}}',
        encoding="utf-8",
    )
    (tmp_path / "manual_openings.json").write_text(
        '{"test-1": {"opened_at": "2026-06-01", "name": "테스트식당"}}',
        encoding="utf-8",
    )

    store = ManualDataStore(tmp_path)

    place = Place(
        id="test-1",
        name="테스트식당",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="서울",
        lat=37.51,
        lng=127.10,
        source="test",
    )

    enricher = PlaceEnricher(store=store, enable_crawl=False)
    result = enricher.enrich_one(place)

    assert result.price_per_person_krw == 13000
    assert result.opened_at == date(2026, 6, 1)


def test_merge_duplicates_prefers_rating() -> None:
    """Kakao+Naver 중복 시 naver_crawl 평점을 우선합니다."""
    a = Place(
        id="k1",
        name="같은식당",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="서울",
        lat=37.5145,
        lng=127.1010,
        rating=None,
        source="kakao",
    )
    b = Place(
        id="n1",
        name="같은식당",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="서울",
        lat=37.5145,
        lng=127.1010,
        rating=4.5,
        rating_source="naver_crawl",
        source="naver",
    )

    enricher = PlaceEnricher(enable_crawl=False)
    merged = enricher.merge_duplicates([a, b])
    assert len(merged) == 1
    assert merged[0].rating == 4.5
