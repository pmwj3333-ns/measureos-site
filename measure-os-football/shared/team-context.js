window.MO_TEAM_CONTEXT = (() => {
  /*
   * Single source of truth for active Team / User context.
   * Observer, Review, Match History, Settings, and Match Setup must use this module only.
   *
   * Future expansion (not implemented):
   * - Multiple users per team
   * - Team invitations
   * - Role-based permissions (owner / coach / analyst)
   * - Subscriptions & Stripe billing
   * - AI usage quotas
   * - Head coach / coach permission tiers
   */

  function getSession() {
    return window.MO_AUTHENTICATION?.getSession?.() || null;
  }

  function getActiveUserId() {
    return getSession()?.userId || null;
  }

  function getActiveUserEmail() {
    return getSession()?.email || "";
  }

  function getActiveRole() {
    return getSession()?.role
      || window.MO_AUTHENTICATION?.DEFAULT_ROLE
      || "owner";
  }

  function getActiveTeamId() {
    return getSession()?.teamId || null;
  }

  function getActiveTeamName() {
    return getSession()?.teamName || "";
  }

  function getActiveTeam() {
    const teamId = getActiveTeamId();
    if (!teamId) return null;
    return window.MO_AUTHENTICATION?.findTeamById?.(teamId) || null;
  }

  function belongsToActiveTeam(teamId) {
    const activeTeamId = getActiveTeamId();
    if (!activeTeamId || !teamId) return false;
    return activeTeamId === teamId;
  }

  function resolveResourceTeamId(source) {
    return window.MO_MATCH_CONTEXT?.resolveTeamId?.(source) || null;
  }

  function canAccessTeamResource(source) {
    const resourceTeamId = typeof source === "string"
      ? source
      : resolveResourceTeamId(source);
    if (!resourceTeamId) return false;
    return belongsToActiveTeam(resourceTeamId);
  }

  function denyAccess() {
    const homePath = window.MO_APP_HOME_PATH || "../../home/v0.1/index.html";
    const homeUrl = new URL(homePath, window.location.href);
    homeUrl.searchParams.set("access", "denied");
    window.location.assign(homeUrl.href);
  }

  function requireAccessToTeam(teamId) {
    if (!belongsToActiveTeam(teamId)) {
      denyAccess();
      return false;
    }
    return true;
  }

  function requireTeamContext() {
    const teamId = getActiveTeamId();
    if (!teamId) {
      window.MO_AUTHENTICATION?.redirectToLogin?.(window.location.href);
      return null;
    }
    return teamId;
  }

  function ensureAuthenticatedTeamPage() {
    if (!window.MO_AUTHENTICATION?.isAuthenticated?.()) {
      window.MO_AUTHENTICATION?.redirectToLogin?.(window.location.href);
      return false;
    }
    if (!requireTeamContext()) return false;
    window.MO_MATCH_CONTEXT?.ensureLiveStorageBelongsToActiveTeam?.();
    return true;
  }

  function updateTeamName(name) {
    const teamId = getActiveTeamId();
    if (!teamId) {
      return { ok: false, error: "ログイン中のチームが見つかりません。" };
    }
    return window.MO_AUTHENTICATION?.updateTeamName?.(teamId, name)
      || { ok: false, error: "保存に失敗しました。" };
  }

  async function changePassword({ currentPassword, newPassword, confirmPassword }) {
    const session = getSession();
    if (!session) {
      return { ok: false, error: "ログインが必要です。" };
    }
    if (String(newPassword || "") !== String(confirmPassword || "")) {
      return { ok: false, error: "新しいパスワードと確認用パスワードが一致しません。" };
    }
    return window.MO_AUTHENTICATION?.changePassword?.({
      userId: session.userId,
      currentPassword,
      newPassword,
    }) || { ok: false, error: "パスワード変更に失敗しました。" };
  }

  function logout() {
    window.MO_AUTHENTICATION?.logout?.();
  }

  return {
    getSession,
    getActiveUserId,
    getActiveUserEmail,
    getActiveRole,
    getActiveTeamId,
    getActiveTeamName,
    getActiveTeam,
    belongsToActiveTeam,
    canAccessTeamResource,
    requireAccessToTeam,
    requireTeamContext,
    ensureAuthenticatedTeamPage,
    denyAccess,
    updateTeamName,
    changePassword,
    logout,
  };
})();
