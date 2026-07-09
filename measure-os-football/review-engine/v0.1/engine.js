window.MO_REVIEW_ENGINE = (() => {
  const { normalizeAnalyzeMode } = window.MO_COMPOSITE_ANALYZE_MODES || {};

  function aggregateMatchMetrics(events) {
    return window.MO_MATCH_METRICS?.aggregate?.(events) || {
      eventCount: 0,
      attack: [],
      buildUp: [],
      finish: [],
    };
  }

  function buildReviewInput({
    plan,
    events,
    elapsed,
    stateResults,
    reasonResults,
    compositeReason,
  }) {
    const matchMetrics = aggregateMatchMetrics(events);
    const analyzeMode = normalizeAnalyzeMode?.(plan?.analyzeMode) || plan?.analyzeMode || "both";

    return {
      plan,
      events,
      elapsed,
      analyzeMode,
      stateResults: Array.isArray(stateResults) ? stateResults : [],
      reasonResults: Array.isArray(reasonResults) ? reasonResults : [],
      compositeReason: compositeReason || null,
      matchMetrics,
    };
  }

  function buildCompositeForAnalyzeMode(reasonResults, analyzeMode) {
    return window.MO_COMPOSITE_REASON_ENGINE?.composeOverallReason?.({
      analyzeMode,
      reasonResults,
    }) || null;
  }

  function generateReview(input) {
    const context = buildReviewInput(input);
    const { analyzeMode, reasonResults } = context;
    const sections = [];

    if (analyzeMode === "attack" || analyzeMode === "both") {
      sections.push(window.MO_REVIEW_ATTACK_NARRATIVE.buildAttackReview({
        ...context,
        compositeReason: buildCompositeForAnalyzeMode(reasonResults, "attack"),
      }));
    }

    if (analyzeMode === "defense" || analyzeMode === "both") {
      sections.push(window.MO_REVIEW_DEFENSE_NARRATIVE.buildDefenseReview({
        ...context,
        compositeReason: buildCompositeForAnalyzeMode(reasonResults, "defense"),
      }));
    }

    return {
      analyzeMode,
      sections,
    };
  }

  function generateMiniReviewSnapshot(options) {
    return window.MO_REVIEW_MINI_ADAPTER?.generateMiniReviewSnapshot?.(options) || null;
  }

  return {
    aggregateMatchMetrics,
    buildReviewInput,
    buildCompositeForAnalyzeMode,
    generateReview,
    generateMiniReviewSnapshot,
  };
})();
