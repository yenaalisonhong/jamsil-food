/**
 * 잠실맛집 웹 UI — 지도(핀 마커) + 분류별 목록
 */

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

const CATEGORY_LABELS = {
  korean: "한식",
  chinese: "중식",
  japanese: "일식",
  western: "양식",
  bunsik: "분식",
  fast_food: "패스트푸드",
  cafe: "카페",
  dessert: "디저트",
  other: "기타",
};

const RESTAURANT_CATEGORY_KEYS = [
  "korean", "chinese", "japanese", "western", "bunsik", "fast_food",
];

const CAFE_SUB_LABELS = {
  cafe_franchise: "프랜차이즈",
  cafe_individual: "개인카페",
};

const FRANCHISE_CAFE_MARKERS = [
  "스타벅스", "이디야", "투썸", "메가커피", "메가MGC", "MGC", "빽다방",
  "컴포즈", "공차", "블루보틀", "파리바게뜨", "뚜레쥬르", "성심당", "폴바셋",
  "탐앤탐스", "할리스", "커피빈", "매머드", "더벤티", "텐퍼센트", "던킨",
  "크리스피크림", "베스킨", "배스킨", "노티드", "아티제", "요거트아이스크림",
  "하삼동", "리사르", "선호커피",
];

const GENERIC_MENUS = new Set([
  "점심 특선",
  "시그니처 메뉴",
  "한정식 / 제육볶음",
  "짜장면 / 탕수육",
  "초밥 / 돈카츠",
  "파스타 / 스테이크",
  "버거 / 샌드위치",
  "떡볶이 / 김밥",
  "아메리카노 / 라떼",
  "케이크 / 마카롱",
]);

const NON_FOOD_NAME_MARKERS = [
  "올리브영", "올영", "문구", "화장실", "학원", "교실", "어학원", "영어교실",
  "네일", "미용실", "헤어샵", "이발소", "바버샵", "약국", "안경", "부동산",
  "세탁", "휴대폰", "주차장", "종합상가", "전철상가", "편집샵", "프린트샵", "치과", "의원",
  "한의원", "은행", "다이소", "교보문고", "영풍문고", "GS25", "세븐일레븐",
  "이마트24", "CU ", "KT ", "SKT", "LG유플러스",
  "후지필름", "상상블럭", "어라운드홈", "아이피아", "월드크리닝", "하나투어",
  "아모레퍼시픽", "코인워시", "뽀송뽀송", "문화센터", "증명사진", "인쇄",
  "통신", "오빠통신", "정관장", "임시휴업", "워크룸", "키즈카페", "ATM",
  "코스트코", "노브랜드", "PC방", "노래방", "헬스", "필라테스",
  "야채가게", "과일가게", "정육점", "수산마트", "양복점", "공유창고",
  "사업협회", "관리소", "홀딩스", "여행사", "더샵", "뷰티카페",
];

const NON_FOOD_REVIEW_MARKERS = [
  "증명사진", "인쇄", "복사", "세탁", "코인워시", "휴대폰", "개통", "통신",
  "문화센터", "강좌", "학원", "여행 상담", "가전", "가구", "보너스쿠폰",
  "임시휴업", "영업 중지", "예쁜 옷",
];

const FOOD_REVIEW_MARKERS = [
  "맛있", "맛집", "먹었", "먹고", "먹을", "식사", "메뉴", "음식", "커피", "라떼",
  "케이크", "버거", "치킨", "고기", "회식", "점심", "저녁", "맥주",
];

function isRetailGroceryShop(name) {
  const compact = (name || "").replace(/\s/g, "");
  const retailHints = ["야채", "과일", "정육", "수산", "청과", "채소"];
  if (!retailHints.some((hint) => compact.includes(hint))) return false;
  if (["가게", "마트", "상회", "직판", "시장"].some((token) => compact.includes(token))) return true;
  return compact.endsWith("청과") || compact.endsWith("정육");
}

function isMallNonFood(name) {
  const foodInMall = ["식탁", "식당", "푸드", "맛집", "카페", "커피", "치킨", "피자", "버거", "국수"];
  if (name.includes("홈플러스") && !foodInMall.some((m) => name.includes(m))) {
    return /홈플러스\s*[^\s]*점/.test(name) && !name.includes("식탁");
  }
  const mallBrands = ["후지필름", "상상블럭", "어라운드홈", "아이피아", "월드크리닝", "하나투어", "KT", "코인워시", "정관장"];
  if (mallBrands.some((b) => name.includes(b))) return true;
  return false;
}

function hasFoodSignal(name, review) {
  const hint = `${name} ${review || ""}`;
  return FOOD_REVIEW_MARKERS.some((marker) => hint.includes(marker));
}

function isFoodPlace(place) {
  const name = place.name || "";
  const review = (place.representative_review || "").slice(0, 240);
  if (isRetailGroceryShop(name)) return false;
  if (isMallNonFood(name)) return false;
  if (NON_FOOD_NAME_MARKERS.some((marker) => `${name} ${review}`.includes(marker))) return false;
  if (["스터디카페", "독서카페", "프린트카페", "무인카페", "보드카페", "뷰티카페"].some((m) => name.includes(m))) return false;
  if (NON_FOOD_REVIEW_MARKERS.some((marker) => review.includes(marker))) return false;
  if (place.category && place.category !== "other") return true;
  return hasFoodSignal(name, review);
}

