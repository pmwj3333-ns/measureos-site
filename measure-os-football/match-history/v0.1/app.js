const historyList = document.getElementById("history-list");
const historyEmpty = document.getElementById("history-empty");
const historyTeamLabel = document.getElementById("history-team-label");

const reviewPath = "../../review/v0.1/index.html";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDisplayDate(value) {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function sortRecordsNewestFirst(records) {
  return [...records].sort((a, b) => {
    const dateA = String(a.setup?.match_date || "");
    const dateB = String(b.setup?.match_date || "");
    if (dateA !== dateB) return dateB.localeCompare(dateA);
    return String(b.archived_at || "").localeCompare(String(a.archived_at || ""));
  });
}

function renderHistory() {
  const teamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
  const teamName = window.MO_TEAM_CONTEXT?.getActiveTeamName?.();
  if (!teamId) return;

  if (historyTeamLabel) {
    historyTeamLabel.textContent = teamName;
  }

  window.MO_REVIEW_ARCHIVE?.upsertFromLiveStorage?.();
  const records = sortRecordsNewestFirst(
    window.MO_REVIEW_ARCHIVE?.search?.({ teamId }) || [],
  ).filter((record) => window.MO_TEAM_CONTEXT?.canAccessTeamResource?.(record));

  if (!historyList || !historyEmpty) return;

  historyList.innerHTML = "";
  historyEmpty.hidden = records.length > 0;

  records.forEach((record) => {
    if (!window.MO_TEAM_CONTEXT?.canAccessTeamResource?.(record)) return;

    const setup = record.setup || {};
    const match = record.match || {};
    const item = document.createElement("li");
    item.className = "history-item";

    const link = document.createElement("a");
    link.className = "history-link";
    link.href = `${reviewPath}#match/${encodeURIComponent(record.id)}`;
    link.innerHTML = `
      <span class="history-date">${escapeHtml(formatDisplayDate(setup.match_date))}</span>
      <span class="history-opponent">${escapeHtml(setup.opponent || "対戦相手")}</span>
      <span class="history-meta muted">${escapeHtml(setup.competition || "大会未設定")} / Home ${match.home_score ?? 0} - ${match.away_score ?? 0} Away</span>
    `;

    item.appendChild(link);
    historyList.appendChild(item);
  });
}

if (window.MO_AUTH_GUARD?.requireAuth?.()) {
  renderHistory();
}
