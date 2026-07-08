window.MO_AI_GLOBAL_ACCESS = (() => {
  /*
   * Global AI data access — anonymized cross-team statistics only.
   * Dummy implementation for future MEASURE OS Global AI (league trends, benchmarks).
   * Must not expose team-confidential identifiers.
   */

  function anonymizeRecord(record) {
    if (!record || typeof record !== "object") return null;
    const setup = record.setup || {};
    return {
      matchRef: record.matchId || setup.match_id || record.id || null,
      matchDate: setup.match_date || null,
      opponentHash: setup.opponent ? `opponent-${String(setup.opponent).length}` : null,
      competitionCategory: setup.competition ? "competition" : "unspecified",
      homeScore: record.match?.home_score ?? null,
      awayScore: record.match?.away_score ?? null,
      eventCount: Array.isArray(record.events) ? record.events.length : 0,
      archivedAt: record.archived_at || null,
    };
  }

  function listAnonymizedRecords() {
    return (window.MO_REVIEW_ARCHIVE?.loadArchive?.() || [])
      .map((record) => anonymizeRecord(record))
      .filter(Boolean);
  }

  function buildDummyGlobalStats(records) {
    const totalTeams = new Set(
      (window.MO_REVIEW_ARCHIVE?.loadArchive?.() || [])
        .map((record) => window.MO_MATCH_CONTEXT?.resolveTeamId?.(record))
        .filter(Boolean),
    ).size;

    return {
      totalAnonymizedMatches: records.length,
      estimatedTeamCount: totalTeams,
      averageEventsPerMatch: records.length > 0
        ? Math.round(
          records.reduce((sum, record) => sum + (record.eventCount || 0), 0) / records.length,
        )
        : 0,
      note: "Dummy Global AI stats — replace with real aggregation later.",
    };
  }

  function getGlobalDataset() {
    const records = listAnonymizedRecords();
    return {
      records,
      stats: buildDummyGlobalStats(records),
    };
  }

  return {
    anonymizeRecord,
    listAnonymizedRecords,
    getGlobalDataset,
    buildDummyGlobalStats,
  };
})();