const CATEGORY_MENU_FALLBACK = {
  korean: "한정식 / 제육볶음",
  chinese: "짜장면 / 탕수육",
  japanese: "초밥 / 돈카츠",
  western: "파스타 / 스테이크",
  fast_food: "버거 / 샌드위치",
  bunsik: "떡볶이 / 김밥",
  cafe: "아메리카노 / 라떼",
  dessert: "케이크 / 마카롱",
  other: "-",
};

const state = {
  data: null,
  filters: {
    minRating: 4,
    maxPrice: 15000,
    maxWalk: 15,
    placeType: "all",
    keyword: "",
  },
  map: null,
  markers: [],
  activeMarker: null,
  newOpeningPanelPosition: localStorage.getItem("newOpeningPanelPosition") || "right",
  dataLoading: false,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function formatPrice(place) {
  const lo = place.price_range_min_krw ?? place.price_per_person_krw;
  const hi = place.price_range_max_krw ?? place.price_per_person_krw;
  if (lo != null && hi != null) {
    if (lo === hi) return `${lo.toLocaleString("ko-KR")}원`;
    return `${lo.toLocaleString("ko-KR")}~${hi.toLocaleString("ko-KR")}원`;
  }
  if (place.price_per_person_krw != null) {
    return `${place.price_per_person_krw.toLocaleString("ko-KR")}원`;
  }
  return "8,000~15,000원";
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

function formatOpenedAt(openedAt) {
  if (!openedAt) return null;
  const parsed = new Date(`${openedAt}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return openedAt;
  const opts = { month: "short", day: "numeric" };
  if (parsed.getFullYear() !== new Date().getFullYear()) {
    opts.year = "numeric";
  }
  return parsed.toLocaleDateString("ko-KR", opts);
}

function displayMenu(place, fallback = "-") {
  const menu = (place?.representative_menu || "").trim();
  if (menu && !GENERIC_MENUS.has(menu)) return menu;
  const category = place?.category || "other";
  return CATEGORY_MENU_FALLBACK[category] || fallback;
}

const REVIEW_PREVIEW_LEN = 36;

function escapeAttr(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function findPlaceById(placeId) {
  return state.data?.places?.find((place) => place.id === placeId) ?? null;
}

function getNaverReviewUrl(place) {
  const idMatch = place.id?.match(/^naver:(\d+)$/);
  const placeId = idMatch?.[1] || place.url?.match(/\/place\/(\d+)/)?.[1];
  if (placeId) {
    return `https://pcmap.place.naver.com/restaurant/${placeId}/review/visitor`;
  }
  return place.url || null;
}

function getPlaceReviews(place) {
  if (!place) return [];
  const fromList = Array.isArray(place.representative_reviews)
    ? place.representative_reviews.filter(Boolean)
    : [];
  if (fromList.length) return fromList.slice(0, 2);
  if (place.representative_review) return [place.representative_review];
  return [];
}

function renderReviewBlocks(reviews, { maxLen } = {}) {
  return reviews
    .map((review, index) => {
      const text = maxLen && review.length > maxLen ? `${review.slice(0, maxLen)}…` : review;
      const indexLabel = reviews.length > 1
        ? `<span class="review-block-index" aria-hidden="true">${index + 1}</span>`
        : "";
      return `<blockquote class="review-block">${indexLabel}${escapeHtml(text)}</blockquote>`;
    })
    .join("");
}

function formatReviewAsRating(place) {
  const reviews = getPlaceReviews(place).slice(0, 2);
  if (!reviews.length) return "평점 없음";

  const renderSnippet = (text, index) => {
    const truncated = text.length > REVIEW_PREVIEW_LEN
      ? `${text.slice(0, REVIEW_PREVIEW_LEN)}…`
      : text;
    const indexBadge = reviews.length > 1
      ? `<span class="review-block-index" aria-hidden="true">${index + 1}</span>`
      : "";
    return `<span class="review-snippet-line">${indexBadge}${escapeHtml(truncated)}</span>`;
  };

  const inner = reviews.map(renderSnippet).join("");
  const needsModal = reviews.some((review) => review.length > REVIEW_PREVIEW_LEN) || reviews.length > 1;

  if (needsModal) {
    return `<button type="button" class="rating-review-link review-fallback-link" data-place-id="${escapeAttr(place.id)}" aria-label="대표 리뷰 보기">💬 ${inner}</button>`;
  }
  return `💬 ${inner}`;
}

function formatRatingLabel(place) {
  const count = place.review_count ? ` (${place.review_count})` : "";
  return `★ ${place.rating.toFixed(1)}${count}`;
}

function formatRating(place) {
  if (typeof place === "number") {
    return place == null ? "평점 없음" : `★ ${place.toFixed(1)}`;
  }
  if (place.rating != null) {
    if (getPlaceReviews(place).length) {
      return `<button type="button" class="rating-review-link" data-place-id="${escapeAttr(place.id)}" aria-label="대표 리뷰 보기">${formatRatingLabel(place)}</button>`;
    }
    return formatRatingLabel(place);
  }
  if (getPlaceReviews(place).length) {
    return formatReviewAsRating(place);
  }
  if (place.review_count > 0) {
    return `리뷰 ${place.review_count}건`;
  }
  return "평점 없음";
}

function openReviewModal(place, reviewText) {
  const modal = $("#review-modal");
  const reviews = reviewText ? [reviewText] : getPlaceReviews(place);
  if (!modal || !reviews.length) return;

  $("#review-modal-title").textContent = place?.name || "리뷰";
  $("#review-modal-body").innerHTML = renderReviewBlocks(reviews);

  const naverLink = $("#review-modal-naver");
  const reviewUrl = getNaverReviewUrl(place);
  if (naverLink) {
    if (reviewUrl) {
      naverLink.href = reviewUrl;
      naverLink.classList.remove("hidden");
    } else {
      naverLink.classList.add("hidden");
    }
  }

  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  modal.querySelector(".review-modal-close")?.focus();
}

function closeReviewModal() {
  const modal = $("#review-modal");
  if (!modal || modal.classList.contains("hidden")) return;
  modal.classList.add("hidden");
  document.body.style.overflow = "";
}

let reviewPopoverHideTimer = null;

function ensureReviewPopover() {
  let popover = $("#review-popover");
  if (!popover) {
    popover = document.createElement("div");
    popover.id = "review-popover";
    popover.className = "review-popover hidden";
    popover.setAttribute("role", "tooltip");
    document.body.appendChild(popover);
  }
  return popover;
}

function positionReviewPopover(popover, anchor) {
  const rect = anchor.getBoundingClientRect();
  const margin = 8;
  popover.style.left = "0";
  popover.style.top = "0";
  popover.classList.remove("hidden");

  const popRect = popover.getBoundingClientRect();
  let left = rect.left + rect.width / 2 - popRect.width / 2;
  let top = rect.bottom + margin;

  if (top + popRect.height > window.innerHeight - margin) {
    top = rect.top - popRect.height - margin;
  }
  left = Math.max(margin, Math.min(left, window.innerWidth - popRect.width - margin));
  top = Math.max(margin, Math.min(top, window.innerHeight - popRect.height - margin));

  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function showReviewPopover(anchor, place) {
  const reviews = getPlaceReviews(place);
  if (!reviews.length) return;

  clearTimeout(reviewPopoverHideTimer);
  const popover = ensureReviewPopover();
  popover.innerHTML = `
    ${renderReviewBlocks(reviews, { maxLen: 140 })}
    <p class="review-popover-hint">클릭하면 전체 보기</p>
  `;
  positionReviewPopover(popover, anchor);
}

function hideReviewPopover(delay = 120) {
  clearTimeout(reviewPopoverHideTimer);
  reviewPopoverHideTimer = setTimeout(() => {
    $("#review-popover")?.classList.add("hidden");
  }, delay);
}

function bindReviewPopover() {
  document.addEventListener("mouseover", (event) => {
    const trigger = event.target.closest(".rating-review-link");
    if (trigger) {
      const place = findPlaceById(trigger.dataset.placeId);
      if (place) showReviewPopover(trigger, place);
      return;
    }
    if (event.target.closest("#review-popover")) return;
    if (!$("#review-popover")?.classList.contains("hidden")) {
      hideReviewPopover(0);
    }
  });

  document.addEventListener("mouseout", (event) => {
    const from = event.target.closest?.(".rating-review-link, #review-popover");
    const to = event.relatedTarget?.closest?.(".rating-review-link, #review-popover");
    if (from && !to) hideReviewPopover();
  });
}

function bindReviewModal() {
  document.addEventListener("click", (event) => {
    const snippetTrigger = event.target.closest(".review-snippet-link");
    if (snippetTrigger) {
      event.preventDefault();
      event.stopPropagation();
      const place = findPlaceById(snippetTrigger.dataset.placeId);
      openReviewModal(place, snippetTrigger.dataset.review);
      return;
    }

    const ratingTrigger = event.target.closest(".rating-review-link");
    if (ratingTrigger) {
      event.preventDefault();
      event.stopPropagation();
      hideReviewPopover(0);
      const place = findPlaceById(ratingTrigger.dataset.placeId);
      openReviewModal(place);
      return;
    }

    if (event.target === $("#review-modal")) {
      closeReviewModal();
    }
  }, true);

  $(".review-modal-close")?.addEventListener("click", closeReviewModal);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#review-modal")?.classList.contains("hidden")) {
      closeReviewModal();
    }
  });
}

