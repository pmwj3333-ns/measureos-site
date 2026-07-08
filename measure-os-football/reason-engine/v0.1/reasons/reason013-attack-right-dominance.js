(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule013";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "右優位";

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

    if (counts.rightAdvance > 0) {
      built.push(countFact("right_advance", "右", counts.rightAdvance));
    }
    if (counts.centralAdvance > 0) {
      built.push(countFact("central_advance", "中央", counts.centralAdvance));
    }
    if (counts.leftAdvance > 0) {
      built.push(countFact("left_advance", "左", counts.leftAdvance));
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
      counts.rightAdvance > counts.leftAdvance
      && counts.rightAdvance > counts.centralAdvance
    ) {
      built.push(thresholdFact(
        "right_dominant",
        "右優位",
        counts.rightAdvance,
        ">",
        Math.max(counts.leftAdvance, counts.centralAdvance),
      ));
    }
    if (counts.rightAdvance === 0) {
      built.push(countFact("no_right_advance", "右", 0));
    }
    if (counts.rightAdvance === counts.centralAdvance && counts.rightAdvance > 0) {
      built.push(thresholdFact(
        "right_tied_central",
        "右・中央",
        counts.rightAdvance,
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
        return `${RULE_ID}.green.right_to_finish`;
      case "yellow":
        if (counts.rightAdvance === 0) {
          return `${RULE_ID}.yellow.no_right_advance`;
        }
        if (counts.rightAdvance === counts.centralAdvance) {
          return `${RULE_ID}.yellow.right_tied_with_central`;
        }
        if (
          counts.rightAdvance > counts.leftAdvance
          && counts.rightAdvance > counts.centralAdvance
          && finish === 0
        ) {
          return `${RULE_ID}.yellow.right_without_finish`;
        }
        return `${RULE_ID}.yellow.right_without_finish`;
      case "orange":
        return `${RULE_ID}.orange.single_counter`;
      case "red":
        if (counts.counterConceded >= 2) {
          return `${RULE_ID}.red.counter_collapse`;
        }
        return `${RULE_ID}.red.counter_without_right`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.right_to_finish`:
        return joinSentences([
          prefix,
          "右からの攻撃が優勢で、シュートまたは決定機まで到達しています。",
        ]);

      case `${RULE_ID}.yellow.no_right_advance`:
        return joinSentences([
          prefix,
          "右からの攻撃は記録されていません。",
        ]);

      case `${RULE_ID}.yellow.right_tied_with_central`:
        return joinSentences([
          prefix,
          "右と中央から同程度の攻撃が行われています。",
        ]);

      case `${RULE_ID}.yellow.right_without_finish`:
        return joinSentences([
          prefix,
          "右から攻撃していますが、シュート・決定機には至っていません。",
        ]);

      case `${RULE_ID}.orange.single_counter`:
        return joinSentences([
          prefix,
          "右からの攻撃中に被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_without_right`:
        return joinSentences([
          prefix,
          "右からの攻撃はなく、被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_collapse`:
        return joinSentences([
          prefix,
          "被カウンターが複数回発生しています。",
        ]);

      default:
        return joinSentences([prefix, "右優位に関する観測事実を整理しています。"]);
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
