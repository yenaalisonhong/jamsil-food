"""맛집·카페 세부 유형 분류."""

from __future__ import annotations

import re

from models.place import Place, PlaceCategory, PlaceType
from services.place_defaults import is_generic_menu

_CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], PlaceCategory]] = [
    (
        (
            "한식",
            "한정식",
            "국밥",
            "찌개",
            "삼겹",
            "갈비",
            "백반",
            "냉면",
            "설렁탕",
            "삼계",
            "순대",
            "칼국수",
            "장칼",
            "만두",
            "한우",
            "도시락",
            "곱창",
            "닭갈비",
            "비빔밥",
            "쌈밥",
            "고깃",
            "족발",
            "보쌈",
            "전복",
            "샤브",
            "떡갈비",
            "밥상",
            "육회",
            "뭉티기",
            "국수",
            "전골",
            "찜",
            "백숙",
            "감자탕",
            "부대찌개",
            "제육",
            "불고기",
            "비빔",
            "쭈꾸미",
            "아구",
            "해물",
            "조개",
            "생선",
            "삼대국수",
            "쌀국수",
            "뼈해장",
            "해장",
            "순두부",
            "닭볶",
            "막창",
            "돼지",
            "식탁",
            "뚝배기",
            "전통주",
            "막걸리",
            "가보자",
            "도야지",
            "어묵",
            "야채",
            "편백",
            "만옥",
            "수하동",
            "연낙",
            "새벽",
            "육회",
            "모둠",
            "숯불",
            "횟집",
            "활어",
            "복국",
            "고기",
            "아구찜",
            "감자탕",
            "전통주",
            "막걸리",
            "구술",
            "동화고옥",
            "송추",
            "가마골",
            "갈비찜",
            "갈비탕",
            "모던눌랑",
            "어양",
            "쌀국수",
            "포시애틀",
            "회집",
            "어부",
            "횟집",
            "보승회관",
            "방이옥",
            "송돝",
            "한돈",
            "합탕",
            "포차",
            "호시카이",
            "지리탕",
            "우거지",
            "스넥",
            "명동",
        ),
        PlaceCategory.KOREAN,
    ),
    (
        ("중식", "중국", "짜장", "짬뽕", "마라", "훠궈", "양꼬치", "마라탕", "딤섬", "딤딤", "탕후루", "마파", "만두", "완탕", "잡채", "딘타이펑", "우육면", "시추안", "사천", "핑퐁", "피에프창", "만리장", "칸톤", "북경오리", "반점", "딩딤", "차알", "강호", "야끼만두", "마파두부", "중국요리", "홍콩식", "꿔바로우", "북경", "마르르", "춘선"),
        PlaceCategory.CHINESE,
    ),
    (
        (
            "일식",
            "일본",
            "초밥",
            "스시",
            "라멘",
            "돈카츠",
            "돈까스",
            "우동",
            "덮밥",
            "카츠",
            "이자카야",
            "야키",
            "가라아게",
            "오므라이스",
            "텐동",
            "규동",
            "카레",
            "curry",
            "함박",
            "함박스테이크",
            "롤",
            "사시미",
            "나베",
            "소바",
            "치마오",
            "가츠동",
            "연어",
            "참치",
            "모밀",
            "정순",
            "히츠노야",
            "라멘",
            "토마토",
            "이자카",
            "사케동",
            "가라아케",
            "캘리포니아",
            "우규",
            "크루스티",
            "낙지",
            "토도",
            "정돈",
            "토오코",
            "니시카",
            "우츄진",
            "간코",
            "코바치",
            "라멘야",
            "히츠마부시",
            "히츠",
            "해목",
            "마키노",
            "돈부리",
            "카이센동",
            "세이류",
            "시선",
            "띠목",
            "토도로끼",
            "오마카세",
            "스키야키",
            "야키니쿠",
            "사바",
            "오뎅",
            "사케",
            "사루",
            "이로",
        ),
        PlaceCategory.JAPANESE,
    ),
    (
        (
            "양식",
            "이탈",
            "파스타",
            "스테이크",
            "브런치",
            "타코",
            "멕시칸",
            "멕시코",
            "치폴레",
            "chipotle",
            "부리토",
            "샌드위치",
            "포켓",
            "폴드",
            "랩",
            "wrap",
            "샐러드",
            "샐러디",
            "버섯",
            "리조또",
            "그릴",
            "바베큐",
            "bbq",
            "비스트로",
            "까사",
            "뵈르하우스",
            "홍콩",
            "이탈리아",
            "빠에야",
            "파에야",
            "트라가",
            "애슐리",
            "런치",
            "갈릭",
            "빌즈",
            "피제리아",
            "오스테리아",
            "라코스트",
            "슈타인",
            "팬케이크",
            "브런치",
            "크래프트",
            "craft",
            "수제맥주",
            "펍",
            "pub",
            "호프",
            "바이더레이크",
            "페어링",
            "라세느",
            "사이드쇼",
            "sideshow",
            "이태리",
            "프렌치",
            "프렌치토스트",
            "스페인",
            "뽈뽀",
            "깔라마리",
            "타파스",
            "tapas",
            "비프",
            "스테이",
            "텍사스",
            "멜팅소울",
            "JBout",
            "jbout",
            "발리",
            "stay",
            "시그니엘",
            "라티튜드",
            "아그라",
            "indian",
            "치즈",
            "라운지",
            "마노",
        ),
        PlaceCategory.WESTERN,
    ),
    (
        ("분식", "떡볶이", "김밥", "라면", "두끼", "뷔페", "떡볶", "쫄면", "순대", "튀김", "청년다방", "마리짱", "마리왕"),
        PlaceCategory.BUNSIK,
    ),
    (
        (
            "패스트",
            "버거",
            "치킨",
            "햄버거",
            "치킹",
            "뿜치",
            "맥도날드",
            "맥너겟",
            "버거킹",
            "롯데리아",
            "모스버거",
            "kfc",
            "bbq",
            "bhc",
            "교촌",
            "굽네",
            "치맥",
            "피자",
            "페페로니",
            "pepperoni",
            "파파존스",
            "도미노",
            "서브웨이",
            "맘스터치",
            "네네",
            "픽스",
            "감자튀김",
            "핫도그",
            "타코벨",
            "생활맥주",
            "데일리픽스",
            "이삭",
            "토스트",
            "통닭",
            "써브웨이",
            "subway",
            "퀴즈노스",
            "치킨마루",
            "굽네치킨",
            "페리카나",
            "까페",
        ),
        PlaceCategory.FAST_FOOD,
    ),
    (
        (
            "디저트",
            "베이커리",
            "케이크",
            "빵집",
            "마카롱",
            "도넛",
            "와플",
            "빙수",
            "호두",
            "크로플",
            "베이글",
            "브런치",
            "레터링",
            "타르트",
            "슈크림",
            "크로와상",
            "제과",
            "쿠키",
            "아이스크림",
            "젤라또",
            "호떡",
            "붕어빵",
            "고망고",
            "래빗",
            "복호두",
            "요거트",
            "크림",
            "콜드브루",
            "크로아상",
            "쿠키",
            "팥빙수",
            "빙수",
            "노티드",
            "파리바게뜨",
            "바게뜨",
            "뚜레쥬르",
            "마호가니",
            "라클로슈",
            "로이즈",
            "한정선",
            "팥빙수",
            "미숫가루",
            "슈가",
            "마카롱",
            "티라미수",
            "에클레어",
            "슈톨렌",
            "킴스델리",
            "베이글",
        ),
        PlaceCategory.DESSERT,
    ),
    (
        (
            "카페",
            "커피",
            "coffee",
            "스타벅스",
            "이디야",
            "투썸",
            "메가커피",
            "빽다방",
            "컴포즈",
            "mgc",
            "공차",
            "밀크티",
            "블루보틀",
            "라떼",
            "아메리카노",
            "에스프레소",
            "티하우스",
            "차공간",
            "드립",
            "리사르",
            "선호커피",
            "바리스타",
            "티룸",
            "로스터리",
            "로스터",
            "콜드브루",
            "텐퍼센트",
            "매머드",
            "더벤티",
            "커피빈",
            "coffeebean",
            "하삼동",
            "ddd",
            "파이브브루잉",
            "브루잉",
            "시트러스",
            "주스",
            "스무디",
            "티하우스",
        ),
        PlaceCategory.CAFE,
    ),
]

