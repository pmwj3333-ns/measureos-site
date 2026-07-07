const state = {
  running: false,
  elapsed: 0,
  timerId: null,
  selectedTeam: "home",
  events: [],
  match: null,
};

const planStorageKey = "measure-os-football:plan:v0.1";
const matchStorageKey = "measure-os-football:match-control:v0.3";
const matchSetupStorageKey = "measure-os-football:match-setup:v1";
const planReturnKey = "measure-os-football:plan-return:v0.3";
const eventStorageKey = "measure-os-football:observer-events:v0.3";
const planPath = "../plan/v0.1/index.html";
const reviewPath = "./review.html";

const planCategoryLabels = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const planDisplayCategories = [
  { key: "attack", label: planCategoryLabels.attack },
  { key: "defense", label: planCategoryLabels.defense },
  { key: "buildUp", label: planCategoryLabels.buildUp },
  { key: "transition", label: planCategoryLabels.transition },
];

const liveStateCategories = [
  { key: "attack", label: "ATTACK", aliases: ["Attack", "attack"] },
  { key: "defense", label: "DEFENSE", aliases: ["Defense", "defense"] },
  { key: "buildUp", label: "BUILD UP", aliases: ["Build Up", "buildUp", "BuildUp"] },
  { key: "transition", label: "TRANSITION", aliases: ["Transition", "transition"] },
];

const attackLiveStateCategories = [
  { key: "attack", label: "ATTACK", aliases: ["Attack", "attack"] },
  { key: "buildUp", label: "BUILD UP", aliases: ["Build Up", "buildUp", "BuildUp"] },
];

const defenseLiveStateCategories = [
  { key: "defense", label: "DEFENSE", aliases: ["Defense", "defense"] },
  { key: "transition", label: "TRANSITION", aliases: ["Transition", "transition"] },
];

const bothLiveStateCategories = [
  { key: "attack", label: "ATTACK", aliases: ["Attack", "attack"] },
  { key: "buildUp", label: "BUILD UP", aliases: ["Build Up", "buildUp", "BuildUp"] },
  { key: "defense", label: "DEFENSE", aliases: ["Defense", "defense"] },
  { key: "transition", label: "TRANSITION", aliases: ["Transition", "transition"] },
];

const observationEventDisplay = {
  左: { icon: "←", label: "左", tier: "intrusion" },
  右: { icon: "→", label: "右", tier: "intrusion" },
  中央: { icon: "↑", label: "中央", tier: "intrusion" },
  背後: { icon: "↗", label: "背後", tier: "behind" },
  被左: { icon: "←", label: "被左", tier: "intrusion" },
  被右: { icon: "→", label: "被右", tier: "intrusion" },
  被中央: { icon: "↑", label: "被中央", tier: "intrusion" },
  被背後: { icon: "↗", label: "被背後", tier: "behind" },
  左侵入: { icon: "←", label: "左", tier: "intrusion" },
  中央侵入: { icon: "↑", label: "中央", tier: "intrusion" },
  右侵入: { icon: "→", label: "右", tier: "intrusion" },
  クロス: { icon: "↗", label: "クロス", tier: "cross" },
  シュート: {
    icon: `<svg class="event-action-svg" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="6" width="14" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="10" cy="11.5" r="1.8" fill="currentColor"/></svg>`,
    label: "シュート",
    tier: "shoot",
    iconHtml: true,
  },
  被左侵入: { icon: "←", label: "左", tier: "intrusion" },
  被中央侵入: { icon: "↑", label: "中央", tier: "intrusion" },
  被右侵入: { icon: "→", label: "右", tier: "intrusion" },
  被クロス: { icon: "↗", label: "クロス", tier: "cross" },
  被シュート: {
    icon: `<svg class="event-action-svg" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="6" width="14" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="10" cy="11.5" r="1.8" fill="currentColor"/></svg>`,
    label: "シュート",
    tier: "shoot",
    iconHtml: true,
  },
  決定機: { icon: "★", label: "決定機", tier: "finish" },
  保持前進: { icon: "⟲", label: "保持前進", tier: "build-up" },
  ロング前進: { icon: "⇢", label: "ロング前進", tier: "build-up" },
  ボール奪取: {
    icon: `<svg class="event-action-svg" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.5 16 5.2v4.8c0 3.8-2.6 6.4-6 7-3.4-.6-6-3.2-6-7V5.2Z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>`,
    label: "奪取",
    tier: "recovery",
    iconHtml: true,
  },
  前線奪取: { icon: "⬆", label: "高奪取", tier: "recovery" },
  即時奪回: { icon: "↺", label: "即時奪回", tier: "transition" },
  リトリート: { icon: "↘", label: "リトリート", tier: "transition" },
  即時奪回成功: { icon: "↺", label: "即奪回", tier: "transition" },
  カウンター開始: { icon: "⇢", label: "カウンター", tier: "transition" },
  カウンター被弾: { icon: "⇠", label: "被カウンター", tier: "transition" },
};

const observationEventDisplayOrder = {
  トランジション: ["カウンター開始", "即時奪回成功", "カウンター被弾"],
};

function getCategoryDisplayEvents(category) {
  return observationEventDisplayOrder[category.label] || category.events;
}

const PLAN_OPTION_RULE_IDS = {
  attack: {
    "左優位": "rule012",
    "右優位": "rule013",
    "中央攻略": "rule014",
    "クロス攻略": "rule015",
    "背後攻略": "rule018",
  },
  defense: {
    "ハイプレス": "rule002",
    "ミドルブロック": "rule016",
    "ローブロック": "rule003",
    "サイド誘導": "rule017",
  },
  buildUp: {
    "保持前進": "rule004",
    "ロング前進": "rule005",
    "サイド前進": "rule006",
    "中央前進": "rule007",
  },
  transition: {
    "即時奪回": "rule008",
    "リトリート": "rule009",
    "縦に速く": "rule010",
    "ボール保持": "rule011",
  },
};

const PLAN_CATEGORY_STATE_LABELS = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const buildUpReasonEventFilter = (event) => [
  "左侵入",
  "中央侵入",
  "右侵入",
  "被左侵入",
  "被中央侵入",
  "被右侵入",
  "カウンター被弾",
  "即時奪回成功",
].includes(event.eventName);

