/**
 * 식사 기록 — 공통 저장·날짜·별점 유틸
 */
const DiaryStorage = (() => {
  const STORAGE_KEY = "jamsil_meal_diary";
  let storage = null;
  let memoryEntries = {};

  function resolveStorage() {
    if (storage !== null) return storage;
    try {
      const probe = "__jamsil_diary_probe__";
      window.localStorage.setItem(probe, "1");
      window.localStorage.removeItem(probe);
      storage = window.localStorage;
      return storage;
    } catch {
      try {
        const probe = "__jamsil_diary_probe__";
        window.sessionStorage.setItem(probe, "1");
        window.sessionStorage.removeItem(probe);
        storage = window.sessionStorage;
        return storage;
      } catch {
        storage = false;
        return storage;
      }
    }
  }

  function parseOptionalPrice(value) {
    if (value == null || value === "") return null;
    const n = Math.round(Number(value));
    return Number.isFinite(n) && n >= 0 ? n : null;
  }

  function normalizePriceFields(entry) {
    let min = parseOptionalPrice(entry.price_min_krw);
    let max = parseOptionalPrice(entry.price_max_krw);
    if (min == null && max == null) return {};
    if (min != null && max != null && min > max) [min, max] = [max, min];
    if (min == null) min = max;
    if (max == null) max = min;
    return { price_min_krw: min, price_max_krw: max };
  }

  function formatPriceRange(min, max) {
    if (min == null && max == null) return null;
    const lo = min ?? max;
    const hi = max ?? min;
    if (lo === hi) return `${lo.toLocaleString("ko-KR")}원`;
    return `${lo.toLocaleString("ko-KR")}~${hi.toLocaleString("ko-KR")}원`;
  }

  function normalizeEntries(data) {
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    const out = {};
    Object.entries(data).forEach(([key, value]) => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(key) || !Array.isArray(value)) return;
      const rows = value
        .filter((entry) => entry && typeof entry.name === "string" && entry.name.trim())
        .map((entry) => ({
          name: entry.name.trim(),
          rating: Math.max(1, Math.min(5, Math.round(Number(entry.rating) || 4))),
          memo: typeof entry.memo === "string" ? entry.memo.trim() : "",
          ...normalizePriceFields(entry),
          createdAt: typeof entry.createdAt === "string" ? entry.createdAt : new Date().toISOString(),
        }));
      if (rows.length) out[key] = rows;
    });
    return out;
  }

  function dateKey(y, m, d) {
    const mm = String(m + 1).padStart(2, "0");
    const dd = String(d).padStart(2, "0");
    return `${y}-${mm}-${dd}`;
  }

  function parseDateKey(key) {
    const [y, m, d] = key.split("-").map(Number);
    return { year: y, month: m - 1, day: d };
  }

  function loadEntries() {
    const store = resolveStorage();
    if (!store) {
      return normalizeEntries(memoryEntries);
    }
    try {
      const raw = store.getItem(STORAGE_KEY);
      if (!raw) return {};
      return normalizeEntries(JSON.parse(raw));
    } catch {
      return {};
    }
  }

  function saveEntries(entries) {
    const normalized = normalizeEntries(entries);
    const store = resolveStorage();
    if (!store) {
      memoryEntries = normalized;
      return { ok: false, persistent: false };
    }
    try {
      store.setItem(STORAGE_KEY, JSON.stringify(normalized));
      memoryEntries = normalized;
      return { ok: true, persistent: store === window.localStorage };
    } catch {
      memoryEntries = normalized;
      return { ok: false, persistent: false };
    }
  }

  function isPersistent() {
    return resolveStorage() === window.localStorage;
  }

  function bindPersistenceReload(reloadFn) {
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) reloadFn();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") reloadFn();
    });
    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEY || event.key === null) reloadFn();
    });
  }

  function countTotal(entries) {
    return Object.values(entries).reduce((sum, arr) => sum + arr.length, 0);
  }

  function formatMonthLabel(year, month) {
    return new Date(year, month, 1).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
    });
  }

  function formatDayTitle(key) {
    const { year, month, day } = parseDateKey(key);
    return new Date(year, month, day).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
    });
  }

  function calendarUrl(year, month) {
    return `diary.html?y=${year}&m=${month + 1}`;
  }

  function dayUrl(key) {
    return `diary-day.html?date=${encodeURIComponent(key)}`;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function truncate(text, max) {
    if (!text || text.length <= max) return text;
    return `${text.slice(0, max)}…`;
  }

  function starsHtml(rating, compact = false) {
    const r = Math.max(0, Math.min(5, Math.round(Number(rating) || 0)));
    let html = "";
    for (let i = 1; i <= 5; i += 1) {
      const cls = i <= r ? "diary-star-display diary-star-display--on" : "diary-star-display";
      html += `<span class="${cls}" aria-hidden="true">★</span>`;
    }
    if (!compact) {
      html += `<span class="diary-rating-num">${r}점</span>`;
    }
    return html;
  }

  function bindStarPicker(pickerEl, hiddenInput, labelEl, initial = 4) {
    const stars = pickerEl.querySelectorAll(".diary-star");
    let selected = initial;

    function render(preview) {
      const value = preview ?? selected;
      stars.forEach((btn) => {
        const r = Number(btn.dataset.rating);
        btn.classList.toggle("active", r <= value);
        btn.setAttribute("aria-checked", r === selected ? "true" : "false");
      });
      hiddenInput.value = String(selected);
      if (labelEl) labelEl.textContent = `${selected}점`;
    }

    stars.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        selected = Number(btn.dataset.rating);
        render();
      });
      btn.addEventListener("mouseenter", () => render(Number(btn.dataset.rating)));
    });

    pickerEl.addEventListener("mouseleave", () => render());
    render();
    return {
      getRating: () => selected,
      setRating: (value) => {
        selected = Math.max(1, Math.min(5, Number(value) || 4));
        render();
      },
    };
  }

  function normalizeName(name) {
    return String(name || "").trim().replace(/\s+/g, " ");
  }

  /** 식사 기록에서 minRating 이상 별점을 준 식당 (이름 기준 중복 제거) */
  function collectHighlyRated(minRating = 4) {
    const entries = loadEntries();
    const byName = new Map();

    Object.entries(entries).forEach(([dateKey, dayEntries]) => {
      dayEntries.forEach((entry) => {
        if (entry.rating < minRating) return;
        const name = normalizeName(entry.name);
        if (!name) return;

        const existing = byName.get(name);
        if (!existing) {
          byName.set(name, {
            name,
            rating: entry.rating,
            lastVisit: dateKey,
            visitCount: 1,
            memo: entry.memo || "",
            price_min_krw: entry.price_min_krw ?? null,
            price_max_krw: entry.price_max_krw ?? null,
          });
          return;
        }

        existing.visitCount += 1;
        if (entry.rating > existing.rating) existing.rating = entry.rating;
        if (dateKey > existing.lastVisit) {
          existing.lastVisit = dateKey;
          if (entry.memo) existing.memo = entry.memo;
          if (entry.price_min_krw != null) existing.price_min_krw = entry.price_min_krw;
          if (entry.price_max_krw != null) existing.price_max_krw = entry.price_max_krw;
        } else if (dateKey === existing.lastVisit) {
          if (entry.memo) existing.memo = entry.memo;
          if (entry.price_min_krw != null) existing.price_min_krw = entry.price_min_krw;
          if (entry.price_max_krw != null) existing.price_max_krw = entry.price_max_krw;
        }
      });
    });

    return [...byName.values()].sort((a, b) => {
      if (b.rating !== a.rating) return b.rating - a.rating;
      if (b.lastVisit !== a.lastVisit) return b.lastVisit.localeCompare(a.lastVisit);
      return a.name.localeCompare(b.name, "ko");
    });
  }

  async function fetchPlacesWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) return null;
      const data = await res.json();
      return Array.isArray(data.places) ? data.places : null;
    } catch {
      return null;
    } finally {
      clearTimeout(timer);
    }
  }

  async function loadPlaces() {
    const cached = await fetchPlacesWithTimeout("data/places.json", 15000);
    if (cached) return cached;
    const live = await fetchPlacesWithTimeout("/api/places", 5000);
    return live || [];
  }

  function findPlaceByName(places, name) {
    const norm = normalizeName(name);
    if (!norm) return null;

    let found = places.find((p) => normalizeName(p.name) === norm);
    if (found) return found;

    found = places.find((p) => {
      const pn = normalizeName(p.name);
      return pn.includes(norm) || norm.includes(pn);
    });
    return found || null;
  }

  async function loadPlaceSuggestions(datalistEl) {
    const places = await loadPlaces();
    if (!places.length) return [];
    const names = [...new Set(places.map((p) => p.name).filter(Boolean))].sort();
    datalistEl.innerHTML = names
      .map((name) => `<option value="${escapeHtml(name)}"></option>`)
      .join("");
    return names;
  }

  return {
    STORAGE_KEY,
    dateKey,
    parseDateKey,
    loadEntries,
    saveEntries,
    isPersistent,
    bindPersistenceReload,
    countTotal,
    formatMonthLabel,
    formatDayTitle,
    calendarUrl,
    dayUrl,
    escapeHtml,
    truncate,
    starsHtml,
    bindStarPicker,
    normalizeName,
    parseOptionalPrice,
    normalizePriceFields,
    formatPriceRange,
    collectHighlyRated,
    loadPlaces,
    findPlaceByName,
    loadPlaceSuggestions,
  };
})();
