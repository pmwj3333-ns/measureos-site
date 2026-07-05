(function () {
  // Rules self-register via scripts loaded after engine.js:
  // rule001-attack-left-advantage.js (superseded by rule012)
  // rule012-attack-left-dominance.js
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

  function registerRule(rule) {
    rules.push(rule);
  }

  function evaluateLiveState({ plan, events, elapsed = 0 }) {
    if (!plan) return [];

    const observationEvents = Array.isArray(events) ? events : [];
    const context = { plan, events: observationEvents, elapsed };
    const states = [];

    for (const rule of rules) {
      if (!rule.isEnabled(plan)) continue;
      const state = rule.evaluate(observationEvents, context);
      if (state) states.push(state);
    }

    return states;
  }

  window.MO_STATE_ENGINE = {
    registerRule,
    evaluateLiveState,
  };
})();
