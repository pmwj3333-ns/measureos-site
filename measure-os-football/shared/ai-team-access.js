window.MO_AI_TEAM_ACCESS = (() => {
  /*
   * Team AI data access — scoped to the logged-in team only.
   * Dummy implementation for future Team AI features (trends, reviews, advice).
   */

  function listRecordsForActiveTeam() {
    const teamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
    if (!teamId) return [];
    return window.MO_REVIEW_ARCHIVE?.listByTeamId?.(teamId) || [];
  }

  function buildDummyTeamSummary(records) {
    const totalMatches = records.length;
    const totalEvents = records.reduce(
      (sum, record) => sum + (Array.isArray(record.events) ? record.events.length : 0),
      0,
    );
    return {
      totalMatches,
      totalEvents,
      averageEventsPerMatch: totalMatches > 0 ? Math.round(totalEvents / totalMatches) : 0,
      note: "Dummy Team AI summary — replace with real analysis later.",
    };
  }

  function getActiveTeamDataset() {
    const teamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
    if (!teamId) {
      return { teamId: null, records: [], summary: null };
    }

    const records = listRecordsForActiveTeam();
    return {
      teamId,
      teamName: window.MO_TEAM_CONTEXT?.getActiveTeamName?.() || "",
      records,
      summary: buildDummyTeamSummary(records),
    };
  }

  return {
    listRecordsForActiveTeam,
    getActiveTeamDataset,
    buildDummyTeamSummary,
  };
})();
