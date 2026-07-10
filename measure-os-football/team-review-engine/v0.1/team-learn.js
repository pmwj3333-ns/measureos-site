window.MO_TEAM_REVIEW_TEAM_LEARN = (() => {
  function sortChronological(contexts) {
    return [...contexts].sort((a, b) => {
      const dateA = String(a.record.setup?.match_date || "");
      const dateB = String(b.record.setup?.match_date || "");
      if (dateA !== dateB) return dateA.localeCompare(dateB);
      return String(a.record.archived_at || "").localeCompare(String(b.record.archived_at || ""));
    });
  }

  function getPlanLabel(plan, key) {
    return window.MO_TEAM_REVIEW_FILTERS?.getPlanLabel?.(plan, key) || "";
  }

  function metricPercent(ctx, category, code) {
    const item = ctx.matchMetrics?.[category]?.find((entry) => entry.code === code);
    return item?.percent ?? 0;
  }

  function countRecentPlanStreak(contexts, planKey, planLabel) {
    const sorted = sortChronological(contexts);
    let streak = 0;
    for (let index = sorted.length - 1; index >= 0; index -= 1) {
      if (getPlanLabel(sorted[index].plan, planKey) === planLabel) {
        streak += 1;
      } else {
        break;
      }
    }
    return streak;
  }

  function countAlignedPlanMatches(contexts, planKey, planLabel) {
    return contexts.filter((ctx) => {
      if (getPlanLabel(ctx.plan, planKey) !== planLabel) return false;
      return !(ctx.deviationSegments || []).some((segment) =>
        (segment.categories || []).some((category) =>
          category.key === planKey && category.deviation?.status === "warn",
        ),
      );
    }).length;
  }

  function buildTeamLearn(contexts) {
    const learns = [];
    if (!Array.isArray(contexts) || contexts.length === 0) return learns;

    const leftStreak = countRecentPlanStreak(contexts, "attack", "左優位");
    if (leftStreak >= 3) {
      learns.push(`左優位は${leftStreak}試合継続`);
    }

    const possessionDominantCount = contexts.filter((ctx) => {
      const possession = metricPercent(ctx, "buildUp", "possession");
      const long = metricPercent(ctx, "buildUp", "long");
      return possession >= 55 && possession > long;
    }).length;

    if (contexts.length >= 3 && possessionDominantCount / contexts.length >= 0.6) {
      learns.push("保持主体が定着している");
    }

    const centerPlanMatches = contexts.filter((ctx) => getPlanLabel(ctx.plan, "attack") === "中央攻略");
    if (centerPlanMatches.length >= 3) {
      const aligned = countAlignedPlanMatches(contexts, "attack", "中央攻略");
      const recent = sortChronological(centerPlanMatches).slice(-3);
      const recentAligned = recent.filter((ctx) =>
        !(ctx.deviationSegments || []).some((segment) =>
          (segment.categories || []).some((category) =>
            category.key === "attack" && category.deviation?.status === "warn",
          ),
        ),
      ).length;
      if (recentAligned >= 2 && aligned >= Math.ceil(centerPlanMatches.length * 0.5)) {
        learns.push("中央攻略のPlan維持が改善傾向");
      }
    }

    const lostDelta = window.MO_TEAM_REVIEW_AGGREGATORS?.compareAverage?.(contexts, "finish", "lost");
    if (typeof lostDelta === "number" && lostDelta <= -5) {
      learns.push("ロスト率は減少傾向");
    }

    const buildUpStable = contexts.length >= 4
      && Math.abs(window.MO_TEAM_REVIEW_AGGREGATORS?.compareAverage?.(contexts, "buildUp", "possession") || 0) < 5
      && Math.abs(window.MO_TEAM_REVIEW_AGGREGATORS?.compareAverage?.(contexts, "buildUp", "long") || 0) < 5;
    if (buildUpStable) {
      learns.push("Build Upの使い分けが安定している");
    }

    const rightStreak = countRecentPlanStreak(contexts, "attack", "右優位");
    if (rightStreak >= 3) {
      learns.push(`右優位は${rightStreak}試合継続`);
    }

    return [...new Set(learns)];
  }

  return {
    buildTeamLearn,
  };
})();
