/**
 * 식사 기록 — 날짜별 상세 페이지
 */

const state = {
  dateKey: null,
  entries: {},
  saving: false,
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

  list.innerHTML = entries.map((entry, idx) => {
    const priceText = DiaryStorage.formatPriceRange(entry.price_min_krw, entry.price_max_krw);
    return `
    <article class="diary-entry-card">
      <div class="diary-entry-main">
        <h3 class="diary-entry-name">${DiaryStorage.escapeHtml(entry.name)}</h3>
        <div class="diary-entry-stars">${DiaryStorage.starsHtml(entry.rating)}</div>
        ${priceText ? `<p class="diary-entry-price">${DiaryStorage.escapeHtml(priceText)}</p>` : ""}
        ${entry.memo ? `<p class="diary-entry-memo">${DiaryStorage.escapeHtml(entry.memo)}</p>` : ""}
      </div>
      <button type="button" class="diary-entry-delete" data-idx="${idx}" aria-label="${DiaryStorage.escapeHtml(entry.name)} 삭제" ${state.saving ? "disabled" : ""}>삭제</button>
    </article>
  `;
  }).join("");

  list.querySelectorAll(".diary-entry-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (state.saving) return;
      const idx = Number(btn.dataset.idx);
      const dayEntries = [...getDayEntries()];
      dayEntries.splice(idx, 1);
      if (dayEntries.length) state.entries[state.dateKey] = dayEntries;
      else delete state.entries[state.dateKey];
      await persistEntries();
      updateStats();
      renderEntryList();
    });
  });
}

function updateStats() {
  $("#diary-stats").textContent = `기록 ${DiaryStorage.countTotal(state.entries)}건`;
}

async function persistEntries() {
  state.saving = true;
  renderEntryList();
  try {
    await DiaryStorage.saveEntriesAsync(state.entries);
  } finally {
    state.saving = false;
    renderEntryList();
  }
}

async function reloadFromStorage() {
  state.entries = DiaryStorage.loadEntries();
  updateStats();
  renderEntryList();
  state.entries = await DiaryStorage.hydrateFromRemote();
  updateStats();
  renderEntryList();
}

function readPriceInputs() {
  return DiaryStorage.normalizePriceFields({
    price_min_krw: $("#diary-price-min")?.value,
    price_max_krw: $("#diary-price-max")?.value,
  });
}

function clearPriceInputs() {
  const minEl = $("#diary-price-min");
  const maxEl = $("#diary-price-max");
  if (minEl) minEl.value = "";
  if (maxEl) maxEl.value = "";
}

function bindForm() {
  $$('input[name="diary-rating"]').forEach((input) => {
    input.addEventListener("change", updateRatingLabel);
  });
  updateRatingLabel();

  $("#diary-entry-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.saving) return;

    const name = $("#diary-name").value.trim();
    if (!name) return;

    const entry = {
      name,
      rating: getSelectedRating(),
      memo: $("#diary-memo").value.trim(),
      ...readPriceInputs(),
      createdAt: new Date().toISOString(),
    };

    if (!state.entries[state.dateKey]) {
      state.entries[state.dateKey] = [];
    }
    state.entries[state.dateKey].push(entry);
    await persistEntries();

    $("#diary-name").value = "";
    $("#diary-memo").value = "";
    clearPriceInputs();
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

  const { year, month } = DiaryStorage.parseDateKey(state.dateKey);

  document.title = `${DiaryStorage.formatDayTitle(state.dateKey)} | 잠실맛집`;
  $("#diary-day-title").textContent = DiaryStorage.formatDayTitle(state.dateKey);
  $("#diary-back-link").href = DiaryStorage.calendarUrl(year, month);

  DiaryStorage.bindSyncStatus($("#diary-sync-status"));
  DiaryStorage.bindSyncSettings($("#diary-sync-settings"));
  bindForm();
  DiaryStorage.bindPersistenceReload(() => {
    reloadFromStorage();
  });
  window.addEventListener("diary-sync-updated", () => {
    reloadFromStorage();
  });
  DiaryStorage.loadPlaceSuggestions($("#diary-place-suggestions"));
  reloadFromStorage();
  $("#diary-name").focus();
}

document.addEventListener("DOMContentLoaded", init);