_FOOD_BUSINESS_CATEGORIES: frozenset[str] = frozenset(
    {"restaurant", "cafe", "bar", "pub", "bakery", "food"}
)

_NON_FOOD_BUSINESS_CATEGORIES: frozenset[str] = frozenset(
    {
        "drugstore",
        "convenience",
        "retail",
        "shopping",
        "beauty",
        "education",
        "medical",
        "finance",
        "travel",
        "service",
        "photo",
        "print",
        "laundry",
        "telecom",
        "electronics",
        "furniture",
        "clothing",
        "sports",
        "parking",
        "hotel",
        "motel",
    }
)

_QUERY_HINTS: list[tuple[str, PlaceCategory]] = [
    ("한식", PlaceCategory.KOREAN),
    ("중식", PlaceCategory.CHINESE),
    ("일식", PlaceCategory.JAPANESE),
    ("양식", PlaceCategory.WESTERN),
    ("분식", PlaceCategory.BUNSIK),
    ("치킨", PlaceCategory.FAST_FOOD),
    ("피자", PlaceCategory.FAST_FOOD),
    ("패스트푸드", PlaceCategory.FAST_FOOD),
    ("카페", PlaceCategory.CAFE),
    ("커피", PlaceCategory.CAFE),
    ("디저트", PlaceCategory.DESSERT),
    ("베이커리", PlaceCategory.DESSERT),
    ("브런치", PlaceCategory.CAFE),
    ("맛집", PlaceCategory.OTHER),
]

