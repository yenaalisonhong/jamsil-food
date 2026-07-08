"""
Monthly Wrapped 집계 서비스.

한 달간의 식사 기록을 통계로 묶고 슬라이드형 카드를 생성합니다.
"""

from collections import Counter
from datetime import date

from adapters.diary_adapter import DiaryAdapter
from adapters.place_catalog_adapter import PlaceCatalogAdapter, PlaceRecord
from models.diary import DiaryEntry, DiaryStore, normalize_diary_name
from models.wrapped import WrappedCard, WrappedReport, WrappedStats
from utils.logger import get_logger

logger = get_logger(__name__)

_CATEGORY_COPY = {
    "한식": "당신의 혈액형은 한식입니다",
    "중식": "짜장면이 부르는 밤이 있었습니다",
    "일식": "정갈한 한 끼를 즐길 줄 아는 당신",
    "양식": "파스타는 사랑입니다",
    "분식": "떡볶이는 영원하다",
    "카페": "카페인으로 구동되는 인간",
    "디저트": "달콤함이 필요했던 한 달",
}


class WrappedGenerator:
    """월별 맛집 탐방 Wrapped 생성기."""

    def __init__(
        self,
        diary_adapter: DiaryAdapter,
        place_adapter: PlaceCatalogAdapter | None = None,
    ) -> None:
        self._diary = diary_adapter
        self._places = place_adapter or PlaceCatalogAdapter()

    def generate(self, year: int, month: int) -> WrappedReport:
        store = self._diary.load()
        month_label = date(year, month, 1).strftime("%Y년 %m월")

        visits = store.entries_for_month(year, month)
        if not visits:
            return self._empty_report(year, month, month_label)

        stats = self._aggregate(store, visits, year, month)
        cards = self._build_cards(stats)
        return WrappedReport(
            year=year,
            month=month,
            month_label=month_label,
            is_empty=False,
            stats=stats,
            cards=cards,
        )

    def _empty_report(self, year: int, month: int, month_label: str) -> WrappedReport:
        return WrappedReport(
            year=year,
            month=month,
            month_label=month_label,
            is_empty=True,
            cards=[
                WrappedCard(
                    title="이번 달은 위장 휴식 모드",
                    subtitle="다음 달엔 잠실 골목으로 탐험을 떠나볼까요?",
                    emoji="☕",
                    stat_value=0,
                    stat_label="방문 기록",
                ),
            ],
        )

    def _aggregate(
        self,
        store: DiaryStore,
        visits: list[tuple[date, DiaryEntry]],
        year: int,
        month: int,
    ) -> WrappedStats:
        month_start = date(year, month, 1)
        prior_counts = store.visit_counts_before(month_start)
        first_visits = store.first_visit_dates()

        place_visits: Counter[str] = Counter()
        category_visits: Counter[str] = Counter()
        ratings: list[int] = []
        walk_minutes: list[float] = []
        distances: list[float] = []
        prices: list[tuple[str, int]] = []

        new_discoveries: set[str] = set()
        revisit_visits = 0
        seen_this_month: Counter[str] = Counter()

        best_rated: tuple[str, int] | None = None

        for day, entry in visits:
            norm = normalize_diary_name(entry.name)
            place_visits[norm] += 1
            ratings.append(entry.rating)

            if best_rated is None or entry.rating > best_rated[1]:
                best_rated = (entry.name, entry.rating)

            place = self._places.lookup(entry.name, entry.place_id)
            if place:
                category_visits[place.category_label] += 1
                if place.walk_minutes is not None:
                    walk_minutes.append(place.walk_minutes)
                if place.distance_meters is not None:
                    distances.append(place.distance_meters)

            price = self._resolve_price(entry, place)
            if price is not None:
                prices.append((entry.name, price))

            had_prior = prior_counts.get(norm, 0) > 0 or seen_this_month[norm] > 0
            if had_prior:
                revisit_visits += 1
            else:
                first_ever = first_visits.get(norm)
                if first_ever and first_ever >= month_start:
                    new_discoveries.add(norm)

            seen_this_month[norm] += 1

        active_days = len({day for day, _ in visits})
        max_streak = self._max_streak({day for day, _ in visits})

        top_category = None
        top_category_count = 0
        if category_visits:
            top_category, top_category_count = category_visits.most_common(1)[0]

        top_places = [(name, count) for name, count in place_visits.most_common() if count >= 2][:3]

        cheapest_place = None
        cheapest_price = None
        if prices:
            cheapest_place, cheapest_price = min(prices, key=lambda item: item[1])

        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

        return WrappedStats(
            year=year,
            month=month,
            total_visits=len(visits),
            unique_places=len(place_visits),
            top_category=top_category,
            top_category_count=top_category_count,
            top_places=top_places,
            new_discoveries=len(new_discoveries),
            revisit_visits=revisit_visits,
            average_rating=avg_rating,
            best_rated_place=best_rated[0] if best_rated else None,
            best_rating=best_rated[1] if best_rated else None,
            cheapest_place=cheapest_place,
            cheapest_price_krw=cheapest_price,
            avg_walk_minutes=round(sum(walk_minutes) / len(walk_minutes), 1)
            if walk_minutes
            else None,
            avg_distance_meters=round(sum(distances) / len(distances), 0)
            if distances
            else None,
            max_streak_days=max_streak,
            active_days=active_days,
        )

    @staticmethod
    def _resolve_price(entry: DiaryEntry, place: PlaceRecord | None) -> int | None:
        if entry.price_min_krw is not None:
            return entry.price_min_krw
        if place and place.price_per_person_krw is not None:
            return place.price_per_person_krw
        return None

    @staticmethod
    def _max_streak(days: set[date]) -> int:
        if not days:
            return 0
        sorted_days = sorted(days)
        best = current = 1
        for i in range(1, len(sorted_days)):
            if (sorted_days[i] - sorted_days[i - 1]).days == 1:
                current += 1
                best = max(best, current)
            else:
                current = 1
        return best

    def _build_cards(self, stats: WrappedStats) -> list[WrappedCard]:
        cards: list[WrappedCard] = []

        cards.append(
            WrappedCard(
                title=f"이번 달 총 {stats.total_visits}곳 탐방!",
                subtitle=f"당신의 위장은 {stats.total_visits}번의 여행을 떠났습니다",
                emoji="🚀",
                stat_value=stats.total_visits,
                stat_label="방문 기록",
            ),
        )

        if stats.top_category:
            copy = _CATEGORY_COPY.get(
                stats.top_category,
                f"{stats.top_category}에 진심인 당신",
            )
            cards.append(
                WrappedCard(
                    title=f"최애 카테고리는 {stats.top_category}",
                    subtitle=copy,
                    emoji="👑",
                    stat_value=stats.top_category_count,
                    stat_label=f"{stats.top_category} 방문",
                ),
            )

        if stats.top_places:
            names = ", ".join(name for name, _ in stats.top_places[:3])
            cards.append(
                WrappedCard(
                    title="이 달의 단골 Top 3",
                    subtitle=f"자주 찾은 곳: {names}",
                    emoji="🏠",
                    stat_value=stats.top_places[0][1],
                    stat_label=f"1위 {stats.top_places[0][0]}",
                ),
            )

        cards.append(
            WrappedCard(
                title="탐험가 vs 단골러",
                subtitle=(
                    f"새로 발견 {stats.new_discoveries}곳 · "
                    f"재방문 {stats.revisit_visits}번"
                ),
                emoji="🧭",
                stat_value=stats.new_discoveries,
                stat_label="새 발견",
            ),
        )

        if stats.average_rating is not None:
            best_line = ""
            if stats.best_rated_place and stats.best_rating:
                best_line = f" — 이 달의 미슐랭: {stats.best_rated_place} ({stats.best_rating}점)"
            cards.append(
                WrappedCard(
                    title=f"평균 별점 {stats.average_rating}점",
                    subtitle=f"입맛이 꽤 까다로운 편이시군요{best_line}",
                    emoji="⭐",
                    stat_value=stats.average_rating,
                    stat_label="평균 평점",
                ),
            )

        if stats.cheapest_place and stats.cheapest_price_krw is not None:
            cards.append(
                WrappedCard(
                    title="가성비의 신",
                    subtitle=(
                        f"{stats.cheapest_place} — "
                        f"{stats.cheapest_price_krw:,}원대 승리"
                    ),
                    emoji="💰",
                    stat_value=f"{stats.cheapest_price_krw:,}원",
                    stat_label="최저가 기록",
                ),
            )

        if stats.avg_walk_minutes is not None:
            cards.append(
                WrappedCard(
                    title=f"탐험 반경 평균 {stats.avg_walk_minutes}분",
                    subtitle="프라운호퍼에서 출발한 잠실 원정대",
                    emoji="🗺️",
                    stat_value=f"{stats.avg_walk_minutes}분",
                    stat_label="평균 도보",
                ),
            )

        if stats.max_streak_days >= 2:
            cards.append(
                WrappedCard(
                    title=f"{stats.max_streak_days}일 연속 기록!",
                    subtitle="맛집 일기장을 놓지 않은 당신에게 박수를",
                    emoji="🔥",
                    stat_value=stats.max_streak_days,
                    stat_label="연속 기록",
                ),
            )

        summary = self._build_summary(stats)
        cards.append(
            WrappedCard(
                title="이번 달 총평",
                subtitle=summary,
                emoji="🎉",
                stat_value=stats.unique_places,
                stat_label="다양한 맛집",
            ),
        )

        return cards

    @staticmethod
    def _build_summary(stats: WrappedStats) -> str:
        parts: list[str] = []
        parts.append(f"{stats.active_days}일 동안 {stats.unique_places}곳을 탐방했어요.")
        if stats.new_discoveries:
            parts.append(f"그중 {stats.new_discoveries}곳은 처음 가본 곳!")
        if stats.top_category:
            parts.append(f"{stats.top_category} 비중이 가장 높았습니다.")
        return " ".join(parts)
