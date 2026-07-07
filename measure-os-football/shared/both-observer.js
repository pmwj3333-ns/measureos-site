window.MO_BOTH_OBSERVER = (() => {
  const FINISH_ATTACK_DEFINITIONS = {
    shot: {
      code: "shot",
      label: "シュート",
      description: "枠内を狙った射門。",
      teamId: null,
    },
    bigChance: {
      code: "bigChance",
      label: "決定機",
      description:
        "ゴール期待値が十分に高いと判断できるチャンス。Review および State Engine 連携の基準イベント。",
      teamId: null,
    },
  };

  const FINISH_DEFENSE_DEFINITIONS = {
    shot: {
      code: "shot",
      label: "被シュート",
      description: "相手が枠内を狙った射門を許した事実。",
      teamId: null,
    },
    bigChance: {
      code: "bigChance",
      label: "被決定機",
      description:
        "相手にゴール期待値が十分に高いと判断できるチャンスを許した事実。Review および State Engine 連携の基準イベント。",
      teamId: null,
    },
  };

  const SHOT_ICON_HTML = `<svg class="event-action-svg" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="6" width="14" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="10" cy="11.5" r="1.8" fill="currentColor"/></svg>`;

  const CATEGORIES = [
    {
      key: "attack",
      label: "Attack",
      subtitle: "どこを攻略したか",
      layout: "pitch",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "left", label: "左", icon: "←", tier: "intrusion" },
        { code: "right", label: "右", icon: "→", tier: "intrusion" },
        { code: "center", label: "中央", icon: "↑", tier: "intrusion" },
        { code: "behind", label: "背後", icon: "↗", tier: "behind" },
      ],
    },
    {
      key: "buildUp",
      label: "Build Up",
      subtitle: "どの方法で前進したか",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "possession", label: "保持前進", icon: "⟲", tier: "build-up" },
        { code: "long", label: "ロング前進", icon: "⇢", tier: "build-up" },
      ],
    },
    {
      key: "defense",
      label: "Defense",
      subtitle: "どこへの危険な侵入を許したか",
      layout: "pitch",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "left", label: "被左", icon: "←", tier: "intrusion" },
        { code: "right", label: "被右", icon: "→", tier: "intrusion" },
        { code: "center", label: "被中央", icon: "↑", tier: "intrusion" },
        { code: "behind", label: "被背後", icon: "↗", tier: "behind" },
      ],
    },
    {
      key: "transition",
      label: "Transition",
      subtitle: "守備トランジション",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "counter", label: "被カウンター", icon: "⇠", tier: "transition" },
        { code: "counterpress", label: "即時奪回", icon: "↺", tier: "transition" },
      ],
    },
    {
      key: "finish",
      label: "Finish (Attack)",
      subtitle: "攻撃結果",
      gridColumns: 4,
      reservedSlots: 2,
      events: [
        {
          code: "shot",
          label: "シュート",
          iconHtml: SHOT_ICON_HTML,
          tier: "finish",
          definitionKey: "shot",
        },
        {
          code: "bigChance",
          label: "決定機",
          icon: "★",
          tier: "finish",
          definitionKey: "bigChance",
        },
      ],
    },
    {
      key: "finishDefense",
      label: "Finish (Defense)",
      subtitle: "守備結果",
      gridColumns: 4,
      reservedSlots: 2,
      events: [
        {
          code: "shot",
          label: "被シュート",
          iconHtml: SHOT_ICON_HTML,
          tier: "finish",
          definitionKey: "shot",
        },
        {
          code: "bigChance",
          label: "被決定機",
          icon: "★",
          tier: "finish",
          definitionKey: "bigChance",
        },
      ],
    },
  ];

  const OBSERVER_EVENT_GROUPS = {
    left: ["left", "左", "左侵入", "被左", "被左侵入"],
    right: ["right", "右", "右侵入", "被右", "被右侵入"],
    center: ["center", "中央", "中央侵入", "被中央", "被中央侵入"],
    behind: ["behind", "背後", "被背後", "被クロス"],
    possession: ["possession", "保持前進"],
    long: ["long", "ロング前進"],
    counter: ["counter", "被カウンター", "カウンター被弾"],
    counterpress: ["counterpress", "即時奪回", "即時奪回成功"],
    shot: ["shot", "シュート", "被シュート"],
    bigChance: ["bigChance", "決定機", "被決定機"],
    左: ["left", "左", "左侵入"],
    右: ["right", "右", "右侵入"],
    中央: ["center", "中央", "中央侵入"],
    背後: ["behind", "背後"],
    被左: ["left", "被左", "被左侵入"],
    被右: ["right", "被右", "被右侵入"],
    被中央: ["center", "被中央", "被中央侵入"],
    被背後: ["behind", "被背後", "被クロス"],
    保持前進: ["possession", "保持前進"],
    ロング前進: ["long", "ロング前進"],
    被カウンター: ["counter", "被カウンター", "カウンター被弾"],
    即時奪回: ["counterpress", "即時奪回", "即時奪回成功"],
    シュート: ["shot", "シュート"],
    決定機: ["bigChance", "決定機"],
    被シュート: ["shot", "被シュート"],
    被決定機: ["bigChance", "被決定機"],
  };

  const ALL_EVENTS = CATEGORIES.flatMap((category) =>
    category.events.map((event) => ({ ...event, categoryKey: category.key })),
  );

  const CODE_CATEGORY_SET = new Set(
    ALL_EVENTS.map((event) => `${event.categoryKey}:${event.code}`),
  );

  function getCategories() {
    return CATEGORIES.map((category) => ({
      label: category.label,
      key: category.key,
      subtitle: category.subtitle,
      layout: category.layout,
      gridColumns: category.gridColumns,
      reservedSlots: category.reservedSlots,
      events: category.events.map((event) => event.code),
      eventDefs: category.events,
    }));
  }

  function getEventDef(code, categoryKey = null) {
    const normalizedCode = String(code || "");
    if (categoryKey) {
      return ALL_EVENTS.find(
        (event) => event.code === normalizedCode && event.categoryKey === categoryKey,
      ) || null;
    }
    return ALL_EVENTS.find((event) => event.code === normalizedCode) || null;
  }

  function getEventLabel(code, categoryKey = null) {
    return getEventDef(code, categoryKey)?.label || code;
  }

  function isBothObserverEvent(code, categoryKey = null) {
    const normalizedCode = String(code || "");
    if (categoryKey) {
      return CODE_CATEGORY_SET.has(`${categoryKey}:${normalizedCode}`);
    }
    return ALL_EVENTS.some((event) => event.code === normalizedCode);
  }

  function resolveFinishDefinition(code, categoryKey = "finish", teamId = null) {
    const definitions = categoryKey === "finishDefense"
      ? FINISH_DEFENSE_DEFINITIONS
      : FINISH_ATTACK_DEFINITIONS;
    const base = definitions[code];
    if (!base) return null;
    if (!teamId) return base;
    const teamOverrides = base.teamOverrides?.[teamId];
    return teamOverrides ? { ...base, ...teamOverrides, teamId } : base;
  }

  function matchesEventName(actual, expected, categoryKey = null) {
    const actualName = String(actual || "");
    const expectedName = String(expected || "");
    if (actualName === expectedName) return true;

    const expectedDef = getEventDef(expectedName, categoryKey);
    if (expectedDef) {
      const group = OBSERVER_EVENT_GROUPS[expectedDef.code];
      if (group?.includes(actualName)) return true;
    }

    const group = OBSERVER_EVENT_GROUPS[expectedName];
    if (group) return group.includes(actualName);

    for (const aliases of Object.values(OBSERVER_EVENT_GROUPS)) {
      if (aliases.includes(expectedName) && aliases.includes(actualName)) {
        return true;
      }
    }

    return false;
  }

  function countMatchingEvents(events, eventName, categoryKey = null) {
    return (Array.isArray(events) ? events : []).filter((event) =>
      matchesEventName(event?.observerEventCode || event?.eventName, eventName, categoryKey),
    ).length;
  }

  function getTotalButtonCount() {
    return ALL_EVENTS.length;
  }

  function getReservedSlotCount() {
    return CATEGORIES.reduce((sum, category) => sum + (category.reservedSlots || 0), 0);
  }

  return {
    FINISH_ATTACK_DEFINITIONS,
    FINISH_DEFENSE_DEFINITIONS,
    CATEGORIES,
    getCategories,
    getEventDef,
    getEventLabel,
    isBothObserverEvent,
    resolveFinishDefinition,
    matchesEventName,
    countMatchingEvents,
    getTotalButtonCount,
    getReservedSlotCount,
  };
})();

window.MO_OBSERVATION_CATEGORIES_BOTH = window.MO_BOTH_OBSERVER.getCategories();
