window.MO_REVIEW_HELPERS = (() => {
  function findMetricItem(items, code) {
    const list = Array.isArray(items) ? items : [];
    return list.find((item) => item.code === code) || { code, label: code, count: 0, percent: 0 };
  }

  function dominantMetricItem(items) {
    const active = (Array.isArray(items) ? items : []).filter((item) => item.count > 0);
    if (active.length === 0) return null;
    return active.reduce((best, item) => (item.percent > best.percent ? item : best));
  }

  function joinSentences(parts) {
    return parts.filter(Boolean).join("");
  }

  function resolveCategoryKeyForRuleId(ruleId) {
    return window.MO_COMPOSITE_ANALYZE_MODES?.resolveCategoryKeyForRuleId(ruleId) || null;
  }

  function resolveStateCategoryKey(category) {
    const map = {
      Attack: "attack",
      Defense: "defense",
      "Build Up": "buildUp",
      Transition: "transition",
    };
    return map[category] || null;
  }

  function filterReasonResultsByCategories(reasonResults, stateResults, categoryKeys) {
    const keys = new Set(categoryKeys);
    return (Array.isArray(reasonResults) ? reasonResults : []).filter((reason) => {
      if (!reason?.summary || !reason.ruleId) return false;
      const state = (Array.isArray(stateResults) ? stateResults : []).find((item) => item.ruleId === reason.ruleId);
      const categoryKey = state?.planCategoryKey || resolveCategoryKeyForRuleId(reason.ruleId);
      return keys.has(categoryKey);
    });
  }

  function filterStatesByCategories(stateResults, categoryKeys) {
    const keys = new Set(categoryKeys);
    return (Array.isArray(stateResults) ? stateResults : []).filter((state) => {
      const categoryKey = state?.planCategoryKey || resolveStateCategoryKey(state?.category);
      return keys.has(categoryKey);
    });
  }

  function formatMetricsBlock(title, items) {
    return {
      title,
      rows: (Array.isArray(items) ? items : []).map((item) => ({
        label: item.label,
        percent: item.percent ?? 0,
      })),
    };
  }

  return {
    findMetricItem,
    dominantMetricItem,
    joinSentences,
    resolveCategoryKeyForRuleId,
    resolveStateCategoryKey,
    filterReasonResultsByCategories,
    filterStatesByCategories,
    formatMetricsBlock,
  };
})();
