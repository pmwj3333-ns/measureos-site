window.MO_MATCH_CONTEXT = (() => {
  const keys = window.MO_STORAGE_KEYS || {};

  function readJson(key) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function removeJson(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (_) {
      // Ignore storage errors in the local prototype.
    }
  }

  function writeJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (_) {
      return false;
    }
  }

  function resolveTeamId(source) {
    if (!source || typeof source !== "object") return null;
    return source.teamId || source.team_id || null;
  }

  function resolveMatchId(source) {
    if (!source || typeof source !== "object") return null;
    return source.matchId || source.match_id || source.id || null;
  }

  function attachTeamId(snapshot, teamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.()) {
    if (!snapshot || typeof snapshot !== "object") return snapshot;
    if (!teamId) return snapshot;
    return {
      ...snapshot,
      teamId,
      match_id: snapshot.match_id || snapshot.matchId || null,
    };
  }

  function canAccessMatch(source) {
    const teamId = resolveTeamId(source);
    const activeTeamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
    if (!activeTeamId) return false;
    if (!teamId) return false;
    return teamId === activeTeamId;
  }

  function buildReviewRecordMeta(setup) {
    const teamId = resolveTeamId(setup) || window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
    const matchId = resolveMatchId(setup);
    return {
      teamId: teamId || null,
      matchId: matchId || null,
    };
  }

  function clearLiveMatchStorage() {
    removeJson(keys.matchSetup || "measure-os-football:match-setup:v1");
    removeJson(keys.matchControl || "measure-os-football:match-control:v0.3");
    removeJson(keys.observerEvents || "measure-os-football:observer-events:v0.3");
    removeJson(keys.plan || "measure-os-football:plan:v0.1");
    removeJson(keys.planReturn || "measure-os-football:plan-return:v0.3");
  }

  function ensureLiveStorageBelongsToActiveTeam() {
    const activeTeamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
    if (!activeTeamId) return false;

    const setupKey = keys.matchSetup || "measure-os-football:match-setup:v1";
    const setup = readJson(setupKey);
    if (!setup) return true;

    const setupTeamId = resolveTeamId(setup);
    if (!setupTeamId) {
      writeJson(setupKey, attachTeamId(setup, activeTeamId));
      return true;
    }
    if (setupTeamId !== activeTeamId) {
      clearLiveMatchStorage();
      return false;
    }

    return true;
  }

  return {
    resolveTeamId,
    resolveMatchId,
    attachTeamId,
    canAccessMatch,
    buildReviewRecordMeta,
    clearLiveMatchStorage,
    ensureLiveStorageBelongsToActiveTeam,
  };
})();
