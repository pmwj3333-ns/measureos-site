const form = document.getElementById("auth-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const teamNameField = document.getElementById("team-name-field");
const teamNameInput = document.getElementById("team-name");
const errorElement = document.getElementById("auth-error");
const submitButton = document.getElementById("auth-submit");
const modeLoginButton = document.getElementById("mode-login");
const modeRegisterButton = document.getElementById("mode-register");

let authMode = "login";

function resolveFootballRoot() {
  if (window.MO_APP_FOOTBALL_ROOT) {
    return window.MO_APP_FOOTBALL_ROOT;
  }
  const match = window.location.pathname.match(/^(.*\/measure-os-football)/);
  return match ? match[1] : "/measure-os-football";
}

function resolveHomePath() {
  if (window.MO_APP_HOME_PATH && window.MO_APP_HOME_PATH.startsWith("/")) {
    return window.MO_APP_HOME_PATH;
  }
  return `${resolveFootballRoot()}/home/v0.1/index.html`;
}

function isSafeReturnTo(url) {
  if (!url || url.origin !== window.location.origin) return false;

  const footballRoot = resolveFootballRoot();
  if (!url.pathname.startsWith(`${footballRoot}/`)) return false;

  const loginPrefix = `${footballRoot}/auth/`;
  if (url.pathname.startsWith(loginPrefix)) return false;

  if (url.pathname.endsWith("/h") || url.pathname === `${footballRoot}/h`) {
    return false;
  }

  return true;
}

function resolveReturnTo() {
  const homePath = resolveHomePath();
  const params = new URLSearchParams(window.location.search);
  const returnTo = params.get("returnTo");
  if (!returnTo) return homePath;

  try {
    const url = new URL(returnTo, window.location.href);
    if (!isSafeReturnTo(url)) return homePath;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch (_) {
    return homePath;
  }
}

function navigateAfterAuth() {
  window.location.assign(resolveReturnTo());
}

function showError(message) {
  if (!errorElement) return;
  errorElement.textContent = message || "";
  errorElement.hidden = !message;
}

function setAuthMode(mode) {
  authMode = mode === "register" ? "register" : "login";
  const isRegister = authMode === "register";

  modeLoginButton.classList.toggle("is-active", !isRegister);
  modeLoginButton.setAttribute("aria-selected", isRegister ? "false" : "true");
  modeRegisterButton.classList.toggle("is-active", isRegister);
  modeRegisterButton.setAttribute("aria-selected", isRegister ? "true" : "false");

  teamNameField.hidden = !isRegister;
  teamNameInput.required = isRegister;
  passwordInput.autocomplete = isRegister ? "new-password" : "current-password";
  submitButton.textContent = isRegister ? "アカウント作成" : "ログイン";
  showError("");
}

async function handleSubmit(event) {
  event.preventDefault();
  showError("");
  submitButton.disabled = true;

  const payload = {
    email: emailInput.value,
    password: passwordInput.value,
  };

  let result;
  if (authMode === "register") {
    result = await window.MO_AUTHENTICATION.register({
      ...payload,
      teamName: teamNameInput.value,
    });
  } else {
    result = await window.MO_AUTHENTICATION.login(payload);
  }

  submitButton.disabled = false;
  if (!result.ok) {
    showError(result.error || "認証に失敗しました。");
    return;
  }

  navigateAfterAuth();
}

if (window.MO_AUTHENTICATION?.isAuthenticated?.()) {
  window.location.replace(resolveReturnTo());
} else {
  setAuthMode("login");
  modeLoginButton.addEventListener("click", () => setAuthMode("login"));
  modeRegisterButton.addEventListener("click", () => setAuthMode("register"));
  form.addEventListener("submit", handleSubmit);
}
