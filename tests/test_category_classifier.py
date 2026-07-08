"""카테고리 분류 단위 테스트."""

from models.place import Place, PlaceCategory, PlaceType
from services.category_classifier import (
    classify_from_menu,
    count_coffee_and_meal_menus,
    guess_category,
    infer_place_type,
    is_food_place,
    refine_category,
    refine_place_type,
    should_classify_as_cafe_by_menus,
)


def test_guess_category_from_naver_text() -> None:
    assert guess_category("음식점>한식", PlaceType.RESTAURANT) == PlaceCategory.KOREAN
    assert guess_category("음식점>중식", PlaceType.RESTAURANT) == PlaceCategory.CHINESE
    assert guess_category("음식점>카페,디저트", PlaceType.RESTAURANT) == PlaceCategory.CAFE


def test_classify_from_menu_not_store_name() -> None:
    assert classify_from_menu("뿜치킹", PlaceType.RESTAURANT) == PlaceCategory.FAST_FOOD
    assert classify_from_menu("양지쌀국수", PlaceType.RESTAURANT) == PlaceCategory.KOREAN
    assert classify_from_menu("페페로니 L", PlaceType.RESTAURANT) == PlaceCategory.FAST_FOOD
    assert classify_from_menu("플레인 베이글", PlaceType.CAFE) == PlaceCategory.DESSERT
    assert classify_from_menu("게이샤 아메리카노", PlaceType.CAFE) == PlaceCategory.CAFE
    assert classify_from_menu("파스타 / 스테이크", PlaceType.RESTAURANT) is None


def test_guess_category_uses_store_name_when_no_menu() -> None:
    assert guess_category("", PlaceType.RESTAURANT, name="모스버거 홈플러스잠실점") == (
        PlaceCategory.FAST_FOOD
    )
    assert (
        guess_category(
            "",
            PlaceType.RESTAURANT,
            name="모스버거 홈플러스잠실점",
            menu_text="모스버거 클래식",
        )
        == PlaceCategory.FAST_FOOD
    )
    assert guess_category("", PlaceType.RESTAURANT, name="청년감자탕 송파 본점") == (
        PlaceCategory.KOREAN
    )


def test_guess_category_from_search_query() -> None:
    assert guess_category("", PlaceType.RESTAURANT, search_query="잠실 한식") == (
        PlaceCategory.KOREAN
    )
    assert guess_category("", PlaceType.CAFE, search_query="잠실 디저트") == (
        PlaceCategory.DESSERT
    )


def test_infer_place_type_from_name_and_business() -> None:
    assert (
        infer_place_type(name="블루보틀 잠실 카페", default=PlaceType.RESTAURANT)
        == PlaceType.CAFE
    )
    assert (
        infer_place_type(
            name="스타벅스 잠실",
            business_category="cafe",
            default=PlaceType.RESTAURANT,
        )
        == PlaceType.CAFE
    )
    assert infer_place_type(name="프린트카페 잠실점", default=PlaceType.RESTAURANT) == (
        PlaceType.RESTAURANT
    )


def test_refine_category_updates_other() -> None:
    place = Place(
        id="naver:1",
        name="교촌치킨 잠실점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="뿜치킹",
    )
    assert refine_category(place) == PlaceCategory.FAST_FOOD


def test_refine_category_uses_review_when_menu_placeholder() -> None:
    place = Place(
        id="naver:2",
        name="정순함박",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
        representative_review="함박스테이크와 튀김함박이 유명한 일식 돈까스 맛집",
    )
    assert refine_category(place) == PlaceCategory.JAPANESE


def test_is_food_place_excludes_retail_and_stationery() -> None:
    assert not is_food_place(name="올리브영 잠실장미상가점")
    assert not is_food_place(name="대우문구")
    assert not is_food_place(
        name="장미상가 A 개방화장실",
        representative_review="화장실이 깨끗해요",
    )
    assert not is_food_place(
        category_text="뷰티>화장품,향수",
        business_category="drugstore",
    )
    assert not is_food_place(name="홈플러스 잠실점 (마트 임시휴업)")
    assert not is_food_place(name="후지필름 홈플러스 잠실점", representative_review="증명사진 잘 찍어주세요")
    assert not is_food_place(name="KT 오빠통신 홈플러스 잠실점")
    assert is_food_place(name="삼청동식탁 홈플러스 잠실점", representative_review="맛있게 잘 먹었습니다.")
    assert is_food_place(name="북촌손만두 홈플러스 잠실점")
    assert is_food_place(name="테루카츠 홈플러스 잠실점")
    assert is_food_place(name="어라운드홈 홈플러스 잠실점")


