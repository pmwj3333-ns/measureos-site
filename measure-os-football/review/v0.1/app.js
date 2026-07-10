const planCategoryLabels = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const setupStorageKey = "measure-os-football:match-setup:v1";
const matchStorageKey = "measure-os-football:match-control:v0.3";
const eventStorageKey = "measure-os-football:observer-events:v0.3";
const planStorageKey = "measure-os-football:plan:v0.1";
const planReturnStorageKey = "measure-os-football:plan-return:v0.3";
const matchSetupPath = "../../match-setup/v0.1/index.html";
const planPath = "../../plan/v0.1/index.html";

const planDisplayCategories = [
  { key: "attack", label: planCategoryLabels.attack },
  { key: "defense", label: planCategoryLabels.defense },
  { key: "buildUp", label: planCategoryLabels.buildUp },
  { key: "transition", label: planCategoryLabels.transition },
];

const stateCategoryMap = {
  Attack: "attack",
  Defense: "defense",
  "Build Up": "buildUp",
  Transition: "transition",
};

const reviewState = {
  filters: { competition: "", opponent: "", match_date: "" },
  records: [],
  selectedId: null,
  activeTab: "match",
};

const $ = (id) => document.getElementById(id);

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

function parseMatchTime(timeValue) {
  const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
  if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
  return minutes * 60 + seconds;
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

function formatPlanSelections(items) {
  if (!Array.isArray(items) || items.length === 0) return "-";
  return items.map((item) => escapeHtml(item)).join("、");
}

function homeAwayLabel(value) {
  if (value === "home") return "Home";
  if (value === "away") return "Away";
  return "-";
}

function formatMatchDuration(record) {
  const match = record.match || {};
  const events = Array.isArray(record.events) ? record.events : [];
  const lastEvent = events.length > 0 ? events[events.length - 1] : null;

  if (lastEvent?.time) return lastEvent.time;

  if (match.kickoff_at && match.fulltime_at) {
    const start = new Date(match.kickoff_at).getTime();
    const end = new Date(match.fulltime_at).getTime();
    if (!Number.isNaN(start) && !Number.isNaN(end) && end > start) {
      const totalSeconds = Math.floor((end - start) / 1000);
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
  }

  return "-";
}

function sortRecordsNewestFirst(records) {
  return [...records].sort((a, b) => {
    const dateA = String(a.setup?.match_date || "");
    const dateB = String(b.setup?.match_date || "");
    if (dateA !== dateB) return dateB.localeCompare(dateA);
    const archivedA = String(a.archived_at || "");
    const archivedB = String(b.archived_at || "");
    return archivedB.localeCompare(archivedA);
  });
}

function getArchiveApi() {
  return window.MO_REVIEW_ARCHIVE;
}

function readStorage(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (_) {
    return false;
  }
}

function removeStorage(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (_) {
    // Ignore storage errors in the local prototype.
  }
}

function generateMatchId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function getActiveTeamId() {
  return window.MO_TEAM_CONTEXT?.getActiveTeamId?.() || null;
}

function assertRecordTeamAccess(record) {
  if (!record) return false;
  return window.MO_TEAM_CONTEXT?.canAccessTeamResource?.(record) ?? false;
}

function archiveCurrentMatchIfNeeded() {
  getArchiveApi()?.upsertFromLiveStorage?.();
}

function resetLiveMatchData() {
  removeStorage(matchStorageKey);
  removeStorage(eventStorageKey);
  removeStorage(planStorageKey);
  removeStorage(planReturnStorageKey);
}

function resolveCompetitionSource() {
  const selected = getSelectedRecord();
  if (selected?.setup?.competition) {
    return String(selected.setup.competition).trim();
  }

  const liveMatch = readStorage(matchStorageKey);
  const liveSetup = readStorage(setupStorageKey);
  if (liveMatch?.match_phase === "fulltime" && liveSetup?.competition) {
    return String(liveSetup.competition).trim();
  }

  const latest = sortRecordsNewestFirst(
    getArchiveApi()?.search?.({ teamId: getActiveTeamId() }) || [],
  )[0];
  if (latest?.setup?.competition) {
    return String(latest.setup.competition).trim();
  }

  return liveSetup?.competition ? String(liveSetup.competition).trim() : "";
}

function resolveNextMatchDefaults() {
  const selected = getSelectedRecord();
  const previousSetup = selected?.setup || readStorage(setupStorageKey) || {};
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");

  return {
    opponent: "対戦相手未定",
    matchDate: `${today.getFullYear()}-${month}-${day}`,
    kickoffTime: previousSetup.kickoff_time || "10:00",
    previousSetup,
  };
}

function showNextMatchError(message) {
  const error = $("review-next-match-error");
  if (!error) return;
  error.textContent = message;
  error.hidden = !message;
}

function startSameCompetitionNext() {
  const competition = resolveCompetitionSource();
  const { opponent, matchDate, kickoffTime, previousSetup } = resolveNextMatchDefaults();

  if (!competition) {
    showNextMatchError("大会名がありません。Match Setupから新しい大会を開始してください。");
    return;
  }

  showNextMatchError("");
  archiveCurrentMatchIfNeeded();

  const teamId = getActiveTeamId();
  if (!teamId) return;

  if (previousSetup.teamId && !window.MO_TEAM_CONTEXT?.canAccessTeamResource?.(previousSetup)) {
    window.MO_TEAM_CONTEXT?.denyAccess?.();
    return;
  }

  const nextSetup = window.MO_MATCH_CONTEXT?.attachTeamId?.({
    match_id: generateMatchId(),
    competition,
    opponent,
    match_date: matchDate,
    kickoff_time: kickoffTime,
    home_away: previousSetup.home_away || "",
    formation: previousSetup.formation || "",
    analyzeMode: previousSetup.analyzeMode || "both",
    match_created_at: new Date().toISOString(),
  }, teamId) || {
    match_id: generateMatchId(),
    teamId,
    competition,
    opponent,
    match_date: matchDate,
    kickoff_time: kickoffTime,
    home_away: previousSetup.home_away || "",
    formation: previousSetup.formation || "",
    analyzeMode: previousSetup.analyzeMode || "both",
    match_created_at: new Date().toISOString(),
  };

  if (!writeStorage(setupStorageKey, nextSetup)) {
    showNextMatchError("試合情報の保存に失敗しました。");
    return;
  }

  resetLiveMatchData();
  window.location.href = planPath;
}

function startNewCompetition() {
  showNextMatchError("");
  archiveCurrentMatchIfNeeded();
  resetLiveMatchData();
  removeStorage(setupStorageKey);
  window.location.href = matchSetupPath;
}

function refreshRecords() {
  const api = getArchiveApi();
  if (!api) {
    reviewState.records = [];
    return;
  }
  api.upsertFromLiveStorage();
  reviewState.records = sortRecordsNewestFirst(
    api.search({
      ...reviewState.filters,
      teamId: getActiveTeamId(),
    }),
  ).filter((record) => assertRecordTeamAccess(record));
}

function getSelectedRecord() {
  const api = getArchiveApi();
  if (!reviewState.selectedId || !api) return null;
  return api.getById(reviewState.selectedId, getActiveTeamId());
}

function renderMatchList() {
  const list = $("review-match-list");
  const empty = $("review-list-empty");
  if (!list || !empty) return;

  if (reviewState.records.length === 0) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  list.innerHTML = reviewState.records.map((record) => {
    const setup = record.setup || {};
    const match = record.match || {};
    const home = Math.max(0, Number(match.home_score) || 0);
    const away = Math.max(0, Number(match.away_score) || 0);
    const competition = setup.competition || "大会未設定";
    const opponent = setup.opponent || "対戦相手未設定";

    return `
      <li>
        <article class="review-match-card panel">
          <p class="review-match-card-date">${escapeHtml(formatDisplayDate(setup.match_date))}</p>
          <p class="review-match-card-competition">${escapeHtml(competition)}</p>
          <p class="review-match-card-opponent">vs ${escapeHtml(opponent)}</p>
          <p class="review-match-card-score">Home ${home} - ${away} Away</p>
          <button type="button" class="review-match-card-action" data-match-id="${escapeHtml(record.id)}">▶ 詳細を見る</button>
        </article>
      </li>
    `;
  }).join("");
}

function renderMatchTab(record) {
  const setup = record.setup || {};
  const match = record.match || {};
  const home = Math.max(0, Number(match.home_score) || 0);
  const away = Math.max(0, Number(match.away_score) || 0);

  $("review-tab-match").innerHTML = `
    <div class="review-grid">
      <div class="review-field"><span>大会名</span><strong>${escapeHtml(setup.competition || "-")}</strong></div>
      <div class="review-field"><span>対戦相手</span><strong>${escapeHtml(setup.opponent || "-")}</strong></div>
      <div class="review-field"><span>試合日</span><strong>${escapeHtml(formatDisplayDate(setup.match_date))}</strong></div>
      <div class="review-field"><span>Home / Away</span><strong>${escapeHtml(homeAwayLabel(setup.home_away))}</strong></div>
      <div class="review-field"><span>キックオフ</span><strong>${escapeHtml(setup.kickoff_time || "-")}</strong></div>
      <div class="review-field"><span>スコア</span><strong>Home ${home} - ${away} Away</strong></div>
      <div class="review-field"><span>試合時間</span><strong>${escapeHtml(formatMatchDuration(record))}</strong></div>
    </div>
  `;
}

function getPlanChangeReason(record, planIndex) {
  const reasons = Array.isArray(record.plan_change_reasons) ? record.plan_change_reasons : [];
  const found = reasons.find((item) => Number(item.planIndex) === planIndex);
  return found?.reason ? String(found.reason).trim() : "";
}

function renderPlanTab(record) {
  const history = Array.isArray(record.match?.planHistory) ? record.match.planHistory : [];
  const validEntries = history
    .map((entry, index) => {
      const plan = normalizePlanSnapshot(entry?.plan);
      if (!plan) return null;
      return { entry, plan, index };
    })
    .filter(Boolean);

  if (validEntries.length === 0) {
    $("review-tab-plan").innerHTML = `<p class="review-empty">Plan履歴がありません。</p>`;
    return;
  }

  const cards = validEntries.map(({ entry, plan, index }) => {
    const rows = planDisplayCategories.map(({ key, label }) => {
      const items = Array.isArray(plan.categories[key]) ? plan.categories[key] : [];
      return `
        <div class="review-plan-row">
          <span>${escapeHtml(label)}</span>
          <strong>${formatPlanSelections(items)}</strong>
        </div>
      `;
    }).join("");

    const reason = getPlanChangeReason(record, index + 1);
    const reasonBlock = index > 0
      ? `<p class="review-plan-reason">変更理由: ${escapeHtml(reason || "（未入力）")}</p>`
      : "";

    return `
      <article class="review-plan-card">
        <div class="review-plan-card-head">
          <p class="review-plan-number">Plan #${index + 1}</p>
          <p class="review-plan-time">開始 ${escapeHtml(entry.matchTime || "00:00")}</p>
          ${reasonBlock}
        </div>
        <div class="review-plan-rows">${rows}</div>
      </article>
    `;
  });

  $("review-tab-plan").innerHTML = cards
    .map((card, index) => (index > 0 ? `<div class="review-plan-divider"></div>${card}` : card))
    .join("");
}

const attackLiveStateCategories = [
  { key: "attack", label: planCategoryLabels.attack },
  { key: "buildUp", label: planCategoryLabels.buildUp },
];

const defenseLiveStateCategories = [
  { key: "defense", label: planCategoryLabels.defense },
  { key: "transition", label: planCategoryLabels.transition },
];

const bothLiveStateCategories = planDisplayCategories;

function getReviewLiveStateCategories(plan) {
  const mode = plan?.analyzeMode || "both";
  if (mode === "attack") return attackLiveStateCategories;
  if (mode === "defense") return defenseLiveStateCategories;
  return bothLiveStateCategories;
}

function resolveCategoryKeyForRuleId(ruleId) {
  return window.MO_COMPOSITE_ANALYZE_MODES?.resolveCategoryKeyForRuleId(ruleId) || null;
}

function buildReasonResults(ruleResults, plan, context) {
  const explainLiveState = window.MO_REASON_ENGINE?.explainLiveState;
  if (typeof explainLiveState !== "function" || !Array.isArray(ruleResults)) return [];
  return explainLiveState({ plan, stateResults: ruleResults, context });
}

function buildCompositeReason(reasonResults, plan) {
  const composeOverallReason = window.MO_COMPOSITE_REASON_ENGINE?.composeOverallReason;
  if (typeof composeOverallReason !== "function" || !Array.isArray(reasonResults)) return null;
  return composeOverallReason({
    analyzeMode: plan?.analyzeMode || "both",
    reasonResults,
  });
}

function buildMatchReviewContext(record) {
  const events = Array.isArray(record.events) ? record.events : [];
  const history = Array.isArray(record.match?.planHistory) ? record.match.planHistory : [];
  const lastEntry = history[history.length - 1];
  const plan = normalizePlanSnapshot(lastEntry?.plan);
  if (!plan) return null;

  return window.MO_REVIEW_ENGINE?.buildReviewInput?.({
    plan,
    events,
  }) || null;
}

function renderReviewMetricsBlock(metricsBlock) {
  if (!metricsBlock?.rows?.length) return "";

  const rows = metricsBlock.rows.map((row) => `
    <div class="review-metrics-row">
      <span class="review-metrics-label">${escapeHtml(row.label)}</span>
      <span class="review-metrics-value">${escapeHtml(String(row.percent))}%</span>
    </div>
  `).join("");

  return `
    <section class="review-metrics-block">
      <h4 class="review-metrics-title">${escapeHtml(metricsBlock.title)}</h4>
      <div class="review-metrics-rows">${rows}</div>
    </section>
  `;
}

function renderAttackReviewSection(section) {
  const metricsHtml = (section.metrics || []).map(renderReviewMetricsBlock).join("");
  const narrativeHtml = section.narrative
    ? `<blockquote class="review-narrative">${escapeHtml(section.narrative)}</blockquote>`
    : `<p class="review-empty">Reviewを生成するデータがありません。</p>`;
  const summaryHtml = section.summary && section.summary !== section.narrative
    ? `<p class="review-summary">${escapeHtml(section.summary)}</p>`
    : "";

  return `
    <section class="review-mode-block" data-review-mode="attack">
      <h3 class="review-mode-title">${escapeHtml(section.title)}</h3>
      <div class="review-metrics-grid">${metricsHtml}</div>
      ${narrativeHtml}
      ${summaryHtml}
    </section>
  `;
}

function renderDefenseReviewSection(section) {
  const categoryBlocks = (section.sections || []).map((entry) => `
    <section class="review-defense-category">
      <h4 class="review-defense-category-title">${escapeHtml(entry.title)}</h4>
      <p class="review-defense-category-body">${escapeHtml(entry.narrative || "")}</p>
    </section>
  `).join("");

  const narrativeHtml = section.narrative
    ? `<blockquote class="review-narrative">${escapeHtml(section.narrative)}</blockquote>`
    : "";
  const summaryHtml = section.summary && section.summary !== section.narrative
    ? `<p class="review-summary">${escapeHtml(section.summary)}</p>`
    : "";

  return `
    <section class="review-mode-block" data-review-mode="defense">
      <h3 class="review-mode-title">${escapeHtml(section.title)}</h3>
      ${categoryBlocks || `<p class="review-empty">Reviewを生成するデータがありません。</p>`}
      ${narrativeHtml}
      ${summaryHtml}
    </section>
  `;
}

function renderReviewSection(section) {
  if (section.key === "attack") return renderAttackReviewSection(section);
  if (section.key === "defense") return renderDefenseReviewSection(section);
  return "";
}

function renderReviewTab(record) {
  const context = buildMatchReviewContext(record);
  if (!context) {
    $("review-tab-review").innerHTML = `<p class="review-empty">Reviewを表示するデータがありません。</p>`;
    return;
  }

  const review = window.MO_REVIEW_ENGINE?.generateReview?.(context);
  if (!review?.sections?.length) {
    $("review-tab-review").innerHTML = `<p class="review-empty">Reviewを生成できませんでした。</p>`;
    return;
  }

  $("review-tab-review").innerHTML = `
    <div class="review-v2">
      ${review.sections.map(renderReviewSection).join("")}
    </div>
  `;
}

function resolveStateCategoryKey(category) {
  return stateCategoryMap[category] || null;
}

function buildEventsTimeline(record) {
  const events = Array.isArray(record.events) ? record.events : [];
  const history = Array.isArray(record.match?.planHistory) ? record.match.planHistory : [];
  const items = [];

  if (record.match?.kickoff_at) {
    items.push({ sortKey: 0, time: "00:00", label: "Kickoff" });
  }

  history.forEach((entry, index) => {
    if (index === 0) return;
    items.push({
      sortKey: parseMatchTime(entry.matchTime) + index * 0.001,
      time: entry.matchTime || "00:00",
      label: "Plan変更",
    });
  });

  if (record.match?.first_half_end_at) {
    items.push({ sortKey: parseMatchTime("45:00"), time: "45:00", label: "Half Time" });
  }

  events.forEach((event, index) => {
    items.push({
      sortKey: parseMatchTime(event.time) + (index + 1) * 0.0001,
      time: event.time || "00:00",
      label: event.eventName || "イベント",
    });
  });

  if (record.match?.fulltime_at) {
    const lastTime = events.length > 0 ? events[events.length - 1].time : "90:00";
    items.push({
      sortKey: parseMatchTime(lastTime) + 0.5,
      time: lastTime,
      label: "Full Time",
    });
  }

  return items.sort((a, b) => a.sortKey - b.sortKey);
}

function renderEventsTab(record) {
  const items = buildEventsTimeline(record);
  if (items.length === 0) {
    $("review-tab-events").innerHTML = `<p class="review-empty">イベントがありません。</p>`;
    return;
  }

  $("review-tab-events").innerHTML = `
    <ol class="review-events-list">
      ${items.map((item) => `
        <li class="review-event-row">
          <time>${escapeHtml(item.time)}</time>
          <span>${escapeHtml(item.label)}</span>
        </li>
      `).join("")}
    </ol>
  `;
}

function buildMatchDeviationContext(record) {
  return window.MO_REVIEW_DEVIATION?.buildDeviationsFromRecord?.(record) || [];
}

function renderDeviationResultBlock(category) {
  const rows = (category.rows || []).map((row) => `
    <div class="review-deviation-result-row">
      <span class="review-deviation-result-label">${escapeHtml(row.label)}</span>
      <span class="review-deviation-result-value">${escapeHtml(String(row.percent))}%</span>
    </div>
  `).join("");

  return `
    <section class="review-deviation-result-group">
      <h4 class="review-deviation-result-title">${escapeHtml(category.title)}</h4>
      <div class="review-deviation-result-rows">${rows}</div>
    </section>
  `;
}

function renderDeviationPlanCard(segment) {
  const {
    categories = [],
    deviations = [],
    planNumber,
    timeRangeLabel,
    startTime,
    endTime,
  } = segment;
  const periodLabel = timeRangeLabel || `${startTime} ～ ${endTime}`;

  if (categories.length === 0) {
    return `
      <article class="review-deviation-plan-card">
        <header class="review-deviation-plan-card-head">
          <h3 class="review-deviation-plan-card-title">Plan #${planNumber}</h3>
          <p class="review-deviation-plan-card-time">${escapeHtml(periodLabel)}</p>
        </header>
        <p class="review-empty">Attack / Build Up の Plan が設定されていないため、Deviation を表示できません。</p>
      </article>
    `;
  }

  const planRows = categories.map((category) => `
    <div class="review-deviation-plan-row">
      <span class="review-deviation-plan-label">${escapeHtml(category.title)}</span>
      <span class="review-deviation-plan-value">${escapeHtml(category.planLabel)}</span>
    </div>
  `).join("");

  const resultHtml = categories.map(renderDeviationResultBlock).join("");

  const deviationItems = deviations.map((item) => `
    <li class="review-deviation-item review-deviation-item-${escapeHtml(item.status)}">
      ${item.status === "ok" ? "✓" : "🟡"} ${escapeHtml(item.text)}
    </li>
  `).join("");

  const deviationHtml = deviations.length > 0
    ? `<ul class="review-deviation-items">${deviationItems}</ul>`
    : `<p class="review-empty">この Plan 期間の試合データがないため、Deviation を判定できません。</p>`;

  return `
    <article class="review-deviation-plan-card">
      <header class="review-deviation-plan-card-head">
        <h3 class="review-deviation-plan-card-title">Plan #${planNumber}</h3>
        <p class="review-deviation-plan-card-time">${escapeHtml(periodLabel)}</p>
      </header>

      <section class="review-deviation-section">
        <h4 class="review-deviation-heading">Plan</h4>
        <div class="review-deviation-plan">${planRows}</div>
      </section>

      <section class="review-deviation-section">
        <h4 class="review-deviation-heading">Result</h4>
        <div class="review-deviation-results">${resultHtml}</div>
      </section>

      <section class="review-deviation-section">
        <h4 class="review-deviation-heading">Deviation</h4>
        ${deviationHtml}
      </section>
    </article>
  `;
}

function renderDeviationTab(record) {
  const segments = buildMatchDeviationContext(record);
  if (segments.length === 0) {
    $("review-tab-deviation").innerHTML = `<p class="review-empty">Planがありません。</p>`;
    return;
  }

  $("review-tab-deviation").innerHTML = `
    <div class="review-deviation-v2">
      ${segments.map(renderDeviationPlanCard).join('<div class="review-deviation-divider" aria-hidden="true"></div>')}
    </div>
  `;
}

function renderDetailTabs(record) {
  renderMatchTab(record);
  renderPlanTab(record);
  renderReviewTab(record);
  renderEventsTab(record);
  renderDeviationTab(record);
}

function showSearchView() {
  reviewState.selectedId = null;
  $("review-search-view").hidden = false;
  $("review-detail-view").hidden = true;
  if (window.location.hash) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}

function showDetailView(recordId) {
  reviewState.selectedId = recordId;
  const api = getArchiveApi();
  const record = getSelectedRecord();

  if (!record) {
    if (api?.existsForAnyTeam?.(recordId)) {
      window.MO_TEAM_CONTEXT?.denyAccess?.();
      return;
    }
    showSearchView();
    return;
  }

  if (!assertRecordTeamAccess(record)) {
    window.MO_TEAM_CONTEXT?.denyAccess?.();
    return;
  }

  const setup = record.setup || {};
  $("review-detail-title").textContent = `${setup.competition || "試合"} vs ${setup.opponent || "対戦相手"}`;
  $("review-detail-subtitle").textContent = `${formatDisplayDate(setup.match_date)} / Home ${record.match?.home_score ?? 0} - ${record.match?.away_score ?? 0} Away`;

  renderDetailTabs(record);
  $("review-search-view").hidden = true;
  $("review-detail-view").hidden = false;
  history.replaceState(null, "", `#match/${encodeURIComponent(recordId)}`);
  setActiveTab(reviewState.activeTab);
}

function setActiveTab(tabName) {
  reviewState.activeTab = tabName;
  document.querySelectorAll(".review-tab").forEach((button) => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  ["match", "plan", "review", "events", "deviation"].forEach((name) => {
    const panel = $(`review-tab-${name}`);
    if (panel) panel.hidden = name !== tabName;
  });
}

function readFiltersFromForm() {
  reviewState.filters = {
    competition: $("search-competition")?.value.trim() || "",
    opponent: $("search-opponent")?.value.trim() || "",
    match_date: $("search-match-date")?.value || "",
  };
}

function resetFilters() {
  if ($("search-competition")) $("search-competition").value = "";
  if ($("search-opponent")) $("search-opponent").value = "";
  if ($("search-match-date")) $("search-match-date").value = "";
  reviewState.filters = { competition: "", opponent: "", match_date: "" };
}

function bootFromHash() {
  const hash = window.location.hash.replace(/^#/, "");
  const match = hash.match(/^match\/(.+)$/);
  if (!match) {
    showSearchView();
    return;
  }
  showDetailView(decodeURIComponent(match[1]));
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.MO_AUTH_GUARD && !window.MO_AUTH_GUARD.requireAuth()) {
    return;
  }

  refreshRecords();
  renderMatchList();
  bootFromHash();

  $("review-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    readFiltersFromForm();
    refreshRecords();
    renderMatchList();
  });

  $("search-reset")?.addEventListener("click", () => {
    resetFilters();
    refreshRecords();
    renderMatchList();
  });

  $("review-match-list")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-match-id]");
    if (!button) return;
    showDetailView(button.dataset.matchId);
  });

  $("review-back-list")?.addEventListener("click", showSearchView);

  document.querySelectorAll(".review-tab").forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
  });

  $("next-game-plan")?.addEventListener("click", startSameCompetitionNext);
  $("next-match-setup")?.addEventListener("click", startNewCompetition);

  window.addEventListener("hashchange", bootFromHash);
});
