/**
 * 식사 기록 — 캘린더 뷰
 */

const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),
  entries: {},
};

const $ = (sel) => document.querySelector(sel);

function readUrlMonth() {
  const params = new URLSearchParams(window.location.search);
  const y = Number(params.get("y"));
  const m = Number(params.get("m"));
  if (y >= 2000 && m >= 1 && m <= 12) {
    state.year = y;
    state.month = m - 1;
  }
}

function getEntriesForDate(key) {
  return state.entries[key] || [];
}

function renderCalendar() {
  const grid = $("#diary-grid");
  const monthLabel = $("#diary-month-label");
  if (!grid || !monthLabel) return;

  monthLabel.textContent = DiaryStorage.formatMonthLabel(state.year, state.month);

  const firstDay = new Date(state.year, state.month, 1);
  const lastDate = new Date(state.year, state.month + 1, 0).getDate();
  const startWeekday = firstDay.getDay();

  const today = new Date();
  const todayKey = DiaryStorage.dateKey(today.getFullYear(), today.getMonth(), today.getDate());

  let html = "";

  for (let i = 0; i < startWeekday; i += 1) {
    html += '<div class="diary-cell diary-cell--empty" aria-hidden="true"></div>';
  }

  for (let day = 1; day <= lastDate; day += 1) {
    const key = DiaryStorage.dateKey(state.year, state.month, day);
    const entries = getEntriesForDate(key);
    const isToday = key === todayKey;
    const weekday = new Date(state.year, state.month, day).getDay();

    let entriesHtml = "";
    if (entries.length) {
      entriesHtml += `<span class="diary-cell-badge" aria-hidden="true">${entries.length}</span>`;
      const preview = entries.slice(0, 2);
      preview.forEach((entry) => {
        entriesHtml += `
          <div class="diary-cell-entry">
            <span class="diary-cell-stars">${DiaryStorage.starsHtml(entry.rating, true)}</span>
            <span class="diary-cell-name">${DiaryStorage.escapeHtml(entry.name)}</span>
          </div>`;
      });
      if (entries.length > 2) {
        entriesHtml += `<div class="diary-cell-more">+${entries.length - 2}</div>`;
      }
    }

    const classes = [
      "diary-cell",
      isToday ? "diary-cell--today" : "",
      entries.length ? "diary-cell--has-entries" : "",
      weekday === 0 ? "diary-cell--sun" : "",
      weekday === 6 ? "diary-cell--sat" : "",
    ].filter(Boolean).join(" ");

    html += `
      <a href="${DiaryStorage.dayUrl(key)}" class="${classes}" aria-label="${day}일, 기록 ${entries.length}건">
        <span class="diary-cell-day">${day}</span>
        <div class="diary-cell-entries">${entriesHtml}</div>
      </a>`;
  }

  grid.innerHTML = html;
}

function updateStats() {
  const el = $("#diary-stats");
  if (el) el.textContent = `기록 ${DiaryStorage.countTotal(state.entries)}건`;
}

function reloadFromStorage() {
  state.entries = DiaryStorage.loadEntries();
  updateStats();
  renderCalendar();
}

function bindEvents() {
  const prev = $("#diary-prev-month");
  const next = $("#diary-next-month");
  const todayBtn = $("#diary-today");
  if (!prev || !next || !todayBtn) return;

  prev.addEventListener("click", () => {
    state.month -= 1;
    if (state.month < 0) {
      state.month = 11;
      state.year -= 1;
    }
    renderCalendar();
  });

  next.addEventListener("click", () => {
    state.month += 1;
    if (state.month > 11) {
      state.month = 0;
      state.year += 1;
    }
    renderCalendar();
  });

  todayBtn.addEventListener("click", () => {
    const now = new Date();
    state.year = now.getFullYear();
    state.month = now.getMonth();
    renderCalendar();
  });
}

function init() {
  if (typeof DiaryStorage === "undefined") {
    const grid = $("#diary-grid");
    if (grid) {
      grid.innerHTML = "<p class=\"diary-entry-empty\">페이지 로드 오류입니다. 새로고침(Ctrl+F5)해 주세요.</p>";
    }
    return;
  }

  readUrlMonth();
  reloadFromStorage();
  bindEvents();
  DiaryStorage.bindPersistenceReload(reloadFromStorage);
}

document.addEventListener("DOMContentLoaded", init);
