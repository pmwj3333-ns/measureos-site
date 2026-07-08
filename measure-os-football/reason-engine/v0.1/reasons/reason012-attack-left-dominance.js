(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule012";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "左優位";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];
    const finish = counts.cross + counts.shot;

    if (counts.leftAdvance > 0) {
      built.push(countFact("left_advance", "左", counts.leftAdvance));
    }
    if (counts.centralAdvance > 0) {
      built.push(countFact("central_advance", "中央", counts.centralAdvance));
    }
    if (counts.rightAdvance > 0) {
      built.push(countFact("right_advance", "右", counts.rightAdvance));
    }
    if (counts.cross > 0) {
      built.push(countFact("cross_created", "クロス", counts.cross));
    }
    if (counts.shot > 0) {
      built.push(countFact("shot_created", "シュート", counts.shot));
    }
    if (counts.counterConceded > 0) {
      built.push(countFact("counter_conceded", "被カウンター", counts.counterConceded));
    }

    if (finish > 0) {
      built.push(thresholdFact("finish_reached", "フィニッシュ", finish, ">=", 1));
    }
    if (
      counts.leftAdvance > counts.centralAdvance
      && counts.leftAdvance > counts.rightAdvance
    ) {
      built.push(thresholdFact(
        "left_dominant",
        "左優位",
        counts.leftAdvance,
        ">",
        Math.max(counts.centralAdvance, counts.rightAdvance),
      ));
    }
    if (counts.leftAdvance === 0) {
      built.push(countFact("no_left_advance", "左", 0));
    }
    if (counts.leftAdvance === counts.centralAdvance && counts.leftAdvance > 0) {
      built.push(thresholdFact(
        "left_tied_central",
        "左・中央",
        counts.leftAdvance,
        "=",
        counts.centralAdvance,
      ));
    }
    if (counts.counterConceded >= 2) {
      built.push(thresholdFact("counter_collapse", "被カウンター", counts.counterConceded, ">=", 2));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);
    const finish = counts.cross + counts.shot;

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.left_to_finish`;
      case "yellow":
        if (counts.leftAdvance === 0) {
          return `${RULE_ID}.yellow.no_left_advance`;
        }
        if (counts.leftAdvance === counts.centralAdvance) {
          return `${RULE_ID}.yellow.left_tied_with_central`;
        }
        if (
          counts.leftAdvance > counts.centralAdvance
          && counts.leftAdvance > counts.rightAdvance
          && finish === 0
        ) {
          return `${RULE_ID}.yellow.left_without_finish`;
        }
        return `${RULE_ID}.yellow.left_without_finish`;
      case "orange":
        return `${RULE_ID}.orange.single_counter`;
      case "red":
        if (counts.counterConceded >= 2) {
          return `${RULE_ID}.red.counter_collapse`;
        }
        return `${RULE_ID}.red.counter_without_left`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.left_to_finish`:
        return joinSentences([
          prefix,
          "左からの攻撃が優勢で、シュートまたは決定機まで到達しています。",
        ]);

      case `${RULE_ID}.yellow.no_left_advance`:
        return joinSentences([
          prefix,
          "左からの攻撃は記録されていません。",
        ]);

      case `${RULE_ID}.yellow.left_tied_with_central`:
        return joinSentences([
          prefix,
          "左と中央から同程度の攻撃が行われています。",
        ]);

      case `${RULE_ID}.yellow.left_without_finish`:
        return joinSentences([
          prefix,
          "左から攻撃していますが、シュート・決定機には至っていません。",
        ]);

      case `${RULE_ID}.orange.single_counter`:
        return joinSentences([
          prefix,
          "左からの攻撃中に被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_without_left`:
        return joinSentences([
          prefix,
          "左からの攻撃はなく、被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_collapse`:
        return joinSentences([
          prefix,
          "被カウンターが複数回発生しています。",
        ]);

      default:
        return joinSentences([prefix, "左優位に関する観測事実を整理しています。"]);
    }
  }

  window.MO_REASON_ENGINE.registerReasonRule({
    ruleId: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const attackPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(attackPlan) && attackPlan.includes(PLAN_OPTION);
    },

    buildFacts,
    resolveReasonKey,
    buildSummary,
  });
})();
