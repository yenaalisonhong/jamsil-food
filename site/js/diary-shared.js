/**
 * 식사 기록 — 공통 저장·날짜·별점 유틸
 *
 * 저장 우선순위:
 * 1) 사이트 data/diary.json (기기 공통)
 * 2) 로컬 서버 /api/diary
 * 3) GitHub Contents API (토큰 설정 시)
 * 4) localStorage 캐시 (오프라인·즉시 반영)
 */
const DiaryStorage = (() => {
  const STORAGE_KEY = "jamsil_meal_diary";
  const TOKEN_KEY = "jamsil_diary_github_token";
  const META_KEY = "jamsil_diary_meta";
  const GITHUB_REPO = "yenaalisonhong/jamsil-food";
  const GITHUB_PATH = "docs/data/diary.json";
  const SITE_DIARY_URL = "data/diary.json";
  const API_DIARY_URL = "/api/diary";

  let storage = null;
  let memoryEntries = {};
  let syncState = {
    status: "idle",
    source: "local",
    message: "",
    updatedAt: null,
  };
  const syncListeners = new Set();

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
          place_id: typeof entry.place_id === "string"
            ? entry.place_id
            : (typeof entry.placeId === "string" ? entry.placeId : ""),
          ...normalizePriceFields(entry),
          createdAt: typeof entry.createdAt === "string" ? entry.createdAt : new Date().toISOString(),
        }));
      if (rows.length) out[key] = rows;
    });
    return out;
  }

  function readUpdatedAt(data) {
    if (!data || typeof data !== "object") return null;
    const raw = data._updatedAt || data.updatedAt;
    return typeof raw === "string" && raw ? raw : null;
  }

  function packPayload(entries, updatedAt) {
    const normalized = normalizeEntries(entries);
    return {
      _updatedAt: updatedAt || new Date().toISOString(),
      ...normalized,
    };
  }

  function entryFingerprint(entry) {
    return [
      entry.createdAt || "",
      entry.name || "",
      entry.rating ?? "",
      entry.memo || "",
      entry.price_min_krw ?? "",
      entry.price_max_krw ?? "",
    ].join("|");
  }

  function mergeEntries(localEntries, remoteEntries) {
    const merged = {};
    const dates = new Set([
      ...Object.keys(normalizeEntries(localEntries)),
      ...Object.keys(normalizeEntries(remoteEntries)),
    ]);
    dates.forEach((date) => {
      const map = new Map();
      [...(localEntries[date] || []), ...(remoteEntries[date] || [])].forEach((entry) => {
        map.set(entryFingerprint(entry), entry);
      });
      const rows = [...map.values()].sort((a, b) =>
        String(a.createdAt).localeCompare(String(b.createdAt)),
      );
      if (rows.length) merged[date] = rows;
    });
    return merged;
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

  function loadMeta() {
    const store = resolveStorage();
    if (!store) return {};
    try {
      return JSON.parse(store.getItem(META_KEY) || "{}") || {};
    } catch {
      return {};
    }
  }

  function saveMeta(meta) {
    const store = resolveStorage();
    if (!store) return;
    try {
      store.setItem(META_KEY, JSON.stringify(meta));
    } catch {
      /* ignore */
    }
  }

  function getGithubToken() {
    const store = resolveStorage();
    if (!store) return "";
    try {
      return String(store.getItem(TOKEN_KEY) || "").trim();
    } catch {
      return "";
    }
  }

  function setGithubToken(token) {
    const store = resolveStorage();
    if (!store) return false;
    try {
      const value = String(token || "").trim();
      if (value) store.setItem(TOKEN_KEY, value);
      else store.removeItem(TOKEN_KEY);
      return true;
    } catch {
      return false;
    }
  }

  function setSyncState(patch) {
    syncState = { ...syncState, ...patch };
    syncListeners.forEach((fn) => {
      try {
        fn(getSyncState());
      } catch {
        /* ignore */
      }
    });
  }

  function getSyncState() {
    return { ...syncState, hasToken: Boolean(getGithubToken()) };
  }

  function onSyncStateChange(fn) {
    syncListeners.add(fn);
    try {
      fn(getSyncState());
    } catch {
      /* ignore */
    }
    return () => syncListeners.delete(fn);
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

  function saveEntriesLocal(entries, updatedAt) {
    const normalized = normalizeEntries(entries);
    const stamp = updatedAt || new Date().toISOString();
    const store = resolveStorage();
    if (!store) {
      memoryEntries = normalized;
      saveMeta({ updatedAt: stamp });
      return { ok: false, persistent: false, updatedAt: stamp };
    }
    try {
      store.setItem(STORAGE_KEY, JSON.stringify(normalized));
      memoryEntries = normalized;
      saveMeta({ updatedAt: stamp });
      return {
        ok: true,
        persistent: store === window.localStorage,
        updatedAt: stamp,
      };
    } catch {
      memoryEntries = normalized;
      saveMeta({ updatedAt: stamp });
      return { ok: false, persistent: false, updatedAt: stamp };
    }
  }

  function saveEntries(entries) {
    return saveEntriesLocal(entries);
  }

  async function fetchJson(url, options = {}, timeoutMs = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      return res;
    } finally {
      clearTimeout(timer);
    }
  }

  async function fetchRemoteFromSite() {
    const bust = `t=${Date.now()}`;
    const urls = [
      `${SITE_DIARY_URL}?${bust}`,
      `https://raw.githubusercontent.com/${GITHUB_REPO}/main/${GITHUB_PATH}?${bust}`,
    ];
    for (const url of urls) {
      try {
        const res = await fetchJson(url, { cache: "no-store" });
        if (!res.ok) continue;
        const data = await res.json();
        if (!data || typeof data !== "object" || Array.isArray(data)) continue;
        return {
          entries: normalizeEntries(data),
          updatedAt: readUpdatedAt(data),
          source: url.includes("raw.githubusercontent") ? "github-raw" : "site",
        };
      } catch {
        /* try next */
      }
    }
    return null;
  }

  async function fetchRemoteFromApi() {
    try {
      const res = await fetchJson(API_DIARY_URL, { cache: "no-store" }, 4000);
      if (!res.ok) return null;
      const data = await res.json();
      if (!data || typeof data !== "object") return null;
      const payload = data.entries && typeof data.entries === "object" ? data : data;
      return {
        entries: normalizeEntries(payload),
        updatedAt: readUpdatedAt(payload) || data.updatedAt || null,
        source: "api",
      };
    } catch {
      return null;
    }
  }

  async function pushToApi(entries, updatedAt) {
    const payload = packPayload(entries, updatedAt);
    const res = await fetchJson(API_DIARY_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(payload),
    }, 8000);
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `API 저장 실패 (${res.status})`);
    }
    return { source: "api", updatedAt: payload._updatedAt };
  }

  function decodeBase64Utf8(b64) {
    const bin = atob(b64);
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  function encodeBase64Utf8(text) {
    const bytes = new TextEncoder().encode(text);
    let bin = "";
    bytes.forEach((b) => {
      bin += String.fromCharCode(b);
    });
    return btoa(bin);
  }

  async function pushToGithub(entries, updatedAt) {
    const token = getGithubToken();
    if (!token) throw new Error("GitHub 토큰이 없습니다");

    const payload = packPayload(entries, updatedAt);
    const content = `${JSON.stringify(payload, null, 2)}\n`;
    const apiBase = `https://api.github.com/repos/${GITHUB_REPO}/contents/${GITHUB_PATH}`;
    const headers = {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28",
    };

    let sha = null;
    const getRes = await fetchJson(apiBase, { headers }, 10000);
    if (getRes.ok) {
      const existing = await getRes.json();
      sha = existing.sha || null;
    } else if (getRes.status !== 404) {
      const err = await getRes.json().catch(() => ({}));
      throw new Error(err.message || `GitHub 읽기 실패 (${getRes.status})`);
    }

    const body = {
      message: `chore: update meal diary (${payload._updatedAt})`,
      content: encodeBase64Utf8(content),
      branch: "main",
    };
    if (sha) body.sha = sha;

    const putRes = await fetchJson(apiBase, {
      method: "PUT",
      headers,
      body: JSON.stringify(body),
    }, 15000);

    if (!putRes.ok) {
      const err = await putRes.json().catch(() => ({}));
      throw new Error(err.message || `GitHub 저장 실패 (${putRes.status})`);
    }

    return { source: "github", updatedAt: payload._updatedAt };
  }

  async function pushRemote(entries, updatedAt) {
    try {
      return await pushToApi(entries, updatedAt);
    } catch {
      /* fall through to GitHub when local API is unavailable */
    }
    if (getGithubToken()) {
      return pushToGithub(entries, updatedAt);
    }
    throw new Error("원격 저장소를 사용할 수 없습니다");
  }

  async function hydrateFromRemote() {
    setSyncState({ status: "syncing", message: "사이트에서 불러오는 중…" });

    const localEntries = loadEntries();
    const localMeta = loadMeta();
    const localUpdatedAt = localMeta.updatedAt || null;

    let remote = await fetchRemoteFromApi();
    if (!remote) remote = await fetchRemoteFromSite();

    if (!remote) {
      const hasLocal = countTotal(localEntries) > 0;
      setSyncState({
        status: hasLocal ? "local-only" : "empty",
        source: "local",
        message: hasLocal
          ? (getGithubToken()
            ? "사이트 기록을 못 불러왔어요. 저장 시 다시 동기화합니다."
            : "이 기기 기록만 있어요. 동기화 설정 후 사이트에 저장하세요.")
          : "아직 기록이 없어요.",
        updatedAt: localUpdatedAt,
      });
      return localEntries;
    }

    const remoteCount = countTotal(remote.entries);
    const localCount = countTotal(localEntries);
    let nextEntries = remote.entries;
    let nextUpdatedAt = remote.updatedAt || new Date().toISOString();
    let shouldPush = false;

    if (localCount && remoteCount) {
      nextEntries = mergeEntries(localEntries, remote.entries);
      if (JSON.stringify(normalizeEntries(nextEntries)) !== JSON.stringify(remote.entries)) {
        shouldPush = true;
        nextUpdatedAt = new Date().toISOString();
      }
    } else if (localCount && !remoteCount) {
      nextEntries = localEntries;
      shouldPush = true;
      nextUpdatedAt = localUpdatedAt || new Date().toISOString();
    }

    saveEntriesLocal(nextEntries, nextUpdatedAt);

    if (shouldPush) {
      try {
        const pushed = await pushRemote(nextEntries, nextUpdatedAt);
        setSyncState({
          status: "synced",
          source: pushed.source,
          message: "사이트에 저장됨 · 모든 기기에서 볼 수 있어요",
          updatedAt: pushed.updatedAt,
        });
      } catch (err) {
        setSyncState({
          status: getGithubToken() ? "error" : "local-only",
          source: remote.source,
          message: getGithubToken()
            ? `불러옴 · 저장 실패: ${err.message || err}`
            : "사이트 기록 불러옴 · 쓰려면 동기화 설정이 필요해요",
          updatedAt: nextUpdatedAt,
        });
      }
      return nextEntries;
    }

    setSyncState({
      status: "synced",
      source: remote.source,
      message: "사이트에 저장됨 · 모든 기기에서 볼 수 있어요",
      updatedAt: nextUpdatedAt,
    });
    return nextEntries;
  }

  async function saveEntriesAsync(entries) {
    const stamp = new Date().toISOString();
    const localResult = saveEntriesLocal(entries, stamp);
    setSyncState({ status: "syncing", message: "사이트에 저장하는 중…", updatedAt: stamp });

    try {
      const pushed = await pushRemote(entries, stamp);
      setSyncState({
        status: "synced",
        source: pushed.source,
        message: "사이트에 저장됨 · 모든 기기에서 볼 수 있어요",
        updatedAt: pushed.updatedAt,
      });
      return { ...localResult, remote: true, source: pushed.source };
    } catch (err) {
      const needsToken = !getGithubToken();
      setSyncState({
        status: needsToken ? "local-only" : "error",
        source: "local",
        message: needsToken
          ? "이 기기에만 저장됨 · 동기화 설정 후 사이트에 올릴 수 있어요"
          : `이 기기에만 저장됨 · ${err.message || err}`,
        updatedAt: stamp,
      });
      return {
        ...localResult,
        remote: false,
        error: err.message || String(err),
      };
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

  function findPlace(places, name, placeId = null) {
    if (placeId) {
      const byId = places.find((p) => p?.id === placeId);
      if (byId) return byId;
    }
    return findPlaceByName(places, name);
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

  function bindSyncStatus(el) {
    if (!el) return () => {};
    return onSyncStateChange((state) => {
      el.textContent = state.message || (
        state.status === "synced" ? "사이트에 저장됨" : "로컬 저장"
      );
      el.dataset.syncStatus = state.status;
    });
  }

  function bindSyncSettings(root) {
    if (!root) return;
    const openBtn = root.querySelector("[data-diary-sync-open]");
    const panel = root.querySelector("[data-diary-sync-panel]");
    const input = root.querySelector("[data-diary-sync-token]");
    const saveBtn = root.querySelector("[data-diary-sync-save]");
    const clearBtn = root.querySelector("[data-diary-sync-clear]");
    const hint = root.querySelector("[data-diary-sync-hint]");
    if (!openBtn || !panel || !input || !saveBtn) return;

    const refresh = () => {
      const token = getGithubToken();
      input.value = token;
      if (hint) {
        hint.textContent = token
          ? "토큰이 이 기기에 저장되어 있어요. 기록 추가·삭제 시 사이트(data/diary.json)에 반영됩니다."
          : "GitHub fine-grained PAT(Contents 읽기/쓰기, 이 저장소만)를 입력하면 다른 기기에서도 같은 기록이 보여요.";
      }
    };

    openBtn.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) {
        refresh();
        input.focus();
      }
    });

    saveBtn.addEventListener("click", async () => {
      setGithubToken(input.value);
      refresh();
      panel.hidden = true;
      setSyncState({ status: "syncing", message: "동기화 설정 저장 · 다시 불러오는 중…" });
      await hydrateFromRemote();
      window.dispatchEvent(new CustomEvent("diary-sync-updated"));
    });

    clearBtn?.addEventListener("click", () => {
      setGithubToken("");
      input.value = "";
      refresh();
      setSyncState({
        status: "local-only",
        source: "local",
        message: "토큰 삭제됨 · 읽기는 사이트 파일, 쓰기는 이 기기만",
      });
    });

    refresh();
  }

  return {
    STORAGE_KEY,
    GITHUB_REPO,
    GITHUB_PATH,
    dateKey,
    parseDateKey,
    loadEntries,
    saveEntries,
    saveEntriesAsync,
    hydrateFromRemote,
    getSyncState,
    onSyncStateChange,
    bindSyncStatus,
    bindSyncSettings,
    getGithubToken,
    setGithubToken,
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
    findPlace,
    findPlaceByName,
    loadPlaceSuggestions,
  };
})();
