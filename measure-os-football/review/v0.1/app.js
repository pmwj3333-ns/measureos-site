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

function hydrateNextMatchSection() {
  const competition = resolveCompetitionSource() || "-";
  const display = $("next-competition-display");
  if (display) display.textContent = competition === "" ? "-" : competition;
}

function showNextMatchError(message) {
  let error = document.getElementById("review-next-match-error");
  if (!error) {
    error = document.createElement("p");
    error.id = "review-next-match-error";
    error.className = "review-next-error";
    $("next-same-competition")?.before(error);
  }
  error.textContent = message;
  error.hidden = !message;
}

function startSameCompetitionNext() {
  const competition = resolveCompetitionSource();
  const opponent = $("next-opponent")?.value.trim() || "";
  const matchDate = $("next-match-date")?.value || "";
  const kickoffTime = $("next-kickoff-time")?.value || "";

  if (!competition) {
    showNextMatchError("大会名がありません。新しい大会を開始してください。");
    return;
  }
  if (!opponent || !matchDate || !kickoffTime) {
    showNextMatchError("対戦相手・試合日・キックオフを入力してください。");
    return;
  }

  showNextMatchError("");
  archiveCurrentMatchIfNeeded();

  const teamId = getActiveTeamId();
  if (!teamId) return;

  const previousSetup = readStorage(setupStorageKey) || {};
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

function renderStateLayer(segment) {
  const categories = getReviewLiveStateCategories(segment.plan).map(({ key, label }) => {
    const items = segment.states
      .filter((state) => resolveStateCategoryKey(state.category) === key)
      .map((state) => `
        <li class="review-state-point">
          <time>${escapeHtml(segment.endTime)}</time>
          <p class="review-status-${escapeHtml(state.status || "green")}">${escapeHtml(state.label)}</p>
        </li>
      `)
      .join("");

    return `
      <div class="review-state-category">
        <h4>${escapeHtml(label)}</h4>
        ${items
          ? `<ol class="review-state-timeline">${items}</ol>`
          : `<p class="review-empty">Stateなし</p>`}
      </div>
    `;
  }).join("");

  return `
    <section class="review-layer-block" data-layer="state">
      <h3 class="review-layer-title">State</h3>
      ${categories || `<p class="review-empty">Stateなし</p>`}
    </section>
  `;
}

function renderReasonLayer(segment) {
  const reasonResults = segment.reasonResults || [];
  if (reasonResults.length === 0) {
    return `
      <section class="review-layer-block" data-layer="reason">
        <h3 class="review-layer-title">Reason</h3>
        <p class="review-empty">Reasonなし</p>
      </section>
    `;
  }

  const summariesByCategory = new Map();
  reasonResults.forEach((reason) => {
    if (!reason?.summary || !reason.ruleId) return;
    const state = segment.states.find((item) => item.ruleId === reason.ruleId);
    const categoryKey = state?.planCategoryKey || resolveCategoryKeyForRuleId(reason.ruleId);
    if (!categoryKey) return;
    if (!summariesByCategory.has(categoryKey)) {
      summariesByCategory.set(categoryKey, []);
    }
    summariesByCategory.get(categoryKey).push(reason);
  });

  const categories = getReviewLiveStateCategories(segment.plan)
    .filter(({ key }) => (summariesByCategory.get(key) || []).length > 0)
    .map(({ key, label }) => {
      const summaries = summariesByCategory.get(key)
        .map((reason) => `
          <li class="review-reason-point">
            <time>${escapeHtml(segment.endTime)}</time>
            <p class="review-reason-summary">${escapeHtml(reason.summary)}</p>
          </li>
        `)
        .join("");

      return `
        <div class="review-reason-category">
          <h4>${escapeHtml(label)}</h4>
          <ol class="review-reason-timeline">${summaries}</ol>
        </div>
      `;
    })
    .join("");

  return `
    <section class="review-layer-block" data-layer="reason">
      <h3 class="review-layer-title">Reason</h3>
      ${categories || `<p class="review-empty">Reasonなし</p>`}
    </section>
  `;
}

function renderCompositeReasonLayer(segment) {
  const composite = segment.compositeReason;
  if (!composite?.summary) {
    return `
      <section class="review-layer-block" data-layer="composite">
        <h3 class="review-layer-title">Composite Reason</h3>
        <p class="review-empty">Composite Reasonなし</p>
      </section>
    `;
  }

  return `
    <section class="review-layer-block" data-layer="composite">
      <h3 class="review-layer-title">Composite Reason</h3>
      <article class="review-composite-point">
        <time>${escapeHtml(segment.endTime)}</time>
        <div class="review-composite-body">
          <p class="review-composite-short review-status-${escapeHtml(composite.severity || "green")}">${escapeHtml(composite.shortSummary || "-")}</p>
          <p class="review-composite-summary">${escapeHtml(composite.summary)}</p>
        </div>
      </article>
    </section>
  `;
}

function resolveStateCategoryKey(category) {
  return stateCategoryMap[category] || null;
}

function buildPlanSegments(record) {
  const events = Array.isArray(record.events) ? record.events : [];
  const history = Array.isArray(record.match?.planHistory) ? record.match.planHistory : [];
  const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;

  return history
    .map((entry, index) => {
      const plan = normalizePlanSnapshot(entry.plan);
      if (!plan) return null;

      const boundary = Number(entry.eventBoundaryIndex) || 0;
      const sliceEnd = history[index + 1]?.eventBoundaryIndex ?? events.length;
      const segmentEvents = events.slice(boundary, sliceEnd);
      const lastEvent = segmentEvents[segmentEvents.length - 1];
      const elapsed = lastEvent ? parseMatchTime(lastEvent.time) : parseMatchTime(entry.matchTime);
      const states = typeof evaluate === "function"
        ? evaluate({ plan, events: segmentEvents, elapsed })
        : [];
      const reasonResults = buildReasonResults(states, plan, { elapsed });
      const compositeReason = buildCompositeReason(reasonResults, plan);

      const nextEntry = history[index + 1];
      const endTime = nextEntry?.matchTime || (lastEvent?.time ?? entry.matchTime);

      return {
        planNumber: index + 1,
        startTime: entry.matchTime || "00:00",
        endTime,
        elapsed,
        plan,
        states,
        reasonResults,
        compositeReason,
      };
    })
    .filter(Boolean);
}

function renderStateTab(record) {
  const segments = buildPlanSegments(record);
  if (segments.length === 0) {
    $("review-tab-state").innerHTML = `<p class="review-empty">State推移を表示するデータがありません。</p>`;
    return;
  }

  $("review-tab-state").innerHTML = segments.map((segment) => `
    <section class="review-segment-block">
      <p class="review-segment-head">Plan #${segment.planNumber}（${escapeHtml(segment.startTime)} 〜 ${escapeHtml(segment.endTime)}）</p>
      ${renderStateLayer(segment)}
      ${renderReasonLayer(segment)}
      ${renderCompositeReasonLayer(segment)}
    </section>
  `).join("");
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

function computeDeviationsBySegment(record) {
  const segments = buildPlanSegments(record);
  const deviationStatuses = new Set(["yellow", "orange", "red"]);

  return segments.map((segment) => ({
    planNumber: segment.planNumber,
    startTime: segment.startTime,
    endTime: segment.endTime,
    items: segment.states
      .filter((state) => deviationStatuses.has(state.status))
      .map((state) => ({
        category: state.category,
        label: state.label,
        status: state.status,
        time: segment.endTime,
      })),
  }));
}

function renderDeviationTab(record) {
  const segments = computeDeviationsBySegment(record);
  const hasDeviations = segments.some((segment) => segment.items.length > 0);

  if (!hasDeviations) {
    $("review-tab-deviation").innerHTML = `
      <p class="review-empty">Yellow / Orange / Red の Deviation は検出されませんでした。Plan 区間ごとのズレはここに表示されます。</p>
    `;
    return;
  }

  $("review-tab-deviation").innerHTML = segments
    .filter((segment) => segment.items.length > 0)
    .map((segment) => `
      <section class="review-deviation-segment review-segment-block">
        <h3>Plan #${segment.planNumber}（${escapeHtml(segment.startTime)} 〜 ${escapeHtml(segment.endTime)}）</h3>
        <ol class="review-deviation-list">
          ${segment.items.map((item) => `
            <li class="review-deviation-row">
              <time>${escapeHtml(item.time)}</time>
              <span class="review-status-${escapeHtml(item.status)}">${escapeHtml(item.category)} — ${escapeHtml(item.label)}</span>
            </li>
          `).join("")}
        </ol>
      </section>
    `)
    .join("");
}

function renderDetailTabs(record) {
  renderMatchTab(record);
  renderPlanTab(record);
  renderStateTab(record);
  renderEventsTab(record);
  renderDeviationTab(record);
}

function showSearchView() {
  reviewState.selectedId = null;
  $("review-search-view").hidden = false;
  $("review-detail-view").hidden = true;
  hydrateNextMatchSection();
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
  hydrateNextMatchSection();
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

  ["match", "plan", "state", "events", "deviation"].forEach((name) => {
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
  hydrateNextMatchSection();
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

  $("next-same-competition")?.addEventListener("click", startSameCompetitionNext);
  $("next-new-competition")?.addEventListener("click", startNewCompetition);

  window.addEventListener("hashchange", bootFromHash);
});
