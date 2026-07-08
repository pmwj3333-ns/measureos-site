window.MO_AUTHENTICATION = (() => {
  const keys = window.MO_STORAGE_KEYS;

  // Team roles — owner only for now; coach / analyst reserved for future multi-user support.
  const ROLES = {
    OWNER: "owner",
    COACH: "coach",
    ANALYST: "analyst",
  };

  const DEFAULT_ROLE = ROLES.OWNER;

  /*
   * Future expansion (not implemented):
   * - Multiple users per team
   * - Team invitations
   * - Role-based permissions (owner / coach / analyst)
   * - Subscriptions & Stripe billing
   * - AI usage quotas
   * - Head coach / coach permission tiers
   */

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

  function removeJson(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (_) {
      // Ignore storage errors in the local prototype.
    }
  }

  function generateId(prefix) {
    if (window.crypto?.randomUUID) {
      return `${prefix}-${window.crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
  }

  function normalizeEmail(email) {
    return String(email || "").trim().toLowerCase();
  }

  function normalizeRole(role) {
    const value = String(role || "").trim().toLowerCase();
    if (value === ROLES.COACH || value === ROLES.ANALYST) return value;
    return DEFAULT_ROLE;
  }

  async function hashPassword(password, salt) {
    const encoded = new TextEncoder().encode(`${salt}:${password}`);
    const digest = await window.crypto.subtle.digest("SHA-256", encoded);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  function loadUsers() {
    const saved = loadJson(keys.users);
    return Array.isArray(saved) ? saved : [];
  }

  function saveUsers(users) {
    saveJson(keys.users, users);
  }

  function loadTeams() {
    const saved = loadJson(keys.teams);
    return Array.isArray(saved) ? saved : [];
  }

  function saveTeams(teams) {
    saveJson(keys.teams, teams);
  }

  function findUserByEmail(email) {
    const normalized = normalizeEmail(email);
    return loadUsers().find((user) => user.email === normalized) || null;
  }

  function findUserById(userId) {
    return loadUsers().find((user) => user.id === userId) || null;
  }

  function findTeamById(teamId) {
    return loadTeams().find((team) => team.id === teamId) || null;
  }

  function getSession() {
    const session = loadJson(keys.authSession);
    if (!session?.userId || !session?.teamId) return null;

    const user = findUserById(session.userId);
    const team = findTeamById(session.teamId);
    if (!user || !team) {
      removeJson(keys.authSession);
      return null;
    }

    return {
      userId: user.id,
      email: user.email,
      role: normalizeRole(user.role),
      teamId: team.id,
      teamName: team.name,
      signedInAt: session.signedInAt || null,
    };
  }

  function isAuthenticated() {
    return Boolean(getSession());
  }

  function writeSession(user, team) {
    saveJson(keys.authSession, {
      userId: user.id,
      teamId: team.id,
      signedInAt: new Date().toISOString(),
    });
  }

  async function register({ email, password, teamName }) {
    const normalizedEmail = normalizeEmail(email);
    const normalizedTeamName = String(teamName || "").trim();
    const rawPassword = String(password || "");

    if (!normalizedEmail || !rawPassword || !normalizedTeamName) {
      return { ok: false, error: "メールアドレス、パスワード、チーム名を入力してください。" };
    }
    if (rawPassword.length < 8) {
      return { ok: false, error: "パスワードは8文字以上で入力してください。" };
    }
    if (findUserByEmail(normalizedEmail)) {
      return { ok: false, error: "このメールアドレスは既に登録されています。" };
    }

    const team = {
      id: generateId("team"),
      name: normalizedTeamName,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    const salt = generateId("salt");
    const passwordHash = await hashPassword(rawPassword, salt);
    const user = {
      id: generateId("user"),
      email: normalizedEmail,
      passwordHash,
      passwordSalt: salt,
      teamId: team.id,
      role: DEFAULT_ROLE,
      createdAt: new Date().toISOString(),
    };

    const teams = loadTeams();
    teams.push(team);
    saveTeams(teams);

    const users = loadUsers();
    users.push(user);
    saveUsers(users);

    writeSession(user, team);
    return { ok: true, session: getSession() };
  }

  async function login({ email, password }) {
    const normalizedEmail = normalizeEmail(email);
    const rawPassword = String(password || "");
    if (!normalizedEmail || !rawPassword) {
      return { ok: false, error: "メールアドレスとパスワードを入力してください。" };
    }

    const user = findUserByEmail(normalizedEmail);
    if (!user) {
      return { ok: false, error: "メールアドレスまたはパスワードが正しくありません。" };
    }

    const passwordHash = await hashPassword(rawPassword, user.passwordSalt);
    if (passwordHash !== user.passwordHash) {
      return { ok: false, error: "メールアドレスまたはパスワードが正しくありません。" };
    }

    const team = findTeamById(user.teamId);
    if (!team) {
      return { ok: false, error: "所属チームが見つかりません。管理者に連絡してください。" };
    }

    writeSession(user, team);
    return { ok: true, session: getSession() };
  }

  function logout() {
    removeJson(keys.authSession);
  }

  async function changePassword({ userId, currentPassword, newPassword }) {
    const rawCurrent = String(currentPassword || "");
    const rawNext = String(newPassword || "");

    if (!userId || !rawCurrent || !rawNext) {
      return { ok: false, error: "すべての項目を入力してください。" };
    }
    if (rawNext.length < 8) {
      return { ok: false, error: "新しいパスワードは8文字以上で入力してください。" };
    }

    const users = loadUsers();
    const index = users.findIndex((user) => user.id === userId);
    if (index < 0) {
      return { ok: false, error: "ユーザーが見つかりません。" };
    }

    const user = users[index];
    const currentHash = await hashPassword(rawCurrent, user.passwordSalt);
    if (currentHash !== user.passwordHash) {
      return { ok: false, error: "現在のパスワードが正しくありません。" };
    }

    const salt = generateId("salt");
    const passwordHash = await hashPassword(rawNext, salt);
    users[index] = {
      ...user,
      passwordHash,
      passwordSalt: salt,
      updatedAt: new Date().toISOString(),
    };
    saveUsers(users);
    return { ok: true };
  }

  function updateTeamName(teamId, name) {
    const normalizedName = String(name || "").trim();
    if (!teamId || !normalizedName) {
      return { ok: false, error: "チーム名を入力してください。" };
    }

    const teams = loadTeams();
    const index = teams.findIndex((team) => team.id === teamId);
    if (index < 0) {
      return { ok: false, error: "チームが見つかりません。" };
    }

    teams[index] = {
      ...teams[index],
      name: normalizedName,
      updatedAt: new Date().toISOString(),
    };
    saveTeams(teams);
    return { ok: true, team: teams[index] };
  }

  function redirectToLogin(returnTo = window.location.href) {
    const loginPath = window.MO_AUTH_LOGIN_PATH || "../../auth/v0.1/login.html";
    const loginUrl = new URL(loginPath, window.location.href);
    loginUrl.searchParams.set("returnTo", returnTo);
    window.location.assign(loginUrl.href);
  }

  return {
    ROLES,
    DEFAULT_ROLE,
    register,
    login,
    logout,
    changePassword,
    getSession,
    isAuthenticated,
    findUserById,
    findTeamById,
    updateTeamName,
    redirectToLogin,
    normalizeRole,
  };
})();
