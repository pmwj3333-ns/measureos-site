window.MO_ATTACK_OBSERVER = (() => {
  const FINISH_EVENT_DEFINITIONS = {
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

  const CATEGORIES = [
    {
      key: "attack",
      label: "Attack",
      subtitle: "どこを攻略したか",
      layout: "pitch",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "left", label: "左", icon: "←", tier: "intrusion", planLabel: "左優位" },
        { code: "right", label: "右", icon: "→", tier: "intrusion", planLabel: "右優位" },
        { code: "center", label: "中央", icon: "↑", tier: "intrusion", planLabel: "中央攻略" },
        { code: "behind", label: "背後", icon: "↗", tier: "behind", planLabel: "背後攻略" },
      ],
    },
    {
      key: "buildUp",
      label: "Build Up",
      subtitle: "どの方法で前進したか",
      gridColumns: 4,
      reservedSlots: 0,
      events: [
        { code: "possession", label: "保持前進", icon: "⟲", tier: "build-up", planLabel: "保持前進" },
        { code: "long", label: "ロング前進", icon: "⇢", tier: "build-up", planLabel: "ロング前進" },
      ],
    },
    {
      key: "finish",
      label: "Finish",
      subtitle: "攻撃結果",
      gridColumns: 4,
      reservedSlots: 2,
      events: [
        {
          code: "shot",
          label: "シュート",
          iconHtml: `<svg class="event-action-svg" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="6" width="14" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="10" cy="11.5" r="1.8" fill="currentColor"/></svg>`,
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
  ];

  const OBSERVER_EVENT_GROUPS = {
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
    保持前進: ["possession", "保持前進"],
    ロング前進: ["long", "ロング前進"],
    シュート: ["shot", "シュート"],
    決定機: ["bigChance", "決定機"],
  };

  const ALL_EVENTS = CATEGORIES.flatMap((category) =>
    category.events.map((event) => ({ ...event, categoryKey: category.key })),
  );

  const CODE_SET = new Set(ALL_EVENTS.map((event) => event.code));

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

  function getEventDef(code) {
    return ALL_EVENTS.find((event) => event.code === code) || null;
  }

  function getEventLabel(code) {
    return getEventDef(code)?.label || code;
  }

  function isAttackObserverCode(value) {
    return CODE_SET.has(String(value || ""));
  }

  function resolveFinishDefinition(code, teamId = null) {
    const base = FINISH_EVENT_DEFINITIONS[code];
    if (!base) return null;
    if (!teamId) return base;
    const teamOverrides = base.teamOverrides?.[teamId];
    return teamOverrides ? { ...base, ...teamOverrides, teamId } : base;
  }

  function matchesEventName(actual, expected) {
    const actualName = String(actual || "");
    const expectedName = String(expected || "");
    if (actualName === expectedName) return true;

    const group = OBSERVER_EVENT_GROUPS[expectedName];
    if (group) return group.includes(actualName);

    for (const aliases of Object.values(OBSERVER_EVENT_GROUPS)) {
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

  function getTotalButtonCount() {
    return ALL_EVENTS.length;
  }

  function getReservedSlotCount() {
    return CATEGORIES.reduce((sum, category) => sum + (category.reservedSlots || 0), 0);
  }

  return {
    FINISH_EVENT_DEFINITIONS,
    CATEGORIES,
    getCategories,
    getEventDef,
    getEventLabel,
    isAttackObserverCode,
    resolveFinishDefinition,
    matchesEventName,
    countMatchingEvents,
    getTotalButtonCount,
    getReservedSlotCount,
  };
})();

window.MO_OBSERVATION_CATEGORIES_ATTACK = window.MO_ATTACK_OBSERVER.getCategories();
