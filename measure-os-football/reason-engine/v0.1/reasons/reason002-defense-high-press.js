(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule002";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ハイプレス";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];

    if (counts.frontLineRecovery > 0) {
      built.push(countFact("front_line_recovery", "前線奪取", counts.frontLineRecovery));
    }
    if (counts.centralPenetration > 0) {
      built.push(countFact("central_penetration", "被中央侵入", counts.centralPenetration));
    }
    if (counts.shotConceded > 0) {
      built.push(countFact("shot_conceded", "被シュート", counts.shotConceded));
    }

    if (counts.frontLineRecovery === 0) {
      built.push(countFact("no_front_line_recovery", "前線奪取", 0));
    }
    if (counts.frontLineRecovery === 1) {
      built.push(thresholdFact("limited_front_recovery", "前線奪取", counts.frontLineRecovery, "=", 1));
    }
    if (counts.frontLineRecovery >= 2) {
      built.push(thresholdFact("front_line_volume", "前線奪取", counts.frontLineRecovery, ">=", 2));
    }
    if (counts.centralPenetration === 2) {
      built.push(thresholdFact("moderate_central_penetration", "被中央侵入", counts.centralPenetration, "=", 2));
    }
    if (counts.centralPenetration >= 3) {
      built.push(thresholdFact("central_penetration_high", "被中央侵入", counts.centralPenetration, ">=", 3));
    }
    if (counts.centralPenetration >= 5) {
      built.push(thresholdFact("excessive_central_penetration", "被中央侵入", counts.centralPenetration, ">=", 5));
    }
    if (counts.shotConceded >= 1) {
      built.push(thresholdFact("shot_conceded_detected", "被シュート", counts.shotConceded, ">=", 1));
    }
    if (counts.shotConceded >= 2) {
      built.push(thresholdFact("multiple_shots_conceded", "被シュート", counts.shotConceded, ">=", 2));
    }
    if (
      counts.frontLineRecovery >= 2
      && counts.centralPenetration <= 1
      && counts.shotConceded === 0
    ) {
      built.push(thresholdFact("press_working", "ハイプレス", counts.frontLineRecovery, ">=", 2));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.press_working`;
      case "yellow":
        if (counts.frontLineRecovery === 1) {
          return `${RULE_ID}.yellow.limited_front_recovery`;
        }
        return `${RULE_ID}.yellow.moderate_central_penetration`;
      case "orange":
        if (counts.shotConceded >= 1) {
          return `${RULE_ID}.orange.shot_conceded`;
        }
        return `${RULE_ID}.orange.central_penetration_high`;
      case "red":
        if (counts.shotConceded >= 2) {
          return `${RULE_ID}.red.multiple_shots_conceded`;
        }
        return `${RULE_ID}.red.excessive_central_penetration`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.press_working`:
        return joinSentences([
          prefix,
          "前線でボールを奪い、被中央侵入・被シュートを抑えています。",
        ]);

      case `${RULE_ID}.yellow.limited_front_recovery`:
        return joinSentences([
          prefix,
          "前線でのボール奪取は限定的です。",
        ]);

      case `${RULE_ID}.yellow.moderate_central_penetration`:
        return joinSentences([
          prefix,
          "中央への侵入を許していますが、被シュートは抑えています。",
        ]);

      case `${RULE_ID}.orange.shot_conceded`:
        return joinSentences([
          prefix,
          "被シュートが発生しています。",
        ]);

      case `${RULE_ID}.orange.central_penetration_high`:
        return joinSentences([
          prefix,
          "中央への侵入を複数回許しています。",
        ]);

      case `${RULE_ID}.red.multiple_shots_conceded`:
        return joinSentences([
          prefix,
          "被シュートが複数回発生しています。",
        ]);

      case `${RULE_ID}.red.excessive_central_penetration`:
        return joinSentences([
          prefix,
          "中央への侵入を継続して許しています。",
        ]);

      default:
        return joinSentences([prefix, "ハイプレスに関する観測事実を整理しています。"]);
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
