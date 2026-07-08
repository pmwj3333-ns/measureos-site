const ALL_PLAN_CATEGORIES = [
  {
    key: "attack",
    options: ["左優位", "右優位", "中央攻略", "クロス攻略", "背後攻略"],
  },
  {
    key: "defense",
    options: ["ハイプレス", "ミドルブロック", "ローブロック", "サイド誘導"],
  },
  {
    key: "buildUp",
    options: ["保持前進", "ロング前進", "サイド前進", "中央前進"],
  },
  {
    key: "transition",
    options: ["即時奪回", "リトリート", "縦に速く", "ボール保持"],
  },
];

const selectedPlan = new Map(ALL_PLAN_CATEGORIES.map((category) => [category.key, new Set()]));
const storageKey = "measure-os-football:plan:v0.1";
const matchSetupStorageKey = "measure-os-football:match-setup:v1";
const matchStorageKey = "measure-os-football:match-control:v0.3";
const planReturnKey = "measure-os-football:plan-return:v0.3";
const observerEventStorageKey = "measure-os-football:observer-events:v0.3";
const observerPath = "../../observer/index.html";
const ANALYZE_MODES = new Set(["attack", "defense", "both"]);
const BOTH_CATEGORY_ORDER = ["attack", "buildUp", "defense", "transition"];
const ANALYZE_MODE_CATEGORIES = {
  attack: ["attack", "buildUp"],
  defense: ["defense", "transition"],
  both: BOTH_CATEGORY_ORDER,
};
let confirmFeedbackTimer = null;
let isPlanConfirmed = false;
let planEditMode = false;
let planReturnContext = null;
let analyzeMode = "both";

function optionId(categoryKey, label) {
  return `${categoryKey}:${label}`;
}

function loadAnalyzeMode() {
  const setup = loadJson(matchSetupStorageKey);
  const mode = setup?.analyzeMode;
  analyzeMode = ANALYZE_MODES.has(mode) ? mode : "both";
}

function getCategoryOptions(categoryKey) {
  if (analyzeMode === "attack" && window.MO_ATTACK_PLAN) {
    const labels = window.MO_ATTACK_PLAN.getLabels(categoryKey);
    if (labels.length > 0) return labels;
  }

  if (analyzeMode === "defense" && window.MO_DEFENSE_PLAN) {
    const labels = window.MO_DEFENSE_PLAN.getLabels(categoryKey);
    if (labels.length > 0) return labels;
  }

  if (analyzeMode === "both") {
    if (
      (categoryKey === "attack" || categoryKey === "buildUp")
      && window.MO_ATTACK_PLAN
    ) {
      const labels = window.MO_ATTACK_PLAN.getLabels(categoryKey);
      if (labels.length > 0) return labels;
    }
    if (
      (categoryKey === "defense" || categoryKey === "transition")
      && window.MO_DEFENSE_PLAN
    ) {
      const labels = window.MO_DEFENSE_PLAN.getLabels(categoryKey);
      if (labels.length > 0) return labels;
    }
  }

  const category = ALL_PLAN_CATEGORIES.find((item) => item.key === categoryKey);
  return category?.options || [];
}

function getPlanCategories() {
  return ALL_PLAN_CATEGORIES.map((category) => ({
    key: category.key,
    options: getCategoryOptions(category.key),
  }));
}

function getVisibleCategoryKeys() {
  return ANALYZE_MODE_CATEGORIES[analyzeMode] || ANALYZE_MODE_CATEGORIES.both;
}

function isCategoryVisible(categoryKey) {
  return getVisibleCategoryKeys().includes(categoryKey);
}

function applyAnalyzeModeLayout() {
  const grid = document.querySelector(".plan-grid");
  if (!grid) return;

  const visibleKeys = getVisibleCategoryKeys();
  grid.dataset.analyzeMode = analyzeMode;
  grid.dataset.layout = analyzeMode === "both"
    ? "both"
    : visibleKeys.length === 2
      ? "two"
      : visibleKeys.length === 3
        ? "three"
        : "four";

  if (analyzeMode === "both") {
    ALL_PLAN_CATEGORIES.forEach((category) => {
      const card = document.querySelector(`[data-category="${category.key}"]`);
      if (!card) return;
      const orderIndex = BOTH_CATEGORY_ORDER.indexOf(category.key);
      const visible = orderIndex >= 0;
      card.hidden = !visible;
      card.style.order = visible ? String(orderIndex) : "";
      if (visible) {
        const indexEl = card.querySelector(".category-index");
        if (indexEl) indexEl.textContent = String(orderIndex + 1).padStart(2, "0");
      }
    });
    return;
  }

  let index = 1;
  ALL_PLAN_CATEGORIES.forEach((category) => {
    const card = document.querySelector(`[data-category="${category.key}"]`);
    if (!card) return;
    const visible = isCategoryVisible(category.key);
    card.hidden = !visible;
    card.style.order = "";
    if (visible) {
      const indexEl = card.querySelector(".category-index");
      if (indexEl) indexEl.textContent = String(index).padStart(2, "0");
      index += 1;
    }
  });
}

