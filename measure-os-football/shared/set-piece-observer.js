window.MO_SET_PIECE_OBSERVER = (() => {
  const EVENTS = [
    {
      code: "corner_kick",
      label: "コーナーキック",
      shortLabel: "CK",
      aliases: ["corner_kick", "CK", "コーナーキック"],
    },
    {
      code: "free_kick",
      label: "フリーキック",
      shortLabel: "FK",
      aliases: ["free_kick", "FK", "フリーキック"],
    },
    {
      code: "penalty_kick",
      label: "PK",
      shortLabel: "PK",
      aliases: ["penalty_kick", "PK"],
    },
  ];

  const ALIAS_GROUPS = EVENTS.reduce((groups, event) => {
    groups[event.code] = event.aliases;
    event.aliases.forEach((alias) => {
      groups[alias] = event.aliases;
    });
    return groups;
  }, {});

  function getEvents() {
    return EVENTS.map((event) => ({ ...event }));
  }

  function getEventDef(code) {
    const normalized = String(code || "");
    return EVENTS.find((event) => event.aliases.includes(normalized) || event.code === normalized) || null;
  }

  function getEventLabel(code) {
    return getEventDef(code)?.label || code;
  }

  function matchesEventName(actual, expected) {
    const actualName = String(actual || "");
    const expectedName = String(expected || "");
    if (actualName === expectedName) return true;

    const group = ALIAS_GROUPS[expectedName];
    if (group) return group.includes(actualName);

    for (const aliases of Object.values(ALIAS_GROUPS)) {
      if (aliases.includes(expectedName) && aliases.includes(actualName)) {
        return true;
      }
    }

    return false;
  }

  return {
    EVENTS,
    getEvents,
    getEventDef,
    getEventLabel,
    matchesEventName,
  };
})();
