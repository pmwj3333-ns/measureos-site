(function () {
  // Reason Rule: buildFacts() が主処理、buildSummary() は Fact の派生データ（UI 表示用）
  const RULE_ID = "rule018";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "背後攻略";

  const vocab = () => window.MO_REASON_EVENT_VOCABULARY;
  const facts = () => window.MO_REASON_FACT_BUILDER;

  function normalizeCounts(state) {
    return vocab()?.normalizeReasonEventCounts(state?.reasonEventCounts, RULE_ID) || {};
  }

  function buildFacts(state) {
    const counts = normalizeCounts(state);
    const { countFact, thresholdFact } = facts();
    const built = [];

    if (counts.behind > 0) {
      built.push(countFact("behind_detected", "背後侵入", counts.behind));
    }
    if (counts.shot > 0) {
      built.push(countFact("shot_created", "シュート", counts.shot));
    }
    if (counts.bigChance > 0) {
      built.push(countFact("chance_created", "決定機", counts.bigChance));
    }
    if (counts.counter > 0) {
      built.push(countFact("counter_conceded", "被カウンター", counts.counter));
    }

    const finish = counts.shot + counts.bigChance;
    const total = counts.behind + finish + counts.counter;

    if (finish > 0) {
      built.push(thresholdFact("finish_reached", "フィニッシュ", finish, ">=", 1));
    }
    if (counts.behind >= 2) {
      built.push(thresholdFact("behind_volume", "背後侵入", counts.behind, ">=", 2));
    }
    if (total === 0) {
      built.push(countFact("no_relevant_activity", "関連イベント", 0));
    }

    return built;
  }

  function resolveReasonKey(state) {
    const counts = normalizeCounts(state);
    const finish = counts.shot + counts.bigChance;

    switch (state.status) {
      case "green":
        return `${RULE_ID}.green.behind_to_finish`;
      case "yellow":
        if (counts.behind === 0 && finish === 0 && counts.counter === 0) {
          return `${RULE_ID}.yellow.no_activity`;
        }
        return `${RULE_ID}.yellow.no_finish_yet`;
      case "orange":
        if (counts.counter === 1) {
          return `${RULE_ID}.orange.single_counter`;
        }
        return `${RULE_ID}.orange.alternative_route`;
      case "red":
        if (counts.counter >= 2) {
          return `${RULE_ID}.red.counter_collapse`;
        }
        return `${RULE_ID}.red.counter_with_no_behind`;
      default:
        return `${RULE_ID}.${state.status || "unknown"}.unknown`;
    }
  }

  function buildSummary(reasonKey, builtFacts, state) {
    const { windowPrefix, joinSentences } = facts();
    const prefix = windowPrefix(state.evaluationWindowMinutes);
    const counts = normalizeCounts(state);
    const finish = counts.shot + counts.bigChance;

    switch (reasonKey) {
      case `${RULE_ID}.green.behind_to_finish`:
        return joinSentences([
          prefix,
          "背後侵入",
          counts.behind,
          "回からシュートまたは決定機に到達しています。",
          counts.counter > 0 ? `被カウンターは${counts.counter}回です。` : "被カウンターは記録されていません。",
        ]);

      case `${RULE_ID}.yellow.no_finish_yet`:
        return joinSentences([
          prefix,
          "背後侵入",
          counts.behind,
          "回は記録されていますが、シュート・決定機には至っていません。",
        ]);

      case `${RULE_ID}.yellow.no_activity`:
        return joinSentences([
          prefix,
          "背後侵入・シュート・決定機・被カウンターの記録がありません。",
        ]);

      case `${RULE_ID}.orange.alternative_route`:
        return joinSentences([
          prefix,
          "背後侵入の記録はなく、シュート",
          counts.shot,
          "回が記録されています。Game Plan「背後攻略」とは別ルートの攻撃が観測されています。",
        ]);

      case `${RULE_ID}.orange.single_counter`:
        return joinSentences([
          prefix,
          "被カウンター1回が記録されています。",
          counts.behind > 0 ? `背後侵入は${counts.behind}回です。` : "背後侵入の記録はありません。",
        ]);

      case `${RULE_ID}.red.counter_collapse`:
        return joinSentences([
          prefix,
          "被カウンター",
          counts.counter,
          "回が記録されています。",
        ]);

      case `${RULE_ID}.red.counter_with_no_behind`:
        return joinSentences([
          prefix,
          "背後侵入・シュート・決定機の記録がなく、被カウンター",
          counts.counter,
          "回を受けています。",
        ]);

      default:
        return joinSentences([prefix, "背後攻略に関する観測事実を整理しています。"]);
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
