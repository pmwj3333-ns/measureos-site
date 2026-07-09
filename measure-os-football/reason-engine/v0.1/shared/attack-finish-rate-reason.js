window.MO_ATTACK_FINISH_RATE_REASON = (() => {
  const PLAN_CATEGORY_KEY = "attack";
  const MIN_ATTACK_COUNT = window.MO_ATTACK_FINISH_RATE?.MIN_ATTACK_COUNT ?? 5;

  function factsBuilder() {
    return window.MO_REASON_FACT_BUILDER;
  }

  function getMetricsFromState(state) {
    const metrics = state?.finishRateMetrics;
    if (metrics && typeof metrics.attackCount === "number") {
      return {
        attackCount: Math.max(0, Number(metrics.attackCount) || 0),
        shotCount: Math.max(0, Number(metrics.shotCount) || 0),
        bigChanceCount: Math.max(0, Number(metrics.bigChanceCount) || 0),
        lostCount: Math.max(0, Number(metrics.lostCount) || 0),
        lostRate: Math.max(0, Number(metrics.lostRate) || 0),
        shotRate: Math.max(0, Number(metrics.shotRate) || 0),
        bigChanceRate: Math.max(0, Number(metrics.bigChanceRate) || 0),
      };
    }

    const counts = state?.reasonEventCounts && typeof state.reasonEventCounts === "object"
      ? state.reasonEventCounts
      : {};

    return {
      attackCount: Math.max(0, Number(counts.attackCount) || 0),
      shotCount: Math.max(0, Number(counts.シュート) || 0),
      bigChanceCount: Math.max(0, Number(counts.決定機) || 0),
      lostCount: Math.max(0, Number(counts.ロスト) || 0),
      lostRate: Math.max(0, Number(counts.lostRate) || 0),
      shotRate: Math.max(0, Number(counts.shotRate) || 0),
      bigChanceRate: Math.max(0, Number(counts.bigChanceRate) || 0),
    };
  }

  function buildFinishRateFacts(state) {
    const { countFact, createFact } = factsBuilder() || {};
    if (!countFact || !createFact) return [];

    const metrics = getMetricsFromState(state);
    const lostRateLabel = `${Math.round(metrics.lostRate)}%`;

    return [
      countFact("attack_total", "Attack", metrics.attackCount),
      countFact("shot_finish", "シュート", metrics.shotCount),
      countFact("big_chance_finish", "決定機", metrics.bigChanceCount),
      countFact("lost_finish", "ロスト", metrics.lostCount),
      createFact({
        code: "lost_rate",
        label: "ロスト率",
        value: lostRateLabel,
      }),
    ];
  }

  function resolveReasonKey(state, ruleId) {
    const status = state?.status || "unknown";

    switch (status) {
      case "green":
        return `${ruleId}.green.finish_rate_fact`;
      case "yellow":
        return `${ruleId}.yellow.finish_rate_fact`;
      case "orange":
        return `${ruleId}.orange.finish_rate_fact`;
      case "red":
        return `${ruleId}.red.finish_rate_fact`;
      case "pending":
        return `${ruleId}.pending.not_enough_data`;
      default:
        return `${ruleId}.${status}.unknown`;
    }
  }

  function buildFactualSummary(state, routeLabel) {
    const metrics = getMetricsFromState(state);
    const status = state?.status || "unknown";

    if (status === "pending" || metrics.attackCount < MIN_ATTACK_COUNT) {
      if (metrics.attackCount <= 0) {
        return "Attackの記録がありません。";
      }
      return `Attack数が${MIN_ATTACK_COUNT}回未満（${metrics.attackCount}回）のため、ロスト率の事実説明を保留しています。`;
    }

    const lostRate = Math.round(metrics.lostRate);
    if (routeLabel) {
      return `${routeLabel}から侵入した攻撃の${lostRate}%がロストで終了しています。`;
    }
    return `攻撃の${lostRate}%がロストで終了しています。`;
  }

  function buildFinishRateSummary(reasonKey, builtFacts, state, routeLabel) {
    return buildFactualSummary(state, routeLabel);
  }

  function registerAttackFinishRateReasonRule({
    ruleId,
    planOption,
    routeLabel = null,
  }) {
    if (!ruleId || !planOption) return;

    window.MO_REASON_ENGINE.registerReasonRule({
      ruleId,
      planCategoryKey: PLAN_CATEGORY_KEY,
      planOption,

      isEnabled(plan) {
        const attackPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
        return Array.isArray(attackPlan) && attackPlan.includes(planOption);
      },

      buildFacts(state) {
        return buildFinishRateFacts(state);
      },

      resolveReasonKey(state) {
        return resolveReasonKey(state, ruleId);
      },

      buildSummary(reasonKey, builtFacts, state) {
        return buildFinishRateSummary(reasonKey, builtFacts, state, routeLabel);
      },
    });
  }

  return {
    MIN_ATTACK_COUNT,
    getMetricsFromState,
    buildFinishRateFacts,
    buildFactualSummary,
    resolveReasonKey,
    buildFinishRateSummary,
    registerAttackFinishRateReasonRule,
  };
})();