function selectedCount() {
  let count = 0;
  getVisibleCategoryKeys().forEach((key) => {
    count += selectedPlan.get(key)?.size || 0;
  });
  return count;
}

function renderSummary() {
  const count = selectedCount();
  const confirmButton = document.getElementById("confirm-plan");
  document.getElementById("selection-count").textContent =
    `選択 ${count} 件`;
  document.getElementById("plan-readiness").textContent =
    planEditMode
      ? "現在の Plan を編集しています"
      : isPlanConfirmed
        ? "プラン確定済み"
        : count > 0
          ? "プランを設定しました"
          : "まだプランは設定されていません";
  confirmButton.disabled = count === 0 || (!planEditMode && isPlanConfirmed);
  confirmButton.textContent = planEditMode
    ? (isPlanConfirmed ? "✓ 保存済み" : "保存")
    : (isPlanConfirmed ? "✓ 確定済み" : "プランを確定");
  confirmButton.classList.toggle("is-confirmed", isPlanConfirmed);
}

function syncCategoryButtons(categoryKey) {
  const bucket = selectedPlan.get(categoryKey);
  const card = document.querySelector(`[data-category="${categoryKey}"]`);
  if (!card) return;
  card.querySelectorAll(".option-button").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      bucket?.has(button.dataset.label) ? "true" : "false",
    );
  });
}

function toggleCategoryOption(categoryKey, label) {
  const bucket = selectedPlan.get(categoryKey);
  if (!bucket) return;

  if (bucket.has(label)) {
    bucket.delete(label);
  } else {
    bucket.clear();
    bucket.add(label);
  }

  syncCategoryButtons(categoryKey);
  isPlanConfirmed = false;
  renderSummary();
}

function normalizePlanSnapshot(raw) {
  return window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot(raw) ?? null;
}

function clonePlanSnapshot(raw) {
  return window.MO_PLAN_SNAPSHOT?.clonePlanSnapshot(raw) ?? null;
}

