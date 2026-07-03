/**
 * 잠실맛집 웹 UI — 지도(하트 마커) + 분류별 목록
 */

const CATEGORY_ORDER = [
  "korean", "chinese", "japanese", "western", "bunsik", "fast_food", "cafe", "dessert", "other",
];

const CATEGORY_ICONS = {
  korean: "🍚",
  chinese: "🥟",
  japanese: "🍣",
  western: "🍝",
  bunsik: "🍢",
  fast_food: "🍔",
  cafe: "☕",
  dessert: "🍰",
  other: "🍽️",
};

const state = {
  data: null,
  filters: {
    minRating: 4,
    maxPrice: 15000,
    maxWalk: 15,
    placeType: "all",
  },
  map: null,
  markers: [],
  activeMarker: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function formatPrice(krw) {
  if (krw == null) return "가격 미정";
  return `${krw.toLocaleString("ko-KR")}원`;
}

function formatWalk(minutes) {
  if (minutes == null) return "-";
  return `도보 ${Math.round(minutes)}분`;
}

function formatDistance(meters) {
  if (meters == null) return "";
  if (meters < 1000) return `${Math.round(meters)}m`;
  return `${(meters / 1000).toFixed(1)}km`;
}

function formatRating(rating) {
  if (rating == null) return "평점 없음";
  return `★ ${rating.toFixed(1)}`;
}

function passesFilters(place) {
  const { minRating, maxPrice, maxWalk, placeType } = state.filters;

  if (placeType !== "all" && place.place_type !== placeType) return false;
  if (place.walk_minutes != null && place.walk_minutes > maxWalk) return false;
  if (place.rating != null && place.rating < minRating) return false;
  if (place.price_per_person_krw != null && place.price_per_person_krw > maxPrice) return false;
  return true;
}

function getFilteredPlaces() {
  if (!state.data?.places) return [];
  return state.data.places.filter(passesFilters);
}

function groupByCategory(places) {
  const groups = {};
  for (const place of places) {
    const key = place.category || "other";
    if (!groups[key]) groups[key] = [];
    groups[key].push(place);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => (a.walk_minutes ?? 99) - (b.walk_minutes ?? 99));
  }
  return groups;
}

function renderPopupContent(place) {
  const newBadge = place.is_new_opening
    ? '<span class="popup-new-badge">NEW</span>'
    : "";
  const link = place.url
    ? `<a class="popup-link" href="${place.url}" target="_blank" rel="noopener">카카오맵에서 보기 →</a>`
    : "";

  return `
    <div class="popup-name">${escapeHtml(place.name)}${newBadge}</div>
    <span class="popup-category">${escapeHtml(place.category_label)}</span>
    <div class="popup-meta">
      <div><strong>메뉴</strong> ${escapeHtml(place.representative_menu || "-")}</div>
      <div><strong>가격</strong> ${formatPrice(place.price_per_person_krw)}</div>
      <div><strong>평점</strong> ${formatRating(place.rating)}</div>
      <div><strong>거리</strong> ${formatWalk(place.walk_minutes)} (${formatDistance(place.distance_meters)})</div>
      <div><strong>주소</strong> ${escapeHtml(place.address)}</div>
    </div>
    ${link}
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showMapPopup(place) {
  const popup = $("#map-popup");
  const body = $("#map-popup-body");
  body.innerHTML = renderPopupContent(place);
  popup.classList.remove("hidden");

  if (state.activeMarker) {
    state.activeMarker.classList.remove("active");
  }
  const markerEl = document.querySelector(`[data-place-id="${place.id}"] .heart-pin`);
  if (markerEl) {
    markerEl.classList.add("active");
    state.activeMarker = markerEl;
  }
}

function hideMapPopup() {
  $("#map-popup").classList.add("hidden");
  if (state.activeMarker) {
    state.activeMarker.classList.remove("active");
    state.activeMarker = null;
  }
}

function createHeartIcon(place) {
  const isNew = place.is_new_opening;
  return L.divIcon({
    className: "heart-marker",
    html: `<div class="heart-pin${isNew ? " new" : ""}" data-place-id="${place.id}">♥</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
  });
}