const liveStateReasonEventFilters = {
  rule012: (event) => [
    "left",
    "center",
    "right",
    "behind",
    "shot",
    "bigChance",
    "左侵入",
    "左",
    "中央侵入",
    "中央",
    "右侵入",
    "右",
    "クロス",
    "背後",
    "シュート",
    "決定機",
    "カウンター被弾",
  ].includes(event.eventName),
  rule013: (event) => [
    "right",
    "left",
    "center",
    "behind",
    "shot",
    "bigChance",
    "右侵入",
    "右",
    "左侵入",
    "左",
    "中央侵入",
    "中央",
    "クロス",
    "背後",
    "シュート",
    "決定機",
    "カウンター被弾",
  ].includes(event.eventName),
  rule014: (event) => [
    "center",
    "left",
    "right",
    "behind",
    "shot",
    "bigChance",
    "中央侵入",
    "中央",
    "左侵入",
    "左",
    "右侵入",
    "右",
    "クロス",
    "背後",
    "シュート",
    "決定機",
    "カウンター被弾",
  ].includes(event.eventName),
  rule015: (event) => [
    "クロス",
    "シュート",
    "左侵入",
    "左",
    "中央侵入",
    "中央",
    "右侵入",
    "右",
    "カウンター被弾",
  ].includes(event.eventName),
  rule018: (event) => [
    "behind",
    "shot",
    "bigChance",
    "left",
    "center",
    "right",
    "背後",
    "シュート",
    "決定機",
    "左",
    "中央",
    "右",
  ].includes(event.eventName),
  rule002: (event) => [
    "前線奪取",
    "被中央侵入",
    "被中央",
    "被シュート",
  ].includes(event.eventName),
  rule003: (event) => [
    "被左侵入",
    "被左",
    "被中央侵入",
    "被中央",
    "被右侵入",
    "被右",
    "被クロス",
    "被背後",
    "被シュート",
    "ボール奪取",
  ].includes(event.eventName),
  rule016: (event) => [
    "被中央侵入",
    "被中央",
    "被左侵入",
    "被左",
    "被右侵入",
    "被右",
    "被クロス",
    "被背後",
    "被シュート",
    "ボール奪取",
    "前線奪取",
  ].includes(event.eventName),
  rule017: (event) => [
    "被左侵入",
    "被左",
    "被中央侵入",
    "被中央",
    "被右侵入",
    "被右",
    "被クロス",
    "被背後",
    "被シュート",
    "ボール奪取",
    "前線奪取",
  ].includes(event.eventName),
  rule004: buildUpReasonEventFilter,
  rule005: buildUpReasonEventFilter,
  rule006: (event) => [
    "左侵入",
    "右侵入",
    "中央侵入",
    "被左侵入",
    "被右侵入",
    "被中央侵入",
    "カウンター被弾",
    "即時奪回成功",
  ].includes(event.eventName),
  rule007: (event) => [
    "中央侵入",
    "被中央侵入",
    "左侵入",
    "右侵入",
    "被左侵入",
    "被右侵入",
    "カウンター被弾",
    "即時奪回成功",
  ].includes(event.eventName),
  rule008: (event) => [
    "即時奪回成功",
    "即時奪回",
    "カウンター開始",
    "カウンター被弾",
  ].includes(event.eventName),
  rule009: (event) => [
    "被中央侵入",
    "被中央",
    "被シュート",
    "カウンター被弾",
    "ボール奪取",
    "被左侵入",
    "被左",
    "被右侵入",
    "被右",
    "被背後",
    "リトリート",
  ].includes(event.eventName),
  rule010: (event) => [
    "カウンター開始",
    "左侵入",
    "中央侵入",
    "右侵入",
    "シュート",
    "カウンター被弾",
    "即時奪回成功",
  ].includes(event.eventName),
  rule011: (event) => [
    "左侵入",
    "中央侵入",
    "右侵入",
    "カウンター被弾",
    "即時奪回成功",
    "カウンター開始",
    "シュート",
  ].includes(event.eventName),
};

let liveStateSnapshot = {
  evaluatedAt: null,
  plan: null,
  events: [],
  elapsed: 0,
  states: [],
};
let selectedLiveStateRuleId = null;
let confirmedLiveStatesByRuleId = {};

const MINI_REVIEW_PLACEHOLDER = "--";

const phaseLabels = {
  before_kickoff: "試合前",
  first_half: "前半",
  halftime_decision: "ハーフタイム",
  halftime_ready: "ハーフタイム",
  second_half: "後半",
  fulltime: "試合終了",
};

const observationCategories = window.MO_OBSERVATION_CATEGORIES || [];
const attackObservationCategories = window.MO_OBSERVATION_CATEGORIES_ATTACK || [];
const defenseObservationCategories = window.MO_OBSERVATION_CATEGORIES_DEFENSE || [];
const bothObservationCategories = window.MO_OBSERVATION_CATEGORIES_BOTH || [];
let analyzeMode = "both";
const matchEvents = [
  { eventName: "Home イエロー", team: "Home", type: "yellow", icon: "■" },
  { eventName: "Away イエロー", team: "Away", type: "yellow", icon: "■" },
  { eventName: "Home レッド", team: "Home", type: "red", icon: "■" },
  { eventName: "Away レッド", team: "Away", type: "red", icon: "■" },
  { eventName: "Home 交代", team: "Home", type: "substitution", icon: "↔" },
  { eventName: "Away 交代", team: "Away", type: "substitution", icon: "↔" },
  { eventName: "Home 負傷交代", team: "Home", type: "injury", icon: "＋" },
  { eventName: "Away 負傷交代", team: "Away", type: "injury", icon: "＋" },
];
const $ = (id) => document.getElementById(id);

function createInitialMatch() {
  return {
    kickoff_at: null,
    first_half_end_at: null,
    second_half_start_at: null,
    fulltime_at: null,
    match_phase: "before_kickoff",
    first_half_plan: null,
    second_half_plan: null,
    currentPlan: null,
    planHistory: [],
    home_score: 0,
    away_score: 0,
    elapsedSeconds: 0,
    firstHalfMiniReview: null,
  };
}

