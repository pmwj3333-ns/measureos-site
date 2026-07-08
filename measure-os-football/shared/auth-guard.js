window.MO_AUTH_GUARD = (() => {
  function requireAuth() {
    return window.MO_TEAM_CONTEXT?.ensureAuthenticatedTeamPage?.() ?? false;
  }

  return { requireAuth };
})();