_NON_FOOD_CAFE_NAME_MARKERS: tuple[str, ...] = (
    "프린트카페",
    "스터디카페",
    "독서카페",
    "보드카페",
    "무인카페",
    "뷰티카페",
    "뷰티 카페",
)

_NON_FOOD_CATEGORY_MARKERS: tuple[str, ...] = (
    "뷰티",
    "화장품",
    "미용",
    "네일",
    "헤어",
    "이발",
    "학원",
    "교육",
    "어학",
    "교실",
    "의료",
    "병원",
    "의원",
    "치과",
    "약국",
    "한의",
    "부동산",
    "금융",
    "은행",
    "보험",
    "생활편의",
    "문구",
    "편의점",
    "마트",
    "슈퍼",
    "통신",
    "휴대폰",
    "전자",
    "세탁",
    "수리",
    "주차",
    "공영",
    "스포츠용품",
    "의류",
    "패션",
    "동물",
    "반려",
    "숙박",
    "모텔",
    "화장실",
    "공중화장실",
    "편집",
    "프린트",
    "여행",
    "사진",
    "인쇄",
    "가전",
    "가구",
    "문화센터",
    "유통",
    "대형마트",
    "쇼핑",
    "스튜디오",
    "워크룸",
    "키즈카페",
    "놀이",
    "공유오피스",
)

_NON_FOOD_NAME_MARKERS: tuple[str, ...] = (
    "올리브영",
    "올영",
    "문구",
    "화장실",
    "학원",
    "교실",
    "어학원",
    "영어교실",
    "네일",
    "미용실",
    "헤어샵",
    "이발소",
    "바버샵",
    "약국",
    "안경",
    "부동산",
    "세탁",
    "휴대폰",
    "주차장",
    "종합상가",
    "편집샵",
    "프린트샵",
    "치과",
    "의원",
    "한의원",
    "은행",
    "다이소",
    "교보문고",
    "영풍문고",
    "GS25",
    "세븐일레븐",
    "이마트24",
    "CU ",
    "KT ",
    "SKT",
    "LG유플러스",
    "후지필름",
    "상상블럭",
    "어라운드홈",
    "아이피아",
    "월드크리닝",
    "하나투어",
    "아모레퍼시픽",
    "코인워시",
    "뽀송뽀송",
    "문화센터",
    "증명사진",
    "사진관",
    "인쇄",
    "프린트",
    "복사",
    "통신",
    "오빠통신",
    "핸드폰",
    "가전",
    "가구",
    "정관장",
    "임시휴업",
    "워크룸",
    "스터디룸",
    "키즈카페",
    "ATM",
    "코스트코",
    "트레이더스",
    "노브랜드",
    "리파인",
    "렌탈",
    "피부관리",
    "왁싱",
    "속눈썹",
    "골프연습",
    "헬스",
    "필라테스",
    "요가",
    "PC방",
    "노래방",
    "코인노래",
    "세차",
    "주유소",
    "자동차",
    "정비",
    "타이어",
    "렌터카",
    "보험",
    "증권",
    "세무",
    "법률",
    "공인중개",
    "이사",
    "청소",
    "AS센터",
    "애플스토어",
    "삼성스토어",
    "전자랜드",
    "하이마트",
    "영어학원",
    "수학학원",
    "피아노",
    "태권도",
    "유치원",
    "어린이집",
    "편의점",
    "야채가게",
    "과일가게",
    "정육점",
    "수산마트",
    "양복점",
    "공유창고",
    "사업협회",
    "관리소",
    "홀딩스",
    "여행사",
    "전철상가",
    "더샵",
    "뷰티카페",
)

