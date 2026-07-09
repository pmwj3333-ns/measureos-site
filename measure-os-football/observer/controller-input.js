window.ControllerInput = (() => {
  const bindings = () => window.MO_ATTACK_CONTROLLER_BINDINGS;

  let initialized = false;
  let rafId = null;
  const previousButtonStates = new WeakMap();

  function isAttackAnalyzeMode() {
    const mode = document.body.dataset.analyzeMode
      || document.body.getAttribute("data-analyze-mode");
    return mode === "attack";
  }

  function isManualInputLocked() {
    const panel = document.querySelector(".dashboard-panel--manual-input");
    return !panel || panel.classList.contains("is-locked");
  }

  function shouldIgnoreTarget(target) {
    if (!target) return false;
    const tag = target.tagName?.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    return Boolean(target.isContentEditable);
  }

  function findManualInputButton(eventCode) {
    const selectors = [
      `#event-categories button[data-event-code="${eventCode}"]:not([data-event-team])`,
      `#event-categories button[data-event-name="${eventCode}"]:not([data-event-team])`,
      `.dashboard-panel--manual-input button[data-event-code="${eventCode}"]:not([data-event-team])`,
      `.dashboard-panel--manual-input button[data-event-name="${eventCode}"]:not([data-event-team])`,
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);
      if (button) return button;
    }

    return null;
  }

  function findSetPieceButton(eventCode) {
    const selectedTeam = document.querySelector(".team-toggle button.selected")?.dataset.team || "home";
    const selectors = [
      `#event-categories button.set-piece-button[data-event-code="${eventCode}"]`,
      `#event-categories button[data-event-code="${eventCode}"][data-event-team]`,
      `.dashboard-panel--manual-input button.set-piece-button[data-event-code="${eventCode}"]`,
      `.dashboard-panel--manual-input button[data-event-code="${eventCode}"][data-event-team]`,
    ];

    for (const selector of selectors) {
      const buttons = document.querySelectorAll(selector);
      if (buttons.length === 0) continue;

      const preferred = Array.from(buttons).find((button) => button.dataset.eventTeam === selectedTeam);
      return preferred || buttons[0];
    }

    return null;
  }

  function findEventButton(eventCode) {
    if (isManualInputLocked()) return null;

    if (bindings()?.isSetPieceEventCode?.(eventCode)) {
      return findSetPieceButton(eventCode);
    }

    return findManualInputButton(eventCode);
  }

  function clickEventButton(button) {
    const wasDisabled = button.disabled;
    if (wasDisabled) button.disabled = false;
    button.click();
    if (wasDisabled) button.disabled = true;
  }

  function triggerEventCode(eventCode) {
    if (!eventCode) return false;
    const button = findEventButton(eventCode);
    if (!button) return false;
    clickEventButton(button);
    return true;
  }

  function handleKeyDown(event) {
    if (!isAttackAnalyzeMode()) return;
    if (shouldIgnoreTarget(event.target)) return;
    if (event.ctrlKey || event.altKey || event.metaKey) return;
    if (event.repeat) return;
    if (event.isComposing) return;

    const eventCode = bindings()?.ARROW_KEY_TO_EVENT?.[event.key]
      || bindings()?.KEYBOARD_TO_EVENT?.[event.key?.toLowerCase()];
    if (!eventCode) return;

    const button = findEventButton(eventCode);
    if (!button) return;

    event.preventDefault();
    clickEventButton(button);
  }

  function pollGamepads() {
    if (!isAttackAnalyzeMode()) {
      rafId = window.requestAnimationFrame(pollGamepads);
      return;
    }

    const gamepads = navigator.getGamepads?.() || [];
    gamepads.forEach((gamepad) => {
      if (!gamepad) return;

      const previous = previousButtonStates.get(gamepad) || [];
      gamepad.buttons.forEach((button, index) => {
        const pressed = Boolean(button?.pressed);
        const wasPressed = Boolean(previous[index]);
        if (pressed && !wasPressed) {
          const eventCode = bindings()?.GAMEPAD_TO_EVENT?.[index];
          if (eventCode) triggerEventCode(eventCode);
        }
      });

      previousButtonStates.set(gamepad, gamepad.buttons.map((button) => Boolean(button?.pressed)));
    });

    rafId = window.requestAnimationFrame(pollGamepads);
  }

  function init() {
    if (initialized) return;
    initialized = true;
    document.addEventListener("keydown", handleKeyDown, true);
    rafId = window.requestAnimationFrame(pollGamepads);
  }

  return {
    init,
    triggerEventCode,
  };
})();
