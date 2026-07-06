"""
Naver Place 페이지 크롤러.

평점(visitorRating), 리뷰 수, 메뉴 가격, 개업일 등을 HTML/임베디드 JSON에서 추출합니다.
API 키 없이 pcmap.place.naver.com 페이지를 파싱합니다.

주의: 요청 간격을 두어 rate limit(429)을 피합니다.
"""

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx

from models.place import Place, PlaceType
from services.category_classifier import guess_category
from services.manual_data_store import ManualDataStore
from services.place_defaults import is_generic_menu
from utils.errors import PlaceProviderError
from utils.logger import get_logger
from utils.naver_urls import build_place_home_url, build_place_menu_url

logger = get_logger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://map.naver.com/",
}

_RATING_PATTERN = re.compile(
    r'"__typename":"VisitorReviewStats","avgRating":([\d.]+),"totalCount":(\d+)',
)
_REVIEW_SCORE_PATTERN = re.compile(r'"visitorReviewScore":([\d.]+)')
_REVIEW_COUNT_PATTERN = re.compile(r'"visitorReviewCount":(\d+)')
_MENU_BLOCK_PATTERN = re.compile(r'\{"__typename":"Menu"[^}]*\}')
_LIST_ITEM_PATTERN = re.compile(
    r'"id":"(\d+)"[^}]*?"name":"([^"]+)"[^}]*?"x":"([\d.]+)"[^}]*?"y":"([\d.]+)"',
)
_REVIEW_BODY_PATTERN = re.compile(
    r'"body":"((?:\\.|[^"\\]){10,400})"',
)
_APOLLO_STATE_PATTERN = re.compile(
    r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});\s*window\.",
    re.DOTALL,
)
_PHOTO_LABEL_DATE_PATTERN = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})\.?$")
_IMAGE_PATH_DATE_PATTERN = re.compile(
    r"https?://(?:ldb-phinf|naverbooking-phinf|video-phinf)\.pstatic\.net/(\d{8})_",
)
_OPENING_DATE_PATTERNS = (
    re.compile(r'"openingDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"'),
    re.compile(r'"openingDate"\s*:\s*(\d{4}-\d{2}-\d{2})'),
    re.compile(r'"openDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"'),
)
_NEW_OPENING_PATTERNS = (
    re.compile(r'"newOpening"\s*:\s*(true|false)'),
    re.compile(r'"newOpening"\s*:\s*(True|False)'),
)

# 식당 가격대 산출 시 제외할 음료·디저트·사이드 메뉴 키워드
_NON_MAIN_DISH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"커피|아메리카노|americano|에스프레소|espresso|라떼|latte|"
        r"카푸치노|cappuccino|모카|mocha|콜드브루|cold.?brew|드립",
        re.I,
    ),
    re.compile(
        r"주스|juice|쥬스|에이드|ade|스무디|smoothie|슬러시|slush|밀크티|milk.?tea",
        re.I,
    ),
    re.compile(r"콜라|cola|사이다|soda|환타|fanta|펩시|pepsi|탄산", re.I),
    re.compile(
        r"맥주|beer|생맥|소주|와인|wine|사케|sake|하이볼|highball|칵테일|cocktail|막걸리",
        re.I,
    ),
    re.compile(r"음료|drink|beverage|보리차|생수|이온음료", re.I),
    re.compile(r"홍차|녹차|허브티|아이스티|보이차|유자차|캐모마일", re.I),
    re.compile(r"케이크|cake|마카롱|macaron|디저트|dessert|타르트|tart", re.I),
    re.compile(r"아이스.?크림|ice.?cream|젤라[또토]|gelato|빙수", re.I),
    re.compile(r"쿠키|cookie|푸딩|pudding|파르페|parfait|마시멜로", re.I),
    re.compile(r"도넛|donut|도너츠|와플|waffle|브라우니|brownie", re.I),
    re.compile(r"스콘|scone|크로와상|croissant|팬케이크|pancake|마들렌", re.I),
    re.compile(r"공깃밥|공기밥|밥.?추가|추가.?밥|사리.?추가|사리추가", re.I),
    re.compile(r"\bside\b|사이드", re.I),
)


@dataclass(frozen=True)
class NaverListPlaceHit:
    """Naver Place 목록 검색 결과 한 건."""

    place_id: str
    name: str
    lng: float
    lat: float
    category_text: str = ""
    business_category: str = ""


