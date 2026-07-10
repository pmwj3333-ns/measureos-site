window.MO_TEAM_REVIEW_FILTERS = (() => {
  const FILTER_DEFINITIONS = [
    { key: "dateFrom", type: "date", label: "期間（開始）", group: "period" },
    { key: "dateTo", type: "date", label: "期間（終了）", group: "period" },
    { key: "competition", type: "text", label: "大会", group: "match" },
    { key: "opponent", type: "text", label: "対戦相手", group: "match" },
    { key: "homeAway", type: "select", label: "ホーム／アウェイ", group: "match", options: ["", "home", "away"] },
    { key: "result", type: "select", label: "勝敗", group: "match", options: ["", "win", "loss", "draw"] },
    { key: "analyzeMode", type: "select", label: "Game Plan", group: "plan", options: ["", "attack", "defense", "both"] },
    { key: "attackPlan", type: "text", label: "Attack Plan", group: "plan" },
    { key: "buildUpPlan", type: "text", label: "Build Up Plan", group: "plan" },
    { key: "defensePlan", type: "text", label: "Defense Plan", group: "plan" },
    { key: "transitionPlan", type: "text", label: "Transition Plan", group: "plan" },
    { key: "stateStatus", type: "select", label: "State", group: "review", options: ["", "maintained", "drift"] },
    { key: "deviationStatus", type: "select", label: "Deviation", group: "review", options: ["", "aligned", "warn"] },
    { key: "reviewFullText", type: "text", label: "Review全文検索", group: "review" },
    { key: "reviewKeyword", type: "text", label: "Reviewキーワード", group: "review" },
    { key: "freeText", type: "text", label: "自由検索", group: "review" },
  ];

  function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function resolveMatchResult(record) {
    const home = Number(record.match?.home_score) || 0;
    const away = Number(record.match?.away_score) || 0;
    if (home === away) return "draw";
    const isHome = record.setup?.home_away === "home";
    const ourScore = isHome ? home : away;
    const oppScore = isHome ? away : home;
    if (ourScore > oppScore) return "win";
    if (ourScore < oppScore) return "loss";
    return "draw";
  }

  function getLastPlan(record) {
    const history = Array.isArray(record.match?.planHistory) ? record.match.planHistory : [];
    const lastEntry = history[history.length - 1];
    return window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot?.(lastEntry?.plan) || null;
  }

  function getPlanLabel(plan, key) {
    if (!plan) return "";
    const fromCategories = plan.categories?.[key]?.[0];
    return typeof fromCategories === "string" ? fromCategories : "";
  }

  function matchesDateRange(record, filters) {
    const matchDate = String(record.setup?.match_date || "");
    if (!matchDate) return false;
    if (filters.dateFrom && matchDate < filters.dateFrom) return false;
    if (filters.dateTo && matchDate > filters.dateTo) return false;
    return true;
  }

  function matchesPlanField(plan, key, filterValue) {
    const needle = normalizeText(filterValue);
    if (!needle) return true;
    return normalizeText(getPlanLabel(plan, key)).includes(needle);
  }

  function applyFilters(records, filters, contextById) {
    const normalized = filters || {};

    return (Array.isArray(records) ? records : []).filter((record) => {
      if (!matchesDateRange(record, normalized)) return false;

      const competition = normalizeText(normalized.competition);
      if (competition && !normalizeText(record.setup?.competition).includes(competition)) return false;

      const opponent = normalizeText(normalized.opponent);
      if (opponent && !normalizeText(record.setup?.opponent).includes(opponent)) return false;

      if (normalized.homeAway && record.setup?.home_away !== normalized.homeAway) return false;

      if (normalized.result && resolveMatchResult(record) !== normalized.result) return false;

      const plan = getLastPlan(record);
      if (normalized.analyzeMode && (plan?.analyzeMode || "both") !== normalized.analyzeMode) return false;

      if (!matchesPlanField(plan, "attack", normalized.attackPlan)) return false;
      if (!matchesPlanField(plan, "buildUp", normalized.buildUpPlan)) return false;
      if (!matchesPlanField(plan, "defense", normalized.defensePlan)) return false;
      if (!matchesPlanField(plan, "transition", normalized.transitionPlan)) return false;

      const context = contextById?.[record.id];
      if (normalized.stateStatus === "maintained" && context?.hasAttackStateDrift) return false;
      if (normalized.stateStatus === "drift" && !context?.hasAttackStateDrift) return false;

      if (normalized.deviationStatus === "aligned" && context?.hasDeviationWarn) return false;
      if (normalized.deviationStatus === "warn" && !context?.hasDeviationWarn) return false;

      const reviewQuery = normalizeText(normalized.reviewFullText || normalized.reviewKeyword);
      if (reviewQuery && !normalizeText(context?.reviewText).includes(reviewQuery)) return false;

      const freeText = normalizeText(normalized.freeText);
      if (freeText) {
        const haystack = [
          record.setup?.competition,
          record.setup?.opponent,
          context?.reviewText,
          getPlanLabel(plan, "attack"),
          getPlanLabel(plan, "buildUp"),
          getPlanLabel(plan, "defense"),
          getPlanLabel(plan, "transition"),
        ].map(normalizeText).join(" ");
        if (!haystack.includes(freeText)) return false;
      }

      return true;
    });
  }

  return {
    FILTER_DEFINITIONS,
    applyFilters,
    resolveMatchResult,
    getLastPlan,
    getPlanLabel,
  };
})();
