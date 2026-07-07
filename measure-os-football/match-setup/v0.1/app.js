const storageKey = "measure-os-football:match-setup:v1";
const planPath = "../../plan/v0.1/index.html";

const PRESET_FORMATIONS = new Set(["4-4-2", "4-3-3", "4-2-3-1", "3-4-2-1", "3-5-2"]);
const ANALYZE_MODES = new Set(["attack", "defense", "both"]);

const form = document.getElementById("match-setup-form");
const competitionInput = document.getElementById("competition");
const opponentInput = document.getElementById("opponent");
const matchDateInput = document.getElementById("match-date");
const kickoffTimeInput = document.getElementById("kickoff-time");
const formationSelect = document.getElementById("formation");
const formationCustomInput = document.getElementById("formation-custom");
const sideHomeButton = document.getElementById("side-home");
const sideAwayButton = document.getElementById("side-away");
const analyzeModeButtons = document.querySelectorAll("[data-analyze-mode]");
const setupStatus = document.getElementById("setup-status");
const nextButton = document.getElementById("next-button");

const errorElements = {
  opponent: document.getElementById("opponent-error"),
  match_date: document.getElementById("match-date-error"),
  kickoff_time: document.getElementById("kickoff-time-error"),
  home_away: document.getElementById("home-away-error"),
};

let selectedHomeAway = "";
let selectedAnalyzeMode = "both";

function generateMatchId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
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

function setHomeAway(side) {
  selectedHomeAway = side === "home" || side === "away" ? side : "";
  sideHomeButton.setAttribute("aria-pressed", selectedHomeAway === "home" ? "true" : "false");
  sideAwayButton.setAttribute("aria-pressed", selectedHomeAway === "away" ? "true" : "false");
  updateStatus();
}

function setAnalyzeMode(mode) {
  selectedAnalyzeMode = ANALYZE_MODES.has(mode) ? mode : "both";
  analyzeModeButtons.forEach((button) => {
    const isSelected = button.dataset.analyzeMode === selectedAnalyzeMode;
    button.setAttribute("aria-pressed", isSelected ? "true" : "false");
  });
}

function resolveFormationValue() {
  const selected = formationSelect.value.trim();
  if (!selected) return "";
  if (selected === "other") {
    return formationCustomInput.value.trim();
  }
  return selected;
}

function syncFormationCustomVisibility() {
  const isOther = formationSelect.value === "other";
  formationCustomInput.hidden = !isOther;
  if (!isOther) {
    formationCustomInput.value = "";
  }
}

function populateFormationSelect(formationValue) {
  const value = String(formationValue || "").trim();
  if (!value) {
    formationSelect.value = "";
    formationCustomInput.value = "";
    syncFormationCustomVisibility();
    return;
  }
  if (PRESET_FORMATIONS.has(value)) {
    formationSelect.value = value;
    formationCustomInput.value = "";
  } else {
    formationSelect.value = "other";
    formationCustomInput.value = value;
  }
  syncFormationCustomVisibility();
}

function restoreDraft() {
  const saved = readStorage(storageKey);
  if (!saved) return;

  competitionInput.value = saved.competition || "";
  opponentInput.value = saved.opponent || "";
  matchDateInput.value = saved.match_date || "";
  kickoffTimeInput.value = saved.kickoff_time || "";
  setHomeAway(saved.home_away || "");
  setAnalyzeMode(saved.analyzeMode || "both");
  populateFormationSelect(saved.formation || "");
}

function clearErrors() {
  Object.values(errorElements).forEach((element) => {
    element.hidden = true;
  });
}

function showError(key) {
  if (errorElements[key]) {
    errorElements[key].hidden = false;
  }
}

function validateForm() {
  clearErrors();
  let isValid = true;

  if (!opponentInput.value.trim()) {
    showError("opponent");
    isValid = false;
  }
  if (!matchDateInput.value) {
    showError("match_date");
    isValid = false;
  }
  if (!kickoffTimeInput.value) {
    showError("kickoff_time");
    isValid = false;
  }
  if (!selectedHomeAway) {
    showError("home_away");
    isValid = false;
  }

  return isValid;
}

function buildMatchSetupSnapshot() {
  return {
    match_id: generateMatchId(),
    competition: competitionInput.value.trim(),
    opponent: opponentInput.value.trim(),
    match_date: matchDateInput.value,
    kickoff_time: kickoffTimeInput.value,
    home_away: selectedHomeAway,
    formation: resolveFormationValue(),
    analyzeMode: selectedAnalyzeMode,
    match_created_at: new Date().toISOString(),
  };
}

function updateStatus() {
  const opponent = opponentInput.value.trim();
  const hasRequired = opponent && matchDateInput.value && kickoffTimeInput.value && selectedHomeAway;
  setupStatus.textContent = hasRequired
    ? "Game Plan へ進めます"
    : "試合情報を入力してください";
  nextButton.disabled = !hasRequired;
}

function handleSubmit(event) {
  event.preventDefault();
  if (!validateForm()) {
    updateStatus();
    return;
  }

  const snapshot = buildMatchSetupSnapshot();
  if (!writeStorage(storageKey, snapshot)) {
    setupStatus.textContent = "保存に失敗しました。入力内容を確認してください。";
    return;
  }

  window.location.href = planPath;
}

sideHomeButton.addEventListener("click", () => setHomeAway("home"));
sideAwayButton.addEventListener("click", () => setHomeAway("away"));
analyzeModeButtons.forEach((button) => {
  button.addEventListener("click", () => setAnalyzeMode(button.dataset.analyzeMode));
});
formationSelect.addEventListener("change", syncFormationCustomVisibility);
form.addEventListener("submit", handleSubmit);

[
  competitionInput,
  opponentInput,
  matchDateInput,
  kickoffTimeInput,
  formationCustomInput,
].forEach((element) => {
  element.addEventListener("input", updateStatus);
});

restoreDraft();
setAnalyzeMode(selectedAnalyzeMode);
updateStatus();