function normalizeSearchText(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

function getPlaceKeywordHaystack(place) {
  const menu = (place?.representative_menu || "").trim();
  const menuText = menu && !GENERIC_MENUS.has(menu) ? menu : displayMenu(place, "");
  return [place?.name, menuText, place?.category_label].filter(Boolean).join(" ");
}

function placeMatchesKeyword(place, rawKeyword) {
  const keyword = normalizeSearchText(rawKeyword);
  if (!keyword) return true;
  return normalizeSearchText(getPlaceKeywordHaystack(place)).includes(keyword);
}

function passesFilters(place) {
  const { minRating, maxPrice, maxWalk, placeType, keyword } = state.filters;

  if (!isFoodPlace(place)) return false;
  if (placeType !== "all" && place.place_type !== placeType) return false;
  if (place.walk_minutes != null && place.walk_minutes > maxWalk) return false;
  if (place.rating != null && place.rating < minRating) return false;
  if (place.price_per_person_krw != null && place.price_per_person_krw > maxPrice) return false;
  if (!placeMatchesKeyword(place, keyword)) return false;
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

function isFranchiseCafe(place) {
  const compact = (place.name || "").replace(/\s/g, "").toLowerCase();
  return FRANCHISE_CAFE_MARKERS.some((marker) => {
    const normalized = marker.replace(/\s/g, "").toLowerCase();
    return compact.includes(normalized);
  });
}

function splitCafeGroups(groups) {
  const franchise = [];
  const individual = [];
  for (const key of ["cafe", "dessert"]) {
    for (const place of groups[key] || []) {
      if (isFranchiseCafe(place)) franchise.push(place);
      else individual.push(place);
    }
  }
  const byWalk = (a, b) => (a.walk_minutes ?? 99) - (b.walk_minutes ?? 99);
  franchise.sort(byWalk);
  individual.sort(byWalk);
  return { cafe_franchise: franchise, cafe_individual: individual };
}

function renderCategoryNavButton(key, label, count, icon) {
  return `
    <button type="button" class="category-nav-btn ${key}" data-category="${key}">
      <span class="category-nav-icon" aria-hidden="true">${icon}</span>
      <span class="category-nav-label">${escapeHtml(label)}</span>
      <span class="category-nav-count">${count}</span>
    </button>
  `;
}

function renderPopupContent(place) {
  const newBadge = place.is_new_opening
    ? '<span class="popup-new-badge">NEW</span>'
    : "";
  const openedLine = place.opened_at
    ? `<div><strong>오픈</strong> ${formatOpenedAt(place.opened_at)}</div>`
    : "";
  const link = place.url
    ? `<a class="popup-link" href="${place.url}" target="_blank" rel="noopener">카카오맵에서 보기 →</a>`
    : "";

  return `
    <div class="popup-name">${escapeHtml(place.name)}${newBadge}</div>
    <span class="popup-category">${escapeHtml(place.category_label)}</span>
    <div class="popup-meta">
      <div><strong>메뉴</strong> ${escapeHtml(displayMenu(place))}</div>
      <div><strong>가격</strong> ${formatPrice(place)}</div>
      <div><strong>평점</strong> ${formatRating(place)}</div>
      <div><strong>거리</strong> ${formatWalk(place.walk_minutes)} (${formatDistance(place.distance_meters)})</div>
      ${openedLine}
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
  const markerEl = document.querySelector(`[data-place-id="${place.id}"]`);
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

function isHighlyRated(place) {
  const defaults = state.data?.defaults ?? {};
  const minRating = defaults.highlight_rating_min ?? 4.5;
  const minReviews = defaults.highlight_review_count_min ?? 10;
  const rating = place.rating;
  const reviews = place.review_count ?? 0;
  return rating != null && rating >= minRating && reviews >= minReviews;
}

function getMapPinClass(place) {
  const classes = ["map-pin-wrap"];
  if (place.place_type === "cafe") {
    classes.push("cafe");
  }
  if (place.is_new_opening || isHighlyRated(place)) {
    classes.push("highlight");
  }
  if (place.is_new_opening) {
    classes.push("new");
  }
  return classes.join(" ");
}

function createMapPinIcon(place) {
  return L.divIcon({
    className: "map-pin-marker",
    html: `<div class="${getMapPinClass(place)}" data-place-id="${place.id}"><div class="map-pin"></div></div>`,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
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
      icon: createMapPinIcon(place),
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

function scrollToCategory(key) {
  const section = document.getElementById(`category-${key}`);
  section?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCategoryNav(groups, totalCount) {
  const wrap = $("#category-nav-wrap");
  const nav = $("#category-nav");
  const summary = $("#category-nav-summary");
  if (!wrap || !nav) return;

  const restaurantKeys = RESTAURANT_CATEGORY_KEYS.filter((k) => groups[k]?.length);
  const cafeSplit = splitCafeGroups(groups);
  const hasCafe = cafeSplit.cafe_franchise.length || cafeSplit.cafe_individual.length;
  const hasOther = groups.other?.length;

  if (!restaurantKeys.length && !hasCafe && !hasOther) {
    wrap.classList.add("hidden");
    nav.innerHTML = "";
    if (summary) summary.textContent = "";
    return;
  }

  if (summary) {
    summary.innerHTML = `총 <strong>${totalCount}</strong>곳`;
  }

  const parts = [];

  if (restaurantKeys.length) {
    const children = restaurantKeys
      .map((key) => {
        const label = CATEGORY_LABELS[key] || key;
        const icon = CATEGORY_ICONS[key] || "🍽️";
        return renderCategoryNavButton(key, label, groups[key].length, icon);
      })
      .join("");
    parts.push(`
      <div class="category-nav-group">
        <span class="category-nav-parent restaurant">🍽️ 맛집</span>
        <div class="category-nav-children">${children}</div>
      </div>
    `);
  }

  if (hasCafe) {
    const children = [
      cafeSplit.cafe_franchise.length
        ? renderCategoryNavButton(
          "cafe_franchise",
          CAFE_SUB_LABELS.cafe_franchise,
          cafeSplit.cafe_franchise.length,
          "🏪",
        )
        : "",
      cafeSplit.cafe_individual.length
        ? renderCategoryNavButton(
          "cafe_individual",
          CAFE_SUB_LABELS.cafe_individual,
          cafeSplit.cafe_individual.length,
          "☕",
        )
        : "",
    ].join("");
    parts.push(`
      <div class="category-nav-group">
        <span class="category-nav-parent cafe">☕ 카페</span>
        <div class="category-nav-children">${children}</div>
      </div>
    `);
  }

  if (hasOther) {
    parts.push(renderCategoryNavButton(
      "other",
      CATEGORY_LABELS.other,
      groups.other.length,
      CATEGORY_ICONS.other,
    ));
  }

  nav.innerHTML = parts.join("");

  nav.querySelectorAll(".category-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => scrollToCategory(btn.dataset.category));
  });

  const listActive = $("#view-list")?.classList.contains("active");
  wrap.classList.toggle("hidden", !listActive);
}

function appendPlaceCard(place, cards) {
  const card = document.createElement("article");
  card.className = "place-card";
  card.innerHTML = `
    <div class="place-card-name">
      ${escapeHtml(place.name)}
      ${place.is_new_opening ? '<span class="place-card-new">NEW</span>' : ""}
    </div>
    <div class="place-card-menu">🍴 ${escapeHtml(displayMenu(place))}</div>
    <div class="place-card-stats">
      <span class="stat-rating">${formatRating(place)}</span>
      <span class="stat-distance">${formatWalk(place.walk_minutes)} · ${formatDistance(place.distance_meters)}</span>
      <span class="stat-price">${formatPrice(place)}</span>
    </div>
  `;
  card.addEventListener("click", (event) => {
    if (event.target.closest(".review-snippet-link, .rating-review-link")) return;
    switchView("map");
    showMapPopup(place);
    state.map?.setView([place.lat, place.lng], 17, { animate: true });
  });
  cards.appendChild(card);
}

function renderCategorySection(key, items, label, icon, container) {
  const section = document.createElement("section");
  section.className = "category-section";
  section.id = `category-${key}`;
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
    appendPlaceCard(place, cards);
  }
  container.appendChild(section);
}

function renderCategoryList() {
  const container = $("#category-list");
  const empty = $("#list-empty");
  const places = getFilteredPlaces();
  const groups = groupByCategory(places);

  container.innerHTML = "";

  if (places.length === 0) {
    const keyword = state.filters.keyword.trim();
    empty.textContent = keyword
      ? `「${keyword}」에 맞는 장소가 없습니다. 검색어·필터를 조정해 보세요.`
      : "조건에 맞는 장소가 없습니다. 필터를 조정해 보세요.";
    empty.classList.remove("hidden");
    renderCategoryNav(groups, 0);
    return;
  }
  empty.classList.add("hidden");

  renderCategoryNav(groups, places.length);

  const restaurantKeys = RESTAURANT_CATEGORY_KEYS.filter((k) => groups[k]?.length);
  if (restaurantKeys.length) {
    const groupEl = document.createElement("div");
    groupEl.className = "category-group";
    groupEl.id = "category-group-restaurant";
    groupEl.innerHTML = '<h2 class="category-group-title">🍽️ 맛집</h2>';
    const sections = document.createElement("div");
    sections.className = "category-group-sections";
    for (const key of restaurantKeys) {
      const items = groups[key];
      const label = items[0].category_label || CATEGORY_LABELS[key] || key;
      const icon = CATEGORY_ICONS[key] || "🍽️";
      renderCategorySection(key, items, label, icon, sections);
    }
    groupEl.appendChild(sections);
    container.appendChild(groupEl);
  }

  const cafeSplit = splitCafeGroups(groups);
  if (cafeSplit.cafe_franchise.length || cafeSplit.cafe_individual.length) {
    const groupEl = document.createElement("div");
    groupEl.className = "category-group";
    groupEl.id = "category-group-cafe";
    groupEl.innerHTML = '<h2 class="category-group-title">☕ 카페</h2>';
    const sections = document.createElement("div");
    sections.className = "category-group-sections";
    if (cafeSplit.cafe_franchise.length) {
      renderCategorySection(
        "cafe_franchise",
        cafeSplit.cafe_franchise,
        CAFE_SUB_LABELS.cafe_franchise,
        "🏪",
        sections,
      );
    }
    if (cafeSplit.cafe_individual.length) {
      renderCategorySection(
        "cafe_individual",
        cafeSplit.cafe_individual,
        CAFE_SUB_LABELS.cafe_individual,
        "☕",
        sections,
      );
    }
    groupEl.appendChild(sections);
    container.appendChild(groupEl);
  }

  if (groups.other?.length) {
    const items = groups.other;
    const label = items[0].category_label || CATEGORY_LABELS.other;
    renderCategorySection("other", items, label, CATEGORY_ICONS.other, container);
  }
}

function passesNewOpeningFilters(place) {
  const { maxWalk } = state.filters;
  if (place.place_type !== "restaurant" && place.place_type !== "cafe") return false;
  if (place.walk_minutes != null && place.walk_minutes > maxWalk) return false;
  return true;
}

function getNewOpenings() {
  const places = state.data?.places ?? [];
  const placeById = new Map(places.map((place) => [place.id, place]));
  const openings = places.filter((place) => place.is_new_opening);
  for (const entry of state.data?.new_openings ?? []) {
    if (!openings.some((place) => place.id === entry.id)) {
      openings.push(placeById.get(entry.id) ?? entry);
    }
  }
  return openings
    .filter(passesNewOpeningFilters)
    .sort((a, b) => {
      const dateA = a.opened_at ? new Date(`${a.opened_at}T00:00:00`).getTime() : 0;
      const dateB = b.opened_at ? new Date(`${b.opened_at}T00:00:00`).getTime() : 0;
      if (dateA !== dateB) return dateB - dateA;
      return (a.walk_minutes ?? 99) - (b.walk_minutes ?? 99);
    });
}

function applyNewOpeningPanelPosition(position) {
  const next = position === "bottom" ? "bottom" : "right";
  state.newOpeningPanelPosition = next;
  localStorage.setItem("newOpeningPanelPosition", next);

  const panel = $("#new-opening-panel");
  const tab = $("#new-opening-panel-tab");
  panel?.classList.remove("position-right", "position-bottom");
  tab?.classList.remove("position-right", "position-bottom");
  panel?.classList.add(`position-${next}`);
  tab?.classList.add(`position-${next}`);

  $$(".position-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.position === next);
  });
}

function openNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const tab = $("#new-opening-panel-tab");
  panel?.classList.remove("collapsed", "hidden");
  tab?.classList.add("hidden");
}

function closeNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const tab = $("#new-opening-panel-tab");
  if (panel?.classList.contains("hidden")) return;
  panel.classList.add("collapsed");
  tab?.classList.remove("hidden");
}

function renderNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const body = $("#new-opening-panel-body");
  const tab = $("#new-opening-panel-tab");
  const countEl = $("#new-opening-count");
  const headerBtn = $("#btn-new-openings");
  const openings = getNewOpenings();
  const days = state.data?.defaults?.new_opening_days ?? 30;

  applyNewOpeningPanelPosition(state.newOpeningPanelPosition);

  if (!openings.length) {
    panel.classList.add("hidden");
    tab.classList.add("hidden");
    headerBtn?.classList.add("hidden");
    return;
  }

  headerBtn?.classList.remove("hidden");

  const eyebrow = panel.querySelector(".new-opening-panel-eyebrow");
  if (eyebrow) eyebrow.textContent = `최근 ${days}일`;

  countEl.textContent = `(${openings.length}곳)`;
  body.innerHTML = openings
    .map(
      (place) => `
    <article class="new-opening-card" data-place-id="${escapeHtml(place.id)}">
      <div class="new-opening-card-head">
        <span class="new-opening-name">${escapeHtml(place.name)}</span>
        <div class="new-opening-badges">
          ${place.opened_at ? `<span class="new-opening-date">${formatOpenedAt(place.opened_at)}</span>` : ""}
          <span class="new-opening-badge">NEW</span>
        </div>
      </div>
      <span class="new-opening-type">${escapeHtml(place.category_label)} · ${place.place_type === "cafe" ? "카페" : "맛집"}</span>
      <dl class="new-opening-details">
        <div><dt>대표메뉴</dt><dd>${escapeHtml(displayMenu(place))}</dd></div>
        <div><dt>가격</dt><dd class="price">${formatPrice(place)}</dd></div>
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

  const wasCollapsed = panel.classList.contains("collapsed");
  panel.classList.remove("hidden");
  if (!wasCollapsed) {
    panel.classList.remove("collapsed");
    tab.classList.add("hidden");
  }
}

function bindNewOpeningPanel() {
  const panel = $("#new-opening-panel");
  const tab = $("#new-opening-panel-tab");

  $("#new-opening-panel-toggle")?.addEventListener("click", closeNewOpeningPanel);

  tab?.addEventListener("click", openNewOpeningPanel);

  $("#btn-new-openings")?.addEventListener("click", openNewOpeningPanel);

  $$(".position-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyNewOpeningPanelPosition(btn.dataset.position);
    });
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
  $("#view-list").classList.toggle("active", view === "list");

  const categoryNavWrap = $("#category-nav-wrap");
  if (categoryNavWrap && $("#category-nav")?.innerHTML.trim()) {
    categoryNavWrap.classList.toggle("hidden", view !== "list");
  }

  if (view === "map" && state.map) {
    setTimeout(() => state.map.invalidateSize(), 100);
  }
}

let keywordFilterTimer = null;

function updateKeywordClearButton() {
  const clearBtn = $("#filter-keyword-clear");
  const keywordInput = $("#filter-keyword");
  if (!clearBtn || !keywordInput) return;
  clearBtn.classList.toggle("hidden", !keywordInput.value.trim());
}

function bindFilters() {
  const ratingInput = $("#filter-rating");
  const priceInput = $("#filter-price");
  const walkInput = $("#filter-walk");
  const keywordInput = $("#filter-keyword");
  const keywordClear = $("#filter-keyword-clear");

  const applyKeywordFilter = () => {
    state.filters.keyword = keywordInput?.value ?? "";
    updateKeywordClearButton();
    render();
  };

  keywordInput?.addEventListener("input", () => {
    clearTimeout(keywordFilterTimer);
    keywordFilterTimer = setTimeout(applyKeywordFilter, 200);
  });

  keywordInput?.addEventListener("search", applyKeywordFilter);

  keywordInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      clearTimeout(keywordFilterTimer);
      applyKeywordFilter();
    }
  });

  keywordClear?.addEventListener("click", () => {
    if (!keywordInput) return;
    keywordInput.value = "";
    clearTimeout(keywordFilterTimer);
    applyKeywordFilter();
    keywordInput.focus();
  });

  ratingInput?.addEventListener("input", () => {
    state.filters.minRating = parseFloat(ratingInput.value);
    $("#rating-value").textContent = state.filters.minRating.toFixed(1);
    render();
  });

  priceInput?.addEventListener("input", () => {
    state.filters.maxPrice = parseInt(priceInput.value, 10);
    $("#price-value").textContent = state.filters.maxPrice.toLocaleString("ko-KR");
    render();
  });

  walkInput?.addEventListener("input", () => {
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

/* ── Lunch slot machine ── */

const slotState = {
  spinning: false,
  winner: null,
};

const REEL_WINDOW = 16;

function getSlotItemHeight(reelEl) {
  const item = reelEl?.querySelector(".slot-reel-item");
  return item?.offsetHeight || 72;
}

function getReelOffset(reelEl, index) {
  return -(index * getSlotItemHeight(reelEl));
}

function getLunchPool() {
  return getFilteredPlaces().filter((p) => p.place_type === "restaurant");
}

function resolvePlaceCategory(place) {
  if (place?.category && CATEGORY_ICONS[place.category]) return place.category;
  if (place?.category_label) {
    const matched = Object.entries(CATEGORY_LABELS).find(([, label]) => label === place.category_label);
    if (matched) return matched[0];
  }
  return "other";
}

function slotCategoryKey(place) {
  return resolvePlaceCategory(place);
}

function slotMenuLabel(place) {
  return displayMenu(place, place.name);
}

function buildReelWindow(places, extractor, focusIdx = 0) {
  const items = places.map(extractor);
  const len = items.length;
  if (!len) return { values: [], targetIndex: 0 };

  const focus = Math.max(0, Math.min(focusIdx, len - 1));

  if (len <= REEL_WINDOW) {
    const values = [...items];
    while (values.length < 8) values.push(...items);
    return { values: values.slice(0, Math.max(8, len)), targetIndex: focus };
  }

  let start = focus - Math.floor(REEL_WINDOW / 2);
  if (start < 0) start = 0;
  if (start + REEL_WINDOW > len) start = len - REEL_WINDOW;

  return {
    values: items.slice(start, start + REEL_WINDOW),
    targetIndex: focus - start,
  };
}

function fillReel(el, values, iconMode = false) {
  el.innerHTML = values
    .map(
      (v) =>
        `<div class="slot-reel-item${iconMode ? " slot-reel-item--icon" : ""}">${escapeHtml(String(v))}</div>`
    )
    .join("");
  el.style.transform = "translateY(0)";
  el.classList.remove("spinning", "stopping", "stopped");
}

function fillCategoryReel(el, categoryKeys) {
  el.innerHTML = categoryKeys
    .map((key) => {
      const icon = CATEGORY_ICONS[key] || "🍽️";
      const label = CATEGORY_LABELS[key] || key;
      return `<div class="slot-reel-item slot-reel-item--icon slot-reel-item--${key}" title="${escapeHtml(label)}">
        <span class="slot-category-icon" aria-hidden="true">${icon}</span>
      </div>`;
    })
    .join("");
  el.style.transform = "translateY(0)";
  el.classList.remove("spinning", "stopping", "stopped");
}

function animateReel(el, values, targetIndex, durationMs) {
  return new Promise((resolve) => {
    const totalItems = values.length;
    if (!totalItems) {
      resolve();
      return;
    }

    const safeTarget = ((targetIndex % totalItems) + totalItems) % totalItems;
    const loops = 3;
    const finalIndex = loops * totalItems + safeTarget;
    const offset = getReelOffset(el, finalIndex);
    let settled = false;

    const finish = () => {
      if (settled) return;
      settled = true;
      el.removeEventListener("transitionend", onEnd);
      clearTimeout(fallbackTimer);
      el.classList.remove("spinning", "stopping");
      el.classList.add("stopped");
      el.style.transition = "none";
      el.style.transform = `translateY(${getReelOffset(el, safeTarget)}px)`;
      resolve();
    };

    const onEnd = (event) => {
      if (event.target !== el || event.propertyName !== "transform") return;
      finish();
    };

    const fallbackTimer = setTimeout(finish, durationMs + 400);

    el.classList.add("spinning");
    el.style.transition = "none";
    el.style.transform = "translateY(0)";

    requestAnimationFrame(() => {
      el.classList.remove("spinning");
      el.classList.add("stopping");
      el.style.transition = `transform ${durationMs}ms cubic-bezier(0.15, 0.85, 0.25, 1)`;
      el.style.transform = `translateY(${offset}px)`;
    });

    el.addEventListener("transitionend", onEnd);
  });
}

function renderSlotResult(place) {
  const body = $("#slot-result-body");
  const category = resolvePlaceCategory(place);
  const icon = CATEGORY_ICONS[category] || "🍽️";
  const label = place.category_label || CATEGORY_LABELS[category] || category;
  body.innerHTML = `
    <div class="slot-result-name">${escapeHtml(place.name)}</div>
    <div class="slot-result-meta">
      <div><strong>종류</strong><span class="slot-result-category slot-result-category--${category}"><span class="slot-category-icon" aria-hidden="true">${icon}</span>${escapeHtml(label)}</span></div>
      <div><strong>메뉴</strong>${escapeHtml(displayMenu(place))}</div>
      <div><strong>가격</strong>${formatPrice(place)}</div>
      <div><strong>평점</strong>${formatRating(place)}</div>
      <div><strong>거리</strong>${formatWalk(place.walk_minutes)} · ${formatDistance(place.distance_meters)}</div>
    </div>
  `;
  $("#slot-result").classList.remove("hidden");
}

function updateSlotPoolCount() {
  const pool = getLunchPool();
  const el = $("#slot-pool-count");
  if (!el) return;
  el.textContent = pool.length
    ? `후보 ${pool.length}곳 (현재 필터 적용)`
    : "조건에 맞는 맛집이 없어요. 필터를 조정해 보세요.";
}

function openSlotOverlay() {
  if (state.dataLoading) {
    alert("맛집 데이터를 불러오는 중입니다. 잠시 후 다시 시도해 주세요.");
    return;
  }

  if (!state.data?.places?.length) {
    alert("맛집 데이터를 불러오지 못했습니다. 새로고침 후 다시 시도해 주세요.");
    return;
  }

  const pool = getLunchPool();
  if (!pool.length) {
    alert("조건에 맞는 맛집이 없습니다. 필터를 조정한 뒤 다시 시도해 주세요.");
    return;
  }

  slotState.winner = null;
  slotState.spinning = false;

  const overlay = $("#slot-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden", "is-spinning", "is-winning");
  $("#slot-result").classList.add("hidden");
  $("#slot-status").textContent = "레버를 당겨 주세요!";
  $("#slot-btn-spin").disabled = false;
  $("#slot-btn-spin").classList.remove("is-pulled");

  const previewIdx = Math.floor(Math.random() * pool.length);
  const categoryReel = buildReelWindow(pool, slotCategoryKey, previewIdx);
  const nameReel = buildReelWindow(pool, (p) => p.name, previewIdx);
  const menuReel = buildReelWindow(pool, slotMenuLabel, previewIdx);

  fillCategoryReel($("#slot-reel-category"), categoryReel.values);
  fillReel($("#slot-reel-name"), nameReel.values);
  fillReel($("#slot-reel-menu"), menuReel.values);

  updateSlotPoolCount();
  document.body.style.overflow = "hidden";
}

function closeSlotOverlay() {
  if (slotState.spinning) return;
  $("#slot-overlay").classList.add("hidden");
  document.body.style.overflow = "";
}

async function spinSlot() {
  if (slotState.spinning) return;

  const pool = getLunchPool();
  if (!pool.length) return;

  slotState.spinning = true;
  slotState.winner = pool[Math.floor(Math.random() * pool.length)];

  const overlay = $("#slot-overlay");
  const lever = $("#slot-btn-spin");
  const status = $("#slot-status");

  overlay.classList.add("is-spinning");
  overlay.classList.remove("is-winning");
  $("#slot-result").classList.add("hidden");
  lever.disabled = true;
  lever.classList.add("is-pulled");
  status.textContent = "돌아가는 중… 🎰";

  const winner = slotState.winner;
  const winnerIdx = pool.findIndex((p) => p.id === winner.id);
  const targetIdx = winnerIdx >= 0 ? winnerIdx : 0;

  const categoryReel = buildReelWindow(pool, slotCategoryKey, targetIdx);
  const nameReel = buildReelWindow(pool, (p) => p.name, targetIdx);
  const menuReel = buildReelWindow(pool, slotMenuLabel, targetIdx);

  fillCategoryReel($("#slot-reel-category"), categoryReel.values);
  fillReel($("#slot-reel-name"), nameReel.values);
  fillReel($("#slot-reel-menu"), menuReel.values);

  await animateReel($("#slot-reel-category"), categoryReel.values, categoryReel.targetIndex, 1400);
  await animateReel($("#slot-reel-name"), nameReel.values, nameReel.targetIndex, 1800);
  await animateReel($("#slot-reel-menu"), menuReel.values, menuReel.targetIndex, 2200);

  overlay.classList.remove("is-spinning");
  overlay.classList.add("is-winning");
  status.textContent = "🎉 오늘의 점심은 여기!";
  renderSlotResult(winner);

  slotState.spinning = false;
  lever.disabled = false;
  lever.classList.remove("is-pulled");
}

function bindSlotMachine() {
  $("#btn-lunch-pick")?.addEventListener("click", openSlotOverlay);
  $(".slot-close")?.addEventListener("click", closeSlotOverlay);
  $("#slot-overlay")?.addEventListener("click", (e) => {
    if (e.target === $("#slot-overlay")) closeSlotOverlay();
  });

  $("#slot-btn-spin")?.addEventListener("click", spinSlot);
  $("#slot-btn-again")?.addEventListener("click", () => {
    $("#slot-result").classList.add("hidden");
    $("#slot-overlay").classList.remove("is-winning");
    $("#slot-status").textContent = "레버를 당겨 주세요!";
    spinSlot();
  });

  $("#slot-btn-map")?.addEventListener("click", () => {
    const place = slotState.winner;
    if (!place) return;
    closeSlotOverlay();
    switchView("map");
    showMapPopup(place);
    state.map?.setView([place.lat, place.lng], 17, { animate: true });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#slot-overlay")?.classList.contains("hidden")) {
      closeSlotOverlay();
    }
  });
}

async function fetchJsonWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return null;
    const data = await res.json();
    return data.places ? data : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function loadData({ preferLive = false } = {}) {
  if (preferLive) {
    const live = await fetchJsonWithTimeout("/api/places", 120000);
    if (live) return live;
    const cached = await fetchJsonWithTimeout("data/places.json", 15000);
    if (cached) return cached;
  } else {
    const cached = await fetchJsonWithTimeout("data/places.json", 15000);
    if (cached) return cached;
    const live = await fetchJsonWithTimeout("/api/places", 5000);
    if (live) return live;
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
  bindFilters();
  bindTabs();
  bindNewOpeningPanel();
  bindSlotMachine();
  bindReviewModal();
  bindReviewPopover();

  $(".popup-close")?.addEventListener("click", hideMapPopup);

  $("#btn-refresh")?.addEventListener("click", async () => {
    $("#btn-refresh").disabled = true;
    state.dataLoading = true;
    try {
      state.data = await loadData({ preferLive: true });
      applyDefaults(state.data);
      initMap();
      render();
    } catch (err) {
      alert(err.message);
    } finally {
      state.dataLoading = false;
      $("#btn-refresh").disabled = false;
    }
  });

  const overlay = document.createElement("div");
  overlay.className = "loading-overlay";
  overlay.textContent = "맛집 데이터 불러오는 중…";
  document.body.appendChild(overlay);

  state.dataLoading = true;
  try {
    state.data = await loadData();
    applyDefaults(state.data);
    initMap();
    render();
  } catch (err) {
    $("#result-count").textContent = err.message;
  } finally {
    state.dataLoading = false;
    overlay.remove();
  }
}

document.addEventListener("DOMContentLoaded", init);
