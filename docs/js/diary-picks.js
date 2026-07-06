/**
 * 식사 기록 4점 이상 맛집 모음
 */
const $ = (sel) => document.querySelector(sel);

function formatPrice(place) {
  if (!place) return "-";
  const lo = place.price_range_min_krw ?? place.price_per_person_krw;
  const hi = place.price_range_max_krw ?? place.price_per_person_krw;
  if (lo != null && hi != null) {
    if (lo === hi) return `${lo.toLocaleString("ko-KR")}원`;
    return `${lo.toLocaleString("ko-KR")}~${hi.toLocaleString("ko-KR")}원`;
  }
  if (place.price_per_person_krw != null) {
    return `${place.price_per_person_krw.toLocaleString("ko-KR")}원`;
  }
  return "-";
}

function formatWalk(place) {
  if (!place || place.walk_minutes == null) return "-";
  return `도보 ${Math.round(place.walk_minutes)}분`;
}

function displayMemo(pick) {
  const memo = (pick?.memo || "").trim();
  return memo || "-";
}

function renderList(picks, places) {
  const list = $("#diary-picks-list");
  const summary = $("#diary-picks-summary");
  const stats = $("#diary-picks-stats");

  if (!picks.length) {
    summary.textContent = "아직 4점 이상 기록이 없어요.";
    list.innerHTML =
      '<p class="diary-entry-empty">식사 기록에서 별점 4점 이상을 남기면 여기에 모여요. <a href="diary.html" class="diary-nav-link">식사 기록 쓰러 가기</a></p>';
    stats.textContent = "0곳";
    return;
  }

  summary.textContent = `총 ${picks.length}곳 · 별점 4점 이상`;
  stats.textContent = `${picks.length}곳`;

  const rows = picks.map((pick) => {
    const place = DiaryStorage.findPlaceByName(places, pick.name);
    const memo = displayMemo(pick);
    const price = formatPrice(place);
    const walk = formatWalk(place);
    const stars = DiaryStorage.starsHtml(pick.rating, true);
    const visitHint =
      pick.visitCount > 1 ? `<span class="diary-picks-visits">${pick.visitCount}회 방문</span>` : "";

    const memoClass = memo === "-" ? " diary-picks-cell--empty" : "";

    return `
      <article class="diary-picks-row">
        <div class="diary-picks-cell diary-picks-cell--name">
          <h2 class="diary-picks-name">${DiaryStorage.escapeHtml(pick.name)}</h2>
          <div class="diary-picks-meta">
            <span class="diary-picks-stars">${stars}</span>
            ${visitHint}
          </div>
        </div>
        <div class="diary-picks-cell diary-picks-cell--memo${memoClass}" data-label="메모">${DiaryStorage.escapeHtml(memo)}</div>
        <div class="diary-picks-cell" data-label="가격대">${DiaryStorage.escapeHtml(price)}</div>
        <div class="diary-picks-cell" data-label="도보거리">${DiaryStorage.escapeHtml(walk)}</div>
      </article>
    `;
  });

  list.innerHTML = `
    <div class="diary-picks-table" role="table" aria-label="4점 이상 맛집 목록">
      <div class="diary-picks-head" role="row">
        <span role="columnheader">식당명</span>
        <span role="columnheader">메모</span>
        <span role="columnheader">가격대</span>
        <span role="columnheader">도보거리</span>
      </div>
      ${rows.join("")}
    </div>
  `;
}

function showLoadError(err) {
  console.error(err);
  const list = $("#diary-picks-list");
  const summary = $("#diary-picks-summary");
  if (summary) summary.textContent = "목록을 불러오지 못했어요.";
  if (list) {
    list.innerHTML =
      '<p class="diary-entry-empty">페이지 로드 오류입니다. 새로고침(Ctrl+F5)해 주세요.</p>';
  }
}

async function reload() {
  try {
    const picks = DiaryStorage.collectHighlyRated(4);
    renderList(picks, []);
    const places = await DiaryStorage.loadPlaces();
    renderList(picks, places);
  } catch (err) {
    showLoadError(err);
  }
}

DiaryStorage.bindPersistenceReload(reload);
reload();