_MALL_ANCHOR_MARKERS: tuple[str, ...] = (
    "홈플러스",
    "이마트",
    "롯데마트",
    "코스트코",
)

_MALL_FOOD_NAME_MARKERS: tuple[str, ...] = (
    "식탁",
    "식당",
    "푸드",
    "맛집",
    "카페",
    "커피",
    "베이커리",
    "분식",
    "치킨",
    "피자",
    "버거",
    "국수",
    "백반",
    "초밥",
    "돈까스",
    "떡볶이",
    "김밥",
    "순대",
    "고기",
    "삼겹",
    "갈비",
    "회",
    "횟집",
    "호프",
    "술집",
    "주점",
    "이자카야",
    "파스타",
    "스테이크",
    "브런치",
    "디저트",
    "케이크",
    "빵",
    "아이스크림",
    "뷔페",
    "푸드코트",
)

_MALL_NON_FOOD_SUFFIXES: tuple[str, ...] = (
    "문화센터",
    "임시휴업",
)

_MALL_NON_FOOD_BRANDS: tuple[str, ...] = (
    "후지필름",
    "상상블럭",
    "어라운드홈",
    "아이피아",
    "월드크리닝",
    "하나투어",
    "아모레퍼시픽",
    "아모레",
    "KT",
    "코인워시",
    "뽀송",
    "정관장",
    "노브랜드",
)

_NON_FOOD_REVIEW_MARKERS: tuple[str, ...] = (
    "증명사진",
    "사진 찍",
    "사진을 찍",
    "인쇄",
    "복사",
    "출력",
    "세탁",
    "코인워시",
    "드라이클리닝",
    "휴대폰",
    "개통",
    "통신",
    "핸드폰",
    "요금제",
    "화장품",
    "스킨케어",
    "향수",
    "문화센터",
    "강좌",
    "수강",
    "학원",
    "레슨",
    "여행 상담",
    "패키지 여행",
    "가전",
    "가구",
    "인테리어",
    "렌탈",
    "주차",
    "세차",
    "정비",
    "AS ",
    "수리",
    "병원",
    "진료",
    "치료",
    "처방",
    "네일",
    "속눈썹",
    "왁싱",
    "헤어컷",
    "펌 ",
    "염색",
    "마트",
    "장 보",
    "장봐",
    "쇼핑",
    "할인쿠폰",
    "보너스쿠폰",
    "임시휴업",
    "영업 중지",
    "예쁜 옷",
    "의류",
)

_FOOD_REVIEW_MARKERS: tuple[str, ...] = (
    "맛있",
    "맛나",
    "맛집",
    "먹었",
    "먹고",
    "먹으",
    "먹을",
    "식사",
    "메뉴",
    "음식",
    "요리",
    "국물",
    "양념",
    "사이드",
    "안주",
    "디저트",
    "커피",
    "라떼",
    "케이크",
    "버거",
    "치킨",
    "피자",
    "고기",
    "회식",
    "점심",
    "저녁",
    "브런치",
    "와인",
    "맥주",
    "술",
    "재방문",
    "또 올",
    "또 방문",
)

_CAFE_NAME_MARKERS: tuple[str, ...] = (
    "카페",
    "커피",
    "coffee",
    "베이커리",
    "디저트",
    "스타벅스",
    "이디야",
    "투썸",
    "메가커피",
    "빽다방",
    "컴포즈",
    "공차",
    "블루보틀",
    "MGC",
    "mgc",
)

