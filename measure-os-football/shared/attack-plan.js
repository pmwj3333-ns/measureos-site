window.MO_ATTACK_PLAN = (() => {
  const ATTACK_OPTIONS = [
    { label: "左優位", code: "left", observerEvent: "左" },
    { label: "右優位", code: "right", observerEvent: "右" },
    { label: "中央攻略", code: "center", observerEvent: "中央" },
    { label: "背後攻略", code: "behind", observerEvent: "背後" },
  ];

  const BUILD_UP_OPTIONS = [
    { label: "保持前進", code: "possession", observerEvent: "保持前進" },
    { label: "ロング前進", code: "long", observerEvent: "ロング前進" },
  ];

  const EVENT_NAME_GROUPS = {
    left: ["left", "左", "左侵入"],
    right: ["right", "右", "右侵入"],
    center: ["center", "中央", "中央侵入"],
    behind: ["behind", "背後"],
    possession: ["possession", "保持前進"],
    long: ["long", "ロング前進"],
    shot: ["shot", "シュート"],
    bigChance: ["bigChance", "決定機"],
    "左侵入": ["left", "左", "左侵入"],
    "右侵入": ["right", "右", "右侵入"],
    "中央侵入": ["center", "中央", "中央侵入"],
    背後: ["behind", "背後"],
    クロス: ["クロス"],
    シュート: ["shot", "シュート"],
    決定機: ["bigChance", "決定機"],
    保持前進: ["possession", "保持前進"],
    ロング前進: ["long", "ロング前進"],
    カウンター被弾: ["カウンター被弾"],
  };

  function getOptions(categoryKey) {
    if (categoryKey === "attack") return ATTACK_OPTIONS;
    if (categoryKey === "buildUp") return BUILD_UP_OPTIONS;
    return [];
  }

  function getLabels(categoryKey) {
    return getOptions(categoryKey).map((item) => item.label);
  }

  function labelToCode(categoryKey, label) {
    const match = getOptions(categoryKey).find((item) => item.label === label);
    return match?.code || null;
  }

  function codeToLabel(categoryKey, code) {
    const match = getOptions(categoryKey).find((item) => item.code === code);
    return match?.label || null;
  }

  function labelToObserverEvent(categoryKey, label) {
    const match = getOptions(categoryKey).find((item) => item.label === label);
    return match?.observerEvent || label;
  }

  function matchesEventName(actual, expected) {
    const observerMatcher = window.MO_ATTACK_OBSERVER?.matchesEventName;
    if (typeof observerMatcher === "function" && observerMatcher(actual, expected)) {
      return true;
    }

    const actualName = String(actual || "");
    const expectedName = String(expected || "");
    if (actualName === expectedName) return true;

    const group = EVENT_NAME_GROUPS[expectedName];
    if (group) return group.includes(actualName);

    for (const aliases of Object.values(EVENT_NAME_GROUPS)) {
      if (aliases.includes(expectedName) && aliases.includes(actualName)) {
        return true;
      }
    }

    return false;
  }

  function countMatchingEvents(events, eventName) {
    const observerCounter = window.MO_ATTACK_OBSERVER?.countMatchingEvents;
    if (typeof observerCounter === "function") {
      const observerCount = observerCounter(events, eventName);
      if (observerCount > 0) return observerCount;
    }

    return (Array.isArray(events) ? events : []).filter((event) =>
      matchesEventName(event?.eventName, eventName),
    ).length;
  }

  function isAttackAnalyzeMode(mode) {
    return mode === "attack";
  }

  return {
    ATTACK_OPTIONS,
    BUILD_UP_OPTIONS,
    getLabels,
    labelToCode,
    codeToLabel,
    labelToObserverEvent,
    matchesEventName,
    countMatchingEvents,
    isAttackAnalyzeMode,
  };
})();