function formatTime(seconds) {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function parseMatchTime(timeValue) {
  const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
  if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
  return Math.max(0, minutes * 60 + seconds);
}

function getLastEventElapsed(events) {
  if (!Array.isArray(events) || events.length === 0) return 0;
  return events.reduce((max, event) => Math.max(max, parseMatchTime(event.time)), 0);
}

function getEvaluationElapsed(events) {
  const clockElapsed = Math.max(0, Number(state.elapsed) || 0);
  const lastEventElapsed = getLastEventElapsed(events);
  return Math.max(clockElapsed, lastEventElapsed);
}

function syncMatchElapsed() {
  if (!state.match) return;
  state.match.elapsedSeconds = Math.max(0, Number(state.elapsed) || 0);
}

function isLiveStateDebugEnabled() {
  try {
    return window.localStorage.getItem("measure-os-football:live-state-debug") === "1";
  } catch (_) {
    return false;
  }
}

function debugLiveState(label, payload) {
  if (!isLiveStateDebugEnabled()) return;
  console.log(`[LIVE STATE] ${label}`, payload);
}

function teamLabel(team) {
  if (team === "Home" || team === "Away") return team;
  return team === "home" ? "Home" : "Away";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function resolveObserverEventDef(eventName, categoryKey = null) {
  const normalizedCode = String(eventName || "");
  if (categoryKey) {
    const bothDef = window.MO_BOTH_OBSERVER?.getEventDef?.(normalizedCode, categoryKey);
    if (bothDef) return bothDef;
    const defenseDef = window.MO_DEFENSE_OBSERVER?.getEventDef?.(normalizedCode, categoryKey);
    if (defenseDef) return defenseDef;
    const attackDef = window.MO_ATTACK_OBSERVER?.getEventDef?.(normalizedCode);
    if (attackDef?.categoryKey === categoryKey) return attackDef;
    return null;
  }

  if (isBothAnalyzeMode()) {
    return window.MO_BOTH_OBSERVER?.getEventDef?.(normalizedCode) || null;
  }

  const attackDef = window.MO_ATTACK_OBSERVER?.getEventDef?.(normalizedCode);
  const defenseDef = window.MO_DEFENSE_OBSERVER?.getEventDef?.(normalizedCode);
  if (attackDef && defenseDef) {
    return isDefenseAnalyzeMode() ? defenseDef : attackDef;
  }
  return attackDef || defenseDef || null;
}

function getObservationEventDisplay(eventName, categoryKey = null) {
  const catalogDef = resolveObserverEventDef(eventName, categoryKey);
  if (catalogDef) {
    return {
      icon: catalogDef.iconHtml || catalogDef.icon || "•",
      label: catalogDef.label,
      tier: catalogDef.tier || "default",
      iconHtml: Boolean(catalogDef.iconHtml),
    };
  }

  return (
    observationEventDisplay[eventName] || {
      icon: "•",
      label: eventName,
      tier: "default",
    }
  );
}

function formatStoredEventName(eventName, event = null) {
  const code = event?.observerEventCode || eventName;
  const categoryKey = event?.eventCategory || null;
  const catalogDef = resolveObserverEventDef(code, categoryKey);
  if (catalogDef) return catalogDef.label;

  return getObservationEventDisplay(eventName, categoryKey).label || eventName;
}

function renderObservationEventIcon(display) {
  if (display.iconHtml) {
    return `<span class="event-action-icon event-action-icon-svg">${display.icon}</span>`;
  }
  return `<span class="event-action-icon" aria-hidden="true">${escapeHtml(display.icon)}</span>`;
}

function appendReservedObservationSlots(grid, count) {
  for (let index = 0; index < count; index += 1) {
    const slot = document.createElement("div");
    slot.className = "event-action-slot event-action-slot--reserved";
    slot.setAttribute("aria-hidden", "true");
    grid.appendChild(slot);
  }
}

function createCatalogObservationEventButton(eventDef, categoryKey) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-action-button";
  button.dataset.eventName = eventDef.code;
  button.dataset.eventCode = eventDef.code;
  button.dataset.eventCategory = categoryKey;
  button.dataset.eventTier = eventDef.tier || "default";
  button.setAttribute("aria-label", eventDef.label);

  const iconMarkup = eventDef.iconHtml
    ? `<span class="event-action-icon event-action-icon-svg">${eventDef.iconHtml}</span>`
    : `<span class="event-action-icon" aria-hidden="true">${escapeHtml(eventDef.icon || "•")}</span>`;

  button.innerHTML = `
    ${iconMarkup}
    <span class="event-action-label">${escapeHtml(eventDef.label)}</span>
  `;
  button.addEventListener("click", () => recordEvent(eventDef.code, button));
  return button;
}

function renderObserverCatalogCategories(host, catalog) {
  if (!catalog || !host) return;

  catalog.getCategories().forEach((category) => {
    const section = document.createElement("section");
    section.className = "event-category event-category--attack-mode";
    section.dataset.category = category.label;
    section.dataset.categoryKey = category.key;

    const title = document.createElement("h3");
    title.textContent = category.label;

    if (category.subtitle) {
      const subtitle = document.createElement("p");
      subtitle.className = "event-category-subtitle";
      subtitle.textContent = category.subtitle;
      section.append(title, subtitle);
    } else {
      section.append(title);
    }

    const grid = document.createElement("div");
    const isPitchGrid = category.layout === "pitch";
    grid.className = isPitchGrid
      ? "event-grid event-grid-pitch event-grid-attack-pitch"
      : "event-grid event-grid-attack-slots";
    grid.style.setProperty("--event-grid-columns", String(category.gridColumns || 4));

    category.eventDefs.forEach((eventDef) => {
      grid.appendChild(createCatalogObservationEventButton(eventDef, category.key));
    });
    appendReservedObservationSlots(grid, category.reservedSlots || 0);

    section.appendChild(grid);
    host.appendChild(section);
  });
}

function createObservationEventButton(eventName, onClick) {
  const display = getObservationEventDisplay(eventName);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-action-button";
  button.dataset.eventName = eventName;
  button.dataset.eventTier = display.tier;
  button.setAttribute("aria-label", eventName);
  button.innerHTML = `
    ${renderObservationEventIcon(display)}
    <span class="event-action-label">${escapeHtml(display.label)}</span>
  `;
  button.addEventListener("click", onClick);
  return button;
}

function nowIso() {
  return new Date().toISOString();
}

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
  } catch (_) {
    // Observer is local-only for now. If storage fails, keep the screen usable.
  }
}

function removeJson(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (_) {
    // Ignore storage errors in the local prototype.
  }
}

function loadAnalyzeMode() {
  const setup = loadJson(matchSetupStorageKey);
  const plan = normalizePlanSnapshot(loadJson(planStorageKey))
    || normalizePlanSnapshot(state.match?.currentPlan);
  const mode = plan?.analyzeMode || setup?.analyzeMode;
  analyzeMode = mode === "attack" || mode === "defense" || mode === "both" ? mode : "both";
}

function isAttackAnalyzeMode() {
  return analyzeMode === "attack";
}

function isDefenseAnalyzeMode() {
  return analyzeMode === "defense";
}

function isBothAnalyzeMode() {
  return analyzeMode === "both";
}

function getActiveObservationCategories() {
  if (isAttackAnalyzeMode()) return attackObservationCategories;
  if (isDefenseAnalyzeMode()) return defenseObservationCategories;
  if (isBothAnalyzeMode()) return bothObservationCategories;
  return observationCategories;
}

function getActivePlanDisplayCategories() {
  if (isAttackAnalyzeMode()) {
    return [
      { key: "attack", label: planCategoryLabels.attack },
      { key: "buildUp", label: planCategoryLabels.buildUp },
    ];
  }
  if (isDefenseAnalyzeMode()) {
    return [
      { key: "defense", label: planCategoryLabels.defense },
      { key: "transition", label: planCategoryLabels.transition },
    ];
  }
  return planDisplayCategories;
}

function getActiveLiveStateCategories() {
  if (isAttackAnalyzeMode()) return attackLiveStateCategories;
  if (isDefenseAnalyzeMode()) return defenseLiveStateCategories;
  if (isBothAnalyzeMode()) return bothLiveStateCategories;
  return liveStateCategories;
}

function applyAnalyzeModeUi() {
  document.body.dataset.analyzeMode = analyzeMode;

  const hiddenMiniReviewKeys = isAttackAnalyzeMode()
    ? new Set(["defense", "transition", "setPiece"])
    : isDefenseAnalyzeMode()
      ? new Set(["attack", "buildUp", "setPiece"])
      : new Set();

  document.querySelectorAll("[data-mini-review-key]").forEach((row) => {
    const key = row.dataset.miniReviewKey;
    row.hidden = hiddenMiniReviewKeys.has(key);
  });
}

function normalizePlanSnapshot(raw) {
  return window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot(raw) ?? null;
}

function clonePlanSnapshot(raw) {
  return window.MO_PLAN_SNAPSHOT?.clonePlanSnapshot(raw) ?? null;
}

function isValidPlanSnapshot(plan) {
  return window.MO_PLAN_SNAPSHOT?.isValidPlanSnapshot(plan) ?? false;
}

function resolvePlanForDisplay() {
  return currentPlanForDisplay();
}

function formatPlanSelections(items) {
  if (!Array.isArray(items) || items.length === 0) return "-";
  return items.map((item) => escapeHtml(item)).join("、");
}

function loadMatch() {
  const saved = loadJson(matchStorageKey);
  state.match = saved && saved.match_phase ? saved : createInitialMatch();
  state.match.home_score = Math.max(0, Number(state.match.home_score) || 0);
  state.match.away_score = Math.max(0, Number(state.match.away_score) || 0);
  state.elapsed = Math.max(0, Number(state.match.elapsedSeconds) || 0);
  migrateMatchPlanFields();
}

function restoreElapsedFromEventsIfNeeded() {
  if (state.elapsed > 0) return;
  const inferred = getLastEventElapsed(state.events);
  if (inferred <= 0) return;
  state.elapsed = inferred;
  syncMatchElapsed();
  saveMatch();
}