function initMap() {
  const office = state.data.office;
  if (state.map) {
    state.map.remove();
    state.map = null;
    state.markers = [];
  }

  state.map = L.map("map", {
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView([office.lat, office.lng], 16);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
    subdomains: "abcd",
    maxZoom: 20,
  }).addTo(state.map);

  const officeIcon = L.divIcon({
    className: "office-marker-wrap",
    html: '<div class="office-marker" title="Fraunhofer 한국사무소">🏢</div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
  L.marker([office.lat, office.lng], { icon: officeIcon })
    .addTo(state.map)
    .bindPopup(`<strong>${office.name}</strong><br>${office.address}`);

  updateMapMarkers();
}

function updateMapMarkers() {
  if (!state.map) return;

  for (const m of state.markers) {
    state.map.removeLayer(m);
  }
  state.markers = [];

  const places = getFilteredPlaces();
  for (const place of places) {
    const marker = L.marker([place.lat, place.lng], {
      icon: createHeartIcon(place),
    }).addTo(state.map);

    marker.on("click", () => showMapPopup(place));
    state.markers.push(marker);
  }

  if (places.length > 0) {
    const bounds = L.latLngBounds(places.map((p) => [p.lat, p.lng]));
    bounds.extend([state.data.office.lat, state.data.office.lng]);
    state.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
  }
}

function renderCategoryList() {
  const container = $("#category-list");
  const empty = $("#list-empty");
  const places = getFilteredPlaces();
  const groups = groupByCategory(places);

  container.innerHTML = "";

  if (places.length === 0) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  const sortedKeys = CATEGORY_ORDER.filter((k) => groups[k]?.length);
  const extraKeys = Object.keys(groups).filter((k) => !CATEGORY_ORDER.includes(k));
  const allKeys = [...sortedKeys, ...extraKeys];

  for (const key of allKeys) {
    const items = groups[key];
    if (!items?.length) continue;

    const label = items[0].category_label || key;
    const icon = CATEGORY_ICONS[key] || "🍽️";

    const section = document.createElement("section");
    section.className = "category-section";
    section.innerHTML = `
      <div class="category-header ${key}">
        <span class="category-icon">${icon}</span>
        <span>${escapeHtml(label)}</span>
        <span style="margin-left:auto;font-size:0.82rem;color:var(--text-muted)">${items.length}곳</span>
      </div>
      <div class="place-cards"></div>
    `;

    const cards = section.querySelector(".place-cards");
    for (const place of items) {
      const card = document.createElement("article");
      card.className = "place-card";
      card.innerHTML = `
        <div class="place-card-name">
          ${escapeHtml(place.name)}
          ${place.is_new_opening ? '<span class="place-card-new">NEW</span>' : ""}
        </div>
        <div class="place-card-menu">🍴 ${escapeHtml(place.representative_menu || "시그니처 메뉴")}</div>
        <div class="place-card-stats">
          <span class="stat-rating">${formatRating(place.rating)}</span>
          <span class="stat-distance">${formatWalk(place.walk_minutes)} · ${formatDistance(place.distance_meters)}</span>
          <span class="stat-price">${formatPrice(place.price_per_person_krw)}</span>
        </div>
      `;
      card.addEventListener("click", () => {
        switchView("map");
        showMapPopup(place);
        state.map?.setView([place.lat, place.lng], 17, { animate: true });
      });
      cards.appendChild(card);
    }
    container.appendChild(section);
  }
}

function passesNewOpeningFilters(place) {
  const { maxWalk } = state.filters;
  if (place.place_type !== "restaurant" && place.place_type !== "cafe") return false;
  if (place.walk_minutes != null && place.walk_minutes > maxWalk) return false;
  return true;
}

function getNewOpenings() {
  let openings = state.data?.new_openings ?? [];
  if (!openings.length) {
    openings = state.data?.places?.filter((p) => p.is_new_opening) ?? [];
  }
  return openings
    .filter(passesNewOpeningFilters)
    .sort((a, b) => (a.walk_minutes ?? 99) - (b.walk_minutes ?? 99));
}

function renderNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const body = $("#new-opening-panel-body");
  const tab = $("#new-opening-panel-tab");
  const countEl = $("#new-opening-count");
  const openings = getNewOpenings();
  const days = state.data?.defaults?.new_opening_days ?? 30;

  if (!openings.length) {
    panel.classList.add("hidden");
    tab.classList.add("hidden");
    return;
  }

  const eyebrow = panel.querySelector(".new-opening-panel-eyebrow");
  if (eyebrow) eyebrow.textContent = `최근 ${days}일`;

  countEl.textContent = `(${openings.length}곳)`;
  body.innerHTML = openings
    .map(
      (place) => `
    <article class="new-opening-card" data-place-id="${escapeHtml(place.id)}">
      <div class="new-opening-card-head">
        <span class="new-opening-name">${escapeHtml(place.name)}</span>
        <span class="new-opening-badge">NEW</span>
      </div>
      <span class="new-opening-type">${escapeHtml(place.category_label)} · ${place.place_type === "cafe" ? "카페" : "맛집"}</span>
      <dl class="new-opening-details">
        <div><dt>대표메뉴</dt><dd>${escapeHtml(place.representative_menu || "-")}</dd></div>
        <div><dt>가격</dt><dd class="price">${formatPrice(place.price_per_person_krw)}</dd></div>
        <div><dt>도보</dt><dd class="walk">${formatWalk(place.walk_minutes)}</dd></div>
      </dl>
    </article>
  `
    )
    .join("");

  body.querySelectorAll(".new-opening-card").forEach((card) => {
    card.addEventListener("click", () => {
      const id = card.dataset.placeId;
      const place =
        openings.find((p) => p.id === id) ?? state.data.places.find((p) => p.id === id);
      if (!place) return;
      switchView("map");
      showMapPopup(place);
      state.map?.setView([place.lat, place.lng], 17, { animate: true });
    });
  });

  panel.classList.remove("hidden", "collapsed");
  tab.classList.add("hidden");
}

function bindNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const tab = $("#new-opening-panel-tab");

  $("#new-opening-panel-toggle")?.addEventListener("click", () => {
    panel.classList.add("collapsed");
    tab.classList.remove("hidden");
  });

  tab?.addEventListener("click", () => {
    panel.classList.remove("collapsed");
    tab.classList.add("hidden");
  });
}

