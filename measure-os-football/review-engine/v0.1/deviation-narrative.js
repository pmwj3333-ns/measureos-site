window.MO_REVIEW_DEVIATION = (() => {
  const { dominantMetricItem } = window.MO_REVIEW_HELPERS;

  const ATTACK_METRIC_CODES = new Set(["left", "center", "right"]);
  const BUILD_UP_METRIC_CODES = new Set(["possession", "long"]);

  function getPlanLabel(plan, categoryKey) {
    const fromCategories = plan?.categories?.[categoryKey]?.[0];
    if (typeof fromCategories === "string" && fromCategories) return fromCategories;

    const code = plan?.[categoryKey];
    if (!code) return null;
    return window.MO_ATTACK_PLAN?.codeToLabel?.(categoryKey, code) || null;
  }

  function getPlanCode(plan, categoryKey) {
    if (typeof plan?.[categoryKey] === "string" && plan[categoryKey]) {
      return plan[categoryKey];
    }

    const label = getPlanLabel(plan, categoryKey);
    if (!label) return null;
    return window.MO_ATTACK_PLAN?.labelToCode?.(categoryKey, label) || null;
  }

  function formatResultRows(items) {
    return (Array.isArray(items) ? items : []).map((item) => ({
      label: item.label,
      percent: item.percent ?? 0,
    }));
  }

  function metricTotal(items) {
    return (Array.isArray(items) ? items : []).reduce((sum, item) => sum + (item.count || 0), 0);
  }

  function compareAttack(plan, attackMetrics) {
    const planLabel = getPlanLabel(plan, "attack");
    const planCode = getPlanCode(plan, "attack");
    if (!planLabel || !ATTACK_METRIC_CODES.has(planCode)) return null;

    const rows = formatResultRows(attackMetrics);
    const total = metricTotal(attackMetrics);
    if (total === 0) {
      return {
        key: "attack",
        title: "Attack",
        planLabel,
        rows,
        deviation: null,
      };
    }

    const dominant = dominantMetricItem(attackMetrics);
    if (!dominant) {
      return {
        key: "attack",
        title: "Attack",
        planLabel,
        rows,
        deviation: null,
      };
    }

    const deviation = dominant.code === planCode
      ? { status: "ok", text: `${planLabel}は維持された` }
      : { status: "warn", text: `${dominant.label}侵入が最も多く、Planとは異なる傾向になった` };

    return {
      key: "attack",
      title: "Attack",
      planLabel,
      rows,
      deviation,
    };
  }

  function compareBuildUp(plan, buildUpMetrics) {
    const planLabel = getPlanLabel(plan, "buildUp");
    const planCode = getPlanCode(plan, "buildUp");
    if (!planLabel || !BUILD_UP_METRIC_CODES.has(planCode)) return null;

    const rows = formatResultRows(buildUpMetrics);
    const total = metricTotal(buildUpMetrics);
    if (total === 0) {
      return {
        key: "buildUp",
        title: "Build Up",
        planLabel,
        rows,
        deviation: null,
      };
    }

    const dominant = dominantMetricItem(buildUpMetrics);
    if (!dominant) {
      return {
        key: "buildUp",
        title: "Build Up",
        planLabel,
        rows,
        deviation: null,
      };
    }

    const deviation = dominant.code === planCode
      ? { status: "ok", text: `${planLabel}主体で攻撃できた` }
      : { status: "warn", text: `${dominant.label}が主体となった` };

    return {
      key: "buildUp",
      title: "Build Up",
      planLabel,
      rows,
      deviation,
    };
  }

  function buildDeviation({ plan, matchMetrics }) {
    if (!plan) {
      return { categories: [], deviations: [] };
    }

    const categories = [
      compareAttack(plan, matchMetrics?.attack || []),
      compareBuildUp(plan, matchMetrics?.buildUp || []),
    ].filter(Boolean);

    const deviations = categories
      .map((category) => category.deviation)
      .filter(Boolean);

    return { categories, deviations };
  }

  return {
    buildDeviation,
    compareAttack,
    compareBuildUp,
  };
})();
