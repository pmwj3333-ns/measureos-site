window.MO_REVIEW_MINI_ADAPTER = (() => {
  const MINI_REVIEW_FORMAT_VERSION = 6;
  const MINI_REVIEW_PLACEHOLDER = "--";

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function filterEventsByHalf(events, half) {
    if (!Array.isArray(events)) return [];
    if (half === "second") {
      return events.filter((event) => event?.phase === "後半");
    }
    return events.filter((event) => event?.phase === "前半" || !event?.phase);
  }

  function getEvaluationElapsed(events) {
    return events.reduce((max, event) => Math.max(max, parseMatchTime(event.time)), 0);
  }

  function createEntry(text, tone = "neutral") {
    const normalized = String(text || "").trim();
    return {
      text: normalized || MINI_REVIEW_PLACEHOLDER,
      tone: tone || "neutral",
    };
  }

  function buildSetPieceEntry(events) {
    const matchesEventName = window.MO_SET_PIECE_OBSERVER?.matchesEventName;
    const getEventLabel = window.MO_SET_PIECE_OBSERVER?.getEventLabel;
    const codes = ["corner_kick", "free_kick", "penalty_kick"];
    const parts = [];

    codes.forEach((code) => {
      const count = events.filter((event) => {
        const eventName = event?.eventName;
        const observerEventCode = event?.observerEventCode;
        return matchesEventName?.(eventName, code)
          || matchesEventName?.(observerEventCode, code);
      }).length;

      if (count > 0) {
        parts.push(`${getEventLabel?.(code) || code} ${count}回`);
      }
    });

    return createEntry(parts.length > 0 ? parts.join("、") : null);
  }

  function mapReviewToMiniReviewCards(review, compositeReason, events) {
    const planText = window.MO_REVIEW_MINI_NARRATIVE?.planMiniNarrative?.(compositeReason);
    const flowText = window.MO_REVIEW_MINI_NARRATIVE?.flowMiniNarrative?.(compositeReason);
    const combineAttackCardText = window.MO_REVIEW_MINI_NARRATIVE?.combineAttackCardText;

    const cards = {
      plan: createEntry(planText || compositeReason?.shortSummary),
      flow: createEntry(flowText || compositeReason?.summary),
      attack: createEntry(null),
      defense: createEntry(null),
      buildUp: createEntry(null),
      transition: createEntry(null),
      setPiece: buildSetPieceEntry(events),
    };

    (review?.sections || []).forEach((section) => {
      if (section.key === "attack") {
        const miniReview = section.miniReview || {};
        cards.buildUp = createEntry(miniReview.buildUp);
        cards.attack = createEntry(combineAttackCardText?.(miniReview) || miniReview.attack);
        return;
      }

      if (section.key === "defense") {
        const miniReview = section.miniReview || {};
        cards.defense = createEntry(miniReview.defense);
        cards.transition = createEntry(miniReview.transition);
      }
    });

    return cards;
  }

  function generateMiniReviewSnapshot({
    plan,
    events,
    half = "first",
    generatedAt,
  } = {}) {
    const normalizedPlan = window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot(plan);
    if (!normalizedPlan) return null;

    const halfEvents = filterEventsByHalf(events, half);
    const elapsed = getEvaluationElapsed(halfEvents);
    const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;
    const stateResults = typeof evaluate === "function"
      ? evaluate({ plan: normalizedPlan, events: halfEvents, elapsed })
      : [];

    const explainLiveState = window.MO_REASON_ENGINE?.explainLiveState;
    const reasonResults = typeof explainLiveState === "function"
      ? explainLiveState({ plan: normalizedPlan, stateResults, context: { elapsed } })
      : [];

    const analyzeMode = normalizedPlan.analyzeMode || "both";
    const compositeReason = window.MO_REVIEW_ENGINE?.buildCompositeForAnalyzeMode?.(
      reasonResults,
      analyzeMode,
    ) || null;

    const reviewInput = window.MO_REVIEW_ENGINE?.buildReviewInput?.({
      plan: normalizedPlan,
      events: halfEvents,
      elapsed,
      stateResults,
      reasonResults,
      compositeReason,
    });

    const review = window.MO_REVIEW_ENGINE?.generateReview?.(reviewInput) || { sections: [] };
    const cards = mapReviewToMiniReviewCards(review, compositeReason, halfEvents);

    return {
      formatVersion: MINI_REVIEW_FORMAT_VERSION,
      half: half === "second" ? "second" : "first",
      analyzeMode: review.analyzeMode || analyzeMode,
      ...cards,
      generatedAt: generatedAt || new Date().toISOString(),
    };
  }

  function normalizeMiniReviewEntry(value) {
    if (!value) {
      return { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" };
    }

    if (typeof value === "string") {
      return { text: value, tone: "neutral" };
    }

    return {
      text: value.text || MINI_REVIEW_PLACEHOLDER,
      tone: value.tone || "neutral",
    };
  }

  function isLegacyMiniReviewSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return true;
    return Number(snapshot.formatVersion) !== MINI_REVIEW_FORMAT_VERSION;
  }

  return {
    MINI_REVIEW_FORMAT_VERSION,
    MINI_REVIEW_PLACEHOLDER,
    filterEventsByHalf,
    generateMiniReviewSnapshot,
    normalizeMiniReviewEntry,
    isLegacyMiniReviewSnapshot,
  };
})();
