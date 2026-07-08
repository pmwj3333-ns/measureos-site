(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule016";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ミドルブロック";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function isCentralSoleMost(counts) {
    return counts.centralPenetration > 0
      && counts.centralPenetration > counts.leftConceded
      && counts.centralPenetration > counts.rightConceded;
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];

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
    if (counts.frontLineRecovery > 0) {
      built.push(countFact("front_line_recovery", "前線奪取", counts.frontLineRecovery));
    }

    if (counts.ballWon === 0 && counts.frontLineRecovery === 0) {
      built.push(countFact("block_not_tested", "守備対応", 0));
    }
    if (isCentralSoleMost(counts)) {
      built.push(thresholdFact("central_sole_most", "被中央侵入", counts.centralPenetration, ">", Math.max(counts.leftConceded, counts.rightConceded)));
    }
    if (counts.centralPenetration > 0 && counts.shotConceded === 0) {
      built.push(thresholdFact("controlled_penetration", "被中央侵入", counts.centralPenetration, ">=", 1));
    }
    if (
      counts.shotConceded === 0
      && (counts.ballWon >= 1 || counts.frontLineRecovery >= 1)
      && !isCentralSoleMost(counts)
    ) {
      built.push(thresholdFact("middle_block_working", "ミドルブロック", counts.ballWon + counts.frontLineRecovery, ">=", 1));
    }
    if (counts.shotConceded >= 1) {
      built.push(thresholdFact("shot_conceded_detected", "被シュート", counts.shotConceded, ">=", 1));
    }
    if (counts.shotConceded >= 2) {
      built.push(thresholdFact("multiple_shots_conceded", "被シュート", counts.shotConceded, ">=", 2));
    }
    if (isCentralSoleMost(counts) && counts.shotConceded === 0) {
      built.push(thresholdFact("middle_space_exposed", "ミドルゾーン", counts.centralPenetration, ">=", 1));
    }
    if (counts.shotConceded >= 2 || (isCentralSoleMost(counts) && counts.centralPenetration >= 3)) {
      built.push(thresholdFact("middle_block_breakdown", "ミドルブロック崩壊", counts.centralPenetration, ">=", 1));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.middle_block_working`;
      case "yellow":
        if (isCentralSoleMost(counts)) {
          return `${RULE_ID}.yellow.controlled_penetration`;
        }
        if (counts.ballWon === 0 && counts.frontLineRecovery === 0) {
          if (counts.centralPenetration >= 1) {
            return `${RULE_ID}.yellow.controlled_penetration`;
          }
          return `${RULE_ID}.yellow.block_not_tested`;
        }
        return `${RULE_ID}.yellow.controlled_penetration`;
      case "orange":
        if (counts.shotConceded >= 1) {
          return `${RULE_ID}.orange.shot_conceded`;
        }
        return `${RULE_ID}.orange.middle_space_exposed`;
      case "red":
        if (counts.shotConceded >= 2) {
          return `${RULE_ID}.red.multiple_shots_conceded`;
        }
        return `${RULE_ID}.red.middle_block_breakdown`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.middle_block_working`:
        return joinSentences([
          prefix,
          "ミドルゾーンで相手の前進を抑えています。",
        ]);

      case `${RULE_ID}.yellow.controlled_penetration`:
        return joinSentences([
          prefix,
          "中央への侵入はありますが、被シュートは抑えています。",
        ]);

      case `${RULE_ID}.yellow.block_not_tested`:
        return joinSentences([
          prefix,
          "ミドルゾーンで大きな守備対応は記録されていません。",
        ]);

      case `${RULE_ID}.orange.shot_conceded`:
        return joinSentences([
          prefix,
          "被シュートが発生しています。",
        ]);

      case `${RULE_ID}.orange.middle_space_exposed`:
        return joinSentences([
          prefix,
          "ミドルゾーンから前進を許しています。",
        ]);

      case `${RULE_ID}.red.multiple_shots_conceded`:
        return joinSentences([
          prefix,
          "被シュートが複数回発生しています。",
        ]);

      case `${RULE_ID}.red.middle_block_breakdown`:
        return joinSentences([
          prefix,
          "ミドルゾーンから継続して前進を許しています。",
        ]);

      default:
        return joinSentences([prefix, "ミドルブロックに関する観測事実を整理しています。"]);
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
