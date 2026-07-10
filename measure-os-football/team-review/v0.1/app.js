const reviewPath = "../../review/v0.1/index.html";

const teamReviewState = {
  records: [],
  filters: {},
};

const $ = (id) => document.getElementById(id);

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

function resultLabel(value) {
  if (value === "win") return "勝ち";
  if (value === "loss") return "負け";
  if (value === "draw") return "引き分け";
  return "-";
}

function readFiltersFromForm() {
  return {
    dateFrom: $("filter-date-from")?.value || "",
    dateTo: $("filter-date-to")?.value || "",
    competition: $("filter-competition")?.value.trim() || "",
    opponent: $("filter-opponent")?.value.trim() || "",
    homeAway: $("filter-home-away")?.value || "",
    result: $("filter-result")?.value || "",
    analyzeMode: $("filter-analyze-mode")?.value || "",
    attackPlan: $("filter-attack-plan")?.value.trim() || "",
    buildUpPlan: $("filter-build-up-plan")?.value.trim() || "",
    defensePlan: $("filter-defense-plan")?.value.trim() || "",
    transitionPlan: $("filter-transition-plan")?.value.trim() || "",
    stateStatus: $("filter-state")?.value || "",
    deviationStatus: $("filter-deviation")?.value || "",
    reviewFullText: $("filter-review-fulltext")?.value.trim() || "",
    freeText: $("filter-free-text")?.value.trim() || "",
  };
}

function resetFiltersForm() {
  $("team-review-filter-form")?.reset();
  teamReviewState.filters = {};
}

function renderTrends(trends) {
  const list = $("team-review-trends");
  if (!list) return;

  if (!Array.isArray(trends) || trends.length === 0) {
    list.innerHTML = `<li class="team-review-trend-item team-review-trend-empty">傾向を判定する試合数が不足しています。</li>`;
    return;
  }

  list.innerHTML = trends.map((trend) => `
    <li class="team-review-trend-item">${escapeHtml(trend)}</li>
  `).join("");
}

function renderStateLegend() {
  const container = $("team-review-state-legend");
  if (!container) return;

  const meta = window.MO_TEAM_REVIEW_STATE_TIMELINE?.STATUS_META || {};
  container.innerHTML = Object.entries(meta).map(([status, item]) => `
    <span class="team-review-state-legend-item" data-state="${escapeHtml(status)}">
      ${item.emoji} ${escapeHtml(item.label)}
    </span>
  `).join("");
}

function renderStateTimeline(stateTimeline) {
  const container = $("team-review-state-timeline");
  if (!container) return;

  const categories = stateTimeline?.categories || [];
  if (categories.length === 0 || categories.every((cat) => cat.points.length === 0)) {
    container.innerHTML = `<p class="team-review-empty">State Timelineを表示する試合がありません。</p>`;
    return;
  }

  container.innerHTML = categories.map((category) => `
    <article class="team-review-state-row">
      <h3 class="team-review-state-row-title">${escapeHtml(category.label)}</h3>
      <div class="team-review-state-track" role="list">
        ${category.points.map((point) => `
          <a
            class="team-review-state-dot state-${escapeHtml(point.status)}"
            role="listitem"
            href="${reviewPath}#match/${encodeURIComponent(point.recordId)}"
            title="${escapeHtml(formatDisplayDate(point.matchDate))} vs ${escapeHtml(point.opponent)} / ${escapeHtml(point.stateLabel)} (${escapeHtml(point.statusLabel)})"
            aria-label="${escapeHtml(formatDisplayDate(point.matchDate))} vs ${escapeHtml(point.opponent)} ${escapeHtml(point.statusLabel)}"
          >${point.emoji}</a>
        `).join("")}
      </div>
    </article>
  `).join("");
}

function renderTeamLearn(teamLearn) {
  const list = $("team-review-learn");
  if (!list) return;

  if (!Array.isArray(teamLearn) || teamLearn.length === 0) {
    list.innerHTML = `<li class="team-review-learn-item team-review-learn-empty">Team Learnを表示する試合数が不足しています。</li>`;
    return;
  }

  list.innerHTML = teamLearn.map((item) => `
    <li class="team-review-learn-item">${escapeHtml(item)}</li>
  `).join("");
}

function renderReviewSearchResults(results, query) {
  const section = $("team-review-search-results-section");
  const list = $("team-review-search-results");
  const lead = $("team-review-search-results-lead");
  if (!section || !list || !lead) return;

  const trimmedQuery = String(query || "").trim();
  if (!trimmedQuery) {
    section.hidden = true;
    list.innerHTML = "";
    return;
  }

  section.hidden = false;
  lead.textContent = `「${trimmedQuery}」を含むReview`;

  if (!Array.isArray(results) || results.length === 0) {
    list.innerHTML = `<li class="team-review-empty">該当するReviewがありません。</li>`;
    return;
  }

  list.innerHTML = results.map((entry) => `
    <li class="team-review-search-item">
      <a class="team-review-search-link" href="${reviewPath}#match/${encodeURIComponent(entry.id)}">
        <span class="team-review-search-date">${escapeHtml(formatDisplayDate(entry.matchDate))}</span>
        <span class="team-review-search-opponent">vs ${escapeHtml(entry.opponent)}</span>
        <span class="team-review-search-excerpt">${escapeHtml(entry.excerpt || entry.reviewText || "")}</span>
      </a>
    </li>
  `).join("");
}

