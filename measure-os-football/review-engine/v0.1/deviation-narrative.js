window.MO_REVIEW_DEVIATION = (() => {
  const { findMetricItem, dominantMetricItem } = window.MO_REVIEW_HELPERS;

  const ATTACK_METRIC_CODES = new Set(["left", "center", "right"]);
  const BUILD_UP_METRIC_CODES = new Set(["possession", "long"]);

  const INTRUSION_LABELS = {
    left: "左",
    center: "中央",
    right: "右",
  };

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

  function aggregateSegmentMetrics(events) {
    return window.MO_MATCH_METRICS?.aggregate?.(events) || {
      attack: [],
      buildUp: [],
    };
  }

  function buildPlanSegments(record) {
    const events = Array.isArray(record?.events) ? record.events : [];
    const history = Array.isArray(record?.match?.planHistory) ? record.match.planHistory : [];
    const normalizePlanSnapshot = window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot;

    if (typeof normalizePlanSnapshot !== "function" || history.length === 0) {
      return [];
    }

    return history
      .map((entry, index) => {
        const plan = normalizePlanSnapshot(entry?.plan);
        if (!plan) return null;

        const boundary = Number(entry.eventBoundaryIndex) || 0;
        const sliceEnd = history[index + 1]?.eventBoundaryIndex ?? events.length;
        const segmentEvents = events.slice(boundary, sliceEnd);
        const matchMetrics = aggregateSegmentMetrics(segmentEvents);

        return {
          planNumber: index + 1,
          startTime: entry.matchTime || "00:00",
          plan,
          segmentEvents,
          matchMetrics,
        };
      })
      .filter(Boolean);
  }

  function describeAttackDeviation(planCode, planLabel, attackMetrics) {
    const dominant = dominantMetricItem(attackMetrics);
    if (!dominant) return null;

    if (dominant.code === planCode && dominant.percent >= 50) {
      return { status: "ok", text: `${planLabel}は維持された` };
    }

    if (dominant.code === planCode && dominant.percent < 50) {
      const intrusionLabel = INTRUSION_LABELS[planCode] || dominant.label;
      return { status: "warn", text: `${intrusionLabel}侵入は増えたが最も多くはならなかった` };
    }

    return {
      status: "warn",
      text: `${dominant.label}侵入が最も多く、Planとは異なる傾向になった`,
    };
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

    return {
      key: "attack",
      title: "Attack",
      planLabel,
      rows,
      deviation: describeAttackDeviation(planCode, planLabel, attackMetrics),
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
      ? { status: "ok", text: `${planLabel}主体だった` }
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

  function buildDeviationsFromRecord(record) {
    return buildPlanSegments(record).map((segment) => ({
      ...segment,
      ...buildDeviation({
        plan: segment.plan,
        matchMetrics: segment.matchMetrics,
      }),
    }));
  }

  return {
    buildPlanSegments,
    buildDeviation,
    buildDeviationsFromRecord,
    compareAttack,
    compareBuildUp,
  };
})();
