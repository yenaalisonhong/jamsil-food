/**
 * Monthly Wrapped 집계 (Python WrappedGenerator와 동일 로직)
 */
const WrappedGenerator = (() => {
  const CATEGORY_COPY = {
    한식: "당신의 혈액형은 한식입니다",
    중식: "짜장면이 부르는 밤이 있었습니다",
    일식: "정갈한 한 끼를 즐길 줄 아는 당신",
    양식: "파스타는 사랑입니다",
    분식: "떡볶이는 영원하다",
    카페: "카페인으로 구동되는 인간",
    디저트: "달콤함이 필요했던 한 달",
  };

  function monthPrefix(year, month) {
    return `${year}-${String(month).padStart(2, "0")}-`;
  }

  function monthStartKey(year, month) {
    return `${year}-${String(month).padStart(2, "0")}-01`;
  }

  function formatMonthLabel(year, month) {
    return new Date(year, month - 1, 1).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
    });
  }

  function entriesForMonth(store, year, month) {
    const prefix = monthPrefix(year, month);
    const result = [];
    Object.entries(store).forEach(([key, dayEntries]) => {
      if (!key.startsWith(prefix)) return;
      dayEntries.forEach((entry) => {
        result.push({ dateKey: key, entry });
      });
    });
    result.sort((a, b) => {
      if (a.dateKey !== b.dateKey) return a.dateKey.localeCompare(b.dateKey);
      const ta = a.entry.createdAt || "";
      const tb = b.entry.createdAt || "";
      return ta.localeCompare(tb);
    });
    return result;
  }

  function firstVisitDates(store) {
    const first = {};
    Object.keys(store)
      .sort()
      .forEach((key) => {
        store[key].forEach((entry) => {
          const norm = DiaryStorage.normalizeName(entry.name);
          if (!norm || first[norm]) return;
          first[norm] = key;
        });
      });
    return first;
  }

  function visitCountsBefore(store, beforeKey) {
    const counts = {};
    Object.entries(store).forEach(([key, entries]) => {
      if (key >= beforeKey) return;
      entries.forEach((entry) => {
        const norm = DiaryStorage.normalizeName(entry.name);
        counts[norm] = (counts[norm] || 0) + 1;
      });
    });
    return counts;
  }

  function resolvePrice(entry, place) {
    if (entry.price_min_krw != null) return entry.price_min_krw;
    if (place?.price_per_person_krw != null) return place.price_per_person_krw;
    return null;
  }

  function maxStreak(dateKeys) {
    if (!dateKeys.length) return 0;
    const sorted = [...dateKeys].sort();
    let best = 1;
    let current = 1;
    for (let i = 1; i < sorted.length; i += 1) {
      const prev = new Date(sorted[i - 1]);
      const cur = new Date(sorted[i]);
      const diff = (cur - prev) / (1000 * 60 * 60 * 24);
      if (diff === 1) {
        current += 1;
        best = Math.max(best, current);
      } else {
        current = 1;
      }
    }
    return best;
  }

  function mostCommon(counter) {
    return Object.entries(counter).sort((a, b) => b[1] - a[1]);
  }

  function joinNames(names) {
    return names.join(", ");
  }

  function topPlacesWithTies(placeVisits) {
    const candidates = mostCommon(placeVisits).filter(([, count]) => count >= 2);
    if (candidates.length <= 3) return candidates;
    const cutoff = candidates[2][1];
    return candidates.filter(([, count]) => count >= cutoff);
  }

  function aggregate(store, visits, year, month, places) {
    const startKey = monthStartKey(year, month);
    const priorCounts = visitCountsBefore(store, startKey);
    const firstVisits = firstVisitDates(store);

    const placeVisits = {};
    const categoryVisits = {};
    const ratings = [];
    const walkMinutes = [];
    const distances = [];
    const newDiscoveries = new Set();
    let revisitVisits = 0;
    const seenThisMonth = {};

    let bestRating = null;
    const bestRatedByNorm = {};
    let cheapestPrice = null;
    const cheapestByNorm = {};

    visits.forEach(({ dateKey, entry }) => {
      const norm = DiaryStorage.normalizeName(entry.name);
      placeVisits[norm] = (placeVisits[norm] || 0) + 1;
      ratings.push(entry.rating);

      if (bestRating == null || entry.rating > bestRating) {
        bestRating = entry.rating;
        Object.keys(bestRatedByNorm).forEach((k) => delete bestRatedByNorm[k]);
        bestRatedByNorm[norm] = entry.name;
      } else if (entry.rating === bestRating && !bestRatedByNorm[norm]) {
        bestRatedByNorm[norm] = entry.name;
      }

      const place = DiaryStorage.findPlace(
        places,
        entry.name,
        entry.place_id || entry.placeId || null,
      );
      if (place) {
        const label = place.category_label || "기타";
        categoryVisits[label] = (categoryVisits[label] || 0) + 1;
        if (place.walk_minutes != null) walkMinutes.push(place.walk_minutes);
        if (place.distance_meters != null) distances.push(place.distance_meters);
      }

      const price = resolvePrice(entry, place);
      if (price != null) {
        if (cheapestPrice == null || price < cheapestPrice) {
          cheapestPrice = price;
          Object.keys(cheapestByNorm).forEach((k) => delete cheapestByNorm[k]);
          cheapestByNorm[norm] = entry.name;
        } else if (price === cheapestPrice && !cheapestByNorm[norm]) {
          cheapestByNorm[norm] = entry.name;
        }
      }

      const hadPrior = (priorCounts[norm] || 0) > 0 || (seenThisMonth[norm] || 0) > 0;
      if (hadPrior) {
        revisitVisits += 1;
      } else {
        const firstEver = firstVisits[norm];
        if (firstEver && firstEver >= startKey) newDiscoveries.add(norm);
      }
      seenThisMonth[norm] = (seenThisMonth[norm] || 0) + 1;
    });

    const activeDaySet = new Set(visits.map((v) => v.dateKey));
    const rankedCategories = mostCommon(categoryVisits);
    const topCategoryCount = rankedCategories.length ? rankedCategories[0][1] : 0;
    const topCategories = rankedCategories
      .filter(([, count]) => count === topCategoryCount)
      .map(([name]) => name);
    const topPlaces = topPlacesWithTies(placeVisits);

    const avgRating = ratings.length
      ? Math.round((ratings.reduce((a, b) => a + b, 0) / ratings.length) * 10) / 10
      : null;

    return {
      year,
      month,
      totalVisits: visits.length,
      uniquePlaces: Object.keys(placeVisits).length,
      topCategories,
      topCategoryCount,
      topPlaces,
      newDiscoveries: newDiscoveries.size,
      revisitVisits,
      averageRating: avgRating,
      bestRatedPlaces: Object.values(bestRatedByNorm),
      bestRating,
      cheapestPlaces: Object.values(cheapestByNorm),
      cheapestPriceKrw: cheapestPrice,
      avgWalkMinutes: walkMinutes.length
        ? Math.round((walkMinutes.reduce((a, b) => a + b, 0) / walkMinutes.length) * 10) / 10
        : null,
      maxStreakDays: maxStreak([...activeDaySet]),
      activeDays: activeDaySet.size,
    };
  }

  function buildSummary(stats) {
    const parts = [`${stats.activeDays}일 동안 ${stats.uniquePlaces}곳을 탐방했어요.`];
    if (stats.newDiscoveries) parts.push(`그중 ${stats.newDiscoveries}곳은 처음 가본 곳!`);
    if (stats.topCategories.length) {
      parts.push(`${joinNames(stats.topCategories)} 비중이 가장 높았습니다.`);
    }
    return parts.join(" ");
  }

  function buildCards(stats) {
    const cards = [];

    cards.push({
      title: `이번 달 총 ${stats.totalVisits}곳 탐방!`,
      subtitle: `당신의 위장은 ${stats.totalVisits}번의 여행을 떠났습니다`,
      emoji: "🚀",
      statValue: stats.totalVisits,
      statLabel: "방문 기록",
    });

    if (stats.topCategories.length) {
      const cats = joinNames(stats.topCategories);
      const copy =
        stats.topCategories.length === 1
          ? CATEGORY_COPY[stats.topCategories[0]] || `${stats.topCategories[0]}에 진심인 당신`
          : `${cats}에 진심인 당신`;
      cards.push({
        title: `최애 카테고리는 ${cats}`,
        subtitle: copy,
        emoji: "👑",
        statValue: stats.topCategoryCount,
        statLabel: `${cats} 방문`,
      });
    }

    if (stats.topPlaces.length) {
      const names = joinNames(stats.topPlaces.map(([name]) => name));
      const topCount = stats.topPlaces[0][1];
      const firstPlaceNames = joinNames(
        stats.topPlaces.filter(([, count]) => count === topCount).map(([name]) => name),
      );
      cards.push({
        title: "이 달의 단골 Top 3",
        subtitle: `자주 찾은 곳: ${names}`,
        emoji: "🏠",
        statValue: topCount,
        statLabel: `1위 ${firstPlaceNames}`,
      });
    }

    cards.push({
      title: "탐험가 vs 단골러",
      subtitle: `새로 발견 ${stats.newDiscoveries}곳 · 재방문 ${stats.revisitVisits}번`,
      emoji: "🧭",
      statValue: stats.newDiscoveries,
      statLabel: "새 발견",
    });

    if (stats.averageRating != null) {
      let bestLine = "";
      if (stats.bestRatedPlaces.length && stats.bestRating != null) {
        bestLine = ` — 이 달의 미슐랭: ${joinNames(stats.bestRatedPlaces)} (${stats.bestRating}점)`;
      }
      cards.push({
        title: `평균 별점 ${stats.averageRating}점`,
        subtitle: `입맛이 꽤 까다로운 편이시군요${bestLine}`,
        emoji: "⭐",
        statValue: stats.averageRating,
        statLabel: "평균 평점",
      });
    }

    if (stats.cheapestPlaces.length && stats.cheapestPriceKrw != null) {
      cards.push({
        title: "가성비의 신",
        subtitle: `${joinNames(stats.cheapestPlaces)} — ${stats.cheapestPriceKrw.toLocaleString("ko-KR")}원대 승리`,
        emoji: "💰",
        statValue: `${stats.cheapestPriceKrw.toLocaleString("ko-KR")}원`,
        statLabel: "최저가 기록",
      });
    }

    if (stats.avgWalkMinutes != null) {
      cards.push({
        title: `탐험 반경 평균 ${stats.avgWalkMinutes}분`,
        subtitle: "프라운호퍼에서 출발한 잠실 원정대",
        emoji: "🗺️",
        statValue: `${stats.avgWalkMinutes}분`,
        statLabel: "평균 도보",
      });
    }

    if (stats.maxStreakDays >= 2) {
      cards.push({
        title: `${stats.maxStreakDays}일 연속 기록!`,
        subtitle: "맛집 일기장을 놓지 않은 당신에게 박수를",
        emoji: "🔥",
        statValue: stats.maxStreakDays,
        statLabel: "연속 기록",
      });
    }

    cards.push({
      title: "이번 달 총평",
      subtitle: buildSummary(stats),
      emoji: "🎉",
      statValue: stats.uniquePlaces,
      statLabel: "다양한 맛집",
    });

    return cards;
  }

  function emptyReport(year, month, monthLabel) {
    return {
      year,
      month,
      monthLabel,
      isEmpty: true,
      stats: null,
      cards: [
        {
          title: "이번 달은 위장 휴식 모드",
          subtitle: "다음 달엔 잠실 골목으로 탐험을 떠나볼까요?",
          emoji: "☕",
          statValue: 0,
          statLabel: "방문 기록",
        },
      ],
    };
  }

  function generate(store, places, year, month) {
    const monthLabel = formatMonthLabel(year, month);
    const visits = entriesForMonth(store, year, month);
    if (!visits.length) return emptyReport(year, month, monthLabel);

    const stats = aggregate(store, visits, year, month, places);
    return {
      year,
      month,
      monthLabel,
      isEmpty: false,
      stats,
      cards: buildCards(stats),
    };
  }

  function generateCurrentMonth(store, places, refDate = new Date()) {
    return generate(store, places, refDate.getFullYear(), refDate.getMonth() + 1);
  }

  return { generate, generateCurrentMonth, formatMonthLabel };
})();
