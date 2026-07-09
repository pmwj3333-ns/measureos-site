(function () {
  // Rules self-register via scripts loaded after engine.js:
  // rule001-attack-left-advantage.js (superseded by rule012)
  // rule012-attack-left-dominance.js (Attack State v2 via attack-finish-rate.js)
  // rule013-attack-right-dominance.js
  // rule014-attack-central-attack.js
  // rule015-attack-cross-strategy.js
  // rule016-defense-middle-block.js
  // rule017-defense-side-guiding.js
  // rule002-defense-high-press.js
  // rule003-defense-low-block.js
  // rule004-build-up-hold-and-advance.js
  // rule005-build-up-long-advance.js
  // rule006-build-up-side-advance.js
  // rule007-build-up-central-advance.js
  // rule008-transition-immediate-recovery.js
  // rule009-transition-retreat.js
  // rule010-transition-fast-vertical.js
  // rule011-transition-ball-retention.js
  const rules = [];

  const CATEGORY_LEGACY_KEYS = {
    buildUp: ["build_up", "BuildUp", "buildup", "Build Up"],
  };

  function registerRule(rule) {
    rules.push(rule);
  }

  function readPlanCategory(plan, categoryKey) {
    const categories = plan?.categories;
    if (!categories || typeof categories !== "object") return [];

    const direct = categories[categoryKey];
    if (Array.isArray(direct)) return direct;

    const legacyKeys = CATEGORY_LEGACY_KEYS[categoryKey] || [];
    for (const legacyKey of legacyKeys) {
      const legacy = categories[legacyKey];
      if (Array.isArray(legacy)) return legacy;
    }

    return [];
  }

  function planIncludesOption(plan, categoryKey, option) {
    return readPlanCategory(plan, categoryKey).includes(option);
  }

  function isRuleEnabled(rule, plan) {
    if (typeof rule.isEnabled === "function") {
      return rule.isEnabled(plan);
    }
    if (rule.planCategoryKey && rule.planOption) {
      return planIncludesOption(plan, rule.planCategoryKey, rule.planOption);
    }
    return false;
  }

  function evaluateLiveState({ plan, events, elapsed = 0 }) {
    if (!plan) return [];

    const observationEvents = Array.isArray(events) ? events : [];
    const context = { plan, events: observationEvents, elapsed };
    const states = [];

    for (const rule of rules) {
      if (!isRuleEnabled(rule, plan)) continue;
      const state = rule.evaluate(observationEvents, context);
      if (!state) continue;

      states.push({
        ...state,
        planCategoryKey: rule.planCategoryKey ?? state.planCategoryKey ?? null,
      });
    }

    return states;
  }

  function evaluateState(input) {
    return evaluateLiveState(input);
  }

  window.MO_STATE_ENGINE = {
    registerRule,
    readPlanCategory,
    planIncludesOption,
    evaluateLiveState,
    evaluateState,
  };
})();