_DESSERT_SHOP_MARKERS: tuple[str, ...] = (
    "케이크",
    "베이커리",
    "디저트",
    "도넛",
    "마카롱",
    "요거트",
    "호떡",
    "베이글",
    "래빗",
    "노티드",
    "빙수",
    "아이스크림",
    "크로플",
    "와플",
    "타르트",
    "쿠키",
    "크로아상",
    "고망고",
    "복호두",
)

_BAKERY_NAME_MARKERS: tuple[str, ...] = (
    "파리바게뜨",
    "뚜레쥬르",
    "성심당",
    "폴바셋",
    "탐앤탐스",
    "할리스",
)

_CAFE_MENU_MARKERS: tuple[str, ...] = (
    "아메리카노",
    "에스프레소",
    "프레소",
    "espresso",
    "라떼",
    "latte",
    "카페라떼",
    "콜드브루",
    "cold brew",
    "샤케라또",
    "shakerato",
    "카푸치노",
    "cappuccino",
    "마끼아또",
    "macchiato",
    "플랫화이트",
    "flat white",
    "드립커피",
    "핸드드립",
    "크렘프레소",
    "슈페너",
    "아포가토",
    "디카페인",
    "콘파냐",
    "리에토",
    "밀크티",
    "버블티",
    "에이드",
    "ade",
    "스무디",
    "smoothie",
    "프라푸",
    "frappe",
    "티라떼",
    "tea",
    "공차",
    "버블",
    "콤부차",
    "녹차",
    "홍차",
    "우롱",
    "히비스커스",
    "초콜릿라떼",
    "모카",
    "mocha",
    "바닐라라떼",
    "카페모카",
    "더치",
)

_DESSERT_MENU_MARKERS: tuple[str, ...] = (
    "케이크",
    "마카롱",
    "쿠키",
    "타르트",
    "크로플",
    "와플",
    "빙수",
    "아이스크림",
    "젤라또",
    "gelato",
    "도넛",
    "베이글",
    "크로아상",
    "슈크림",
    "에클레어",
    "휘낭시에",
    "스콘",
    "브라우니",
    "요거트",
    "빵",
    "디저트",
)

_MEAL_MENU_MARKERS: tuple[str, ...] = (
    "국밥",
    "찌개",
    "백반",
    "삼겹",
    "갈비",
    "고기",
    "정식",
    "덮밥",
    "파스타",
    "스테이크",
    "버거",
    "짜장",
    "짬뽕",
    "초밥",
    "돈까스",
    "돈카츠",
    "라멘",
    "우동",
    "떡볶이",
    "김밥",
    "피자",
    "샌드위치",
    "브런치",
    "리조또",
    "볶음밥",
    "비빔밥",
    "탕수육",
    "마라",
    "훠궈",
    "냉면",
    "칼국수",
    "국수",
    "만두",
    "탕",
    "찜",
    "구이",
    "볶음",
    "튀김",
    "스프",
    "샐러드",
    "가츠",
    "카츠",
    "회",
    "사시미",
    "육회",
    "족발",
    "보쌈",
    "치킨",
    "핫도그",
    "부리토",
    "타코",
    "빠에야",
    "리코타",
    "오믈렛",
    "오므라이스",
    "함박",
    "카레",
    "나베",
    "전골",
    "곱창",
    "막창",
    "순대",
    "쭈꾸미",
    "해물",
    "조개",
    "생선",
    "밥",
    "면",
    "피자",
    "토스트",
)


def _is_cafe_menu(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CAFE_MENU_MARKERS)


def _is_coffee_menu_item(text: str) -> bool:
    return _is_cafe_menu(text)


def _is_dessert_menu_item(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _DESSERT_MENU_MARKERS)


def _is_meal_menu_item(text: str) -> bool:
    if _is_coffee_menu_item(text) or _is_dessert_menu_item(text):
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _MEAL_MENU_MARKERS):
        return True
    from_menu = classify_from_menu(text, PlaceType.RESTAURANT)
    return from_menu not in {
        None,
        PlaceCategory.CAFE,
        PlaceCategory.DESSERT,
        PlaceCategory.OTHER,
    }