function createPlanSnapshot() {
  const memo = document.getElementById("free-memo").value || "";

  if (analyzeMode === "attack") {
    const attackLabel = Array.from(selectedPlan.get("attack") || [])[0] || null;
    const buildUpLabel = Array.from(selectedPlan.get("buildUp") || [])[0] || null;
    const attackPlan = window.MO_ATTACK_PLAN;

    return {
      version: "0.1",
      confirmed: true,
      confirmedAt: new Date().toISOString(),
      analyzeMode: "attack",
      attack: attackLabel ? attackPlan?.labelToCode("attack", attackLabel) : null,
      buildUp: buildUpLabel ? attackPlan?.labelToCode("buildUp", buildUpLabel) : null,
      categories: {
        ...(attackLabel ? { attack: [attackLabel] } : {}),
        ...(buildUpLabel ? { buildUp: [buildUpLabel] } : {}),
      },
      memo,
    };
  }

  if (analyzeMode === "defense") {
    const defenseLabel = Array.from(selectedPlan.get("defense") || [])[0] || null;
    const transitionLabel = Array.from(selectedPlan.get("transition") || [])[0] || null;
    const defensePlan = window.MO_DEFENSE_PLAN;

    return {
      version: "0.1",
      confirmed: true,
      confirmedAt: new Date().toISOString(),
      analyzeMode: "defense",
      defense: defenseLabel ? defensePlan?.labelToCode("defense", defenseLabel) : null,
      transition: transitionLabel ? defensePlan?.labelToCode("transition", transitionLabel) : null,
      categories: {
        ...(defenseLabel ? { defense: [defenseLabel] } : {}),
        ...(transitionLabel ? { transition: [transitionLabel] } : {}),
      },
      memo,
    };
  }

  if (analyzeMode === "both") {
    const attackLabel = Array.from(selectedPlan.get("attack") || [])[0] || null;
    const buildUpLabel = Array.from(selectedPlan.get("buildUp") || [])[0] || null;
    const defenseLabel = Array.from(selectedPlan.get("defense") || [])[0] || null;
    const transitionLabel = Array.from(selectedPlan.get("transition") || [])[0] || null;
    const attackPlan = window.MO_ATTACK_PLAN;
    const defensePlan = window.MO_DEFENSE_PLAN;

    return {
      version: "0.1",
      confirmed: true,
      confirmedAt: new Date().toISOString(),
      analyzeMode: "both",
      attack: attackLabel ? attackPlan?.labelToCode("attack", attackLabel) : null,
      buildUp: buildUpLabel ? attackPlan?.labelToCode("buildUp", buildUpLabel) : null,
      defense: defenseLabel ? defensePlan?.labelToCode("defense", defenseLabel) : null,
      transition: transitionLabel ? defensePlan?.labelToCode("transition", transitionLabel) : null,
      categories: {
        ...(attackLabel ? { attack: [attackLabel] } : {}),
        ...(buildUpLabel ? { buildUp: [buildUpLabel] } : {}),
        ...(defenseLabel ? { defense: [defenseLabel] } : {}),
        ...(transitionLabel ? { transition: [transitionLabel] } : {}),
      },
      memo,
    };
  }

  const categories = {};
  ALL_PLAN_CATEGORIES.forEach(({ key }) => {
    categories[key] = Array.from(selectedPlan.get(key) || []);
  });

  return {
    version: "0.1",
    confirmed: true,
    confirmedAt: new Date().toISOString(),
    analyzeMode,
    categories,
    memo,
  };
}

function saveConfirmedPlan(snapshot) {
  const normalized = clonePlanSnapshot(snapshot);
  if (!normalized) return false;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(normalized));
    return true;
  } catch (_) {
    // Version 0.1 is local-only. If storage is unavailable, keep the UI state.
    return false;
  }
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
    // Keep the Plan screen usable if localStorage is unavailable.
  }
}

function removeJson(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (_) {
    // Ignore storage errors in the local prototype.
  }
}

function createPlanHistoryEntry(snapshot, context, reason) {
  const plan = clonePlanSnapshot(snapshot);
  if (!plan) return null;
  return {
    plan,
    matchTime: context?.matchTime || "00:00",
    elapsedSeconds: Number(context?.elapsedSeconds) || 0,
    phase: context?.phase || "",
    changedAt: plan.confirmedAt,
    reason,
    eventBoundaryIndex: Number(context?.eventBoundaryIndex) || 0,
  };
}

function appendPlanHistory(match, snapshot, context, reason) {
  const entry = createPlanHistoryEntry(snapshot, context, reason);
  if (!entry) return;
  if (!Array.isArray(match.planHistory)) {
    match.planHistory = [];
  }
  match.planHistory.push(entry);
}

function applyPlanReturnContext(snapshot) {
  const context = loadJson(planReturnKey);
  if (!context || context.returnTo !== "observer") return false;

  const normalized = clonePlanSnapshot(snapshot);
  if (!normalized) return false;

  const match = loadJson(matchStorageKey) || {};
  match.currentPlan = normalized;

  if (
    context.reason === "halftime_plan_change" ||
    context.reason === "second_half_plan_change"
  ) {
    match.match_phase = "halftime_ready";
    match.second_half_plan = normalized;
    appendPlanHistory(match, normalized, context, "halftime_change");
    saveJson(matchStorageKey, match);
    removeJson(planReturnKey);
    return true;
  }

  if (context.reason === "mid_match_plan_change") {
    if (match.match_phase === "before_kickoff") {
      match.first_half_plan = normalized;
    } else if (match.match_phase === "first_half") {
      match.first_half_plan = normalized;
    } else if (match.match_phase === "second_half") {
      match.second_half_plan = normalized;
    } else if (
      match.match_phase === "halftime_decision" ||
      match.match_phase === "halftime_ready"
    ) {
      match.second_half_plan = normalized;
    }
    if (match.kickoff_at) {
      appendPlanHistory(match, normalized, context, "mid_match");
    }
    saveJson(matchStorageKey, match);
    removeJson(planReturnKey);
    return true;
  }

  return false;
}