function sanitizeStoredPlans() {
  let changed = false;

  const normalizedCurrent = normalizePlanSnapshot(state.match.currentPlan);
  if (state.match.currentPlan !== normalizedCurrent) {
    state.match.currentPlan = normalizedCurrent;
    changed = true;
  }

  const normalizedFirstHalf = normalizePlanSnapshot(state.match.first_half_plan);
  if (state.match.first_half_plan !== normalizedFirstHalf) {
    state.match.first_half_plan = normalizedFirstHalf;
    changed = true;
  }

  const normalizedSecondHalf = normalizePlanSnapshot(state.match.second_half_plan);
  if (state.match.second_half_plan !== normalizedSecondHalf) {
    state.match.second_half_plan = normalizedSecondHalf;
    changed = true;
  }

  const storedPlan = loadJson(planStorageKey);
  const normalizedStored = normalizePlanSnapshot(storedPlan);
  if (!normalizedStored) {
    if (storedPlan != null) {
      removeJson(planStorageKey);
      changed = true;
    }
  } else if (JSON.stringify(storedPlan) !== JSON.stringify(normalizedStored)) {
    saveJson(planStorageKey, normalizedStored);
    changed = true;
  }

  if (Array.isArray(state.match.planHistory)) {
    const sanitizedHistory = state.match.planHistory
      .map((entry) => {
        const plan = normalizePlanSnapshot(entry?.plan);
        if (!plan) return null;
        return { ...entry, plan };
      })
      .filter(Boolean);

    if (JSON.stringify(state.match.planHistory) !== JSON.stringify(sanitizedHistory)) {
      state.match.planHistory = sanitizedHistory;
      changed = true;
    }
  }

  if (changed) saveMatch();
}

function migrateMatchPlanFields() {
  if (!Array.isArray(state.match.planHistory)) {
    state.match.planHistory = [];
  }

  sanitizeStoredPlans();

  if (!state.match.currentPlan && state.match.kickoff_at) {
    const activeHalfPlan =
      state.match.match_phase === "second_half" || state.match.match_phase === "fulltime"
        ? state.match.second_half_plan
        : state.match.first_half_plan;
    const migrated = clonePlanSnapshot(activeHalfPlan);
    if (migrated) {
      state.match.currentPlan = migrated;
      saveMatch();
    }
  }

  if (
    state.match.planHistory.length === 0 &&
    state.match.kickoff_at &&
    isValidPlanSnapshot(state.match.currentPlan)
  ) {
    const entry = createPlanHistoryEntry({
      plan: state.match.currentPlan,
      matchTime: "00:00",
      elapsedSeconds: 0,
      phase: "前半",
      changedAt: state.match.kickoff_at,
      reason: "initial",
      eventBoundaryIndex: 0,
    });
    if (entry) {
      appendPlanHistoryEntry(entry);
      saveMatch();
    }
  }
}

function createPlanHistoryEntry({
  plan,
  matchTime,
  elapsedSeconds,
  phase,
  changedAt,
  reason,
  eventBoundaryIndex,
}) {
  const normalizedPlan = clonePlanSnapshot(plan);
  if (!normalizedPlan) return null;

  return {
    plan: normalizedPlan,
    matchTime: matchTime || "00:00",
    elapsedSeconds: Number(elapsedSeconds) || 0,
    phase: phase || "",
    changedAt: changedAt || nowIso(),
    reason: reason || "mid_match",
    eventBoundaryIndex: Number(eventBoundaryIndex) || 0,
  };
}

function appendPlanHistoryEntry(entry) {
  if (!entry) return;
  if (!Array.isArray(state.match.planHistory)) {
    state.match.planHistory = [];
  }
  state.match.planHistory.push(entry);
}

function getPlanEvaluationBoundaryIndex() {
  const history = state.match.planHistory;
  if (!Array.isArray(history) || history.length === 0) return 0;
  const last = history[history.length - 1];
  return Number(last.eventBoundaryIndex) || 0;
}

function getEventsForStateEvaluation() {
  const boundaryIndex = getPlanEvaluationBoundaryIndex();
  return state.events.slice(boundaryIndex);
}

function saveMatch() {
  syncMatchElapsed();
  saveJson(matchStorageKey, state.match);
}

function loadEvents() {
  const saved = loadJson(eventStorageKey);
  state.events = Array.isArray(saved) ? saved : [];
}

function saveEvents() {
  saveJson(eventStorageKey, state.events);
}

function currentPlanForDisplay() {
  return normalizePlanSnapshot(state.match.currentPlan);
}

function isObservationOpen() {
  return state.match.match_phase === "first_half" || state.match.match_phase === "second_half";
}

function isMatchEventOpen() {
  return state.match.match_phase !== "before_kickoff" && state.match.match_phase !== "fulltime";
}

function currentObservationPhaseLabel() {
  return state.match.match_phase === "second_half" ? "後半" : "前半";
}

function renderClock() {
  $("clock").textContent = formatTime(state.elapsed);
  $("phase-label").textContent = phaseLabels[state.match.match_phase] || "試合前";
}

function renderTeamButtons() {
  document.querySelectorAll("[data-team]").forEach((button) => {
    button.classList.toggle("selected", button.dataset.team === state.selectedTeam);
  });
}

function renderScore() {
  $("home-score").textContent = String(state.match.home_score);
  $("away-score").textContent = String(state.match.away_score);
  $("home-score-mini").textContent = String(state.match.home_score);
  $("away-score-mini").textContent = String(state.match.away_score);
  document.querySelectorAll("[data-score-team]").forEach((button) => {
    button.disabled = state.match.match_phase === "fulltime";
  });
}

function getCurrentPlanNumber() {
  const history = state.match.planHistory;
  if (Array.isArray(history) && history.length > 0) {
    return history.length;
  }
  if (isValidPlanSnapshot(state.match.currentPlan)) {
    return 1;
  }
  return null;
}

function getCurrentPlanEffectiveMatchTime() {
  const history = state.match.planHistory;
  if (Array.isArray(history) && history.length > 0) {
    return history[history.length - 1].matchTime || "00:00";
  }
  return null;
}

function renderCurrentPlanCardHead({ planNumber = null, effectiveTime = null } = {}) {
  const planNumberLine = planNumber
    ? `<p class="current-plan-number">Plan #${planNumber}</p>`
    : "";
  const timeLine = effectiveTime
    ? `<p class="current-plan-effective-time">開始 ${escapeHtml(effectiveTime)}</p>`
    : "";

  return `
    <header class="current-plan-card-head">
      <h3 class="current-plan-card-title">Current Plan</h3>
      ${planNumberLine}
      ${timeLine}
    </header>
  `;
}

function renderGamePlan() {
  const plan = resolvePlanForDisplay();
  const empty = $("game-plan-empty");
  const content = $("game-plan-content");
  if (!empty || !content) return;

  if (!plan) {
    empty.innerHTML = `
      ${renderCurrentPlanCardHead()}
      <p class="current-plan-empty-title">Planが設定されていません</p>
      <button type="button" id="setup-game-plan" class="current-plan-setup-button">Game Planを設定</button>
    `;
    empty.hidden = false;
    content.hidden = true;
    content.innerHTML = "";
    return;
  }

  const groups = getActivePlanDisplayCategories().map(({ key, label }) => {
    const items = Array.isArray(plan.categories[key]) ? plan.categories[key] : [];
    const value = formatPlanSelections(items);
    return `
      <section class="current-plan-row">
        <p class="current-plan-row-label">${escapeHtml(label)}</p>
        <p class="current-plan-row-value">${value}</p>
      </section>
    `;
  });

  const memo = typeof plan.memo === "string" ? plan.memo.trim() : "";
  if (memo) {
    groups.push(`
      <section class="current-plan-row current-plan-row-memo">
        <p class="current-plan-row-label">Free Memo</p>
        <p class="current-plan-row-value">${escapeHtml(memo)}</p>
      </section>
    `);
  }

  content.innerHTML = `
    ${renderCurrentPlanCardHead({
      planNumber: getCurrentPlanNumber(),
      effectiveTime: getCurrentPlanEffectiveMatchTime(),
    })}
    <div class="game-plan-popover-content">
      ${groups.join("")}
    </div>
  `;
  content.hidden = false;
  empty.hidden = true;
}

function isPlanChangeOpen() {
  return state.match.match_phase !== "fulltime";
}

