(function () {
  // Reason Engine 設計思想:
  //
  // Reason Engine の中心データは Fact です。
  //
  // summary は Fact を UI 向けに自然言語化した表示形式の一つであり、唯一の正解ではありません。
  //
  // 将来的には、
  // ・Review は Fact を直接利用
  // ・Suggestion Engine は Fact と reasonKey を利用
  // ・AI Coach は Fact を入力として文章生成
  //
  // できる構造を前提とします。
  //
  // そのため Reason Engine は Fact を最も重要な出力とし、summary は Fact の派生データとして扱います。
  //
  // 処理順: buildFacts() → resolveReasonKey() → buildSummary()
  // State Engine の結果（status / reasonEventCounts）を信頼し、State は再判定しません。
  const reasonRules = [];

  function registerReasonRule(rule) {
    if (!rule?.ruleId) return;
    reasonRules.push(rule);
  }

  function findReasonRule(ruleId) {
    return reasonRules.find((rule) => rule.ruleId === ruleId) || null;
  }

  function explainState({ plan, state, context = {} }) {
    if (!state?.ruleId || !state?.status) return null;

    const rule = findReasonRule(state.ruleId);
    if (!rule) return null;

    if (typeof rule.isEnabled === "function" && !rule.isEnabled(plan)) {
      return null;
    }

    const facts = typeof rule.buildFacts === "function"
      ? rule.buildFacts(state, plan, context)
      : [];

    const reasonKey = typeof rule.resolveReasonKey === "function"
      ? rule.resolveReasonKey(state, facts, plan, context)
      : `${state.ruleId}.${state.status}.unknown`;

    // summary は facts / reasonKey から生成する派生データ（UI 表示用）
    const summary = typeof rule.buildSummary === "function"
      ? rule.buildSummary(reasonKey, facts, state, plan, context)
      : "";

    return {
      ruleId: state.ruleId,
      status: state.status,
      reasonKey,
      facts: Array.isArray(facts) ? facts : [],
      summary,
      evaluationWindowMinutes: state.evaluationWindowMinutes ?? 5,
    };
  }

  function explainLiveState({ plan, stateResults, context = {} }) {
    const states = Array.isArray(stateResults) ? stateResults : [];
    return states
      .map((state) => explainState({ plan, state, context }))
      .filter(Boolean);
  }

  window.MO_REASON_ENGINE = {
    registerReasonRule,
    findReasonRule,
    explainState,
    explainLiveState,
  };
})();
