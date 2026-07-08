const teamNameDisplay = document.getElementById("team-name-display");
const userEmailDisplay = document.getElementById("user-email-display");
const teamIdDisplay = document.getElementById("team-id-display");
const userRoleDisplay = document.getElementById("user-role-display");
const accessDeniedBanner = document.getElementById("access-denied-banner");

function formatRoleLabel(role) {
  const value = String(role || "owner").toLowerCase();
  if (value === "coach") return "coach";
  if (value === "analyst") return "analyst";
  return "owner";
}

function renderAccessDeniedBanner() {
  const params = new URLSearchParams(window.location.search);
  if (!accessDeniedBanner) return;
  const denied = params.get("access") === "denied";
  accessDeniedBanner.hidden = !denied;
}

function renderHome() {
  const session = window.MO_TEAM_CONTEXT?.getSession?.();
  if (!session) return;

  if (teamNameDisplay) {
    teamNameDisplay.textContent = session.teamName || "Team";
  }
  if (userEmailDisplay) {
    userEmailDisplay.textContent = session.email;
  }
  if (teamIdDisplay) {
    teamIdDisplay.textContent = `Team ID: ${session.teamId}`;
  }
  if (userRoleDisplay) {
    userRoleDisplay.textContent = `Role: ${formatRoleLabel(session.role)}`;
  }
}

if (window.MO_AUTH_GUARD?.requireAuth?.()) {
  renderAccessDeniedBanner();
  renderHome();
}
