window.MO_DEFENSE_PLAN = (() => {
  const DEFENSE_OPTIONS = [
    { label: "ハイプレス", code: "high" },
    { label: "ミドルブロック", code: "middle" },
    { label: "ローブロック", code: "low" },
  ];

  const TRANSITION_OPTIONS = [
    { label: "即時奪回", code: "counterpress" },
    { label: "リトリート", code: "retreat" },
  ];

  const EVENT_NAME_GROUPS = {
    "被左侵入": ["被左侵入", "被左", "left"],
    "被右侵入": ["被右侵入", "被右", "right"],
    "被中央侵入": ["被中央侵入", "被中央", "center"],
    被背後: ["被背後", "被クロス", "behind"],
    被シュート: ["被シュート", "shot"],
    被決定機: ["被決定機", "bigChance"],
    即時奪回成功: ["即時奪回成功", "即時奪回", "counterpress"],
    被カウンター: ["被カウンター", "カウンター被弾", "counter"],
    保持前進: ["保持前進", "possession"],
    ロング前進: ["ロング前進", "long"],
    リトリート: ["リトリート", "retreat"],
    カウンター被弾: ["カウンター被弾", "被カウンター", "counter"],
    カウンター開始: ["カウンター開始"],
    ボール奪取: ["ボール奪取"],
    前線奪取: ["前線奪取"],
  };

  function getOptions(categoryKey) {
    if (categoryKey === "defense") return DEFENSE_OPTIONS;
    if (categoryKey === "transition") return TRANSITION_OPTIONS;
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

  function matchesEventName(actual, expected) {
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
    return (Array.isArray(events) ? events : []).filter((event) =>
      matchesEventName(event?.eventName, eventName),
    ).length;
  }

  function isDefenseAnalyzeMode(mode) {
    return mode === "defense";
  }

  return {
    DEFENSE_OPTIONS,
    TRANSITION_OPTIONS,
    getLabels,
    labelToCode,
    codeToLabel,
    matchesEventName,
    countMatchingEvents,
    isDefenseAnalyzeMode,
  };
})();
