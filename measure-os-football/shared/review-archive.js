window.MO_REVIEW_ARCHIVE = (() => {
  const keys = window.MO_STORAGE_KEYS || {};
  const archiveKey = keys.reviewArchive || "measure-os-football:review-archive:v0.1";
  const setupKey = keys.matchSetup || "measure-os-football:match-setup:v1";
  const matchKey = keys.matchControl || "measure-os-football:match-control:v0.3";
  const eventsKey = keys.observerEvents || "measure-os-football:observer-events:v0.3";

  function loadJson(key) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function saveJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (_) {
      return false;
    }
  }

  function loadArchive() {
    const saved = loadJson(archiveKey);
    return Array.isArray(saved) ? saved : [];
  }

  function saveArchive(records) {
    saveJson(archiveKey, records);
  }

  function resolveRecordTeamId(record) {
    return window.MO_MATCH_CONTEXT?.resolveTeamId?.(record)
      || window.MO_MATCH_CONTEXT?.resolveTeamId?.(record?.setup)
      || record?.teamId
      || record?.setup?.teamId
      || null;
  }

  function resolveRecordMatchId(record, setup, match) {
    return window.MO_MATCH_CONTEXT?.resolveMatchId?.(record)
      || window.MO_MATCH_CONTEXT?.resolveMatchId?.(setup)
      || setup?.match_id
      || match?.match_id
      || record?.matchId
      || null;
  }

  function buildRecordId(setup, match) {
    if (setup?.match_id) return setup.match_id;
    if (match?.kickoff_at) return `kickoff-${match.kickoff_at}`;
    return `review-${Date.now()}`;
  }

  function buildSnapshotFromLiveStorage() {
    const setup = loadJson(setupKey);
    const match = loadJson(matchKey);
    const events = loadJson(eventsKey);

    if (!match || !match.match_phase) return null;
    if (match.match_phase !== "fulltime") return null;

    const activeTeamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.() || null;
    const setupTeamId = setup?.teamId || null;
    if (setupTeamId && activeTeamId && setupTeamId !== activeTeamId) {
      return null;
    }

    const id = buildRecordId(setup, match);
    const existingReasons = loadArchive().find((item) => item.id === id)?.plan_change_reasons;
    const teamId = setup?.teamId || window.MO_TEAM_CONTEXT?.getActiveTeamId?.() || null;
    const matchId = setup?.match_id || id;

    return {
      id,
      matchId,
      teamId,
      archived_at: new Date().toISOString(),
      setup: setup || {
        match_id: id,
        teamId,
        competition: "",
        opponent: "不明",
        match_date: "",
        kickoff_time: "",
        home_away: "",
        formation: "",
        match_created_at: match.kickoff_at || new Date().toISOString(),
      },
      match,
      events: Array.isArray(events) ? events : [],
      plan_change_reasons: Array.isArray(existingReasons) ? existingReasons : [],
    };
  }

  function upsertFromLiveStorage() {
    const snapshot = buildSnapshotFromLiveStorage();
    if (!snapshot) return null;

    const archive = loadArchive();
    const index = archive.findIndex((item) => item.id === snapshot.id);
    if (index >= 0) {
      archive[index] = { ...archive[index], ...snapshot, archived_at: new Date().toISOString() };
    } else {
      archive.unshift(snapshot);
    }
    saveArchive(archive);
    return snapshot;
  }

  function search(filters = {}) {
    const competition = String(filters.competition || "").trim().toLowerCase();
    const opponent = String(filters.opponent || "").trim().toLowerCase();
    const matchDate = String(filters.match_date || "").trim();
    const teamId = String(filters.teamId || "").trim();

    return loadArchive().filter((record) => {
      if (teamId) {
        const recordTeamId = resolveRecordTeamId(record);
        if (recordTeamId !== teamId) return false;
      }

      const setup = record.setup || {};
      if (competition && !String(setup.competition || "").toLowerCase().includes(competition)) {
        return false;
      }
      if (opponent && !String(setup.opponent || "").toLowerCase().includes(opponent)) {
        return false;
      }
      if (matchDate && String(setup.match_date || "") !== matchDate) {
        return false;
      }
      return true;
    });
  }

  function getById(id, teamId = null) {
    const record = loadArchive().find((item) => item.id === id) || null;
    if (!record) return null;
    const recordTeamId = resolveRecordTeamId(record);
    if (teamId && recordTeamId !== teamId) return null;
    return record;
  }

  function existsForAnyTeam(id) {
    return loadArchive().some((item) => item.id === id);
  }

  function listByTeamId(teamId) {
    if (!teamId) return [];
    return search({ teamId });
  }

  return {
    archiveKey,
    setupKey,
    matchKey,
    eventsKey,
    loadArchive,
    saveArchive,
    buildSnapshotFromLiveStorage,
    upsertFromLiveStorage,
    search,
    getById,
    listByTeamId,
    existsForAnyTeam,
    resolveRecordTeamId,
    resolveRecordMatchId,
  };
})();