function updateResultCount() {
  const total = state.data?.places?.length ?? 0;
  const filtered = getFilteredPlaces().length;
  $("#result-count").textContent = `표시 중 ${filtered}곳 / 전체 ${total}곳`;
}

function render() {
  renderNewOpeningPanel();
  updateMapMarkers();
  renderCategoryList();
  updateResultCount();
}

function switchView(view) {
  $$(".tab").forEach((tab) => {
    const isActive = tab.dataset.view === view;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", isActive);
  });

  $("#view-map").classList.toggle("active", view === "map");
  $("#view-map").hidden = view !== "map";
  $("#view-list").classList.toggle("active", view === "list");
  $("#view-list").hidden = view !== "list";

  if (view === "map" && state.map) {
    setTimeout(() => state.map.invalidateSize(), 100);
  }
}

function bindFilters() {
  const ratingInput = $("#filter-rating");
  const priceInput = $("#filter-price");
  const walkInput = $("#filter-walk");

  ratingInput.addEventListener("input", () => {
    state.filters.minRating = parseFloat(ratingInput.value);
    $("#rating-value").textContent = state.filters.minRating.toFixed(1);
    render();
  });

  priceInput.addEventListener("input", () => {
    state.filters.maxPrice = parseInt(priceInput.value, 10);
    $("#price-value").textContent = state.filters.maxPrice.toLocaleString("ko-KR");
    render();
  });

  walkInput.addEventListener("input", () => {
    state.filters.maxWalk = parseInt(walkInput.value, 10);
    $("#walk-value").textContent = state.filters.maxWalk;
    render();
  });

  $$(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $$(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.filters.placeType = chip.dataset.type;
      render();
    });
  });
}

function bindTabs() {
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
}

async function loadData() {
  const sources = ["/api/places", "data/places.json"];

  for (const url of sources) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const data = await res.json();
      if (data.places) return data;
    } catch {
      /* try next */
    }
  }
  throw new Error("데이터를 불러올 수 없습니다.");
}

function applyDefaults(data) {
  if (!data.defaults) return;
  const d = data.defaults;
  state.filters.minRating = d.min_rating ?? 4;
  state.filters.maxPrice = d.max_price_per_person_krw ?? 15000;
  state.filters.maxWalk = d.max_walk_minutes ?? 15;

  $("#filter-rating").value = state.filters.minRating;
  $("#rating-value").textContent = state.filters.minRating.toFixed(1);
  $("#filter-price").value = state.filters.maxPrice;
  $("#price-value").textContent = state.filters.maxPrice.toLocaleString("ko-KR");
  $("#filter-walk").value = state.filters.maxWalk;
  $("#walk-value").textContent = state.filters.maxWalk;
}

async function init() {
  const overlay = document.createElement("div");
  overlay.className = "loading-overlay";
  overlay.textContent = "맛집 데이터 불러오는 중…";
  document.body.appendChild(overlay);

  try {
    state.data = await loadData();
    applyDefaults(state.data);
    initMap();
    render();
  } catch (err) {
    $("#result-count").textContent = err.message;
  } finally {
    overlay.remove();
  }

  bindFilters();
  bindTabs();
  bindNewOpeningPanel();

  $(".popup-close").addEventListener("click", hideMapPopup);

  $("#btn-refresh").addEventListener("click", async () => {
    $("#btn-refresh").disabled = true;
    try {
      state.data = await loadData();
      applyDefaults(state.data);
      initMap();
      render();
    } catch (err) {
      alert(err.message);
    } finally {
      $("#btn-refresh").disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
