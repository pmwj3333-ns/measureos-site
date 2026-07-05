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
const planReturnKey = "measure-os-football:plan-return:v0.3";
const eventStorageKey = "measure-os-football:observer-events:v0.3";
const planPath = "../../plan/v0.1/index.html";

const planCategoryLabels = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const phaseLabels = {
  before_kickoff: "Before Kickoff",
  first_half: "前半 Observation",
  halftime_decision: "ハーフタイム",
  halftime_ready: "後半開始待ち",
  second_half: "後半 Observation",
  fulltime: "試合終了済み",
};

const observationCategories = window.MO_OBSERVATION_CATEGORIES || [
  {
    label: "攻撃",
    events: [
      "中央侵入",
      "左侵入",
      "右侵入",
      "裏抜け",
      "クロス",
      "シュート",
      "決定機",
      "セカンド回収",
      "ボールロスト",
      "前進成功",
    ],
  },
  {
    label: "守備",
    events: [
      "ボール奪取",
      "インターセプト",
      "前線奪取",
      "被中央侵入",
      "被クロス",
      "被シュート",
      "決定機を許す",
      "プレス回避",
    ],
  },
  {
    label: "トランジション",
    events: [
      "即時奪回成功",
      "即時奪回失敗",
      "カウンター開始",
      "カウンター被弾",
    ],
  },
  {
    label: "セットプレー",
    events: ["CK", "FK", "PK", "ロングスロー"],
  },
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
    home_score: 0,
    away_score: 0,
  };
}

function formatTime(seconds) {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
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
    // Version 0.3 is local-only. If storage fails, keep the screen usable.
  }
}

function loadConfirmedPlan() {
  const plan = loadJson(planStorageKey);
  if (!plan || plan.version !== "0.1" || plan.confirmed !== true) return null;
  return plan;
}

function loadMatch() {
  const saved = loadJson(matchStorageKey);
  state.match = saved && saved.match_phase ? saved : createInitialMatch();
  state.match.home_score = Math.max(0, Number(state.match.home_score) || 0);
  state.match.away_score = Math.max(0, Number(state.match.away_score) || 0);
}

function saveMatch() {
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
  if (state.match.match_phase === "second_half" || state.match.match_phase === "fulltime") {
    return state.match.second_half_plan || state.match.first_half_plan || loadConfirmedPlan();
  }
  return state.match.first_half_plan || loadConfirmedPlan();
}

function isObservationOpen() {
  return state.match.match_phase === "first_half" || state.match.match_phase === "second_half";
}

function currentObservationPhaseLabel() {
  return state.match.match_phase === "second_half" ? "後半" : "前半";
}

function renderClock() {
  $("clock").textContent = formatTime(state.elapsed);
  $("phase-label").textContent = phaseLabels[state.match.match_phase] || "Before Kickoff";
}

function renderTeamButtons() {
  document.querySelectorAll("[data-team]").forEach((button) => {
    button.classList.toggle("selected", button.dataset.team === state.selectedTeam);
  });
}

function renderScore() {
  const home = $("home-score");
  const away = $("away-score");
  if (!home || !away) return;
  home.textContent = String(state.match.home_score);
  away.textContent = String(state.match.away_score);
}

function renderGamePlan() {
  const plan = currentPlanForDisplay();
  const empty = $("game-plan-empty");
  const content = $("game-plan-content");
  if (!plan || !plan.categories) {
    empty.hidden = false;
    content.hidden = true;
    content.innerHTML = "";
    return;
  }

  const groups = Object.keys(planCategoryLabels).map((key) => {
    const items = Array.isArray(plan.categories[key]) ? plan.categories[key] : [];
    const body = items.length
      ? `<ul>${items.map((item) => `<li>・${escapeHtml(item)}</li>`).join("")}</ul>`
      : `<p class="game-plan-memo">-</p>`;
    return `
      <section class="game-plan-group">
        <span>${escapeHtml(planCategoryLabels[key])}</span>
        ${body}
      </section>
    `;
  });

  const memo = typeof plan.memo === "string" ? plan.memo.trim() : "";
  groups.push(`
    <section class="game-plan-group">
      <span>Free Memo</span>
      <p class="game-plan-memo">${memo ? escapeHtml(memo) : "-"}</p>
    </section>
  `);

  content.innerHTML = groups.join("");
  content.hidden = false;
  empty.hidden = true;
}

