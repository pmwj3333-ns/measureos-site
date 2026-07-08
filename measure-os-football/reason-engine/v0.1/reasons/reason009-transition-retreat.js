(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule009";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "リトリート";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function getFlankPenetration(counts) {
    return counts.leftConceded + counts.rightConceded;
  }

  function getRetreatPressure(counts) {
    return counts.centralPenetration + getFlankPenetration(counts) + counts.shotConceded + counts.counterConceded;
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];
    const flankPenetration = getFlankPenetration(counts);
    const retreatPressure = getRetreatPressure(counts);

    if (counts.centralPenetration > 0) {
      built.push(countFact("central_penetration", "被中央侵入", counts.centralPenetration));
    }
    if (counts.leftConceded > 0) {
      built.push(countFact("left_conceded", "被左侵入", counts.leftConceded));
    }
    if (counts.rightConceded > 0) {
      built.push(countFact("right_conceded", "被右侵入", counts.rightConceded));
    }
    if (counts.shotConceded > 0) {
      built.push(countFact("shot_conceded", "被シュート", counts.shotConceded));
    }
    if (counts.counterConceded > 0) {
      built.push(countFact("counter_conceded", "被カウンター", counts.counterConceded));
    }
    if (counts.ballWon > 0) {
      built.push(countFact("ball_won", "ボール奪取", counts.ballWon));
    }

    if (retreatPressure === 0) {
      built.push(countFact("no_retreat_pressure", "リトリート", 0));
    }
    if (
      counts.counterConceded === 0
      && counts.shotConceded === 0
      && counts.centralPenetration <= 1
      && flankPenetration === 0
    ) {
      built.push(thresholdFact("retreat_working", "リトリート", counts.centralPenetration, "<=", 1));
    }
    if (
      counts.counterConceded === 0
      && counts.shotConceded === 0
      && retreatPressure === 0
    ) {
      built.push(countFact("retreat_not_required", "リトリート", 0));
    }
    if (
      counts.counterConceded === 0
      && counts.shotConceded === 0
      && counts.centralPenetration >= 2
    ) {
      built.push(thresholdFact("retreat_in_progress", "被中央侵入", counts.centralPenetration, ">=", 2));
    }
    if (counts.counterConceded >= 1) {
      built.push(thresholdFact("counter_pressure_detected", "被カウンター", counts.counterConceded, ">=", 1));
    }
    if (
      counts.counterConceded === 0
      && (counts.shotConceded >= 1 || counts.centralPenetration >= 3)
    ) {
      built.push(thresholdFact("retreat_delayed", "守備切り替え", counts.centralPenetration, ">=", 1));
    }
    if (counts.counterConceded >= 2) {
      built.push(thresholdFact("multiple_counters", "被カウンター", counts.counterConceded, ">=", 2));
    }
    if (
      counts.counterConceded >= 1
      && counts.centralPenetration >= 2
      && counts.counterConceded < 2
    ) {
      built.push(thresholdFact("retreat_breakdown", "リトリート崩壊", counts.centralPenetration, ">=", 2));
    }
    if (
      counts.counterConceded < 2
      && (counts.shotConceded >= 2 || counts.centralPenetration >= 5)
    ) {
      built.push(thresholdFact("retreat_breakdown", "リトリート崩壊", counts.centralPenetration, ">=", 5));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.retreat_working`;
      case "yellow":
        if (getRetreatPressure(counts) === 0) {
          return `${RULE_ID}.yellow.retreat_not_required`;
        }
        return `${RULE_ID}.yellow.retreat_in_progress`;
      case "orange":
        if (counts.counterConceded >= 1) {
          return `${RULE_ID}.orange.counter_pressure`;
        }
        return `${RULE_ID}.orange.retreat_delayed`;
      case "red":
        if (counts.counterConceded >= 2) {
          return `${RULE_ID}.red.multiple_counters`;
        }
        return `${RULE_ID}.red.retreat_breakdown`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.retreat_working`:
        return joinSentences([
          prefix,
          "守備への切り替えが速く、相手の前進を抑えています。",
        ]);

      case `${RULE_ID}.yellow.retreat_not_required`:
        return joinSentences([
          prefix,
          "リトリートが必要となる場面は記録されていません。",
        ]);

      case `${RULE_ID}.yellow.retreat_in_progress`:
        return joinSentences([
          prefix,
          "守備への切り替えは行われていますが、大きな守備対応は発生していません。",
        ]);

      case `${RULE_ID}.orange.counter_pressure`:
        return joinSentences([
          prefix,
          "被カウンターを受けています。",
        ]);

      case `${RULE_ID}.orange.retreat_delayed`:
        return joinSentences([
          prefix,
          "守備への切り替えに時間を要しています。",
        ]);

      case `${RULE_ID}.red.retreat_breakdown`:
        return joinSentences([
          prefix,
          "守備への切り替えが遅れ、相手の攻撃継続を許しています。",
        ]);

      case `${RULE_ID}.red.multiple_counters`:
        return joinSentences([
          prefix,
          "被カウンターが複数回発生しています。",
        ]);

      default:
        return joinSentences([prefix, "リトリートに関する観測事実を整理しています。"]);
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
