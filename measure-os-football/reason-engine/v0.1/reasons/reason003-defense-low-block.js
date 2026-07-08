(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule003";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ローブロック";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function getFlankPenetration(counts) {
    return counts.leftConceded + counts.rightConceded;
  }

  function getTotalPenetration(counts) {
    return counts.centralPenetration + getFlankPenetration(counts) + counts.crossConceded;
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];
    const flankPenetration = getFlankPenetration(counts);
    const totalPenetration = getTotalPenetration(counts);

    if (counts.centralPenetration > 0) {
      built.push(countFact("central_penetration", "被中央侵入", counts.centralPenetration));
    }
    if (counts.leftConceded > 0) {
      built.push(countFact("left_conceded", "被左侵入", counts.leftConceded));
    }
    if (counts.rightConceded > 0) {
      built.push(countFact("right_conceded", "被右侵入", counts.rightConceded));
    }
    if (counts.crossConceded > 0) {
      built.push(countFact("cross_conceded", "被クロス", counts.crossConceded));
    }
    if (counts.shotConceded > 0) {
      built.push(countFact("shot_conceded", "被シュート", counts.shotConceded));
    }
    if (counts.ballWon > 0) {
      built.push(countFact("ball_won", "ボール奪取", counts.ballWon));
    }

    if (totalPenetration === 0 && counts.ballWon === 0) {
      built.push(countFact("block_not_tested", "守備対応", 0));
    }
    if (totalPenetration > 0 && counts.shotConceded === 0) {
      built.push(thresholdFact("defending_without_shot", "自陣侵入", totalPenetration, ">=", 1));
    }
    if (
      counts.centralPenetration <= 1
      && counts.shotConceded === 0
      && flankPenetration <= 1
      && counts.crossConceded <= 1
    ) {
      built.push(thresholdFact("low_block_working", "ローブロック", counts.centralPenetration, "<=", 1));
    }
    if (counts.shotConceded >= 1) {
      built.push(thresholdFact("shot_conceded_detected", "被シュート", counts.shotConceded, ">=", 1));
    }
    if (counts.centralPenetration >= 2 && counts.shotConceded === 0) {
      built.push(thresholdFact("deep_penetration", "被中央侵入", counts.centralPenetration, ">=", 2));
    }
    if (flankPenetration >= 2 || counts.crossConceded >= 2) {
      built.push(thresholdFact("deep_flank_pressure", "サイド侵入", flankPenetration, ">=", 2));
    }
    if (counts.shotConceded >= 2) {
      built.push(thresholdFact("multiple_shots_conceded", "被シュート", counts.shotConceded, ">=", 2));
    }
    if (counts.centralPenetration >= 5 || (counts.shotConceded >= 1 && counts.centralPenetration >= 2)) {
      built.push(thresholdFact("low_block_breakdown", "ローブロック崩壊", counts.centralPenetration, ">=", 5));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);
    const totalPenetration = getTotalPenetration(counts);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.low_block_working`;
      case "yellow":
        if (totalPenetration >= 1) {
          return `${RULE_ID}.yellow.defending_without_shot`;
        }
        return `${RULE_ID}.yellow.block_not_tested`;
      case "orange":
        if (counts.shotConceded >= 1) {
          return `${RULE_ID}.orange.shot_conceded`;
        }
        return `${RULE_ID}.orange.deep_penetration`;
      case "red":
        if (counts.shotConceded >= 2) {
          return `${RULE_ID}.red.multiple_shots_conceded`;
        }
        return `${RULE_ID}.red.low_block_breakdown`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.low_block_working`:
        return joinSentences([
          prefix,
          "自陣深い位置で守備ブロックを維持し、被シュートを抑えています。",
        ]);

      case `${RULE_ID}.yellow.defending_without_shot`:
        return joinSentences([
          prefix,
          "自陣への侵入はありますが、被シュートは抑えています。",
        ]);

      case `${RULE_ID}.yellow.block_not_tested`:
        return joinSentences([
          prefix,
          "ローブロックで大きな守備対応は記録されていません。",
        ]);

      case `${RULE_ID}.orange.shot_conceded`:
        return joinSentences([
          prefix,
          "被シュートが発生しています。",
        ]);

      case `${RULE_ID}.orange.deep_penetration`:
        return joinSentences([
          prefix,
          "自陣深い位置への侵入を許しています。",
        ]);

      case `${RULE_ID}.red.multiple_shots_conceded`:
        return joinSentences([
          prefix,
          "被シュートが複数回発生しています。",
        ]);

      case `${RULE_ID}.red.low_block_breakdown`:
        return joinSentences([
          prefix,
          "自陣深い位置への侵入が続き、被シュートを許しています。",
        ]);

      default:
        return joinSentences([prefix, "ローブロックに関する観測事実を整理しています。"]);
    }
  }

  window.MO_REASON_ENGINE.registerReasonRule({
    ruleId: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const defensePlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(defensePlan) && defensePlan.includes(PLAN_OPTION);
    },

    buildFacts,
    resolveReasonKey,
    buildSummary,
  });
})();