function renderPlanChangeButton() {
  const button = $("change-plan-action");
  if (!button) return;
  button.disabled = !isPlanChangeOpen();
}

function isCurrentPlanPopoverOpen() {
  const popover = $("current-plan-popover");
  return Boolean(popover && !popover.hidden);
}

function setCurrentPlanPopoverOpen(open) {
  const toggle = $("current-plan-toggle");
  const popover = $("current-plan-popover");
  const icon = toggle?.querySelector(".current-plan-toggle-icon");
  if (!toggle || !popover) return;

  popover.hidden = !open;
  toggle.setAttribute("aria-expanded", open ? "true" : "false");
  if (icon) icon.textContent = open ? "▲" : "▼";
}

function toggleCurrentPlanPopover() {
  setCurrentPlanPopoverOpen(!isCurrentPlanPopoverOpen());
}

function closeCurrentPlanPopover() {
  if (!isCurrentPlanPopoverOpen()) return;
  setCurrentPlanPopoverOpen(false);
}

function bindCurrentPlanPopover() {
  const toggle = $("current-plan-toggle");
  const popover = $("current-plan-popover");
  const controls = document.querySelector(".game-plan-controls");
  if (!toggle || !popover) return;

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleCurrentPlanPopover();
  });

  popover.addEventListener("click", (event) => {
    event.stopPropagation();
    if (event.target.closest("#setup-game-plan")) {
      openGamePlanSetup();
    }
  });

  controls?.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.addEventListener("click", () => {
    closeCurrentPlanPopover();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCurrentPlanPopover();
  });
}

function renderMatchControl() {
  const action = $("match-action");
  const phaseText = $("match-phase-text");
  const halftime = $("halftime-panel");
  const control = action.closest(".match-control");
  const phase = state.match.match_phase;

  action.hidden = false;
  action.disabled = false;
  control.hidden = phase === "halftime_decision";
  halftime.hidden = phase !== "halftime_decision";

  if (phase === "before_kickoff") {
    action.textContent = "キックオフ";
    phaseText.textContent = "Game Plan 確定後、キックオフから観測を開始します。";
  } else if (phase === "first_half") {
    action.textContent = "前半終了";
    phaseText.textContent = "前半 Observation 中です。";
  } else if (phase === "halftime_decision") {
    action.hidden = true;
    phaseText.textContent = "前半終了。イベント入力を停止しています。";
  } else if (phase === "halftime_ready") {
    action.textContent = "後半開始";
    phaseText.textContent = "後半開始待ちです。";
  } else if (phase === "second_half") {
    action.textContent = "試合終了";
    phaseText.textContent = "後半 Observation 中です。";
  } else {
    action.textContent = "試合終了済み";
    action.disabled = true;
    phaseText.textContent = "試合ライフサイクルは終了しています。";
  }
}

function renderPostMatch() {
  const isFulltime = state.match.match_phase === "fulltime";
  const panel = $("post-match-panel");
  if (!panel) return;
  panel.hidden = !isFulltime;
  if (!isFulltime) return;

  const timeEl = $("post-match-time");
  const scoreEl = $("post-match-score");
  const home = Math.max(0, Number(state.match.home_score) || 0);
  const away = Math.max(0, Number(state.match.away_score) || 0);
  if (timeEl) timeEl.textContent = formatTime(state.elapsed);
  if (scoreEl) scoreEl.textContent = `Home ${home} - ${away} Away`;
}

function renderObservationLock() {
  const locked = !isObservationOpen();
  document.querySelector(".dashboard-panel--manual-input.event-panel")?.classList.toggle("is-locked", locked);
  document.querySelector(".dashboard-panel--set-piece.event-panel")?.classList.toggle("is-locked", locked);
  document.querySelectorAll(
    ".dashboard-panel--manual-input [data-event-name], .dashboard-panel--set-piece [data-event-name]",
  ).forEach((button) => {
    button.disabled = locked;
  });
  const lock = $("observation-lock");
  if (!lock) return;
  lock.textContent = locked
    ? phaseLabels[state.match.match_phase] || "試合前"
    : `${currentObservationPhaseLabel()} Observation中`;
}

function renderMatchEventsLock() {
  const locked = !isMatchEventOpen();
  document.querySelector(".match-events-panel").classList.toggle("is-locked", locked);
  document.querySelectorAll("[data-match-event]").forEach((button) => {
    button.disabled = locked;
  });
}

const SET_PIECE_CATEGORY = {
  label: "セットプレー",
  layout: "team-split",
  events: ["CK", "FK", "PK", "決定機"],
};

function getSetPieceCategory() {
  const categories = isAttackAnalyzeMode() || isDefenseAnalyzeMode() || isBothAnalyzeMode()
    ? observationCategories
    : getActiveObservationCategories();
  return categories.find((category) => category.layout === "team-split") || SET_PIECE_CATEGORY;
}

function renderSetPieceButtons() {
  const host = $("set-piece-categories");
  if (!host) return;
  host.innerHTML = "";
  host.appendChild(renderSetPieceCategory(getSetPieceCategory()));
}

function renderSetPieceCategory(category) {
  const section = document.createElement("section");
  section.className = "event-category event-category-set-piece";
  section.dataset.category = category.label;

  const title = document.createElement("h3");
  title.textContent = category.label;

  const columns = document.createElement("div");
  columns.className = "set-piece-columns";

  [
    { team: "home", label: "Home" },
    { team: "away", label: "Away" },
  ].forEach(({ team, label }) => {
    const block = document.createElement("section");
    block.className = `set-piece-team-block is-${team}`;

    const teamLabel = document.createElement("p");
    teamLabel.className = "set-piece-team-label";
    teamLabel.textContent = label;

    const grid = document.createElement("div");
    grid.className = "set-piece-grid";
    grid.dataset.eventCount = String(category.events.length);

    category.events.forEach((eventName) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "set-piece-button";
      button.dataset.eventName = eventName;
      button.dataset.eventTeam = team;
      button.textContent = eventName;
      button.addEventListener("click", () => recordEvent(eventName, button, team));
      grid.appendChild(button);
    });

    block.append(teamLabel, grid);
    columns.appendChild(block);
  });

  section.append(title, columns);
  return section;
}

function renderEventButtons() {
  const host = $("event-categories");
  host.innerHTML = "";

  if (isAttackAnalyzeMode() && window.MO_ATTACK_OBSERVER) {
    renderObserverCatalogCategories(host, window.MO_ATTACK_OBSERVER);
    return;
  }

  if (isDefenseAnalyzeMode() && window.MO_DEFENSE_OBSERVER) {
    renderObserverCatalogCategories(host, window.MO_DEFENSE_OBSERVER);
    return;
  }

  if (isBothAnalyzeMode() && window.MO_BOTH_OBSERVER) {
    renderObserverCatalogCategories(host, window.MO_BOTH_OBSERVER);
    return;
  }

  getActiveObservationCategories().forEach((category) => {
    if (category.layout === "team-split") {
      return;
    }

    const section = document.createElement("section");
    section.className = "event-category";
    section.dataset.category = category.label;
    const title = document.createElement("h3");
    title.textContent = category.label;
    const grid = document.createElement("div");
    const isPitchGrid = category.label === "攻撃"
      || category.label === "守備"
      || category.label === "Attack"
      || category.label === "Defense";
    grid.className = isPitchGrid ? "event-grid event-grid-pitch" : "event-grid";
    getCategoryDisplayEvents(category).forEach((eventName) => {
      const button = createObservationEventButton(eventName, () => recordEvent(eventName, button));
      grid.appendChild(button);
    });
    section.append(title, grid);
    host.appendChild(section);
  });
}

