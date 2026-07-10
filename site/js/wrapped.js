/**
 * Monthly Wrapped UI — 점심 뽑기와 동일한 오버레이 패턴
 */
(() => {
  const $ = (sel) => document.querySelector(sel);

  const GRADIENTS = [
    "linear-gradient(145deg, #1db954 0%, #0d3d2a 45%, #0a1f14 100%)",
    "linear-gradient(145deg, #8b5cf6 0%, #4c1d95 50%, #1e1033 100%)",
    "linear-gradient(145deg, #f59e0b 0%, #b45309 45%, #451a03 100%)",
    "linear-gradient(145deg, #06b6d4 0%, #0e7490 50%, #083344 100%)",
    "linear-gradient(145deg, #ec4899 0%, #9d174d 50%, #500724 100%)",
    "linear-gradient(145deg, #6366f1 0%, #3730a3 50%, #1e1b4b 100%)",
  ];

  const state = {
    report: null,
    cardIndex: 0,
    loading: false,
  };

  function renderCard(index) {
    if (!state.report?.cards?.length) return;
    const card = state.report.cards[index];
    const area = $("#wrapped-card");
    const gradient = GRADIENTS[index % GRADIENTS.length];
    if (!area || !card) return;

    area.style.background = gradient;
    area.innerHTML = `
      <div class="wrapped-card-emoji" aria-hidden="true">${card.emoji}</div>
      <p class="wrapped-card-stat-label">${DiaryStorage.escapeHtml(card.statLabel)}</p>
      <div class="wrapped-card-stat">${DiaryStorage.escapeHtml(String(card.statValue))}</div>
      <h3 class="wrapped-card-title">${DiaryStorage.escapeHtml(card.title)}</h3>
      <p class="wrapped-card-subtitle">${DiaryStorage.escapeHtml(card.subtitle)}</p>
    `;

    const total = state.report.cards.length;
    const progress = $("#wrapped-progress");
    if (progress) progress.textContent = `${index + 1} / ${total}`;

    const dots = $("#wrapped-dots");
    if (dots) {
      dots.innerHTML = state.report.cards
        .map(
          (_, i) =>
            `<span class="wrapped-dot${i === index ? " wrapped-dot--active" : ""}" aria-hidden="true"></span>`,
        )
        .join("");
    }

    const prev = $("#wrapped-prev");
    const next = $("#wrapped-next");
    if (prev) prev.disabled = index <= 0;
    if (next) {
      next.textContent = index >= total - 1 ? "닫기" : "다음 ›";
    }
  }

  function goToCard(index) {
    if (!state.report) return;
    const max = state.report.cards.length - 1;
    state.cardIndex = Math.max(0, Math.min(index, max));
    renderCard(state.cardIndex);
  }

  function nextCard() {
    if (!state.report) return;
    if (state.cardIndex >= state.report.cards.length - 1) {
      closeWrappedOverlay();
      return;
    }
    goToCard(state.cardIndex + 1);
  }

  function prevCard() {
    goToCard(state.cardIndex - 1);
  }

  async function openWrappedOverlay() {
    if (state.loading) return;

    const overlay = $("#wrapped-overlay");
    if (!overlay) return;

    state.loading = true;
    const status = $("#wrapped-status");
    if (status) status.textContent = "이번 달 기록을 모으는 중…";

    overlay.classList.remove("hidden");
    document.body.style.overflow = "hidden";

    try {
      await DiaryStorage.hydrateFromRemote();
      const store = DiaryStorage.loadEntries();
      const places = await DiaryStorage.loadPlaces();
      const now = new Date();
      state.report = WrappedGenerator.generateCurrentMonth(store, places, now);
      state.cardIndex = 0;

      const title = $("#wrapped-title");
      if (title) title.textContent = `${state.report.monthLabel} 맛집 Wrapped`;

      if (status) {
        status.textContent = state.report.isEmpty
          ? "이번 달 식사 기록이 없어요. 식사 기록을 남기면 다음에 볼 수 있어요!"
          : `총 ${state.report.stats?.totalVisits ?? 0}번의 탐방을 정리했어요`;
      }

      renderCard(0);
    } catch (err) {
      console.error(err);
      if (status) status.textContent = "리포트를 만들지 못했어요. 새로고침 후 다시 시도해 주세요.";
    } finally {
      state.loading = false;
    }
  }

  function closeWrappedOverlay() {
    $("#wrapped-overlay")?.classList.add("hidden");
    document.body.style.overflow = "";
    state.report = null;
    state.cardIndex = 0;
  }

  function bindWrapped() {
    $("#btn-wrapped")?.addEventListener("click", openWrappedOverlay);
    $(".wrapped-close")?.addEventListener("click", closeWrappedOverlay);
    $("#wrapped-overlay")?.addEventListener("click", (e) => {
      if (e.target === $("#wrapped-overlay")) closeWrappedOverlay();
    });
    $("#wrapped-next")?.addEventListener("click", nextCard);
    $("#wrapped-prev")?.addEventListener("click", prevCard);
    $("#wrapped-card")?.addEventListener("click", nextCard);

    document.addEventListener("keydown", (e) => {
      if ($("#wrapped-overlay")?.classList.contains("hidden")) return;
      if (e.key === "Escape") closeWrappedOverlay();
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        nextCard();
      }
      if (e.key === "ArrowLeft") prevCard();
    });
  }

  document.addEventListener("DOMContentLoaded", bindWrapped);
})();
