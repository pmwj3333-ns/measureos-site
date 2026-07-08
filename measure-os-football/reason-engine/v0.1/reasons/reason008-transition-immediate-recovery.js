(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule008";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "即時奪回";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];

    if (counts.quickRecovery > 0) {
      built.push(countFact("quick_recovery", "即時奪回", counts.quickRecovery));
    }
    if (counts.counterStarted > 0) {
      built.push(countFact("counter_started", "カウンター開始", counts.counterStarted));
    }
    if (counts.counterConceded > 0) {
      built.push(countFact("counter_conceded", "被カウンター", counts.counterConceded));
    }

    if (counts.quickRecovery === 0) {
      built.push(countFact("no_immediate_recovery", "即時奪回", 0));
    }
    if (counts.quickRecovery === 0 && counts.counterStarted === 0 && counts.counterConceded === 0) {
      built.push(countFact("no_transition", "切り替え", 0));
    }
    if (counts.quickRecovery >= 1 && counts.counterStarted >= 1) {
      built.push(thresholdFact("delayed_recovery", "即時奪回", counts.quickRecovery, ">=", 1));
    }
    if (
      counts.counterConceded === 0
      && counts.quickRecovery >= 1
      && (counts.quickRecovery > counts.counterStarted || (counts.quickRecovery >= 2 && counts.counterStarted <= 1))
    ) {
      built.push(thresholdFact("immediate_recovery_working", "即時奪回", counts.quickRecovery, ">=", 1));
    }
    if (counts.counterConceded >= 1) {
      built.push(thresholdFact("counter_conceded_detected", "被カウンター", counts.counterConceded, ">=", 1));
    }
    if (
      counts.counterConceded === 0
      && (counts.counterStarted >= 2 || (counts.counterStarted >= 1 && counts.quickRecovery === 0))
    ) {
      built.push(thresholdFact("recovery_under_pressure", "カウンター開始", counts.counterStarted, ">=", 1));
    }
    if (counts.counterConceded >= 2) {
      built.push(thresholdFact("multiple_counters", "被カウンター", counts.counterConceded, ">=", 2));
    }
    if (counts.counterConceded >= 1 && counts.quickRecovery === 0) {
      built.push(thresholdFact("transition_breakdown", "即時奪回崩壊", counts.counterConceded, ">=", 1));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.immediate_recovery_working`;
      case "yellow":
        if (counts.quickRecovery === 0) {
          return `${RULE_ID}.yellow.no_transition`;
        }
        return `${RULE_ID}.yellow.delayed_recovery`;
      case "orange":
        if (counts.counterConceded >= 1) {
          return `${RULE_ID}.orange.counter_conceded`;
        }
        return `${RULE_ID}.orange.recovery_under_pressure`;
      case "red":
        if (counts.counterConceded >= 2) {
          return `${RULE_ID}.red.multiple_counters`;
        }
        return `${RULE_ID}.red.transition_breakdown`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.immediate_recovery_working`:
        return joinSentences([
          prefix,
          "ボールロスト後に素早く奪い返しています。",
        ]);

      case `${RULE_ID}.yellow.delayed_recovery`:
        return joinSentences([
          prefix,
          "ボール奪取はありますが、即時奪回には至っていません。",
        ]);

      case `${RULE_ID}.yellow.no_transition`:
        return joinSentences([
          prefix,
          "即時奪回の場面は記録されていません。",
        ]);

      case `${RULE_ID}.orange.counter_conceded`:
        return joinSentences([
          prefix,
          "被カウンターが発生しています。",
        ]);

      case `${RULE_ID}.orange.recovery_under_pressure`:
        return joinSentences([
          prefix,
          "ボール奪取まで時間を要しています。",
        ]);

      case `${RULE_ID}.red.transition_breakdown`:
        return joinSentences([
          prefix,
          "即時奪回が成立せず、相手に攻撃を継続されています。",
        ]);

      case `${RULE_ID}.red.multiple_counters`:
        return joinSentences([
          prefix,
          "被カウンターが複数回発生しています。",
        ]);

      default:
        return joinSentences([prefix, "即時奪回に関する観測事実を整理しています。"]);
    }
  }

  window.MO_REASON_ENGINE.registerReasonRule({
    ruleId: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const transitionPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(transitionPlan) && transitionPlan.includes(PLAN_OPTION);
    },

    buildFacts,
    resolveReasonKey,
    buildSummary,
  });
})();