function renderMatchEventButtons() {
  const host = $("match-events");
  host.innerHTML = "";
  ["Home", "Away"].forEach((team) => {
    const column = document.createElement("section");
    column.className = "match-event-column";
    const title = document.createElement("h3");
    title.textContent = team;
    const list = document.createElement("div");
    list.className = "match-event-list";
    matchEvents
      .filter((event) => event.team === team)
      .forEach((event) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.matchEvent = event.eventName;
        button.dataset.eventType = event.type;
        button.innerHTML = `
          <span class="match-event-icon" aria-hidden="true">${escapeHtml(event.icon)}</span>
          <span>${escapeHtml(event.eventName.replace(`${team} `, ""))}</span>
        `;
        button.addEventListener("click", () => recordMatchEvent(event, button));
        list.appendChild(button);
      });
    column.append(title, list);
    host.appendChild(column);
  });
}

function renderTimeline() {
  const timeline = $("timeline");
  const emptyState = $("event-log-empty");
  if (!timeline) return;

  const events = state.events;

  if (events.length === 0) {
    timeline.innerHTML = "";
    timeline.hidden = true;
    if (emptyState) emptyState.hidden = false;
    return;
  }

  timeline.hidden = false;
  if (emptyState) emptyState.hidden = true;

  timeline.innerHTML = "";
  events.forEach((event) => {
    const li = document.createElement("li");
    li.className = "timeline-live-row";
    li.innerHTML = `
      <span class="timeline-live-time">${escapeHtml(event.time)}</span>
      <span class="timeline-live-label">${escapeHtml(formatStoredEventName(event.eventName, event))}</span>
    `;
    timeline.appendChild(li);
  });

  const logBody = timeline.closest(".event-log-body");
  if (logBody) {
    logBody.scrollTop = logBody.scrollHeight;
  }
}

function renderSavedStatus() {
  const countEl = $("event-log-count");
  if (!countEl) return;
  countEl.textContent = `${state.events.length}件`;
}

function resolveLiveStateCategoryKey(category, planCategoryKey) {
  const categories = getActiveLiveStateCategories();
  if (planCategoryKey && categories.some((item) => item.key === planCategoryKey)) {
    return planCategoryKey;
  }

  const normalized = String(category || "").trim();
  if (!normalized) return null;

  const matched = categories.find((item) => item.aliases.includes(normalized));
  if (matched) return matched.key;

  const lower = normalized.toLowerCase();
  if (lower === "build up" || lower === "buildup") return "buildUp";

  return categories.find((item) => item.key.toLowerCase() === lower)?.key || null;
}

function groupLiveStatesByCategory(liveStates) {
  const grouped = new Map(getActiveLiveStateCategories().map((category) => [category.key, []]));
  liveStates.forEach((item) => {
    const key = resolveLiveStateCategoryKey(item.category, item.planCategoryKey);
    if (!key || !grouped.has(key)) return;
    grouped.get(key).push(item);
  });
  return grouped;
}

function resetConfirmedLiveStates() {
  confirmedLiveStatesByRuleId = {};
}

function readPlanCategoryOptions(plan, categoryKey) {
  if (window.MO_STATE_ENGINE?.readPlanCategory) {
    return window.MO_STATE_ENGINE.readPlanCategory(plan, categoryKey);
  }
  const items = plan?.categories?.[categoryKey];
  return Array.isArray(items) ? items : [];
}

function resolveRuleIdForPlanOption(categoryKey, planOption) {
  return PLAN_OPTION_RULE_IDS[categoryKey]?.[planOption] ?? null;
}

function createPlanDefaultLiveState(categoryKey, planOption) {
  const ruleId = resolveRuleIdForPlanOption(categoryKey, planOption);
  if (!ruleId) return null;

  return {
    ruleId,
    planCategoryKey: categoryKey,
    category: PLAN_CATEGORY_STATE_LABELS[categoryKey] || categoryKey,
    planOption,
    label: `🟢 ${planOption}`,
    status: "green",
    source: "plan",
  };
}

function updateConfirmedLiveStatesFromRuleResults(ruleResults) {
  if (!Array.isArray(ruleResults)) return;

  ruleResults.forEach((item) => {
    if (!item?.ruleId) return;
    confirmedLiveStatesByRuleId[item.ruleId] = {
      ...item,
      source: "rule",
    };
  });
}

function buildLiveStateDisplayByCategory(plan) {
  const categories = getActiveLiveStateCategories();
  const grouped = new Map(categories.map((category) => [category.key, []]));
  if (!plan) return grouped;

  categories.forEach(({ key: categoryKey }) => {
    readPlanCategoryOptions(plan, categoryKey).forEach((planOption) => {
      const ruleId = resolveRuleIdForPlanOption(categoryKey, planOption);
      if (!ruleId) return;

      const displayState = confirmedLiveStatesByRuleId[ruleId]
        ?? createPlanDefaultLiveState(categoryKey, planOption);
      if (displayState) grouped.get(categoryKey).push(displayState);
    });
  });

  return grouped;
}

function flattenGroupedLiveStates(groupedStates) {
  return getActiveLiveStateCategories().flatMap(({ key }) => groupedStates.get(key) || []);
}

function renderLiveStateValue(items) {
  if (!items.length) {
    return `<span class="live-state-empty-value">--</span>`;
  }

  return items.map((item) => `
    <button
      type="button"
      class="live-state-label${selectedLiveStateRuleId === item.ruleId ? " is-selected" : ""}"
      data-rule-id="${escapeHtml(item.ruleId)}"
      data-status="${escapeHtml(item.status)}"
    >${escapeHtml(item.label)}</button>
  `).join("");
}

function formatPlanForDetail(plan) {
  if (!plan?.categories) return "-";

  return liveStateCategories.map((category) => {
    const items = Array.isArray(plan.categories[category.key]) ? plan.categories[category.key] : [];
    const label = planCategoryLabels[category.key] || category.label;
    return `${label}: ${items.length ? items.join(" / ") : "-"}`;
  }).join(" ｜ ");
}

function getReasonEvents(ruleId, events) {
  const filter = liveStateReasonEventFilters[ruleId];
  if (typeof filter !== "function") return [];
  return events.filter(filter);
}

