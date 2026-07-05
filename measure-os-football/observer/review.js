const matchStorageKey = "measure-os-football:match-control:v0.3";
const observerPath = "./index.html";

const planCategoryPriority = ["defense", "attack", "buildUp", "transition"];

function loadJson(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function normalizePlanSnapshot(raw) {
  return window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot(raw) ?? null;
}

function isValidPlanSnapshot(plan) {
  return normalizePlanSnapshot(plan) !== null;
}

function formatPlanSummary(plan) {
  const normalized = normalizePlanSnapshot(plan);
  if (!normalized?.categories) return "-";

  for (const key of planCategoryPriority) {
    const items = normalized.categories[key];
    if (Array.isArray(items) && items.length > 0) {
      return items[0];
    }
  }

  const memo = typeof normalized.memo === "string" ? normalized.memo.trim() : "";
  return memo || "-";
}

function formatPlanLabel(index) {
  const symbols = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"];
  return symbols[index] || `#${index + 1}`;
}

function renderPlanHistory(match) {
  const list = document.getElementById("plan-history-list");
  const empty = document.getElementById("review-empty");
  const section = document.getElementById("plan-history-section");
  if (!list || !empty || !section) return;

  const history = Array.isArray(match?.planHistory) ? match.planHistory : [];
  const validEntries = history
    .map((entry) => {
      const plan = normalizePlanSnapshot(entry?.plan);
      if (!plan) return null;
      return { ...entry, plan };
    })
    .filter(Boolean);

  if (validEntries.length === 0) {
    section.hidden = true;
    empty.hidden = false;
    list.innerHTML = "";
    return;
  }

  section.hidden = false;
  empty.hidden = true;
  list.innerHTML = validEntries.map((entry, index) => `
    <li class="plan-history-item">
      <p class="plan-history-time">${escapeHtml(entry.matchTime || "00:00")}</p>
      <p class="plan-history-label">Plan${escapeHtml(formatPlanLabel(index))}</p>
      <p class="plan-history-summary">${escapeHtml(formatPlanSummary(entry.plan))}</p>
    </li>
  `).join("");
}

function renderMatchSummary(match) {
  const host = document.getElementById("review-match-summary");
  if (!host || !match) return;

  const home = Math.max(0, Number(match.home_score) || 0);
  const away = Math.max(0, Number(match.away_score) || 0);
  host.innerHTML = `
    <p class="review-score">${home} - ${away}</p>
    <p class="muted review-phase">${escapeHtml(match.match_phase || "unknown")}</p>
  `;
}

document.addEventListener("DOMContentLoaded", () => {
  const match = loadJson(matchStorageKey);
  renderMatchSummary(match);
  renderPlanHistory(match);

  document.getElementById("back-to-observer")?.addEventListener("click", () => {
    window.location.assign(new URL(observerPath, window.location.href).href);
  });
});
