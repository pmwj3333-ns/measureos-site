const teamForm = document.getElementById("team-form");
const teamNameInput = document.getElementById("team-name");
const teamSaveStatus = document.getElementById("team-save-status");
const passwordForm = document.getElementById("password-form");
const currentPasswordInput = document.getElementById("current-password");
const newPasswordInput = document.getElementById("new-password");
const confirmPasswordInput = document.getElementById("confirm-password");
const passwordSaveStatus = document.getElementById("password-save-status");
const accountEmail = document.getElementById("account-email");
const accountRole = document.getElementById("account-role");
const logoutButton = document.getElementById("logout-button");

const loginPath = "../../auth/v0.1/login.html";

function renderSettings() {
  const session = window.MO_TEAM_CONTEXT?.getSession?.();
  if (!session) return;

  if (teamNameInput) {
    teamNameInput.value = session.teamName || "";
  }
  if (accountEmail) {
    accountEmail.textContent = session.email;
  }
  if (accountRole) {
    accountRole.textContent = session.role || "owner";
  }
}

function handleTeamSubmit(event) {
  event.preventDefault();
  if (!window.MO_TEAM_CONTEXT?.requireTeamContext?.()) return;

  const result = window.MO_TEAM_CONTEXT.updateTeamName(teamNameInput.value);

  if (teamSaveStatus) {
    teamSaveStatus.textContent = result.ok
      ? "チーム名を保存しました。"
      : result.error || "保存に失敗しました。";
  }
}

async function handlePasswordSubmit(event) {
  event.preventDefault();
  if (!window.MO_TEAM_CONTEXT?.requireTeamContext?.()) return;

  if (passwordSaveStatus) {
    passwordSaveStatus.textContent = "";
  }

  const result = await window.MO_TEAM_CONTEXT.changePassword({
    currentPassword: currentPasswordInput.value,
    newPassword: newPasswordInput.value,
    confirmPassword: confirmPasswordInput.value,
  });

  if (passwordSaveStatus) {
    passwordSaveStatus.textContent = result.ok
      ? "パスワードを変更しました。"
      : result.error || "パスワード変更に失敗しました。";
  }

  if (result.ok) {
    passwordForm.reset();
  }
}

function handleLogout() {
  window.MO_TEAM_CONTEXT.logout();
  window.location.assign(loginPath);
}

if (window.MO_AUTH_GUARD?.requireAuth?.()) {
  renderSettings();
  teamForm?.addEventListener("submit", handleTeamSubmit);
  passwordForm?.addEventListener("submit", handlePasswordSubmit);
  logoutButton?.addEventListener("click", handleLogout);
}