function renderSummary(summary) {
  const container = $("team-review-summary");
  if (!container) return;

  const items = [
    { label: "対象試合数", value: summary.matchCount ?? 0 },
    { label: "勝率", value: `${summary.winRate ?? 0}%` },
    { label: "平均得点", value: summary.avgGoalsFor ?? "0.0" },
    { label: "平均失点", value: summary.avgGoalsAgainst ?? "0.0" },
    { label: "Review件数", value: summary.reviewCount ?? 0 },
    { label: "Deviation件数", value: summary.deviationWarnCount ?? 0 },
    { label: "Plan変更回数", value: summary.planChangeCount ?? 0 },
  ];

  container.innerHTML = items.map((item) => `
    <div class="team-review-summary-item">
      <span class="team-review-summary-label">${escapeHtml(item.label)}</span>
      <strong class="team-review-summary-value">${escapeHtml(String(item.value))}</strong>
    </div>
  `).join("");
}

function renderAggregationBlock(title, rows) {
  const body = (rows || []).map((row) => `
    <div class="team-review-aggregation-row">
      <span>${escapeHtml(row.label)}</span>
      <strong>${escapeHtml(String(row.percent))}%</strong>
    </div>
  `).join("");

  return `
    <article class="team-review-aggregation-block">
      <h3 class="team-review-aggregation-title">${escapeHtml(title)}</h3>
      <div class="team-review-aggregation-rows">${body}</div>
    </article>
  `;
}

function renderAggregations(aggregations) {
  const container = $("team-review-aggregations");
  if (!container) return;

  container.innerHTML = [
    renderAggregationBlock("Attack", aggregations.attack),
    renderAggregationBlock("Build Up", aggregations.buildUp),
    renderAggregationBlock("Finish", aggregations.finish),
    renderAggregationBlock("Defense", aggregations.defense),
    renderAggregationBlock("Transition", aggregations.transition),
  ].join("");
}

function renderReviewHistory(reviewHistory) {
  const list = $("team-review-history");
  const empty = $("team-review-history-empty");
  if (!list || !empty) return;

  if (!Array.isArray(reviewHistory) || reviewHistory.length === 0) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  list.innerHTML = reviewHistory.map((entry, index) => {
    const deviationLabel = entry.hasDeviationWarn ? "Deviationあり" : "Deviationなし";
    const reviewPreview = entry.reviewText
      ? escapeHtml(entry.reviewText.split("\n\n")[0])
      : "Reviewなし";

    return `
      <li class="team-review-history-item" style="--memory-index:${index}">
        <a class="team-review-history-link" href="${reviewPath}#match/${encodeURIComponent(entry.id)}">
          <span class="team-review-history-date">${escapeHtml(formatDisplayDate(entry.matchDate))}</span>
          <span class="team-review-history-opponent">vs ${escapeHtml(entry.opponent)}</span>
          <span class="team-review-history-badges">
            <span class="team-review-badge">Review</span>
            <span class="team-review-badge ${entry.hasDeviationWarn ? "is-warn" : "is-ok"}">${escapeHtml(deviationLabel)}</span>
            <span class="team-review-badge">${escapeHtml(resultLabel(entry.matchResult))}</span>
          </span>
          <span class="team-review-history-preview">${reviewPreview}</span>
        </a>
      </li>
    `;
  }).join("");
}

function renderMatches(matches) {
  const list = $("team-review-matches");
  const empty = $("team-review-matches-empty");
  if (!list || !empty) return;

  if (!Array.isArray(matches) || matches.length === 0) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  list.innerHTML = matches.map((match) => `
    <li class="team-review-match-item">
      <a class="team-review-match-link" href="${reviewPath}#match/${encodeURIComponent(match.id)}">
        <span class="team-review-match-date">${escapeHtml(formatDisplayDate(match.matchDate))}</span>
        <span class="team-review-match-opponent">vs ${escapeHtml(match.opponent)}</span>
        <span class="team-review-match-meta muted">${escapeHtml(match.competition || "大会未設定")} / ${escapeHtml(match.scoreLabel)} / ${escapeHtml(resultLabel(match.matchResult))}</span>
      </a>
    </li>
  `).join("");
}

function renderTeamReviewView(view) {
  renderTrends(view.trends || []);
  renderStateTimeline(view.stateTimeline || { categories: [] });
  renderTeamLearn(view.teamLearn || []);
  renderReviewSearchResults(
    view.reviewSearchResults || [],
    view.filters?.reviewFullText || view.filters?.reviewKeyword || "",
  );
  renderSummary(view.summary || {});
  renderAggregations(view.aggregations || {});
  renderReviewHistory(view.reviewHistory || []);
  renderMatches(view.matches || []);
}

function refreshTeamReview() {
  const teamId = window.MO_TEAM_CONTEXT?.getActiveTeamId?.();
  if (!teamId) return;

  teamReviewState.records = window.MO_TEAM_REVIEW_ENGINE?.loadTeamRecords?.(teamId) || [];
  const view = window.MO_TEAM_REVIEW_ENGINE?.buildTeamReview?.({
    records: teamReviewState.records,
    filters: teamReviewState.filters,
  }) || {};

  renderTeamReviewView(view);
}

function bindEvents() {
  $("team-review-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    teamReviewState.filters = readFiltersFromForm();
    refreshTeamReview();
  });

  $("team-review-reset")?.addEventListener("click", () => {
    resetFiltersForm();
    refreshTeamReview();
  });
}

if (window.MO_AUTH_GUARD?.requireAuth?.()) {
  renderStateLegend();
  bindEvents();
  refreshTeamReview();
}
