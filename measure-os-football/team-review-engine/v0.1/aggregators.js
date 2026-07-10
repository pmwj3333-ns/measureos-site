window.MO_TEAM_REVIEW_AGGREGATORS = (() => {
  function averagePercent(contexts, category, code) {
    const values = contexts
      .map((ctx) => ctx.matchMetrics?.[category]?.find((item) => item.code === code)?.percent)
      .filter((value) => typeof value === "number");
    if (values.length === 0) return 0;
    return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
  }

  function sumCounts(contexts, category, code) {
    return contexts.reduce((sum, ctx) => {
      const item = ctx.matchMetrics?.[category]?.find((entry) => entry.code === code);
      return sum + (item?.count || 0);
    }, 0);
  }

  function buildMetricRows(contexts, category, codes) {
    return codes.map(({ code, label }) => ({
      code,
      label,
      percent: averagePercent(contexts, category, code),
      count: sumCounts(contexts, category, code),
    }));
  }

  function countDefenseEvents(contexts, code) {
    const matcher = window.MO_DEFENSE_OBSERVER?.matchesEventName;
    if (typeof matcher !== "function") return 0;
    return contexts.reduce((sum, ctx) => {
      const events = Array.isArray(ctx.record?.events) ? ctx.record.events : [];
      return sum + events.filter((event) => matcher(event?.eventName, code)).length;
    }, 0);
  }

  function buildDefenseRows(contexts) {
    const definitions = [
      { code: "left", label: "被左" },
      { code: "center", label: "被中央" },
      { code: "right", label: "被右" },
      { code: "behind", label: "被背後" },
    ];
    const total = definitions.reduce((sum, def) => sum + countDefenseEvents(contexts, def.code), 0);
    return definitions.map((def) => {
      const count = countDefenseEvents(contexts, def.code);
      return {
        code: def.code,
        label: def.label,
        count,
        percent: total > 0 ? Math.round((count / total) * 100) : 0,
      };
    });
  }

  function buildTransitionRows(contexts) {
    const definitions = [
      { code: "counter", label: "被カウンター" },
      { code: "counterpress", label: "即時奪回" },
    ];
    const total = definitions.reduce((sum, def) => sum + countDefenseEvents(contexts, def.code), 0);
    return definitions.map((def) => {
      const count = countDefenseEvents(contexts, def.code);
      return {
        code: def.code,
        label: def.label,
        count,
        percent: total > 0 ? Math.round((count / total) * 100) : 0,
      };
    });
  }

  function buildTeamSummary(contexts) {
    const matchCount = contexts.length;
    let wins = 0;
    let goalsFor = 0;
    let goalsAgainst = 0;
    let deviationWarnCount = 0;
    let planChangeCount = 0;
    let reviewCount = 0;

    contexts.forEach((ctx) => {
      const result = window.MO_TEAM_REVIEW_FILTERS?.resolveMatchResult?.(ctx.record);
      if (result === "win") wins += 1;

      const home = Number(ctx.record.match?.home_score) || 0;
      const away = Number(ctx.record.match?.away_score) || 0;
      const isHome = ctx.record.setup?.home_away === "home";
      goalsFor += isHome ? home : away;
      goalsAgainst += isHome ? away : home;

      deviationWarnCount += ctx.deviationWarnCount || 0;
      const historyLen = Array.isArray(ctx.record.match?.planHistory)
        ? ctx.record.match.planHistory.length
        : 0;
      planChangeCount += Math.max(0, historyLen - 1);
      if (ctx.reviewText) reviewCount += 1;
    });

    return {
      matchCount,
      winRate: matchCount > 0 ? Math.round((wins / matchCount) * 100) : 0,
      avgGoalsFor: matchCount > 0 ? (goalsFor / matchCount).toFixed(1) : "0.0",
      avgGoalsAgainst: matchCount > 0 ? (goalsAgainst / matchCount).toFixed(1) : "0.0",
      reviewCount,
      deviationWarnCount,
      planChangeCount,
    };
  }

  function buildAggregations(contexts) {
    return {
      attack: buildMetricRows(contexts, "attack", [
        { code: "left", label: "左侵入" },
        { code: "center", label: "中央侵入" },
        { code: "right", label: "右侵入" },
      ]),
      buildUp: buildMetricRows(contexts, "buildUp", [
        { code: "possession", label: "保持前進" },
        { code: "long", label: "ロング前進" },
      ]),
      finish: buildMetricRows(contexts, "finish", [
        { code: "lost", label: "ロスト" },
        { code: "shot", label: "シュート" },
        { code: "bigChance", label: "決定機" },
      ]),
      defense: buildDefenseRows(contexts),
      transition: buildTransitionRows(contexts),
    };
  }

  function compareAverage(contexts, category, code) {
    if (contexts.length < 2) return 0;
    const sorted = [...contexts].sort((a, b) => {
      const dateA = String(a.record.setup?.match_date || "");
      const dateB = String(b.record.setup?.match_date || "");
      return dateA.localeCompare(dateB);
    });
    const mid = Math.floor(sorted.length / 2);
    const early = sorted.slice(0, mid);
    const late = sorted.slice(mid);
    return averagePercent(late, category, code) - averagePercent(early, category, code);
  }

  function buildTrends(contexts) {
    const trends = [];
    if (contexts.length < 2) return trends;

    const possessionDelta = compareAverage(contexts, "buildUp", "possession");
    const longDelta = compareAverage(contexts, "buildUp", "long");
    const leftDelta = compareAverage(contexts, "attack", "left");
    const centerDelta = compareAverage(contexts, "attack", "center");
    const lostDelta = compareAverage(contexts, "finish", "lost");
    const bigChanceDelta = compareAverage(contexts, "finish", "bigChance");

    if (possessionDelta >= 5) trends.push("保持主体が増えている");
    if (longDelta >= 5) trends.push("ロング前進が増えている");
    if (leftDelta >= 5) trends.push("左侵入の割合が増えている");
    if (leftDelta <= -5) trends.push("左侵入の割合が減っている");
    if (centerDelta >= 5) trends.push("中央侵入の割合が増えている");
    if (centerDelta <= -5 && leftDelta >= 0) trends.push("左優位が継続している");
    if (lostDelta <= -5) trends.push("ロスト率が減少している");
    if (lostDelta >= 5) trends.push("ロスト率が増加している");
    if (bigChanceDelta >= 5) trends.push("決定機まで到達する割合が増えている");
    if (Math.abs(possessionDelta) < 5 && Math.abs(longDelta) < 5 && contexts.length >= 3) {
      trends.push("Build Upの使い分けが安定している");
    }

    return [...new Set(trends)];
  }

  return {
    buildTeamSummary,
    buildAggregations,
    buildTrends,
    averagePercent,
    compareAverage,
  };
})();