def count_coffee_and_meal_menus(menu_names: list[str]) -> tuple[int, int]:
    """메뉴명 목록에서 커피·음료 메뉴 수와 식사 메뉴 수를 셉니다."""
    coffee = 0
    meal = 0
    for raw in menu_names:
        name = str(raw or "").strip()
        if not name:
            continue
        if _is_coffee_menu_item(name):
            coffee += 1
        elif _is_meal_menu_item(name):
            meal += 1
    return coffee, meal


def should_classify_as_cafe_by_menus(menu_names: list[str]) -> bool:
    """식사 메뉴가 없거나 커피 메뉴보다 적으면 카페로 봅니다."""
    coffee, meal = count_coffee_and_meal_menus(menu_names)
    if coffee == 0:
        return False
    return meal == 0 or meal < coffee


def _menu_names_from_parts(*parts: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for chunk in re.split(r"\s*·\s*", part or ""):
            for piece in chunk.split("/"):
                for segment in piece.split(","):
                    name = segment.strip()
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)
    return names


def _is_mall_non_food(name: str) -> bool:
    """대형마트·백화점 내 비음식 매장 여부."""
    if "홈플러스" in name and not any(m in name for m in _MALL_FOOD_NAME_MARKERS):
        if re.search(r"홈플러스\s*[^\s]*점", name) and "식탁" not in name:
            return True

    if not any(anchor in name for anchor in _MALL_ANCHOR_MARKERS):
        return False

    if any(brand in name for brand in _MALL_NON_FOOD_BRANDS):
        return True
    if any(suffix in name for suffix in _MALL_NON_FOOD_SUFFIXES):
        return True
    if any(m in name for m in _MALL_FOOD_NAME_MARKERS):
        return False
    if re.search(r"(홈플러스|이마트|롯데마트|코스트코)\s*[^\s]*점", name):
        return True
    return False


def _has_food_signal(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t).lower()
    if not combined.strip():
        return False
    if _match_keywords(combined) is not None:
        return True
    return any(marker in combined for marker in _FOOD_REVIEW_MARKERS)


def _is_retail_grocery_shop(name: str) -> bool:
    """과일·야채·정육 등 식자재 소매점(식당 아님)."""
    lowered = name.replace(" ", "")
    retail_hints = ("야채", "과일", "정육", "수산", "청과", "채소")
    if not any(hint in lowered for hint in retail_hints):
        return False
    if any(token in lowered for token in ("가게", "마트", "상회", "직판", "시장")):
        return True
    return lowered.endswith("청과") or lowered.endswith("정육")


def _is_non_food_hint(name: str, review: str = "", category_text: str = "") -> bool:
    if any(marker in name for marker in _NON_FOOD_CAFE_NAME_MARKERS):
        return True
    if _is_retail_grocery_shop(name):
        return True
    if _is_mall_non_food(name):
        return True
    hint = f"{name} {review[:200]} {category_text}"
    if any(marker in hint for marker in _NON_FOOD_NAME_MARKERS):
        return True
    if review and any(marker in review for marker in _NON_FOOD_REVIEW_MARKERS):
        return True
    if category_text:
        if any(marker in category_text for marker in _NON_FOOD_CATEGORY_MARKERS):
            if not any(
                food in category_text for food in ("음식점", "카페", "베이커리", "술집", "주점")
            ):
                return True
    return False


def _category_allowed(category: PlaceCategory, place_type: PlaceType) -> bool:
    if place_type == PlaceType.CAFE:
        return category in {PlaceCategory.CAFE, PlaceCategory.DESSERT}
    if place_type == PlaceType.RESTAURANT:
        return category not in {PlaceCategory.CAFE, PlaceCategory.DESSERT}
    return True


def _split_menu_parts(menu: str) -> list[str]:
    """'돈까스 정식 · 우동' / '한정식 / 제육볶음' 형태를 메뉴 조각으로 나눕니다."""
    parts: list[str] = []
    for chunk in re.split(r"\s*·\s*", menu):
        chunk = chunk.strip()
        if not chunk:
            continue
        for segment in chunk.split("/"):
            for piece in segment.split(","):
                piece = piece.strip()
                if piece:
                    parts.append(piece)
    return parts


