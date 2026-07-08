window.ControllerInput = (() => {
  const KEY_TO_EVENT_CODE = {
    a: "left",
    s: "center",
    d: "right",
    g: "behind",
    l: "possession",
    o: "long",
    j: "shot",
    k: "bigChance",
  };

  let initialized = false;

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

  function findAttackEventButton(eventCode) {
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

  function clickEventButton(button) {
    const wasDisabled = button.disabled;
    if (wasDisabled) button.disabled = false;
    button.click();
    if (wasDisabled) button.disabled = true;
  }

  function handleKeyDown(event) {
    if (!isAttackAnalyzeMode()) return;
    if (isManualInputLocked()) return;
    if (shouldIgnoreTarget(event.target)) return;
    if (event.ctrlKey || event.altKey || event.metaKey) return;
    if (event.repeat) return;
    if (event.isComposing) return;

    const eventCode = KEY_TO_EVENT_CODE[event.key?.toLowerCase()];
    if (!eventCode) return;

    const button = findAttackEventButton(eventCode);
    if (!button) return;

    event.preventDefault();
    clickEventButton(button);
  }

  function init() {
    if (initialized) return;
    initialized = true;
    document.addEventListener("keydown", handleKeyDown, true);
  }

  return { init };
})();
