window.MO_REVIEW_DEFENSE_NARRATIVE = (() => {
  const {
    filterReasonResultsByCategories,
    filterStatesByCategories,
    resolveCategoryKeyForRuleId,
  } = window.MO_REVIEW_HELPERS;

  const DEFENSE_SECTIONS = [
    { key: "defense", title: "Defense" },
    { key: "transition", title: "Transition" },
  ];

  function groupReasonsByCategory(reasonResults, stateResults, categoryKey) {
    return filterReasonResultsByCategories(reasonResults, stateResults, [categoryKey]);
  }

  function buildCategoryNarrative(categoryKey, stateResults, reasonResults) {
    const states = filterStatesByCategories(stateResults, [categoryKey]);
    const reasons = groupReasonsByCategory(reasonResults, stateResults, categoryKey);

    const reasonSummaries = reasons.map((reason) => reason.summary).filter(Boolean);
    if (reasonSummaries.length > 0) {
      return reasonSummaries.join("");
    }

    const stateLabels = states.map((state) => state.label).filter(Boolean);
    if (stateLabels.length > 0) {
      return stateLabels.join("。") + "。";
    }

    return null;
  }

  function buildDefenseReview({ stateResults, reasonResults, compositeReason }) {
    const sections = DEFENSE_SECTIONS.map(({ key, title }) => ({
      key,
      title,
      narrative: buildCategoryNarrative(key, stateResults, reasonResults),
    })).filter((section) => section.narrative);

    const narrative = sections.map((section) => section.narrative).join("") || null;
    const summary = compositeReason?.summary || null;
    const miniReview = window.MO_REVIEW_MINI_NARRATIVE?.buildDefenseMiniNarrative?.({
      stateResults,
      reasonResults,
    }) || {
      defense: null,
      transition: null,
    };

    return {
      key: "defense",
      title: "Defense Review",
      sections,
      narrative,
      summary,
      miniReview,
    };
  }

  return {
    DEFENSE_SECTIONS,
    buildDefenseReview,
    resolveCategoryKeyForRuleId,
  };
})();