def classify_from_menu(
    menu: str,
    place_type: PlaceType = PlaceType.RESTAURANT,
) -> PlaceCategory | None:
    """대표 메뉴(메인 디시) 이름으로 PlaceCategory를 추정합니다."""
    menu = (menu or "").strip()
    if not menu or is_generic_menu(menu):
        return None

    parts = [menu, *_split_menu_parts(menu)]
    if any(_is_cafe_menu(part) for part in parts):
        return PlaceCategory.CAFE

    best_len = 0
    best_category: PlaceCategory | None = None
    for text in parts:
        lowered = text.lower()
        for keywords, category in _CATEGORY_KEYWORDS:
            for keyword in keywords:
                if keyword in lowered and len(keyword) > best_len:
                    best_len = len(keyword)
                    best_category = category
    return best_category


def _match_category_segments(category_text: str) -> PlaceCategory | None:
    """Naver '음식점>카페,디저트'에서 앞쪽 세그먼트를 우선 매칭합니다."""
    if not category_text:
        return None
    for chunk in category_text.split(">"):
        for segment in chunk.split(","):
            matched = _match_keywords(segment.strip())
            if matched is not None:
                return matched
    return None


def _match_keywords(text: str) -> PlaceCategory | None:
    """가장 긴 키워드 매칭을 우선합니다 (예: '소고기' 안의 '고기' 오매칭 방지)."""
    lowered = text.lower()
    best_len = 0
    best_category: PlaceCategory | None = None
    for keywords, category in _CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in lowered and len(keyword) > best_len:
                best_len = len(keyword)
                best_category = category
    return best_category


def _normalize_category_text(category_text: str) -> str:
    """Naver '음식점>한식>백반' 형식을 키워드 매칭용 문자열로 펼칩니다."""
    if not category_text:
        return ""
    parts: list[str] = []
    for chunk in category_text.split(">"):
        parts.extend(segment.strip() for segment in chunk.split(",") if segment.strip())
    return " ".join(parts)


def is_food_place(
    *,
    name: str = "",
    category_text: str = "",
    business_category: str = "",
    representative_review: str = "",
    place_category: PlaceCategory | None = None,
) -> bool:
    """맛집·카페 추천 대상인 음식 업종인지 판별합니다."""
    review = (representative_review or "")[:240]

    if _is_non_food_hint(name, review, category_text):
        return False

    if place_category is not None and place_category != PlaceCategory.OTHER:
        return True

    business = business_category.lower().strip()
    if business:
        if business in _FOOD_BUSINESS_CATEGORIES:
            return True
        if business in _NON_FOOD_BUSINESS_CATEGORIES:
            return False
        return False

    category = category_text.strip()
    if category:
        if "음식점" in category or "카페" in category or "베이커리" in category:
            return True
        if any(marker in category for marker in _NON_FOOD_CATEGORY_MARKERS):
            return False
        first_segment = category.split(">")[0].strip()
        if first_segment not in {"음식점", "카페,디저트", "카페"}:
            return False

    if place_category == PlaceCategory.OTHER:
        return _has_food_signal(name, review)

    return True


def infer_place_type(
    *,
    name: str = "",
    category_text: str = "",
    business_category: str = "",
    default: PlaceType = PlaceType.RESTAURANT,
) -> PlaceType:
    """상호명·Naver 업종 정보로 맛집/카페 유형을 추정합니다."""
    business = business_category.lower().strip()
    if business == "cafe":
        return PlaceType.CAFE
    if business in {"restaurant", "bar", "pub"}:
        return PlaceType.RESTAURANT

    if any(marker in name for marker in _NON_FOOD_CAFE_NAME_MARKERS):
        return default

    if any(marker in name for marker in _BAKERY_NAME_MARKERS):
        return PlaceType.CAFE

    expanded = _normalize_category_text(category_text)
    combined = f"{expanded} {name}".lower()
    if _is_cafe_menu(expanded) or _is_cafe_menu(name):
        return PlaceType.CAFE
    if any(marker in combined for marker in _CAFE_NAME_MARKERS):
        return PlaceType.CAFE
    if any(marker in name for marker in _DESSERT_SHOP_MARKERS):
        return PlaceType.CAFE
    return default


