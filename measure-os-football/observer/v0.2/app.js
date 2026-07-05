const state = {
  running: false,
  elapsed: 0,
  timerId: null,
  selectedTeam: "home",
  events: [],
};

const planStorageKey = "measure-os-football:plan:v0.1";
const eventStorageKey = "measure-os-football:observer-events:v0.2";

const planCategoryLabels = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const observationCategories = [
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

function formatTime(seconds) {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function teamLabel(team) {
  return team === "home" ? "Home" : "Away";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderClock() {
  $("clock").textContent = formatTime(state.elapsed);
  $("clock-toggle").textContent = state.running ? "Pause" : "Start";
}

function renderTeamButtons() {
  document.querySelectorAll("[data-team]").forEach((button) => {
    button.classList.toggle("selected", button.dataset.team === state.selectedTeam);
  });
}

function loadConfirmedPlan() {
  let raw = null;
  try {
    raw = window.localStorage.getItem(planStorageKey);
  } catch (_) {
    raw = null;
  }
  if (!raw) return null;
  try {
    const plan = JSON.parse(raw);
    if (!plan || plan.version !== "0.1" || plan.confirmed !== true) return null;
    return plan;
  } catch (_) {
    return null;
  }
}

function renderGamePlan() {
  const plan = loadConfirmedPlan();
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
      button.textContent = eventName;
      button.addEventListener("click", () => recordEvent(eventName));
      grid.appendChild(button);
    });
    section.append(title, grid);
    host.appendChild(section);
  });
}

function loadEvents() {
  let raw = null;
  try {
    raw = window.localStorage.getItem(eventStorageKey);
  } catch (_) {
    raw = null;
  }
  if (!raw) return;
  try {
    const saved = JSON.parse(raw);
    state.events = Array.isArray(saved) ? saved : [];
  } catch (_) {
    state.events = [];
  }
}

function saveEvents() {
  try {
    window.localStorage.setItem(eventStorageKey, JSON.stringify(state.events));
  } catch (_) {
    // Version 0.2 keeps observation local-only. If storage fails, keep the screen usable.
  }
}

function renderTimeline() {
  const timeline = $("timeline");
  timeline.innerHTML = "";
  state.events.forEach((event) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="time">${escapeHtml(event.time)}</span>
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

function renderObservation() {
  renderClock();
  renderTeamButtons();
  renderTimeline();
  renderSavedStatus();
}

function recordEvent(eventName) {
  state.events.push({
    eventName,
    time: formatTime(state.elapsed),
    team: state.selectedTeam,
    inputOrder: state.events.length + 1,
  });
  saveEvents();
  renderObservation();
}

function startClock() {
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

function clearEvents() {
  state.events = [];
  saveEvents();
  renderObservation();
}

document.addEventListener("DOMContentLoaded", () => {
  renderGamePlan();
  renderEventButtons();
  loadEvents();

  document.querySelectorAll("[data-team]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTeam = button.dataset.team;
      renderTeamButtons();
    });
  });

  $("clock-toggle").addEventListener("click", () => {
    if (state.running) pauseClock();
    else startClock();
  });
  $("clock-reset").addEventListener("click", () => {
    pauseClock();
    state.elapsed = 0;
    renderClock();
  });
  $("clear-events").addEventListener("click", clearEvents);

  renderObservation();
});
