(function () {
  const factBuilder = () => window.MO_COMPOSITE_FACT_BUILDER;

  function slugify(value) {
    return String(value || "unknown")
      .replace(/\s+/g, "_")
      .replace(/[^\w]/g, "")
      .toLowerCase();
  }

  function resolvePlanMatchKey({ analyzeMode, facts = [], bestMatch = null }) {
    const mode = analyzeMode || "both";
    const score = Number(bestMatch?.score) || 0;
    const planSlug = slugify(bestMatch?.plan?.label || "unknown_plan");

    if (factBuilder()?.hasFact(facts, "counter_observed")) {
      return `planMatch.${mode}.counter_pressure_profile`;
    }
    if (factBuilder()?.hasFact(facts, "central_penetration_observed")) {
      return `planMatch.${mode}.central_penetration_profile`;
    }
    if (score >= 70) {
      return `planMatch.${mode}.strong_${planSlug}_alignment`;
    }
    if (score >= 45) {
      return `planMatch.${mode}.moderate_${planSlug}_alignment`;
    }
    if (score >= 20) {
      return `planMatch.${mode}.weak_${planSlug}_alignment`;
    }
    return `planMatch.${mode}.low_alignment`;
  }

  window.MO_PLAN_MATCH_KEY_RESOLVER = {
    resolvePlanMatchKey,
  };
})();
