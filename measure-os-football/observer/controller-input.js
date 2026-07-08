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

  function isAttackAnalyzeMode() {
    return document.body.dataset.analyzeMode === "attack";
  }

  function shouldIgnoreTarget(target) {
    if (!target) return false;
    const tag = target.tagName?.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    return Boolean(target.isContentEditable);
  }

  function findAttackEventButton(eventCode) {
    return document.querySelector(
      `.dashboard-panel--manual-input [data-event-code="${eventCode}"]`,
    );
  }

  function handleKeyDown(event) {
    if (!isAttackAnalyzeMode()) return;
    if (shouldIgnoreTarget(event.target)) return;
    if (event.ctrlKey || event.altKey || event.metaKey) return;
    if (event.repeat) return;

    const eventCode = KEY_TO_EVENT_CODE[event.key?.toLowerCase()];
    if (!eventCode) return;

    const button = findAttackEventButton(eventCode);
    if (!button || button.disabled) return;

    event.preventDefault();
    button.click();
  }

  function init() {
    document.addEventListener("keydown", handleKeyDown);
  }

  return { init };
})();
