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

        new_discoveries: set[str] = set()
        revisit_visits = 0
        seen_this_month: Counter[str] = Counter()

        best_rating: int | None = None
        best_rated_by_norm: dict[str, str] = {}
        cheapest_price: int | None = None
        cheapest_by_norm: dict[str, str] = {}

        for day, entry in visits:
            norm = normalize_diary_name(entry.name)
            place_visits[norm] += 1
            ratings.append(entry.rating)

            if best_rating is None or entry.rating > best_rating:
                best_rating = entry.rating
                best_rated_by_norm = {norm: entry.name}
            elif entry.rating == best_rating and norm not in best_rated_by_norm:
                best_rated_by_norm[norm] = entry.name

            place = self._places.lookup(entry.name, entry.place_id)
            if place:
                category_visits[place.category_label] += 1
                if place.walk_minutes is not None:
                    walk_minutes.append(place.walk_minutes)
                if place.distance_meters is not None:
                    distances.append(place.distance_meters)

            price = self._resolve_price(entry, place)
            if price is not None:
                if cheapest_price is None or price < cheapest_price:
                    cheapest_price = price
                    cheapest_by_norm = {norm: entry.name}
                elif price == cheapest_price and norm not in cheapest_by_norm:
                    cheapest_by_norm[norm] = entry.name

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

        top_categories: list[str] = []
        top_category_count = 0
        if category_visits:
            top_category_count = category_visits.most_common(1)[0][1]
            top_categories = [
                name for name, count in category_visits.most_common() if count == top_category_count
            ]

        top_places = self._top_places_with_ties(place_visits)

        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

        return WrappedStats(
            year=year,
            month=month,
            total_visits=len(visits),
            unique_places=len(place_visits),
            top_categories=top_categories,
            top_category_count=top_category_count,
            top_places=top_places,
            new_discoveries=len(new_discoveries),
            revisit_visits=revisit_visits,
            average_rating=avg_rating,
            best_rated_places=list(best_rated_by_norm.values()),
            best_rating=best_rating,
            cheapest_places=list(cheapest_by_norm.values()),
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
    def _top_places_with_ties(place_visits: Counter[str]) -> list[tuple[str, int]]:
        """방문 2회 이상 단골. Top 3 컷오프와 동점인 곳까지 모두 포함."""
        candidates = [(name, count) for name, count in place_visits.most_common() if count >= 2]
        if len(candidates) <= 3:
            return candidates
        cutoff = candidates[2][1]
        return [(name, count) for name, count in candidates if count >= cutoff]

    @staticmethod
    def _join_names(names: list[str]) -> str:
        return ", ".join(names)

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

        if stats.top_categories:
            cats = self._join_names(stats.top_categories)
            if len(stats.top_categories) == 1:
                copy = _CATEGORY_COPY.get(
                    stats.top_categories[0],
                    f"{stats.top_categories[0]}에 진심인 당신",
                )
            else:
                copy = f"{cats}에 진심인 당신"
            cards.append(
                WrappedCard(
                    title=f"최애 카테고리는 {cats}",
                    subtitle=copy,
                    emoji="👑",
                    stat_value=stats.top_category_count,
                    stat_label=f"{cats} 방문",
                ),
            )

        if stats.top_places:
            names = self._join_names([name for name, _ in stats.top_places])
            top_count = stats.top_places[0][1]
            first_place_names = self._join_names(
                [name for name, count in stats.top_places if count == top_count]
            )
            cards.append(
                WrappedCard(
                    title="이 달의 단골 Top 3",
                    subtitle=f"자주 찾은 곳: {names}",
                    emoji="🏠",
                    stat_value=top_count,
                    stat_label=f"1위 {first_place_names}",
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
            if stats.best_rated_places and stats.best_rating:
                best_names = self._join_names(stats.best_rated_places)
                best_line = f" — 이 달의 미슐랭: {best_names} ({stats.best_rating}점)"
            cards.append(
                WrappedCard(
                    title=f"평균 별점 {stats.average_rating}점",
                    subtitle=f"입맛이 꽤 까다로운 편이시군요{best_line}",
                    emoji="⭐",
                    stat_value=stats.average_rating,
                    stat_label="평균 평점",
                ),
            )

        if stats.cheapest_places and stats.cheapest_price_krw is not None:
            cheap_names = self._join_names(stats.cheapest_places)
            cards.append(
                WrappedCard(
                    title="가성비의 신",
                    subtitle=(
                        f"{cheap_names} — "
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
        if stats.top_categories:
            cats = WrappedGenerator._join_names(stats.top_categories)
            parts.append(f"{cats} 비중이 가장 높았습니다.")
        return " ".join(parts)