def test_is_food_place_excludes_produce_and_beauty_cafe() -> None:
    assert not is_food_place(
        name="총각네야채가게 장미상가점",
        representative_review="과일 맛집입니다 딸기가 엄청 싱싱하고 달아요",
        place_category=PlaceCategory.KOREAN,
    )
    assert not is_food_place(
        name="에르모소뷰티카페 롯데월드몰점",
        place_category=PlaceCategory.CAFE,
    )
    assert not is_food_place(name="양복점 방이점")
    assert not is_food_place(name="캐리박스 공유창고 잠실장미상가점")


def test_is_food_place_other_requires_food_signal() -> None:
    assert not is_food_place(
        name="MIP",
        place_category=PlaceCategory.OTHER,
    )
    assert is_food_place(
        name="토도로끼",
        representative_review="그럭저럭 먹을만 했음니다.",
        place_category=PlaceCategory.OTHER,
    )


def test_refine_category_from_store_name_when_menu_placeholder() -> None:
    place = Place(
        id="naver:dimdim",
        name="딤딤섬 롯데월드몰점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
    )
    assert refine_category(place) == PlaceCategory.CHINESE

    place = Place(
        id="naver:fish",
        name="싱싱활어횟집",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
    )
    assert refine_category(place) == PlaceCategory.KOREAN


def test_refine_category_from_review_keywords() -> None:
    place = Place(
        id="naver:3",
        name="정순함박 잠실 본점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
        representative_review="함박스테이크와 튀김함박이 유명한 일식 돈까스 맛집",
    )
    assert refine_category(place) == PlaceCategory.JAPANESE


def test_refine_category_chipotle_sandwich_not_korean() -> None:
    place = Place(
        id="naver:pantry12",
        name="팬트리12 롯데월드타워점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.KOREAN,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="폴드 비프 치폴레",
        representative_review=(
            "포켓 샌드위치가 핫하던데 시도해봤어요. "
            "빈달루 소스가 딱 소고기랑 잘 어울리는 인도커리 느낌"
        ),
    )
    assert refine_category(place) == PlaceCategory.WESTERN


def test_refine_category_casa_busano_coffee_menu_is_cafe() -> None:
    place = Place(
        id="naver:casa-busano",
        name="까사부사노 송파점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.WESTERN,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="부사노 크렘프레소",
        representative_review="샤케라또도 진짜 맛있구",
    )
    assert refine_category(place) == PlaceCategory.CAFE
    assert refine_place_type(place) == PlaceType.CAFE


def test_longest_keyword_wins_over_substring() -> None:
    review = "소고기 샌드위치가 맛있어요"
    assert guess_category(review, PlaceType.RESTAURANT) == PlaceCategory.WESTERN


def test_refine_category_craft_island_traga_todorokki() -> None:
    craft = Place(
        id="naver:craft",
        name="크래프트아일랜드 잠실점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
        representative_review="맥주 + 안주가 좋았던곳. 가볍게 한잔 추천 드려요.",
    )
    assert refine_category(craft) == PlaceCategory.WESTERN

    traga = Place(
        id="naver:traga",
        name="트라가 잠실점",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="점심 특선",
        representative_review="스페인 전문점. 뽈뽀, 깔라마리가 맛있어요.",
    )
    assert refine_category(traga) == PlaceCategory.WESTERN

    todorokki = Place(
        id="naver:todoro",
        name="토도로끼",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.OTHER,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_review="그럭저럭 먹을만 했음니다.",
    )
    assert refine_category(todorokki) == PlaceCategory.JAPANESE


