(function () {
  // Plan Match Engine 設計思想:
  //
  // 現在の観測がどの Game Plan の特徴に近いかを分析します。
  // Game Plan の変更提案は行いません。
  //
  // 入力は CompositeReasonResult のみです。
  // State・Reason・Composite の再評価は行いません。
  //
  // 処理順: Composite Facts → planMatchKey → Plan Match Score → Plan Match Result
  const catalog = () => window.MO_PLAN_MATCH_CATALOG;
  const keyResolver = () => window.MO_PLAN_MATCH_KEY_RESOLVER;
  const scoreCalculator = () => window.MO_PLAN_MATCH_SCORE_CALCULATOR;
  const compositeModes = () => window.MO_COMPOSITE_ANALYZE_MODES;

  function normalizeCurrentPlan(compositeReason, currentPlan) {
    if (currentPlan?.categories) {
      return {
        analyzeMode: currentPlan.analyzeMode || compositeReason?.analyzeMode || "both",
        categories: currentPlan.categories,
        label: catalog()?.formatPlanLabel(
          currentPlan.categories,
          catalog()?.getCategoryKeysForMode(currentPlan.analyzeMode || compositeReason?.analyzeMode) || [],
        ),
      };
    }

    const analyzeMode = compositeReason?.analyzeMode || "both";
    const categoryKeys = catalog()?.getCategoryKeysForMode(analyzeMode) || [];
    const categories = {};

    (compositeReason?.categories || []).forEach((entry) => {
      const options = (entry.reasonKeys || [])
        .map((reasonKey) => {
          const ruleId = String(reasonKey || "").split(".")[0];
          return catalog()?.resolveOptionLabel(entry.categoryKey, ruleId);
        })
        .filter(Boolean);
      if (options.length > 0) {
        categories[entry.categoryKey] = [...new Set(options)];
      }
    });

    categoryKeys.forEach((key) => {
      if (!categories[key]) categories[key] = [];
    });

    return {
      analyzeMode,
      categories,
      label: catalog()?.formatPlanLabel(categories, categoryKeys) || "-",
    };
  }

  function matchPlan(compositeReason) {
    if (!compositeReason || !Array.isArray(compositeReason.facts)) return null;

    const analyzeMode = compositeModes()?.normalizeAnalyzeMode(compositeReason.analyzeMode) || "both";
    const facts = compositeReason.facts;
    const normalizedCurrentPlan = normalizeCurrentPlan(compositeReason, null);
    const candidates = catalog()?.buildCandidatePlans(analyzeMode) || [];

    const matches = candidates.map((plan) => {
      const score = scoreCalculator()?.scoreCandidatePlan(plan, facts, compositeReason) ?? 0;
      return {
        plan,
        score,
        severity: scoreCalculator()?.resolveMatchSeverity(score) || "red",
      };
    }).sort((a, b) => b.score - a.score);

    const bestMatch = matches[0] || null;
    const planMatchKey = keyResolver()?.resolvePlanMatchKey({
      analyzeMode,
      facts,
      bestMatch,
    }) || `planMatch.${analyzeMode}.unknown`;

    return {
      analyzeMode,
      planMatchKey,
      currentPlan: normalizedCurrentPlan,
      bestMatch,
      matches,
    };
  }

  window.MO_PLAN_MATCH_ENGINE = {
    matchPlan,
  };
})();