function initializeMatchForNewPlan(snapshot) {
  const normalized = clonePlanSnapshot(snapshot);
  if (!normalized) return;

  removeJson(observerEventStorageKey);
  saveJson(matchStorageKey, {
    kickoff_at: null,
    first_half_end_at: null,
    second_half_start_at: null,
    fulltime_at: null,
    match_phase: "before_kickoff",
    first_half_plan: normalized,
    second_half_plan: null,
    currentPlan: normalized,
    planHistory: [],
    home_score: 0,
    away_score: 0,
  });
}

function removeSavedPlan() {
  try {
    window.localStorage.removeItem(storageKey);
  } catch (_) {
    // Ignore storage errors in the local prototype.
  }
}

function hydratePlanFromSnapshot(saved) {
  const normalized = normalizePlanSnapshot(saved);
  if (!normalized) return false;

  selectedPlan.forEach((items, key) => {
    items.clear();
    const values = Array.isArray(normalized.categories[key]) ? normalized.categories[key] : [];
    const first = values.find((label) => typeof label === "string");
    if (first) {
      items.add(first);
    }
  });
  getPlanCategories().forEach((category) => {
    syncCategoryButtons(category.key);
  });
  const memo = document.getElementById("free-memo");
  if (memo) memo.value = typeof normalized.memo === "string" ? normalized.memo : "";
  return selectedCount() > 0;
}

function loadPlanReturnContext() {
  const context = loadJson(planReturnKey);
  if (!context || context.returnTo !== "observer") return null;
  planEditMode = true;
  planReturnContext = context;
  return context;
}

function restoreSavedPlan() {
  const context = loadPlanReturnContext();
  let saved = null;

  if (context) {
    const match = loadJson(matchStorageKey);
    saved = normalizePlanSnapshot(match?.currentPlan);
  }

  if (!saved) {
    saved = normalizePlanSnapshot(loadJson(storageKey));
    if (!saved) {
      removeSavedPlan();
    }
  }

  if (!saved) return;

  hydratePlanFromSnapshot(saved);
  isPlanConfirmed = planEditMode ? false : saved.confirmed === true;
}

function renderOption(categoryKey, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "option-button";
  button.dataset.optionId = optionId(categoryKey, label);
  button.dataset.categoryKey = categoryKey;
  button.dataset.label = label;
  button.setAttribute("aria-pressed", "false");
  button.textContent = label;
  button.addEventListener("click", () => {
    toggleCategoryOption(categoryKey, label);
  });
  return button;
}

function renderCategories() {
  getPlanCategories().forEach((category) => {
    const card = document.querySelector(`[data-category="${category.key}"]`);
    if (!card) return;
    const host = card.querySelector("[data-options]");
    if (!host) return;
    host.innerHTML = "";
    category.options.forEach((label) => {
      host.appendChild(renderOption(category.key, label));
    });
  });
}

function clearPlan() {
  selectedPlan.forEach((items) => items.clear());
  document.querySelectorAll(".option-button").forEach((button) => {
    button.setAttribute("aria-pressed", "false");
  });
  const memo = document.getElementById("free-memo");
  if (memo) memo.value = "";
  isPlanConfirmed = false;
  removeSavedPlan();
  renderSummary();
}

function confirmPlan() {
  if (selectedCount() === 0) return;
  const snapshot = createPlanSnapshot();
  const normalized = clonePlanSnapshot(snapshot);
  if (!normalized) return;

  isPlanConfirmed = true;
  const saved = saveConfirmedPlan(normalized);
  if (!saved) {
    isPlanConfirmed = false;
    renderSummary();
    return;
  }
  if (!applyPlanReturnContext(normalized)) {
    initializeMatchForNewPlan(normalized);
  }
  if (confirmFeedbackTimer != null) {
    window.clearTimeout(confirmFeedbackTimer);
    confirmFeedbackTimer = null;
  }
  renderSummary();
  const observerUrl = new URL(observerPath, window.location.href);
  window.location.assign(observerUrl.href);
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.MO_AUTH_GUARD && !window.MO_AUTH_GUARD.requireAuth()) {
    return;
  }

  loadAnalyzeMode();
  renderCategories();
  applyAnalyzeModeLayout();
  restoreSavedPlan();
  applyAnalyzeModeLayout();
  renderSummary();
  document.getElementById("clear-plan").addEventListener("click", clearPlan);
  document.getElementById("confirm-plan").addEventListener("click", confirmPlan);
});