def test_refine_category_remaining_other_escapes() -> None:
    cases = [
        (
            Place(
                id="naver:mahogany",
                name="마호가니 잠실점",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.OTHER,
                address="",
                lat=37.5,
                lng=127.1,
                source="naver_map",
                representative_menu="점심 특선",
                representative_review="미숫가루 팥빙수 맛있네요",
            ),
            PlaceCategory.DESSERT,
        ),
        (
            Place(
                id="naver:pf",
                name="피에프창 롯데월드몰점",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.OTHER,
                address="",
                lat=37.5,
                lng=127.1,
                source="naver_map",
                representative_menu="점심 특선",
                representative_review="향신료도 지나치지 않고 간도 적절했어요",
            ),
            PlaceCategory.CHINESE,
        ),
        (
            Place(
                id="naver:pingpong",
                name="핑퐁",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.OTHER,
                address="",
                lat=37.5,
                lng=127.1,
                source="naver_map",
                representative_menu="점심 특선",
                representative_review="일본식 중국요리 전문점. 마파두부, 야끼만두",
            ),
            PlaceCategory.CHINESE,
        ),
        (
            Place(
                id="naver:haemok",
                name="해목 롯데월드몰점",
                place_type=PlaceType.RESTAURANT,
                category=PlaceCategory.OTHER,
                address="",
                lat=37.5,
                lng=127.1,
                source="naver_map",
                representative_menu="점심 특선",
                representative_review="히츠마부시와 카이센동 그리고 기린생맥주",
            ),
            PlaceCategory.JAPANESE,
        ),
    ]
    for place, expected in cases:
        assert refine_category(place) == expected


def test_should_classify_as_cafe_by_menus() -> None:
    assert should_classify_as_cafe_by_menus(
        ["아메리카노", "카페라떼", "에스프레소", "크로플"]
    )
    assert should_classify_as_cafe_by_menus(
        ["아메리카노", "카페라떼", "파스타"]
    )
    assert not should_classify_as_cafe_by_menus(
        ["아메리카노", "파스타", "스테이크", "리조또"]
    )
    assert not should_classify_as_cafe_by_menus(["케이크", "마카롱", "쿠키"])
    coffee, meal = count_coffee_and_meal_menus(
        ["아메리카노", "카페라떼", "파스타", "크로플"]
    )
    assert coffee == 2
    assert meal == 1


def test_refine_category_cafe_when_meals_fewer_than_coffee() -> None:
    place = Place(
        id="naver:cafe-mix",
        name="모르는 카페",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.WESTERN,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="아메리카노 · 카페라떼 · 에스프레소",
    )
    menu_names = ["아메리카노", "카페라떼", "에스프레소", "크로플"]
    assert refine_category(place, menu_names=menu_names) == PlaceCategory.CAFE
    assert refine_place_type(place, menu_names=menu_names) == PlaceType.CAFE


def test_refine_category_stays_restaurant_when_meals_dominate() -> None:
    place = Place(
        id="naver:rest",
        name="브런치 레스토랑",
        place_type=PlaceType.RESTAURANT,
        category=PlaceCategory.WESTERN,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="아메리카노 · 파스타 · 스테이크 · 리조또",
    )
    menu_names = ["아메리카노", "파스타", "스테이크", "리조또"]
    assert refine_place_type(place, menu_names=menu_names) == PlaceType.RESTAURANT
    assert refine_category(place, menu_names=menu_names) == PlaceCategory.WESTERN


def test_refine_place_type_taco_booth_meal_only_escapes_cafe() -> None:
    place = Place(
        id="naver:2085916295",
        name="더타코부스 잠실스타점",
        place_type=PlaceType.CAFE,
        category=PlaceCategory.CAFE,
        address="",
        lat=37.5,
        lng=127.1,
        source="naver_map",
        representative_menu="올미트 파히타 · NY타코플래터 · 비리아 타코 (2PCS)",
        representative_review="비리아타코 풍미 너무 좋고 멕시코 풍미가 진짜 입안 가득",
    )
    menu_names = [
        "올미트 파히타",
        "NY타코플래터",
        "비리아 타코 (2PCS)",
        "까르네아사다 타코 (2PCS)",
        "감바스 타코 (2PCS)",
        "올미트 라이스 포케",
    ]
    assert refine_place_type(place, menu_names=menu_names) == PlaceType.RESTAURANT
    restaurant = place.model_copy(update={"place_type": PlaceType.RESTAURANT})
    assert refine_category(restaurant, menu_names=menu_names) == PlaceCategory.WESTERN


def test_is_food_place_keeps_classified_restaurants() -> None:
    assert is_food_place(
        name="정순함박",
        place_category=PlaceCategory.JAPANESE,
    )
    assert is_food_place(
        name="모르는 식당",
        category_text="음식점>한식>백반",
        business_category="restaurant",
    )
