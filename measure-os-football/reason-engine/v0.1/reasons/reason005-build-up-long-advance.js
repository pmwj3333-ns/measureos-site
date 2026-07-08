(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule005";
  const PLAN_CATEGORY_KEY = "buildUp";
  const PLAN_OPTION = "ロング前進";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function getForwardTotal(counts) {
    return counts.leftAdvance + counts.centralAdvance + counts.rightAdvance;
  }

  function getPushedBackTotal(counts) {
    return counts.leftConceded + counts.centralConceded + counts.rightConceded;
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];
    const forward = getForwardTotal(counts);
    const pushedBack = getPushedBackTotal(counts);
    const forwardAdvantage = forward - pushedBack;

    if (counts.leftAdvance > 0) {
      built.push(countFact("left_advance", "左侵入", counts.leftAdvance));
    }
    if (counts.centralAdvance > 0) {
      built.push(countFact("central_advance", "中央侵入", counts.centralAdvance));
    }
    if (counts.rightAdvance > 0) {
      built.push(countFact("right_advance", "右侵入", counts.rightAdvance));
    }
    if (forward > 0) {
      built.push(countFact("long_forward_advance", "ロング前進", forward));
    }
    if (counts.leftConceded > 0) {
      built.push(countFact("left_conceded", "被左侵入", counts.leftConceded));
    }
    if (counts.centralConceded > 0) {
      built.push(countFact("central_conceded", "被中央侵入", counts.centralConceded));
    }
    if (counts.rightConceded > 0) {
      built.push(countFact("right_conceded", "被右侵入", counts.rightConceded));
    }
    if (pushedBack > 0) {
      built.push(countFact("pushed_back", "押し返し", pushedBack));
    }
    if (counts.counterConceded > 0) {
      built.push(countFact("counter_conceded", "被カウンター", counts.counterConceded));
    }
    if (counts.quickRecovery > 0) {
      built.push(countFact("quick_recovery", "即時奪回", counts.quickRecovery));
    }

    if (forward === 0) {
      built.push(countFact("no_long_build_up", "ロング前進", 0));
    }
    if (forward > pushedBack) {
      built.push(thresholdFact("forward_advantage", "前進優位", forwardAdvantage, ">", 0));
    }
    if (
      forward >= 1
      && counts.counterConceded === 0
      && (forward > pushedBack || (forward >= 2 && pushedBack <= 2))
    ) {
      built.push(thresholdFact("long_build_up_progressing", "ロング前進", forward, ">=", 1));
    }
    if (pushedBack >= 2 || counts.counterConceded >= 1) {
      built.push(thresholdFact("long_build_up_under_pressure", "押し返し", pushedBack, ">=", 1));
    }
    if (counts.counterConceded >= 2 || pushedBack >= 5) {
      built.push(thresholdFact("long_build_up_breakdown", "ロング前進崩壊", counts.counterConceded, ">=", 2));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);
    const forward = getForwardTotal(counts);

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.long_build_up_progressing`;
      case "yellow":
        if (forward === 0) {
          return `${RULE_ID}.yellow.no_long_build_up`;
        }
        return `${RULE_ID}.yellow.long_build_up_without_progress`;
      case "orange":
        return `${RULE_ID}.orange.long_build_up_under_pressure`;
      case "red":
        return `${RULE_ID}.red.long_build_up_breakdown`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.long_build_up_progressing`:
        return joinSentences([
          prefix,
          "ロングボールによる前進から、シュートまたは決定機まで到達しています。",
        ]);

      case `${RULE_ID}.yellow.no_long_build_up`:
        return joinSentences([
          prefix,
          "ロングボールによる前進は記録されていません。",
        ]);

      case `${RULE_ID}.yellow.long_build_up_without_progress`:
        return joinSentences([
          prefix,
          "ロングボールによる前進はありますが、シュート・決定機には至っていません。",
        ]);

      case `${RULE_ID}.orange.long_build_up_under_pressure`:
        return joinSentences([
          prefix,
          "ロングボールによる前進中にボールを失う場面が見られます。",
        ]);

      case `${RULE_ID}.red.long_build_up_breakdown`:
        return joinSentences([
          prefix,
          "ロングボールによる前進が成立せず、シュート・決定機には至っていません。",
        ]);

      default:
        return joinSentences([prefix, "ロング前進に関する観測事実を整理しています。"]);
    }
  }

  window.MO_REASON_ENGINE.registerReasonRule({
    ruleId: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const buildUpPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(buildUpPlan) && buildUpPlan.includes(PLAN_OPTION);
    },

    buildFacts,
    resolveReasonKey,
    buildSummary,
  });
})();
