window.MO_TEAM_REVIEW_ENGINE = (() => {
  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return minutes * 60 + seconds;
  }

  function resolveRecordElapsed(record) {
    const events = Array.isArray(record?.events) ? record.events : [];
    const lastEvent = events[events.length - 1];
    if (lastEvent?.time) return parseMatchTime(lastEvent.time);
    const history = Array.isArray(record?.match?.planHistory) ? record.match.planHistory : [];
    const lastEntry = history[history.length - 1];
    return parseMatchTime(lastEntry?.matchTime);
  }

  function buildRecordContext(record) {
    const events = Array.isArray(record.events) ? record.events : [];
    const plan = window.MO_TEAM_REVIEW_FILTERS?.getLastPlan?.(record) || null;
    const matchMetrics = window.MO_MATCH_METRICS?.aggregate?.(events) || {
      attack: [],
      buildUp: [],
      finish: [],
    };

    const review = window.MO_REVIEW_ENGINE?.generateReview?.({ plan, events }) || { sections: [] };
    const attackSection = (review.sections || []).find((section) => section.key === "attack");
    const reviewText = attackSection?.narrative || "";

    const defenseSection = (review.sections || []).find((section) => section.key === "defense");
    const fullReviewText = [reviewText, defenseSection?.narrative || ""]
      .filter(Boolean)
      .join("\n\n");

    const deviationSegments = window.MO_REVIEW_DEVIATION?.buildDeviationsFromRecord?.(record) || [];
    let deviationWarnCount = 0;
    deviationSegments.forEach((segment) => {
      (segment.deviations || []).forEach((item) => {
        if (item.status === "warn") deviationWarnCount += 1;
      });
    });

    const stateResults = window.MO_STATE_ENGINE?.evaluateLiveState?.({
      plan,
      events,
      elapsed: resolveRecordElapsed(record),
    }) || [];

    return {
      record,
      plan,
      matchMetrics,
      reviewText: fullReviewText,
      stateResults,
      deviationSegments,
      deviationWarnCount,
      hasDeviationWarn: deviationWarnCount > 0,
      hasAttackStateDrift: deviationSegments.some((segment) =>
        (segment.categories || []).some((category) =>
          category.key === "attack" && category.deviation?.status === "warn",
        ),
      ),
      matchResult: window.MO_TEAM_REVIEW_FILTERS?.resolveMatchResult?.(record) || "draw",
    };
  }

  function buildContextMap(records) {
    const map = {};
    (Array.isArray(records) ? records : []).forEach((record) => {
      map[record.id] = buildRecordContext(record);
    });
    return map;
  }

  function sortRecordsNewestFirst(records) {
    return [...records].sort((a, b) => {
      const dateA = String(a.setup?.match_date || "");
      const dateB = String(b.setup?.match_date || "");
      if (dateA !== dateB) return dateB.localeCompare(dateA);
      return String(b.archived_at || "").localeCompare(String(a.archived_at || ""));
    });
  }

  function buildTeamReview({ records, filters }) {
    const contextMap = buildContextMap(records);
    const filteredRecords = window.MO_TEAM_REVIEW_FILTERS?.applyFilters?.(
      records,
      filters,
      contextMap,
    ) || [];
    const contexts = filteredRecords.map((record) => contextMap[record.id]).filter(Boolean);
    const sortedRecords = sortRecordsNewestFirst(filteredRecords);

    const reviewHistory = sortedRecords.map((record) => {
        const ctx = contextMap[record.id];
        return {
          id: record.id,
          matchDate: record.setup?.match_date || "",
          opponent: record.setup?.opponent || "対戦相手",
          competition: record.setup?.competition || "",
          reviewText: ctx?.reviewText || "",
          hasDeviationWarn: Boolean(ctx?.hasDeviationWarn),
          deviationWarnCount: ctx?.deviationWarnCount || 0,
          matchResult: ctx?.matchResult || "draw",
        };
      });

    const reviewQuery = filters?.reviewFullText || filters?.reviewKeyword || "";

    return {
      filters: filters || {},
      matchCount: filteredRecords.length,
      trends: window.MO_TEAM_REVIEW_AGGREGATORS?.buildTrends?.(contexts) || [],
      stateTimeline: window.MO_TEAM_REVIEW_STATE_TIMELINE?.buildStateTimeline?.(
        filteredRecords,
        contextMap,
      ) || { categories: [] },
      teamLearn: window.MO_TEAM_REVIEW_TEAM_LEARN?.buildTeamLearn?.(contexts) || [],
      reviewSearchResults: window.MO_TEAM_REVIEW_SEARCH?.buildReviewSearchResults?.(
        reviewHistory,
        reviewQuery,
      ) || [],
      summary: window.MO_TEAM_REVIEW_AGGREGATORS?.buildTeamSummary?.(contexts) || {},
      aggregations: window.MO_TEAM_REVIEW_AGGREGATORS?.buildAggregations?.(contexts) || {},
      reviewHistory,
      matches: sortedRecords.map((record) => {
        const ctx = contextMap[record.id];
        const home = Number(record.match?.home_score) || 0;
        const away = Number(record.match?.away_score) || 0;
        return {
          id: record.id,
          matchDate: record.setup?.match_date || "",
          opponent: record.setup?.opponent || "対戦相手",
          competition: record.setup?.competition || "",
          homeAway: record.setup?.home_away || "",
          scoreLabel: `Home ${home} - ${away} Away`,
          matchResult: ctx?.matchResult || "draw",
          hasDeviationWarn: Boolean(ctx?.hasDeviationWarn),
        };
      }),
    };
  }

  function loadTeamRecords(teamId) {
    window.MO_REVIEW_ARCHIVE?.upsertFromLiveStorage?.();
    const records = window.MO_REVIEW_ARCHIVE?.search?.({ teamId }) || [];
    return records.filter((record) => window.MO_TEAM_CONTEXT?.canAccessTeamResource?.(record));
  }

  return {
    buildRecordContext,
    buildTeamReview,
    loadTeamRecords,
    sortRecordsNewestFirst,
  };
})();
