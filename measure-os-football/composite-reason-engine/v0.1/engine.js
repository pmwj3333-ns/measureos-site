(function () {
  // Composite Reason Engine 設計思想:
  //
  // Composite Reason Engine の中心データは Composite Fact です。
  //
  // shortSummary は compositeReasonKey から生成する派生データです。
  // summary は shortSummary と compositeReasonKey から生成する派生データです。
  // severity は Composite Facts（Rule Reason status）から算出する総合状態です。
  //
  // 処理順: buildCompositeFacts() → resolveCompositeSeverity() → resolveCompositeReasonKey() → buildCompositeShortSummary() → buildCompositeSummary()
  //
  // Rule Reason（summary / reasonKey / status / facts）を入力とし、
  // Analyze Mode 単位の Overall Reason を生成します。
  //
  // State Engine・Reason Engine の再実行は行いません。
  // Rule の再評価・Reason の再生成も禁止です。
  const modes = () => window.MO_COMPOSITE_ANALYZE_MODES;
  const compositeFacts = () => window.MO_COMPOSITE_FACT_BUILDER;
  const severityResolver = () => window.MO_COMPOSITE_SEVERITY_RESOLVER;
  const reasonKeyResolver = () => window.MO_COMPOSITE_REASON_KEY_RESOLVER;
  const summaryBuilder = () => window.MO_COMPOSITE_SUMMARY_BUILDER;

  function groupReasonsByCategory(reasonResults, categoryKeys) {
    const grouped = {};
    categoryKeys.forEach((categoryKey) => {
      grouped[categoryKey] = [];
    });

    (reasonResults || []).forEach((reason) => {
      if (!reason?.ruleId || !reason?.reasonKey) return;

      const categoryKey = modes()?.resolveCategoryKeyForRuleId(reason.ruleId);
      if (!categoryKey || !categoryKeys.includes(categoryKey)) return;

      grouped[categoryKey].push(reason);
    });

    return grouped;
  }

  function buildCategoryEntries(groupedReasons) {
    return Object.entries(groupedReasons)
      .filter(([, reasons]) => reasons.length > 0)
      .map(([categoryKey, reasons]) => ({
        categoryKey,
        label: modes()?.CATEGORY_LABELS?.[categoryKey] || categoryKey,
        reasonKeys: reasons.map((reason) => reason.reasonKey),
        statuses: reasons.map((reason) => reason.status),
        summaries: reasons.map((reason) => reason.summary),
        facts: reasons.flatMap((reason) => (
          Array.isArray(reason.facts)
            ? reason.facts.map((fact) => ({
              ...fact,
              ruleId: reason.ruleId,
              reasonKey: reason.reasonKey,
              status: reason.status,
              categoryKey,
            }))
            : []
        )),
      }));
  }

  function composeOverallReason({ analyzeMode, reasonResults = [] }) {
    const normalizedMode = modes()?.normalizeAnalyzeMode(analyzeMode) || "both";
    const categoryKeys = modes()?.getCategoryKeysForMode(normalizedMode) || [];
    const includedReasons = (reasonResults || []).filter((reason) => {
      const categoryKey = modes()?.resolveCategoryKeyForRuleId(reason?.ruleId);
      return categoryKey && categoryKeys.includes(categoryKey);
    });

    const groupedReasons = groupReasonsByCategory(includedReasons, categoryKeys);

    const facts = compositeFacts()?.buildCompositeFacts({
      analyzeMode: normalizedMode,
      includedReasons,
      groupedReasons,
    }) || [];

    const severity = severityResolver()?.resolveCompositeSeverity(facts) || "green";

    const compositeReasonKey = reasonKeyResolver()?.resolveCompositeReasonKey({
      analyzeMode: normalizedMode,
      facts,
    }) || "composite.unknown.aggregated_rule_summaries";

    const summaryContext = {
      analyzeMode: normalizedMode,
      severity,
      groupedReasons,
      includedReasons,
    };

    const shortSummary = summaryBuilder()?.buildCompositeShortSummary(
      compositeReasonKey,
      facts,
      summaryContext,
    ) || "";

    const summary = summaryBuilder()?.buildCompositeSummary(
      compositeReasonKey,
      shortSummary,
      facts,
      summaryContext,
    ) || "";

    return {
      analyzeMode: normalizedMode,
      category: normalizedMode,
      severity,
      compositeReasonKey,
      shortSummary,
      summary,
      reasonKeys: includedReasons.map((reason) => reason.reasonKey),
      categories: buildCategoryEntries(groupedReasons),
      facts,
    };
  }

  window.MO_COMPOSITE_REASON_ENGINE = {
    composeOverallReason,
  };
})();
