(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule014";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "中央攻略";

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
    const sideAdvance = Math.max(counts.leftAdvance, counts.rightAdvance);

    if (counts.centralAdvance > 0) {
      built.push(countFact("central_advance", "中央", counts.centralAdvance));
    }
    if (counts.leftAdvance > 0) {
      built.push(countFact("left_advance", "左", counts.leftAdvance));
    }
    if (counts.rightAdvance > 0) {
      built.push(countFact("right_advance", "右", counts.rightAdvance));
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
      counts.centralAdvance > counts.leftAdvance
      && counts.centralAdvance > counts.rightAdvance
    ) {
      built.push(thresholdFact(
        "central_dominant",
        "中央攻略",
        counts.centralAdvance,
        ">",
        sideAdvance,
      ));
    }
    if (counts.centralAdvance === 0) {
      built.push(countFact("no_central_advance", "中央", 0));
    }
    if (
      (counts.centralAdvance === counts.leftAdvance && counts.centralAdvance > 0)
      || (counts.centralAdvance === counts.rightAdvance && counts.centralAdvance > 0)
    ) {
      built.push(thresholdFact(
        "central_tied_side",
        "中央・サイド",
        counts.centralAdvance,
        "=",
        sideAdvance,
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
        return `${RULE_ID}.green.central_to_finish`;
      case "yellow":
        if (counts.centralAdvance === 0) {
          return `${RULE_ID}.yellow.no_central_attack`;
        }
        if (
          counts.centralAdvance === counts.leftAdvance
          || counts.centralAdvance === counts.rightAdvance
        ) {
          return `${RULE_ID}.yellow.central_tied_with_side`;
        }
        if (
          counts.centralAdvance > counts.leftAdvance
          && counts.centralAdvance > counts.rightAdvance
          && finish === 0
        ) {
          return `${RULE_ID}.yellow.central_without_finish`;
        }
        return `${RULE_ID}.yellow.central_without_finish`;
      case "orange":
        return `${RULE_ID}.orange.single_counter`;
      case "red":
        if (counts.counterConceded >= 2) {
          return `${RULE_ID}.red.counter_collapse`;
        }
        return `${RULE_ID}.red.counter_without_central`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);

    switch (reasonKey) {
      case `${RULE_ID}.green.central_to_finish`:
        return joinSentences([
          prefix,
          "中央からの攻撃が優勢で、シュートまたは決定機まで到達しています。",
        ]);

      case `${RULE_ID}.yellow.no_central_attack`:
        return joinSentences([
          prefix,
          "中央からの攻撃は記録されていません。",
        ]);

      case `${RULE_ID}.yellow.central_tied_with_side`:
        return joinSentences([
          prefix,
          "中央とサイドから同程度の攻撃が行われています。",
        ]);

      case `${RULE_ID}.yellow.central_without_finish`:
        return joinSentences([
          prefix,
          "中央から攻撃していますが、シュート・決定機には至っていません。",
        ]);

      case `${RULE_ID}.orange.single_counter`:
        return joinSentences([
          prefix,
          "中央からの攻撃中に被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_without_central`:
        return joinSentences([
          prefix,
          "中央からの攻撃はなく、被カウンターを受けています。",
        ]);

      case `${RULE_ID}.red.counter_collapse`:
        return joinSentences([
          prefix,
          "被カウンターが複数回発生しています。",
        ]);

      default:
        return joinSentences([prefix, "中央攻略に関する観測事実を整理しています。"]);
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
