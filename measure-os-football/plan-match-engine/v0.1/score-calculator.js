(function () {
  const catalog = () => window.MO_PLAN_MATCH_CATALOG;
  const factBuilder = () => window.MO_COMPOSITE_FACT_BUILDER;

  const STATUS_SCORE = {
    green: 20,
    yellow: 10,
    orange: 4,
    red: 0,
  };

  function hasFact(facts, code) {
    return factBuilder()?.hasFact(facts, code) || false;
  }

  function getRuleStatus(facts, ruleId) {
    const fact = (facts || []).find((item) => (
      item.code === "included_rule_status" && item.label === ruleId
    ));
    return fact?.value || null;
  }

  function getRuleReasonKey(facts, ruleId) {
    const fact = (facts || []).find((item) => (
      item.code === "included_rule_reason" && item.label === ruleId
    ));
    return fact?.value || null;
  }

  function scoreFromSeverity(severity) {
    switch (severity) {
      case "green": return 70;
      case "yellow": return 45;
      case "orange": return 20;
      default: return 0;
    }
  }

  function resolveMatchSeverity(score) {
    if (score >= 70) return "green";
    if (score >= 45) return "yellow";
    if (score >= 20) return "orange";
    return "red";
  }

  function scoreCandidatePlan(candidatePlan, facts, compositeReason) {
    const categoryKeys = catalog()?.getCategoryKeysForMode(candidatePlan.analyzeMode) || [];
    let earned = 0;
    let max = 0;

    categoryKeys.forEach((categoryKey) => {
      const options = Array.isArray(candidatePlan.categories?.[categoryKey])
        ? candidatePlan.categories[categoryKey]
        : [];

      options.forEach((optionLabel) => {
        const ruleId = catalog()?.resolveRuleId(categoryKey, optionLabel);
        if (!ruleId) return;

        const signature = catalog()?.PLAN_SIGNATURES?.[ruleId] || {};
        const positive = Array.isArray(signature.positive) ? signature.positive : [];
        const negative = Array.isArray(signature.negative) ? signature.negative : [];

        positive.forEach((code) => {
          max += 10;
          if (hasFact(facts, code)) earned += 10;
        });

        negative.forEach((code) => {
          max += 5;
          if (!hasFact(facts, code)) earned += 5;
          else earned -= 3;
        });

        const observedStatus = getRuleStatus(facts, ruleId);
        if (observedStatus) {
          max += 20;
          earned += STATUS_SCORE[observedStatus] ?? 0;
        }

        const observedReasonKey = getRuleReasonKey(facts, ruleId);
        if (observedReasonKey?.startsWith(`${ruleId}.green.`)) {
          max += 15;
          earned += 15;
        } else         if (observedReasonKey?.startsWith(`${ruleId}.yellow.`)) {
          max += 15;
          earned += 8;
        }
      });
    });

    if (max === 0) {
      return scoreFromSeverity(compositeReason?.severity);
    }

    const normalized = Math.round((earned / max) * 100);
    return Math.max(0, Math.min(100, normalized));
  }

  window.MO_PLAN_MATCH_SCORE_CALCULATOR = {
    scoreCandidatePlan,
    resolveMatchSeverity,
  };
})();
