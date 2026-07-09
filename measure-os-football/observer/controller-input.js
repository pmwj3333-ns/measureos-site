window.ControllerInput = (() => {
  const bindings = () => window.MO_ATTACK_CONTROLLER_BINDINGS;
  const SET_PIECE_SELECTOR = ".dashboard-panel--set-piece";

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

  function isSetPieceLocked() {
    const panel = document.querySelector(SET_PIECE_SELECTOR);
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
      `#event-categories button[data-event-code="${eventCode}"]`,
      `#event-categories button[data-event-name="${eventCode}"]`,
      `.dashboard-panel--manual-input button[data-event-code="${eventCode}"]`,
      `.dashboard-panel--manual-input button[data-event-name="${eventCode}"]`,
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);
      if (button) return button;
    }

    return null;
  }

  function findSetPieceButton(eventCode) {
    const selectors = [
      `${SET_PIECE_SELECTOR} button[data-event-code="${eventCode}"]`,
      `${SET_PIECE_SELECTOR} button[data-event-name="${eventCode}"]`,
    ];

    for (const selector of selectors) {
      const buttons = document.querySelectorAll(selector);
      if (buttons.length === 0) continue;

      const selectedTeam = document.querySelector(".team-toggle button.selected")?.dataset.team || "home";
      const preferred = Array.from(buttons).find((button) => button.dataset.eventTeam === selectedTeam);
      return preferred || buttons[0];
    }

    return null;
  }

  function findEventButton(eventCode) {
    if (bindings()?.isSetPieceEventCode?.(eventCode)) {
      if (isSetPieceLocked()) return null;
      return findSetPieceButton(eventCode);
    }

    if (isManualInputLocked()) return null;
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

  function renderGuide(host) {
    if (!host) return;

    const rows = bindings()?.GUIDE_ROWS || [];
    host.innerHTML = rows.map((group) => `
      <section class="controller-guide-group">
        <h3 class="controller-guide-group-title">${group.group}</h3>
        <ul class="controller-guide-list">
          ${group.items.map((item) => `
            <li class="controller-guide-item">
              <span class="controller-guide-control">${item.control}</span>
              <span class="controller-guide-arrow" aria-hidden="true">→</span>
              <span class="controller-guide-label">${item.label}</span>
            </li>
          `).join("")}
        </ul>
      </section>
    `).join("");
  }

  function initGuide() {
    renderGuide(document.getElementById("controller-guide-content"));
  }

  function init() {
    if (initialized) return;
    initialized = true;
    document.addEventListener("keydown", handleKeyDown, true);
    initGuide();
    rafId = window.requestAnimationFrame(pollGamepads);
  }

  return {
    init,
    renderGuide,
    triggerEventCode,
  };
})();