function renderMatchControl() {
  const action = $("match-action");
  const phaseText = $("match-phase-text");
  const halftime = $("halftime-panel");
  const phase = state.match.match_phase;

  action.hidden = false;
  action.disabled = false;
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

function renderObservationLock() {
  const lock = $("observation-lock");
  const locked = !isObservationOpen();
  document.querySelector(".event-panel").classList.toggle("is-locked", locked);
  document.querySelectorAll("[data-event-name]").forEach((button) => {
    button.disabled = locked;
  });
  lock.textContent = locked
    ? "Observation停止中"
    : `${currentObservationPhaseLabel()} Observation中`;
}

function renderEventButtons() {
  const host = $("event-categories");
  host.innerHTML = "";
  observationCategories.forEach((category) => {
    const section = document.createElement("section");
    section.className = "event-category";
    const title = document.createElement("h3");
    title.textContent = category.label;
    const grid = document.createElement("div");
    grid.className = "event-grid";
    category.events.forEach((eventName) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.eventName = eventName;
      button.textContent = eventName;
      button.addEventListener("click", () => recordEvent(eventName));
      grid.appendChild(button);
    });
    section.append(title, grid);
    host.appendChild(section);
  });
}

function renderTimeline() {
  const timeline = $("timeline");
  timeline.innerHTML = "";
  state.events.forEach((event) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="time">${escapeHtml(event.time)}</span>
      <span class="phase">${escapeHtml(event.phase)}</span>
      <span class="team">${escapeHtml(teamLabel(event.team))}</span>
      <span class="event-name">${escapeHtml(event.eventName)}</span>
    `;
    timeline.appendChild(li);
  });
}

function renderSavedStatus() {
  const count = state.events.length;
  $("saved-status").textContent = count > 0 ? `記録 ${count} 件` : "未入力";
}

function renderAll() {
  renderClock();
  renderTeamButtons();
  renderScore();
  renderGamePlan();
  renderMatchControl();
  renderObservationLock();
  renderTimeline();
  renderSavedStatus();
}

function startClock(reset = false) {
  if (reset) state.elapsed = 0;
  if (state.running) return;
  state.running = true;
  state.timerId = window.setInterval(() => {
    state.elapsed += 1;
    renderClock();
  }, 1000);
  renderClock();
}

function pauseClock() {
  state.running = false;
  if (state.timerId != null) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
  renderClock();
}

function handleMatchAction() {
  const phase = state.match.match_phase;
  const plan = loadConfirmedPlan();

  if (phase === "before_kickoff") {
    state.match.kickoff_at = nowIso();
    state.match.match_phase = "first_half";
    state.match.first_half_plan = state.match.first_half_plan || plan;
    state.match.second_half_plan = null;
    saveMatch();
    startClock(true);
  } else if (phase === "first_half") {
    state.match.first_half_end_at = nowIso();
    state.match.match_phase = "halftime_decision";
    saveMatch();
    pauseClock();
  } else if (phase === "halftime_ready") {
    state.match.second_half_start_at = nowIso();
    state.match.match_phase = "second_half";
    state.match.second_half_plan = state.match.second_half_plan || state.match.first_half_plan || plan;
    saveMatch();
    startClock(true);
  } else if (phase === "second_half") {
    state.match.fulltime_at = nowIso();
    state.match.match_phase = "fulltime";
    saveMatch();
    pauseClock();
  }

  renderAll();
}

function continuePlan() {
  state.match.second_half_plan = state.match.first_half_plan || loadConfirmedPlan();
  state.match.match_phase = "halftime_ready";
  saveMatch();
  renderAll();
}

function changePlan() {
  saveJson(planReturnKey, {
    reason: "second_half_plan_change",
    returnTo: window.location.pathname.includes("/v0.5/")
      ? "observer/v0.5"
      : window.location.pathname.includes("/v0.4/")
        ? "observer/v0.4"
        : "observer/v0.3",
  });
  const planUrl = new URL(planPath, window.location.href);
  window.location.assign(planUrl.href);
}

function recordEvent(eventName) {
  if (!isObservationOpen()) return;
  state.events.push({
    eventName,
    time: formatTime(state.elapsed),
    team: state.selectedTeam,
    inputOrder: state.events.length + 1,
    phase: currentObservationPhaseLabel(),
  });
  saveEvents();
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

document.addEventListener("DOMContentLoaded", () => {
  loadMatch();
  loadEvents();
  renderEventButtons();

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
  $("clear-events").addEventListener("click", clearEvents);

  renderAll();
});
