/**
 * 식사 기록 — 날짜별 상세 페이지
 */

const state = {
  dateKey: null,
  entries: {},
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function getDateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("date");
  if (!raw || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const { year, month, day } = DiaryStorage.parseDateKey(raw);
  const check = new Date(year, month, day);
  if (
    check.getFullYear() !== year
    || check.getMonth() !== month
    || check.getDate() !== day
  ) {
    return null;
  }
  return raw;
}

function getDayEntries() {
  return state.entries[state.dateKey] || [];
}

function getSelectedRating() {
  const checked = document.querySelector('input[name="diary-rating"]:checked');
  return Math.max(1, Math.min(5, Number(checked?.value) || 4));
}

function setSelectedRating(value) {
  const rating = Math.max(1, Math.min(5, Number(value) || 4));
  const input = document.querySelector(`input[name="diary-rating"][value="${rating}"]`);
  if (input) input.checked = true;
  updateRatingLabel();
}

function updateRatingLabel() {
  const label = $("#diary-rating-label");
  if (label) label.textContent = `${getSelectedRating()}점 선택됨`;
}

function renderEntryList() {
  const list = $("#diary-entry-list");
  const entries = getDayEntries();

  if (!entries.length) {
    list.innerHTML = '<p class="diary-entry-empty">아직 기록이 없어요. 아래에서 추가해 보세요.</p>';
    return;
  }

  list.innerHTML = entries.map((entry, idx) => `
    <article class="diary-entry-card">
      <div class="diary-entry-main">
        <h3 class="diary-entry-name">${DiaryStorage.escapeHtml(entry.name)}</h3>
        <div class="diary-entry-stars">${DiaryStorage.starsHtml(entry.rating)}</div>
        ${entry.memo ? `<p class="diary-entry-memo">${DiaryStorage.escapeHtml(entry.memo)}</p>` : ""}
      </div>
      <button type="button" class="diary-entry-delete" data-idx="${idx}" aria-label="${DiaryStorage.escapeHtml(entry.name)} 삭제">삭제</button>
    </article>
  `).join("");

  list.querySelectorAll(".diary-entry-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.idx);
      const dayEntries = [...getDayEntries()];
      dayEntries.splice(idx, 1);
      if (dayEntries.length) state.entries[state.dateKey] = dayEntries;
      else delete state.entries[state.dateKey];
      DiaryStorage.saveEntries(state.entries);
      updateStats();
      renderEntryList();
    });
  });
}

function updateStats() {
  $("#diary-stats").textContent = `기록 ${DiaryStorage.countTotal(state.entries)}건`;
}

function reloadFromStorage() {
  state.entries = DiaryStorage.loadEntries();
  updateStats();
  renderEntryList();
}

function bindForm() {
  $$('input[name="diary-rating"]').forEach((input) => {
    input.addEventListener("change", updateRatingLabel);
  });
  updateRatingLabel();

  $("#diary-entry-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const name = $("#diary-name").value.trim();
    if (!name) return;

    const entry = {
      name,
      rating: getSelectedRating(),
      memo: $("#diary-memo").value.trim(),
      createdAt: new Date().toISOString(),
    };

    if (!state.entries[state.dateKey]) {
      state.entries[state.dateKey] = [];
    }
    state.entries[state.dateKey].push(entry);
    DiaryStorage.saveEntries(state.entries);

    $("#diary-name").value = "";
    $("#diary-memo").value = "";
    setSelectedRating(4);
    updateStats();
    renderEntryList();
    $("#diary-name").focus();
  });
}

function showInvalidDate() {
  $("#diary-day-title").textContent = "잘못된 날짜입니다";
  document.querySelector(".diary-day-main").innerHTML =
    '<p class="diary-entry-empty">캘린더에서 날짜를 다시 선택해 주세요. <a href="diary.html" class="diary-nav-link">캘린더로 돌아가기</a></p>';
}

function init() {
  if (typeof DiaryStorage === "undefined") {
    document.body.innerHTML = "<p class=\"diary-entry-empty\">페이지 로드 오류입니다. 새로고침(Ctrl+F5)해 주세요.</p>";
    return;
  }

  state.dateKey = getDateFromUrl();
  if (!state.dateKey) {
    showInvalidDate();
    return;
  }

  reloadFromStorage();
  const { year, month } = DiaryStorage.parseDateKey(state.dateKey);

  document.title = `${DiaryStorage.formatDayTitle(state.dateKey)} | 잠실맛집`;
  $("#diary-day-title").textContent = DiaryStorage.formatDayTitle(state.dateKey);
  $("#diary-back-link").href = DiaryStorage.calendarUrl(year, month);

  bindForm();
  DiaryStorage.bindPersistenceReload(reloadFromStorage);
  DiaryStorage.loadPlaceSuggestions($("#diary-place-suggestions"));
  $("#diary-name").focus();
}

document.addEventListener("DOMContentLoaded", init);