def guess_category(
    category_text: str = "",
    place_type: PlaceType = PlaceType.RESTAURANT,
    *,
    name: str = "",
    search_query: str = "",
    business_category: str = "",
    review_text: str = "",
    menu_text: str = "",
) -> PlaceCategory:
    """카테고리 문자열·대표메뉴·상호명·리뷰로 PlaceCategory를 추정합니다."""
    place_type = infer_place_type(
        name=name,
        category_text=f"{menu_text} {category_text}",
        business_category=business_category,
        default=place_type,
    )

    if menu_text:
        from_menu = classify_from_menu(menu_text, place_type)
        if from_menu is not None:
            return from_menu

    expanded_category = _normalize_category_text(category_text)
    segment_match = _match_category_segments(category_text)
    if segment_match is not None:
        matched = segment_match
        if _category_allowed(matched, place_type):
            return matched

    for text in (expanded_category, category_text, name, search_query, review_text):
        matched = _match_keywords(text)
        if matched is not None and _category_allowed(matched, place_type):
            return matched

    for hint, category in _QUERY_HINTS:
        combined_query = f"{search_query} {review_text}"
        if hint in combined_query and _category_allowed(category, place_type):
            return category

    if place_type == PlaceType.CAFE:
        return PlaceCategory.CAFE
    return PlaceCategory.OTHER


def refine_category(
    place: Place,
    *,
    search_query: str = "",
    menu_names: list[str] | None = None,
) -> PlaceCategory:
    """대표 메뉴·상호명·리뷰로 카테고리를 재분류합니다 (기타 탈출 우선)."""
    review_hint = (place.representative_review or "")[:240]
    query = search_query or review_hint
    menu = (place.representative_menu or "").strip()

    names = list(menu_names or [])
    if not names and menu and not is_generic_menu(menu):
        names = _menu_names_from_parts(menu)
    if should_classify_as_cafe_by_menus(names):
        return PlaceCategory.CAFE

    coffee, meal = count_coffee_and_meal_menus(names)
    meals_dominate_coffee = coffee > 0 and meal >= coffee

    if menu and not is_generic_menu(menu):
        from_menu = classify_from_menu(menu, place.place_type)
        if from_menu is not None and from_menu != PlaceCategory.OTHER:
            if from_menu in {PlaceCategory.CAFE, PlaceCategory.DESSERT}:
                if not meals_dominate_coffee:
                    return from_menu
            elif _category_allowed(from_menu, place.place_type):
                return from_menu

    if place.name:
        from_name = _match_keywords(place.name)
        if from_name is not None:
            if _category_allowed(from_name, place.place_type):
                return from_name
            if (
                place.category == PlaceCategory.OTHER
                and from_name in {PlaceCategory.CAFE, PlaceCategory.DESSERT}
            ):
                return from_name

    inferred = guess_category(
        "",
        place.place_type,
        name=place.name,
        search_query=query,
        review_text=review_hint,
        menu_text="",
    )
    if inferred != PlaceCategory.OTHER:
        return inferred

    if place.category != PlaceCategory.OTHER:
        return place.category
    return PlaceCategory.OTHER


def refine_place_type(
    place: Place,
    *,
    search_query: str = "",
    menu_names: list[str] | None = None,
) -> PlaceType:
    """맛집/카페 유형을 대표메뉴·리뷰로 재추정합니다."""
    review_hint = (place.representative_review or "")[:240]
    menu = (place.representative_menu or "").strip()
    names = list(menu_names or [])
    if not names and menu and not is_generic_menu(menu):
        names = _menu_names_from_parts(menu)
    if should_classify_as_cafe_by_menus(names):
        return PlaceType.CAFE

    coffee, meal = count_coffee_and_meal_menus(names)
    if meal > 0 and coffee == 0:
        return PlaceType.RESTAURANT
    meals_dominate_coffee = coffee > 0 and meal >= coffee
    if meals_dominate_coffee:
        return PlaceType.RESTAURANT

    if menu and not is_generic_menu(menu):
        from_menu = classify_from_menu(menu, PlaceType.CAFE)
        if from_menu in {PlaceCategory.CAFE, PlaceCategory.DESSERT}:
            return PlaceType.CAFE
    if any(marker in place.name for marker in _BAKERY_NAME_MARKERS):
        return PlaceType.CAFE
    combined = " ".join(part for part in (menu, review_hint, search_query) if part).strip()
    return infer_place_type(
        name=place.name,
        category_text=combined,
        business_category="",
        default=place.place_type,
    )
