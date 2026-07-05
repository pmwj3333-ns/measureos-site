const state = {
  running: false,
  elapsed: 0,
  timerId: null,
  selectedTeam: "home",
  selectedEvent: "press",
  events: [],
};

const eventLabels = {
  press: "Press",
  recover: "Recover",
  progress: "Progress",
  entry: "Box Entry",
  shot: "Shot",
  loss: "Loss",
};

const planStorageKey = "measure-os-football:plan:v0.1";
const planCategoryLabels = {
  attack: "Attack",
  defense: "Defense",
  buildUp: "Build Up",
  transition: "Transition",
};

const $ = (id) => document.getElementById(id);

function formatTime(seconds) {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function teamLabel(team) {
  const value = team === "home" ? $("home-team").value : $("away-team").value;
  return String(value || (team === "home" ? "Home" : "Away")).trim();
}

function renderClock() {
  $("clock").textContent = formatTime(state.elapsed);
  $("phase-label").textContent = $("phase").value;
  $("clock-toggle").textContent = state.running ? "Pause" : "Start";
}

function renderTeamLabels() {
  $("home-label").textContent = teamLabel("home");
  $("away-label").textContent = teamLabel("away");
}

function renderEventButtons() {
  document.querySelectorAll("[data-event]").forEach((button) => {
    button.classList.toggle("active", button.dataset.event === state.selectedEvent);
  });
}

function renderTeamButtons() {
  document.querySelectorAll("[data-team]").forEach((button) => {
    button.classList.toggle("selected", button.dataset.team === state.selectedTeam);
  });
}

function computeMomentum() {
  const recent = state.events.slice(0, 5);
  if (!recent.length) return "Neutral";
  const home = recent.filter((event) => event.team === "home").length;
  const away = recent.filter((event) => event.team === "away").length;
  if (home === away) return "Neutral";
  return home > away ? teamLabel("home") : teamLabel("away");
}

function renderDashboard() {
  const home = state.events.filter((event) => event.team === "home").length;
  const away = state.events.filter((event) => event.team === "away").length;
  $("home-count").textContent = String(home);
  $("away-count").textContent = String(away);
  $("total-count").textContent = String(state.events.length);
  $("last-event").textContent = state.events[0]
    ? eventLabels[state.events[0].type] || state.events[0].type
    : "-";
  $("momentum").textContent = computeMomentum();
}

function renderTimeline() {
  const timeline = $("timeline");
  timeline.innerHTML = "";
  state.events.forEach((event) => {
    const li = document.createElement("li");
    const note = event.note
      ? `<div class="note">${escapeHtml(event.note)}</div>`
      : "";
    li.innerHTML = `
      <span class="time">${escapeHtml(event.time)}</span>
      <span class="team">${escapeHtml(teamLabel(event.team))}</span>
      <span>
        <span class="event">${escapeHtml(eventLabels[event.type] || event.type)}</span>
        ${note}
      </span>
    `;
    timeline.appendChild(li);
  });
}

function renderAll() {
  renderClock();
  renderTeamLabels();
  renderEventButtons();
  renderTeamButtons();
  renderDashboard();
  renderTimeline();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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

function recordEvent() {
  const note = $("note").value.trim();
  state.events.unshift({
    team: state.selectedTeam,
    type: state.selectedEvent,
    note,
    time: formatTime(state.elapsed),
    phase: $("phase").value,
    createdAt: new Date().toISOString(),
  });
  $("note").value = "";
  renderAll();
}

document.addEventListener("DOMContentLoaded", () => {
  renderGamePlan();

  $("clock-toggle").addEventListener("click", () => {
    if (state.running) pauseClock();
    else startClock();
  });

  $("clock-reset").addEventListener("click", () => {
    pauseClock();
    state.elapsed = 0;
    renderClock();
  });

  $("phase").addEventListener("change", renderClock);
  $("home-team").addEventListener("input", renderAll);
  $("away-team").addEventListener("input", renderAll);

  document.querySelectorAll("[data-team]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTeam = button.dataset.team;
      renderTeamButtons();
    });
  });

  document.querySelectorAll("[data-event]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedEvent = button.dataset.event;
      renderEventButtons();
    });
  });

  $("record-event").addEventListener("click", recordEvent);
  $("clear-note").addEventListener("click", () => {
    $("note").value = "";
  });
  $("clear-events").addEventListener("click", () => {
    state.events = [];
    renderAll();
  });

  renderAll();
});