function formatReasonEventsDetail(liveState) {
  if (liveState.reasonEventCounts) {
    return Object.entries(liveState.reasonEventCounts)
      .map(([eventName, count]) => `${eventName} ${count}`)
      .join(" ｜ ");
  }

  const reasonEvents = getReasonEvents(liveState.ruleId, liveStateSnapshot.events);
  if (reasonEvents.length === 0) return "0";

  const counts = new Map();
  reasonEvents.forEach((event) => {
    counts.set(event.eventName, (counts.get(event.eventName) || 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([eventName, count]) => `${eventName} ${count}`)
    .join(" ｜ ");
}

function formatGeneratedTime(iso) {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function findLiveStateByRuleId(ruleId) {
  return liveStateSnapshot.states.find((item) => item.ruleId === ruleId) || null;
}

function renderLiveStateDetail() {
  const panel = $("live-state-detail");
  if (!panel) return;

  const liveState = findLiveStateByRuleId(selectedLiveStateRuleId);
  if (!liveState) {
    panel.hidden = true;
    panel.innerHTML = "";
    return;
  }

  panel.hidden = false;
  panel.innerHTML = `
    <div class="live-state-detail-head">
      <h3>State Detail</h3>
      <button type="button" id="close-live-state-detail" class="live-state-detail-close">閉じる</button>
    </div>
    <dl class="live-state-detail-list">
      <div class="live-state-detail-item">
        <dt>Current Plan</dt>
        <dd>${escapeHtml(formatPlanForDetail(liveStateSnapshot.plan))}</dd>
      </div>
      <div class="live-state-detail-item">
        <dt>State</dt>
        <dd>${escapeHtml(liveState.label)}</dd>
      </div>
      <div class="live-state-detail-item">
        <dt>Reason Events</dt>
        <dd>${escapeHtml(formatReasonEventsDetail(liveState))}</dd>
      </div>
      <div class="live-state-detail-item">
        <dt>Generated Time</dt>
        <dd>${escapeHtml(formatGeneratedTime(liveStateSnapshot.evaluatedAt))}</dd>
      </div>
    </dl>
  `;

  $("close-live-state-detail")?.addEventListener("click", closeLiveStateDetail);
}

function openLiveStateDetail(ruleId) {
  selectedLiveStateRuleId = ruleId;
  renderLiveState();
  renderLiveStateDetail();
}

function closeLiveStateDetail() {
  selectedLiveStateRuleId = null;
  renderLiveState();
  renderLiveStateDetail();
}

function enrichLiveStateForExplain(liveState, plan) {
  if (!liveState?.ruleId || liveState.planOption) return liveState;

  for (const { key: categoryKey } of liveStateCategories) {
    for (const planOption of readPlanCategoryOptions(plan, categoryKey)) {
      if (resolveRuleIdForPlanOption(categoryKey, planOption) === liveState.ruleId) {
        return { ...liveState, planOption, planCategoryKey: categoryKey };
      }
    }
  }

  return liveState;
}

function renderLiveStateExplain(items, context, plan) {
  const buildExplain = window.MO_LIVE_STATE_EXPLAIN?.buildLiveStateExplainLine;
  const pickPrimary = window.MO_LIVE_STATE_EXPLAIN?.pickPrimaryLiveStateItem;
  if (typeof buildExplain !== "function") return "--";

  const primary = typeof pickPrimary === "function" ? pickPrimary(items) : items[0];
  const enriched = enrichLiveStateForExplain(primary, plan);
  return buildExplain(enriched, context, {
    getReasonEvents,
  });
}

function renderLiveState() {
  const host = $("live-state-content");
  if (!host) return;

  const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;
  const plan = currentPlanForDisplay();
  const events = getEventsForStateEvaluation();
  const evaluationElapsed = getEvaluationElapsed(events);
  const ruleResults = typeof evaluate === "function"
    ? evaluate({ plan, events, elapsed: evaluationElapsed })
    : [];

  updateConfirmedLiveStatesFromRuleResults(ruleResults);

  const groupedStates = buildLiveStateDisplayByCategory(plan);
  const displayStates = flattenGroupedLiveStates(groupedStates);

  liveStateSnapshot = {
    evaluatedAt: nowIso(),
    plan,
    events,
    elapsed: evaluationElapsed,
    states: displayStates,
  };

  if (selectedLiveStateRuleId && !findLiveStateByRuleId(selectedLiveStateRuleId)) {
    selectedLiveStateRuleId = null;
  }

  debugLiveState("evaluate", {
    clockElapsed: state.elapsed,
    evaluationElapsed,
    eventCount: events.length,
    boundaryIndex: getPlanEvaluationBoundaryIndex(),
    planCategories: plan?.categories ?? null,
    ruleResultCount: ruleResults.length,
    ruleResults: ruleResults.map((item) => ({
      ruleId: item.ruleId,
      category: item.category,
      planCategoryKey: item.planCategoryKey,
      label: item.label,
    })),
    displayStateCount: displayStates.length,
    displayStates: displayStates.map((item) => ({
      ruleId: item.ruleId,
      source: item.source,
      label: item.label,
      status: item.status,
    })),
    grouped: Object.fromEntries(
      liveStateCategories.map(({ key }) => [key, (groupedStates.get(key) || []).length]),
    ),
  });

  host.innerHTML = getActiveLiveStateCategories().map((category) => {
    const items = groupedStates.get(category.key) || [];
    const explainLine = renderLiveStateExplain(items, {
      events,
      elapsed: evaluationElapsed,
    }, plan);
    return `
      <article class="live-state-row" data-category="${escapeHtml(category.key)}">
        <span class="live-state-row-label">${escapeHtml(category.label)}</span>
        <div class="live-state-row-value">${renderLiveStateValue(items)}</div>
        <p class="live-state-explain">${escapeHtml(explainLine)}</p>
      </article>
    `;
  }).join("");

  renderLiveStateDetail();
}

function calculateMiniReview() {
  const plan = normalizePlanSnapshot(state.match?.first_half_plan)
    || currentPlanForDisplay();
  const calculator = window.MO_MINI_REVIEW?.calculateMiniReview;

  if (typeof calculator !== "function") {
    return {
      formatVersion: 3,
      plan: { text: "プランおおむね維持", tone: "neutral" },
      flow: { text: "拮抗した前半", tone: "neutral" },
      attack: { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" },
      defense: { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" },
      buildUp: { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" },
      transition: { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" },
      setPiece: { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" },
      generatedAt: nowIso(),
    };
  }

  return calculator({
    plan,
    events: state.events,
    liveStatesByRuleId: confirmedLiveStatesByRuleId,
    generatedAt: nowIso(),
  });
}

function isLegacyMiniReviewSnapshot(snapshot) {
  const check = window.MO_MINI_REVIEW?.isLegacyMiniReviewSnapshot;
  if (typeof check === "function") {
    return check(snapshot);
  }

  if (!snapshot || typeof snapshot !== "object") return false;
  return Number(snapshot.formatVersion) !== 3;
}

function refreshMiniReviewSnapshotIfNeeded() {
  if (!state.match?.first_half_end_at) return;

  if (!state.match.firstHalfMiniReview || isLegacyMiniReviewSnapshot(state.match.firstHalfMiniReview)) {
    state.match.firstHalfMiniReview = calculateMiniReview();
    saveMatch();
  }
}

function resetFirstHalfMiniReview() {
  if (!state.match) return;
  state.match.firstHalfMiniReview = null;
}

function generateFirstHalfMiniReview() {
  if (!state.match) return null;
  refreshMiniReviewSnapshotIfNeeded();
  return state.match.firstHalfMiniReview;
}

function ensureFirstHalfMiniReviewForRestoredMatch() {
  refreshMiniReviewSnapshotIfNeeded();
}

function normalizeMiniReviewEntry(value) {
  const normalize = window.MO_MINI_REVIEW?.normalizeMiniReviewEntry;
  if (typeof normalize === "function") {
    const entry = normalize(value);
    return {
      text: entry.text || MINI_REVIEW_PLACEHOLDER,
      tone: entry.tone || "neutral",
    };
  }

  if (!value) {
    return { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" };
  }

  if (typeof value === "string") {
    return { text: value, tone: "neutral" };
  }

  return {
    text: value.text || MINI_REVIEW_PLACEHOLDER,
    tone: value.tone || "neutral",
  };
}

function renderMiniReview() {
  refreshMiniReviewSnapshotIfNeeded();
  const snapshot = state.match?.firstHalfMiniReview;
  document.querySelectorAll("[data-mini-review-key]").forEach((row) => {
    const key = row.dataset.miniReviewKey;
    const valueEl = row.querySelector(".mini-review-value");
    if (!key || !valueEl) return;

    const entry = normalizeMiniReviewEntry(snapshot?.[key]);
    valueEl.textContent = entry.text;
    valueEl.classList.remove("is-positive", "is-negative", "is-neutral");
    valueEl.classList.add(`is-${entry.tone}`);
  });
}

function renderAll() {
  renderClock();
  renderTeamButtons();
  renderScore();
  renderGamePlan();
  renderPlanChangeButton();
  renderMatchControl();
  renderPostMatch();
  renderObservationLock();
  renderMatchEventsLock();
  renderTimeline();
  renderSavedStatus();
  renderLiveState();
  renderMiniReview();
}

function startClock(reset = false) {
  if (reset) {
    state.elapsed = 0;
    syncMatchElapsed();
  }
  if (state.running) return;
  state.running = true;
  state.timerId = window.setInterval(() => {
    state.elapsed += 1;
    syncMatchElapsed();
    renderClock();
    renderLiveState();
  }, 1000);
  renderClock();
}

function pauseClock() {
  state.running = false;
  if (state.timerId != null) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
  syncMatchElapsed();
  saveMatch();
  renderClock();
}

function resumeClockIfNeeded() {
  const phase = state.match?.match_phase;
  if (phase === "first_half" || phase === "second_half") {
    startClock(false);
  }
}

function handleMatchAction() {
  const phase = state.match.match_phase;

  if (phase === "before_kickoff") {
    const kickoffPlan = clonePlanSnapshot(state.match.currentPlan);
    if (!kickoffPlan) return;
    resetConfirmedLiveStates();
    resetFirstHalfMiniReview();
    state.match.kickoff_at = nowIso();
    state.match.match_phase = "first_half";
    state.match.first_half_plan = kickoffPlan;
    state.match.second_half_plan = null;
    state.match.currentPlan = kickoffPlan;
    if (!Array.isArray(state.match.planHistory) || state.match.planHistory.length === 0) {
      const entry = createPlanHistoryEntry({
        plan: kickoffPlan,
        matchTime: "00:00",
        elapsedSeconds: 0,
        phase: "前半",
        changedAt: state.match.kickoff_at,
        reason: "initial",
        eventBoundaryIndex: 0,
      });
      if (entry) appendPlanHistoryEntry(entry);
    }
    saveMatch();
    startClock(true);
  } else if (phase === "first_half") {
    state.match.first_half_end_at = nowIso();
    state.match.match_phase = "halftime_decision";
    generateFirstHalfMiniReview();
    saveMatch();
    pauseClock();
  } else if (phase === "halftime_ready") {
    const secondHalfPlan = clonePlanSnapshot(state.match.currentPlan);
    if (!secondHalfPlan) return;
    state.match.second_half_start_at = nowIso();
    state.match.match_phase = "second_half";
    state.match.second_half_plan = secondHalfPlan;
    state.match.currentPlan = secondHalfPlan;
    saveMatch();
    startClock(true);
  } else if (phase === "second_half") {
    state.match.fulltime_at = nowIso();
    state.match.match_phase = "fulltime";
    saveMatch();
    pauseClock();
    archiveMatchForReviewIfNeeded();
  }

  renderAll();
}

function continuePlan() {
  const plan = clonePlanSnapshot(state.match.currentPlan);
  if (!plan) return;
  state.match.second_half_plan = plan;
  state.match.currentPlan = plan;
  state.match.match_phase = "halftime_ready";
  saveMatch();
  renderAll();
}

function openGamePlanSetup() {
  closeCurrentPlanPopover();
  const planUrl = new URL(planPath, window.location.href);
  window.location.assign(planUrl.href);
}

function openPlanChange(options = {}) {
  const reason = options.reason || "mid_match_plan_change";
  const current = clonePlanSnapshot(state.match.currentPlan);
  if (current) {
    saveJson(planStorageKey, current);
  }
  saveJson(planReturnKey, {
    reason,
    returnTo: "observer",
    matchTime: formatTime(state.elapsed),
    elapsedSeconds: state.elapsed,
    phase: currentObservationPhaseLabel() || phaseLabels[state.match.match_phase] || "",
    eventBoundaryIndex: state.events.length,
    matchPhase: state.match.match_phase,
  });
  const planUrl = new URL(planPath, window.location.href);
  window.location.assign(planUrl.href);
}

function changePlan() {
  openPlanChange({ reason: "halftime_plan_change" });
}

function flashEventButton(button) {
  if (!button) return;
  button.classList.remove("is-feedback");
  void button.offsetWidth;
  button.classList.add("is-feedback");
  window.setTimeout(() => {
    button.classList.remove("is-feedback");
  }, 180);
}

function recordEvent(eventName, button, teamOverride) {
  if (!isObservationOpen()) return;

  const categoryKey = button?.dataset?.eventCategory || null;
  const eventDef = resolveObserverEventDef(eventName, categoryKey);
  const storedEventName = eventDef?.code || eventName;

  state.events.push({
    eventName: storedEventName,
    observerEventCode: eventDef?.code || null,
    eventCategory: categoryKey || eventDef?.categoryKey || null,
    time: formatTime(state.elapsed),
    team: teamOverride ?? state.selectedTeam,
    inputOrder: state.events.length + 1,
    phase: currentObservationPhaseLabel(),
  });
  saveEvents();
  flashEventButton(button);
  renderAll();
}

function recordMatchEvent(event, button) {
  if (!isMatchEventOpen()) return;
  state.events.push({
    eventName: event.eventName,
    time: formatTime(state.elapsed),
    team: event.team,
    inputOrder: state.events.length + 1,
    phase: phaseLabels[state.match.match_phase] || currentObservationPhaseLabel(),
  });
  saveEvents();
  flashEventButton(button);
  renderAll();
}

function recordGoalEvent(team) {
  const label = teamLabel(team);
  state.events.push({
    eventName: `${label} Goal`,
    time: formatTime(state.elapsed),
    team: label,
    inputOrder: state.events.length + 1,
    phase: currentObservationPhaseLabel(),
  });
  saveEvents();
}

function updateScore(team, delta) {
  const key = team === "home" ? "home_score" : "away_score";
  const current = Math.max(0, Number(state.match[key]) || 0);
  if (delta > 0) {
    state.match[key] = current + 1;
    recordGoalEvent(team);
  } else {
    state.match[key] = Math.max(0, current - 1);
  }
  saveMatch();
  renderAll();
}

function clearEvents() {
  state.events = [];
  saveEvents();
  renderAll();
}

function archiveMatchForReviewIfNeeded() {
  window.MO_REVIEW_ARCHIVE?.upsertFromLiveStorage?.();
}

function openReview() {
  archiveMatchForReviewIfNeeded();
  window.location.assign(reviewPath);
}

document.addEventListener("DOMContentLoaded", () => {
  loadMatch();
  loadEvents();
  loadAnalyzeMode();
  restoreElapsedFromEventsIfNeeded();
  ensureFirstHalfMiniReviewForRestoredMatch();
  resumeClockIfNeeded();
  applyAnalyzeModeUi();
  const manualInputPanel = document.querySelector(".dashboard-panel--manual-input");
  if (manualInputPanel) manualInputPanel.open = false;
  renderSetPieceButtons();
  renderEventButtons();
  renderMatchEventButtons();

  document.querySelectorAll("[data-team]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTeam = button.dataset.team;
      renderTeamButtons();
    });
  });

  document.querySelectorAll("[data-score-team]").forEach((button) => {
    button.addEventListener("click", () => {
      updateScore(button.dataset.scoreTeam, Number(button.dataset.scoreDelta));
    });
  });

  $("match-action").addEventListener("click", handleMatchAction);
  $("continue-plan").addEventListener("click", continuePlan);
  $("change-plan").addEventListener("click", changePlan);
  $("change-plan-action")?.addEventListener("click", (event) => {
    event.stopPropagation();
    closeCurrentPlanPopover();
    openPlanChange();
  });
  $("open-review").addEventListener("click", openReview);
  const clearButton = $("clear-events");
  if (clearButton) clearButton.addEventListener("click", clearEvents);

  $("live-state-content")?.addEventListener("click", (event) => {
    const button = event.target.closest(".live-state-label");
    if (!button?.dataset.ruleId) return;
    openLiveStateDetail(button.dataset.ruleId);
  });

  bindCurrentPlanPopover();
  renderAll();
});
