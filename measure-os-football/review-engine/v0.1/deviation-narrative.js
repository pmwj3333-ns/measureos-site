window.MO_REVIEW_DEVIATION = (() => {
  const { findMetricItem, dominantMetricItem } = window.MO_REVIEW_HELPERS;

  const ATTACK_METRIC_CODES = new Set(["left", "center", "right"]);
  const BUILD_UP_METRIC_CODES = new Set(["possession", "long"]);

  const INTRUSION_LABELS = {
    left: "左",
    center: "中央",
    right: "右",
  };

  const BUILD_UP_SHORT_LABELS = {
    possession: "保持",
    long: "ロング",
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

  function intrusionPhrase(code, fallbackLabel = "") {
    const label = INTRUSION_LABELS[code] || fallbackLabel;
    return label ? `${label}侵入` : "侵入";
  }

  function isSecondHighest(items, code) {
    const ranked = (Array.isArray(items) ? items : [])
      .filter((item) => item.count > 0)
      .sort((a, b) => b.percent - a.percent);
    return ranked.length >= 2 && ranked[1].code === code;
  }

  function resolveSegmentEndTime(history, index) {
    const nextEntry = history[index + 1];
    if (nextEntry?.matchTime) return nextEntry.matchTime;
    return "試合終了";
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
        const startTime = entry.matchTime || "00:00";
        const endTime = resolveSegmentEndTime(history, index);

        return {
          planNumber: index + 1,
          startTime,
          endTime,
          timeRangeLabel: `${startTime} ～ ${endTime}`,
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

    const planned = findMetricItem(attackMetrics, planCode);
    const plannedPhrase = intrusionPhrase(planCode, planned.label);
    const dominantPhrase = intrusionPhrase(dominant.code, dominant.label);

    if (dominant.code === planCode && dominant.percent >= 50) {
      return {
        status: "ok",
        text: `${plannedPhrase}が最も多く見られ、${planLabel}の傾向を維持できました。`,
      };
    }

    if (dominant.code === planCode && dominant.percent < 50) {
      return {
        status: "warn",
        text: `${plannedPhrase}は増えましたが、主体には至りませんでした。`,
      };
    }

    if (planned.percent > 0 && isSecondHighest(attackMetrics, planCode)) {
      return {
        status: "warn",
        text: `${plannedPhrase}は増えましたが、主体には至りませんでした。`,
      };
    }

    if (planned.percent > 0) {
      return {
        status: "warn",
        text: `${dominantPhrase}が中心となり、Planとは異なる攻撃になりました。`,
      };
    }

    return {
      status: "warn",
      text: `${dominantPhrase}が中心となり、Planの${planLabel}から外れた攻撃になりました。`,
    };
  }

  function describeBuildUpDeviation(planCode, planLabel, buildUpMetrics) {
    const dominant = dominantMetricItem(buildUpMetrics);
    if (!dominant) return null;

    const shortLabel = BUILD_UP_SHORT_LABELS[planCode] || planLabel;

    if (dominant.code === planCode) {
      return {
        status: "ok",
        text: `${shortLabel}主体で試合を進められました。`,
      };
    }

    return {
      status: "warn",
      text: `${dominant.label}が主体となり、${shortLabel}主体のPlanから外れました。`,
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

    return {
      key: "buildUp",
      title: "Build Up",
      planLabel,
      rows,
      deviation: describeBuildUpDeviation(planCode, planLabel, buildUpMetrics),
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