@dataclass
class NaverPlaceDetail:
    """크롤링으로 추출한 Naver Place 상세 정보."""

    rating: float | None = None
    review_count: int | None = None
    price_per_person_krw: int | None = None
    price_range_min_krw: int | None = None
    price_range_max_krw: int | None = None
    representative_menu: str | None = None
    representative_review: str | None = None
    representative_reviews: list[str] = field(default_factory=list)
    opened_at: date | None = None
    is_new_opening: bool = False
    menu_prices: list[int] = field(default_factory=list)


class NaverPlaceCrawler:
    """Naver Place 상세·메뉴·리뷰 페이지 크롤러."""

    def __init__(
        self,
        store: ManualDataStore | None = None,
        request_delay_sec: float = 1.0,
    ) -> None:
        self._store = store or ManualDataStore()
        self._delay = request_delay_sec
        self._last_request_at: float = 0.0

    def search_list_places(
        self,
        query: str,
        place_type: PlaceType,
        *,
        lng: float,
        lat: float,
    ) -> list[NaverListPlaceHit]:
        """
        Naver Place 목록 페이지에서 주변 장소를 추출합니다.
        """
        # pcmap의 cafe/list는 404 — 카페도 restaurant/list(또는 place/list)를 사용합니다.
        enc_query = urllib.parse.quote(query)
        url = (
            "https://pcmap.place.naver.com/restaurant/list"
            f"?query={enc_query}&x={lng}&y={lat}"
        )
        try:
            html = self._get_page(url)
        except PlaceProviderError as exc:
            logger.warning("Naver 목록 검색 실패 (query=%s): %s", query, exc)
            return []

        return self._parse_list_hits_from_html(html)

    @classmethod
    def _parse_list_hits_from_html(cls, html: str) -> list[NaverListPlaceHit]:
        hits: dict[str, NaverListPlaceHit] = {}
        state = cls._extract_apollo_state(html)
        if state:
            for key, value in state.items():
                if not key.startswith(
                    ("PlaceListBusinessesItem:", "RestaurantAdSummary:", "PlaceAdSummary:")
                ):
                    continue
                if not isinstance(value, dict):
                    continue
                place_id = value.get("id")
                name = value.get("name")
                if not place_id or not name or not str(place_id).isdigit():
                    continue
                try:
                    item_lng = float(value["x"])
                    item_lat = float(value["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                hits[str(place_id)] = NaverListPlaceHit(
                    place_id=str(place_id),
                    name=str(name),
                    lng=item_lng,
                    lat=item_lat,
                    category_text=str(value.get("category") or ""),
                    business_category=str(value.get("businessCategory") or ""),
                )

        for place_id, place_name, x_str, y_str in _LIST_ITEM_PATTERN.findall(html):
            if place_id in hits:
                continue
            try:
                hits[place_id] = NaverListPlaceHit(
                    place_id=place_id,
                    name=place_name,
                    lng=float(x_str),
                    lat=float(y_str),
                )
            except ValueError:
                continue
        return list(hits.values())

    def fetch_trending_new_openings(
        self,
        lat: float,
        lng: float,
        *,
        restaurant_query: str = "잠실 맛집",
        cafe_query: str = "잠실 카페",
    ) -> list[Place]:
        """
        Naver Place '요즘뜨는' 목록에서 newOpening=true 장소를 수집합니다.
        """
        seen_ids: set[str] = set()
        results: list[Place] = []

        for query, place_type in (
            (restaurant_query, PlaceType.RESTAURANT),
            (cafe_query, PlaceType.CAFE),
        ):
            url = self._build_trending_list_url(query, lng, lat, place_type)
            try:
                html = self._get_page(url)
            except PlaceProviderError as exc:
                logger.warning("Naver 요즘뜨는 목록 실패 (query=%s): %s", query, exc)
                continue

            for place in self._parse_new_openings_from_list_html(html, place_type):
                key = place.naver_place_id or place.id
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                results.append(place)

        logger.info("Naver 요즘뜨는 신규 오픈 %d건", len(results))
        return results

    @staticmethod
    def _build_trending_list_url(
        query: str,
        lng: float,
        lat: float,
        place_type: PlaceType,
    ) -> str:
        # 카페도 pcmap은 restaurant/list 엔드포인트를 사용합니다.
        enc_query = urllib.parse.quote(query)
        enc_rank = urllib.parse.quote("요즘뜨는")
        return (
            f"https://pcmap.place.naver.com/restaurant/list"
            f"?query={enc_query}&rank={enc_rank}&x={lng}&y={lat}"
        )

    @classmethod
    def _parse_new_openings_from_list_html(
        cls,
        html: str,
        default_place_type: PlaceType,
    ) -> list[Place]:
        state = cls._extract_apollo_state(html)
        if not state:
            return []

        places: list[Place] = []
        for key, value in state.items():
            if not isinstance(value, dict) or value.get("newOpening") is not True:
                continue
            if not key.startswith(
                ("PlaceListBusinessesItem:", "RestaurantAdSummary:", "PlaceAdSummary:")
            ):
                continue
            place = cls._apollo_list_item_to_place(value, default_place_type)
            if place is not None:
                places.append(place)
        return places

    @classmethod
    def _apollo_list_item_to_place(
        cls,
        item: dict[str, Any],
        default_place_type: PlaceType,
    ) -> Place | None:
        place_id = item.get("id")
        name = item.get("name")
        if not place_id or not name or not str(place_id).isdigit():
            return None

        try:
            lng = float(item["x"])
            lat = float(item["y"])
        except (KeyError, TypeError, ValueError):
            return None

        business_category = str(item.get("businessCategory") or "").lower()
        if business_category == "cafe":
            place_type = PlaceType.CAFE
        elif business_category in {"restaurant", "bar", "pub"}:
            place_type = PlaceType.RESTAURANT
        else:
            place_type = default_place_type

        category = guess_category(
            str(item.get("category") or ""),
            place_type,
            name=str(name),
            business_category=str(item.get("businessCategory") or ""),
        )
        image_blob = json.dumps(item, ensure_ascii=False)
        opened_candidates = cls._dates_from_image_urls(image_blob)
        opened_at = cls._pick_opening_date(opened_candidates) if opened_candidates else date.today()

        route_url = item.get("routeUrl")
        home_category = "restaurant"
        place_url = route_url or build_place_home_url(str(place_id), home_category)

        return Place(
            id=f"naver:{place_id}",
            name=str(name),
            place_type=place_type,
            category=category,
            address=item.get("roadAddress") or item.get("address") or "",
            lat=lat,
            lng=lng,
            rating=None,
            rating_source=None,
            review_count=None,
            price_per_person_krw=None,
            phone=item.get("phone") or item.get("virtualPhone"),
            url=place_url,
            source="naver_trending",
            naver_place_id=str(place_id),
            opened_at=opened_at,
        )

    def resolve_place_id_by_map_search(
        self,
        name: str,
        lat: float | None = None,
        lng: float | None = None,
        place_type: PlaceType = PlaceType.RESTAURANT,
    ) -> str | None:
        """Naver Place 목록 검색 페이지에서 place ID를 추출합니다."""
        query = urllib.parse.quote(name)
        url = f"https://pcmap.place.naver.com/restaurant/list?query={query}"
        try:
            html = self._get_page(url)
        except PlaceProviderError:
            return None

        best_id: str | None = None
        best_score = -1.0
        norm_target = re.sub(r"\s+", "", name.lower())

        for place_id, place_name, x_str, y_str in _LIST_ITEM_PATTERN.findall(html):
            norm_name = re.sub(r"\s+", "", place_name.lower())
            name_score = 1.0 if norm_target in norm_name or norm_name in norm_target else 0.5
            if lat is not None and lng is not None:
                try:
                    dist = self._haversine_m(lat, lng, float(y_str), float(x_str))
                    if dist > 800:
                        continue
                    score = name_score - dist / 1000
                except ValueError:
                    score = name_score
            else:
                score = name_score
            if score > best_score:
                best_score = score
                best_id = place_id

        return best_id

    @staticmethod
    def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        import math

        r = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def fetch_representative_menu(
        self,
        naver_place_id: str,
        place_type: PlaceType = PlaceType.RESTAURANT,
    ) -> str | None:
        """메뉴 페이지만 조회해 대표 메뉴(최대 3개)를 반환합니다."""
        if not naver_place_id.isdigit():
            return None

        category = "restaurant"
        try:
            menu_html = self._get_page(build_place_menu_url(naver_place_id, category))
            menus = self._extract_menu_items(menu_html)
            menu = self._format_representative_menu(menus)
            if not menu:
                return None

            cached = self._store.get_cached_detail(naver_place_id) or {}
            merged = dict(cached)
            merged["representative_menu"] = menu
            if menus:
                prices = self._menu_prices_for_range(menus, place_type)
                price_fields = self._price_fields_from_menus(menus, place_type)
                merged["menu_prices"] = prices
                merged["menu_items"] = [
                    {"name": name, "price": price, "recommend": recommend}
                    for name, price, recommend in menus
                ]
                if merged.get("price_per_person_krw") is None:
                    merged["price_per_person_krw"] = price_fields["price_per_person_krw"]
                if price_fields["price_range_min_krw"] is not None:
                    merged["price_range_min_krw"] = price_fields["price_range_min_krw"]
                    merged["price_range_max_krw"] = price_fields["price_range_max_krw"]
            self._store.set_cached_detail(naver_place_id, merged)
            return menu
        except PlaceProviderError as exc:
            logger.warning(
                "Naver Place 메뉴 조회 실패 (id=%s): %s", naver_place_id, exc
            )
            return None

    def fetch_detail(
        self,
        naver_place_id: str,
        place_type: PlaceType = PlaceType.RESTAURANT,
        *,
        light: bool = False,
    ) -> NaverPlaceDetail:
        """
        place ID로 상세 정보를 수집합니다.

        light=True이면 홈 페이지만 조회해 개업일·평점 위주로 보강합니다.
        """
        if not naver_place_id.isdigit():
            return NaverPlaceDetail()

        category = "restaurant"
        detail = NaverPlaceDetail()
        cached = self._store.get_cached_detail(naver_place_id)
        if cached:
            detail = self._detail_from_dict(cached)
            if not light:
                self._supplement_menu_if_needed(
                    detail, naver_place_id, category, place_type
                )
            has_review_data = bool(
                detail.representative_review or detail.representative_reviews
            )
            if (
                detail.opened_at is not None
                and detail.rating is not None
                and has_review_data
            ):
                return detail
            try:
                home_html = self._get_page(build_place_home_url(naver_place_id, category))
                self._apply_opening_from_html(detail, home_html, naver_place_id)
                if detail.rating is None:
                    detail.rating = self._extract_rating(home_html)
                if detail.review_count is None:
                    detail.review_count = self._extract_review_count(home_html)
                self._store.set_cached_detail(naver_place_id, self._detail_to_dict(detail))
            except PlaceProviderError as exc:
                logger.warning(
                    "Naver Place 개업일 보강 실패 (id=%s): %s", naver_place_id, exc
                )
            has_review_data = bool(
                detail.representative_review or detail.representative_reviews
            )
            if detail.rating is None:
                try:
                    review_url = (
                        f"https://pcmap.place.naver.com/{category}/{naver_place_id}/review/visitor"
                    )
                    review_html = self._get_page(review_url)
                    detail.rating = self._extract_rating(review_html)
                    if not has_review_data:
                        detail.representative_reviews = self._extract_review_texts(review_html)
                        detail.representative_review = (
                            detail.representative_reviews[0]
                            if detail.representative_reviews
                            else None
                        )
                    self._store.set_cached_detail(naver_place_id, self._detail_to_dict(detail))
                except PlaceProviderError as exc:
                    logger.warning(
                        "Naver Place 평점 보강 실패 (id=%s): %s", naver_place_id, exc
                    )
                has_review_data = bool(
                    detail.representative_review or detail.representative_reviews
                )
            if not light:
                self._supplement_menu_if_needed(
                    detail, naver_place_id, category, place_type
                )
            if has_review_data and detail.rating is not None:
                return detail
            if has_review_data and not light:
                return detail
            if light:
                try:
                    review_url = (
                        f"https://pcmap.place.naver.com/{category}/{naver_place_id}/review/visitor"
                    )
                    review_html = self._get_page(review_url)
                    detail.representative_reviews = self._extract_review_texts(review_html)
                    detail.representative_review = (
                        detail.representative_reviews[0]
                        if detail.representative_reviews
                        else None
                    )
                    if detail.rating is None:
                        detail.rating = self._extract_rating(review_html)
                    self._store.set_cached_detail(naver_place_id, self._detail_to_dict(detail))
                except PlaceProviderError as exc:
                    logger.warning(
                        "Naver Place 리뷰 보강 실패 (id=%s): %s", naver_place_id, exc
                    )
                return detail

        try:
            home_html = self._get_page(build_place_home_url(naver_place_id, category))
            detail.rating = self._extract_rating(home_html)
            detail.review_count = self._extract_review_count(home_html)
            self._apply_opening_from_html(detail, home_html, naver_place_id)

            if light:
                if detail.representative_review is None:
                    review_url = (
                        f"https://pcmap.place.naver.com/{category}/{naver_place_id}/review/visitor"
                    )
                    review_html = self._get_page(review_url)
                    detail.representative_reviews = self._extract_review_texts(review_html)
                    detail.representative_review = (
                        detail.representative_reviews[0]
                        if detail.representative_reviews
                        else None
                    )
                    if detail.rating is None:
                        detail.rating = self._extract_rating(review_html)
                self._store.set_cached_detail(naver_place_id, self._detail_to_dict(detail))
                return detail

            menu_html = self._get_page(build_place_menu_url(naver_place_id, category))
            menus = self._extract_menu_items(menu_html)
            if menus:
                detail.representative_menu = self._format_representative_menu(menus)
                price_fields = self._price_fields_from_menus(menus, place_type)
                detail.menu_prices = price_fields["menu_prices"] or []
                detail.price_per_person_krw = price_fields["price_per_person_krw"]
                detail.price_range_min_krw = price_fields["price_range_min_krw"]
                detail.price_range_max_krw = price_fields["price_range_max_krw"]

            if detail.representative_review is None:
                review_url = (
                    f"https://pcmap.place.naver.com/{category}/{naver_place_id}/review/visitor"
                )
                review_html = self._get_page(review_url)
                detail.representative_reviews = self._extract_review_texts(review_html)
                detail.representative_review = (
                    detail.representative_reviews[0] if detail.representative_reviews else None
                )
                if detail.rating is None:
                    detail.rating = self._extract_rating(review_html)

            cached_data = self._detail_to_dict(detail)
            if menus:
                cached_data["menu_items"] = [
                    {"name": name, "price": price, "recommend": recommend}
                    for name, price, recommend in menus
                ]
                cached_data["menu_prices"] = detail.menu_prices
            self._store.set_cached_detail(naver_place_id, cached_data)
        except PlaceProviderError as exc:
            logger.warning("Naver Place 크롤링 실패 (id=%s): %s", naver_place_id, exc)

        if not light:
            self._supplement_menu_if_needed(detail, naver_place_id, category, place_type)
        return detail

    def _supplement_menu_if_needed(
        self,
        detail: NaverPlaceDetail,
        naver_place_id: str,
        category: str,
        place_type: PlaceType,
    ) -> None:
        """캐시에 리뷰만 있고 메뉴가 비어 있을 때 메뉴 페이지를 보강합니다."""
        if not is_generic_menu(detail.representative_menu):
            return
        try:
            menu_html = self._get_page(build_place_menu_url(naver_place_id, category))
            menus = self._extract_menu_items(menu_html)
            if not menus:
                return
            detail.representative_menu = self._format_representative_menu(menus)
            price_fields = self._price_fields_from_menus(menus, place_type)
            detail.menu_prices = price_fields["menu_prices"] or []
            if detail.price_per_person_krw is None:
                detail.price_per_person_krw = price_fields["price_per_person_krw"]
            if detail.price_range_min_krw is None:
                detail.price_range_min_krw = price_fields["price_range_min_krw"]
                detail.price_range_max_krw = price_fields["price_range_max_krw"]
            cached_data = self._detail_to_dict(detail)
            cached_data["menu_items"] = [
                {"name": name, "price": price, "recommend": recommend}
                for name, price, recommend in menus
            ]
            cached_data["menu_prices"] = detail.menu_prices
            self._store.set_cached_detail(naver_place_id, cached_data)
        except PlaceProviderError as exc:
            logger.warning(
                "Naver Place 메뉴 보강 실패 (id=%s): %s", naver_place_id, exc
            )

    def _get_page(self, url: str, *, retries: int = 3) -> str:
        """Rate limit을 지키며 HTTP GET. 429 시 백오프 재시도."""
        last_error: PlaceProviderError | None = None
        for attempt in range(retries):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)

            try:
                with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                    response = client.get(url, headers=_BROWSER_HEADERS)
                    self._last_request_at = time.monotonic()

                    if response.status_code == 429:
                        wait = self._delay * (2 ** attempt) + 2.0
                        logger.warning(
                            "Naver rate limit (429), %.1fs 후 재시도 (%d/%d)",
                            wait,
                            attempt + 1,
                            retries,
                        )
                        time.sleep(wait)
                        last_error = PlaceProviderError("Naver rate limit (429)")
                        continue
                    if response.status_code >= 400:
                        raise PlaceProviderError(f"HTTP {response.status_code}")

                    return response.text
            except httpx.RequestError as exc:
                raise PlaceProviderError("Naver Place 네트워크 오류", cause=exc) from exc

        if last_error:
            raise last_error
        raise PlaceProviderError("Naver Place 요청 실패")

    @classmethod
    def _extract_rating(cls, html: str) -> float | None:
        match = _RATING_PATTERN.search(html)
        if match:
            rating = float(match.group(1))
            if rating > 0:
                return rating
        for pattern in (_REVIEW_SCORE_PATTERN, re.compile(r'"avgRating":([\d.]+)')):
            fallback = pattern.search(html)
            if fallback:
                rating = float(fallback.group(1))
                if rating > 0:
                    return rating
        state = cls._extract_apollo_state(html)
        if state:
            from_apollo = cls._extract_rating_from_apollo_nodes(state)
            if from_apollo is not None:
                return from_apollo
        return None

    @classmethod
    def _extract_rating_from_apollo_nodes(cls, state: dict[str, Any]) -> float | None:
        for value in state.values():
            if not isinstance(value, dict):
                continue
            if value.get("__typename") == "VisitorReviewStats":
                avg = value.get("avgRating")
                if avg is not None:
                    try:
                        rating = float(avg)
                        if rating > 0:
                            return rating
                    except (TypeError, ValueError):
                        pass
            score = value.get("visitorReviewScore")
            if score is not None:
                try:
                    rating = float(score)
                    if 0 < rating <= 5:
                        return rating
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_review_count(html: str) -> int | None:
        match = _RATING_PATTERN.search(html)
        if match:
            return int(match.group(2))
        match = _REVIEW_COUNT_PATTERN.search(html)
        return int(match.group(1)) if match else None

    @staticmethod
    def _apply_opening_from_html(
        detail: NaverPlaceDetail,
        html: str,
        place_id: str,
    ) -> None:
        is_new = NaverPlaceCrawler._extract_new_opening_flag(html, place_id)
        if is_new:
            detail.is_new_opening = True
        opened = NaverPlaceCrawler._extract_opening_date(html, place_id)
        if opened is not None:
            detail.opened_at = opened

    @staticmethod
    def _extract_apollo_state(html: str) -> dict[str, Any] | None:
        match = _APOLLO_STATE_PATTERN.search(html)
        if not match:
            return None
        try:
            state = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        return state if isinstance(state, dict) else None

    @staticmethod
    def _resolve_apollo_value(state: dict[str, Any], value: Any) -> Any:
        if isinstance(value, dict):
            if "__ref" in value:
                ref = value["__ref"]
                if ref in state:
                    return NaverPlaceCrawler._resolve_apollo_value(state, state[ref])
                return value
            return {
                key: NaverPlaceCrawler._resolve_apollo_value(state, item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [NaverPlaceCrawler._resolve_apollo_value(state, item) for item in value]
        return value

    @classmethod
    def _extract_place_detail_node(
        cls,
        html: str,
        place_id: str,
    ) -> dict[str, Any] | None:
        state = cls._extract_apollo_state(html)
        if not state:
            return None
        root = state.get("ROOT_QUERY")
        if not isinstance(root, dict):
            return None
        for key, value in root.items():
            if not key.startswith("placeDetail(") or place_id not in key:
                continue
            resolved = cls._resolve_apollo_value(state, value)
            return resolved if isinstance(resolved, dict) else None
        return None

    @staticmethod
    def _parse_label_date(raw: str | None) -> date | None:
        if not raw:
            return None
        match = _PHOTO_LABEL_DATE_PATTERN.match(str(raw).strip())
        if not match:
            return None
        year, month, day = (int(match.group(i)) for i in range(1, 4))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    @staticmethod
    def _dates_from_image_urls(text: str) -> list[date]:
        dates: list[date] = []
        for token in _IMAGE_PATH_DATE_PATTERN.findall(text):
            try:
                dates.append(date.fromisoformat(f"{token[:4]}-{token[4:6]}-{token[6:8]}"))
            except ValueError:
                continue
        return dates

    @classmethod
    def _collect_opening_date_candidates(
        cls,
        html: str,
        place_id: str,
        *,
        is_new_opening: bool,
    ) -> list[date]:
        if not is_new_opening:
            return []

        candidates: list[date] = []
        detail_node = cls._extract_place_detail_node(html, place_id)
        if detail_node:
            top_photos = detail_node.get("topPhotos")
            if isinstance(top_photos, dict):
                for item in top_photos.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    label_date = cls._parse_label_date(item.get("date"))
                    if label_date:
                        candidates.append(label_date)
                    origin = item.get("origin")
                    if isinstance(origin, str):
                        candidates.extend(cls._dates_from_image_urls(origin))

            for menu_image in detail_node.get("menuImages") or []:
                if isinstance(menu_image, dict):
                    url = menu_image.get("imageUrl")
                    if isinstance(url, str):
                        candidates.extend(cls._dates_from_image_urls(url))

            candidates.extend(cls._dates_from_image_urls(json.dumps(detail_node, ensure_ascii=False)))

        candidates.extend(cls._dates_from_image_urls(html))
        return candidates

    @staticmethod
    def _pick_opening_date(candidates: list[date], *, within_days: int = 120) -> date | None:
        if not candidates:
            return None
        today = date.today()
        earliest = min(candidates)
        cutoff = today - timedelta(days=within_days)
        if earliest > today:
            return today
        if earliest < cutoff:
            return None
        return earliest

    @classmethod
    def _extract_opening_date(cls, html: str, place_id: str | None = None) -> date | None:
        for pattern in _OPENING_DATE_PATTERNS:
            match = pattern.search(html)
            if match:
                return date.fromisoformat(match.group(1))

        if not place_id:
            return None

        is_new = cls._extract_new_opening_flag(html, place_id)
        if not is_new:
            return None

        candidates = cls._collect_opening_date_candidates(
            html,
            place_id,
            is_new_opening=True,
        )
        estimated = cls._pick_opening_date(candidates)
        if estimated is not None:
            return estimated

        return date.today()

    @classmethod
    def _extract_new_opening_flag(cls, html: str, place_id: str | None = None) -> bool:
        detail_node = cls._extract_place_detail_node(html, place_id) if place_id else None
        if isinstance(detail_node, dict) and detail_node.get("newOpening") is True:
            return True

        for pattern in _NEW_OPENING_PATTERNS:
            match = pattern.search(html)
            if match:
                return match.group(1).lower() == "true"
        return False

    @staticmethod
    def _decode_menu_name(name: str) -> str:
        if "\\u" in name or "\\" in name:
            try:
                return json.loads(f'"{name}"')
            except json.JSONDecodeError:
                return name.encode().decode("unicode_escape", errors="replace")
        return name

    @classmethod
    def _extract_menu_items(cls, html: str) -> list[tuple[str, int, bool]]:
        items: list[tuple[str, int, bool]] = []
        seen: set[str] = set()
        for block in _MENU_BLOCK_PATTERN.findall(html):
            name_match = re.search(r'"name":"([^"]+)"', block)
            price_match = re.search(r'"price":"(\d+)"', block)
            if not name_match or not price_match:
                continue
            try:
                name = cls._decode_menu_name(name_match.group(1))
                if name in seen:
                    continue
                seen.add(name)
                recommend = bool(re.search(r'"recommend":true', block))
                items.append((name, int(price_match.group(1)), recommend))
            except (json.JSONDecodeError, ValueError, UnicodeError):
                continue
        return items

    @staticmethod
    def _format_representative_menu(
        items: list[tuple[str, int, bool]],
        *,
        max_items: int = 3,
    ) -> str | None:
        if not items:
            return None
        recommended = [name for name, _, rec in items if rec]
        others = [name for name, _, rec in items if not rec]
        names: list[str] = []
        for name in recommended + others:
            if name in names:
                continue
            names.append(name)
            if len(names) >= max_items:
                break
        return " · ".join(names) if names else None

    @staticmethod
    def _decode_review_body(raw: str) -> str | None:
        try:
            text = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            text = raw.replace("\\n", " ").strip()
        text = re.sub(r"\s+", " ", text).strip()
        return text[:200] if text else None

    @classmethod
    def _extract_review_texts(cls, html: str, limit: int = 2) -> list[str]:
        texts: list[str] = []
        seen: set[str] = set()
        for match in _REVIEW_BODY_PATTERN.finditer(html):
            text = cls._decode_review_body(match.group(1))
            if not text or text in seen:
                continue
            seen.add(text)
            texts.append(text)
            if len(texts) >= limit:
                break
        return texts

    @classmethod
    def _extract_review_text(cls, html: str) -> str | None:
        texts = cls._extract_review_texts(html, limit=1)
        return texts[0] if texts else None

    @classmethod
    def _price_fields_from_menus(
        cls,
        menus: list[tuple[str, int, bool]],
        place_type: PlaceType,
    ) -> dict[str, int | list[int] | None]:
        prices = cls._menu_prices_for_range(menus, place_type)
        price_range = cls._price_range_from_prices(prices)
        return {
            "price_per_person_krw": cls._estimate_price_from_prices(prices),
            "price_range_min_krw": price_range[0] if price_range else None,
            "price_range_max_krw": price_range[1] if price_range else None,
            "menu_prices": prices,
        }

    @classmethod
    def _price_fields_from_menu_items(
        cls,
        menu_items: list[dict],
        place_type: PlaceType,
    ) -> dict[str, int | list[int] | None]:
        menus = [
            (str(item["name"]), int(item["price"]), bool(item.get("recommend")))
            for item in menu_items
            if item.get("name") and item.get("price") is not None
        ]
        return cls._price_fields_from_menus(menus, place_type)

    @staticmethod
    def _is_main_dish(name: str) -> bool:
        normalized = name.strip()
        if not normalized:
            return False
        return not any(pattern.search(normalized) for pattern in _NON_MAIN_DISH_PATTERNS)

    @classmethod
    def _menu_prices_for_range(
        cls,
        menus: list[tuple[str, int, bool]],
        place_type: PlaceType,
    ) -> list[int]:
        """식당은 메인 디시 가격만, 카페는 전체 메뉴 가격을 사용합니다."""
        if place_type == PlaceType.CAFE:
            return [price for _, price, _ in menus]
        main_prices = [price for name, price, _ in menus if cls._is_main_dish(name)]
        if main_prices:
            return main_prices
        return [price for _, price, _ in menus]

    @staticmethod
    def _price_range_from_prices(prices: list[int]) -> tuple[int, int] | None:
        lunch = [p for p in prices if 4_000 <= p <= 35_000]
        if not lunch:
            return None
        return min(lunch), max(lunch)

    @staticmethod
    def _estimate_price_from_menu(
        html: str,
        *,
        place_type: PlaceType = PlaceType.RESTAURANT,
    ) -> int | None:
        menus = NaverPlaceCrawler._extract_menu_items(html)
        if menus:
            prices = NaverPlaceCrawler._menu_prices_for_range(menus, place_type)
        else:
            prices = [int(p) for p in re.findall(r'"price":"(\d+)"', html)]
        return NaverPlaceCrawler._estimate_price_from_prices(prices)

    @staticmethod
    def _estimate_price_from_prices(prices: list[int]) -> int | None:
        lunch_range = [p for p in prices if 5_000 <= p <= 30_000]
        if not lunch_range:
            lunch_range = [p for p in prices if 4_000 <= p <= 35_000]
        if not lunch_range:
            return None
        lunch_range.sort()
        mid = len(lunch_range) // 2
        return lunch_range[mid]

    @staticmethod
    def _detail_to_dict(detail: NaverPlaceDetail) -> dict[str, Any]:
        return {
            "rating": detail.rating,
            "review_count": detail.review_count,
            "price_per_person_krw": detail.price_per_person_krw,
            "price_range_min_krw": detail.price_range_min_krw,
            "price_range_max_krw": detail.price_range_max_krw,
            "representative_menu": detail.representative_menu,
            "representative_review": detail.representative_review,
            "representative_reviews": detail.representative_reviews,
            "opened_at": detail.opened_at.isoformat() if detail.opened_at else None,
            "is_new_opening": detail.is_new_opening,
        }

    @staticmethod
    def _detail_from_dict(data: dict[str, Any]) -> NaverPlaceDetail:
        opened = data.get("opened_at")
        return NaverPlaceDetail(
            rating=data.get("rating"),
            review_count=data.get("review_count"),
            price_per_person_krw=data.get("price_per_person_krw"),
            price_range_min_krw=data.get("price_range_min_krw"),
            price_range_max_krw=data.get("price_range_max_krw"),
            representative_menu=data.get("representative_menu"),
            representative_review=data.get("representative_review"),
            representative_reviews=list(data.get("representative_reviews") or []),
            opened_at=date.fromisoformat(opened) if opened else None,
            is_new_opening=bool(data.get("is_new_opening")),
        )
