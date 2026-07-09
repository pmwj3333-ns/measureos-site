window.MO_MATCH_METRICS = (() => {
  const ATTACK_ITEMS = [
    { code: "left", label: "左" },
    { code: "center", label: "中央" },
    { code: "right", label: "右" },
  ];

  const BUILD_UP_ITEMS = [
    { code: "possession", label: "保持前進" },
    { code: "long", label: "ロング前進" },
  ];

  const FINISH_ITEMS = [
    { code: "lost", label: "ロスト" },
    { code: "shot", label: "シュート" },
    { code: "bigChance", label: "決定機" },
  ];

  function normalizeEvents(events) {
    return Array.isArray(events) ? events : [];
  }

  function countByCode(events, code) {
    const matcher = window.MO_ATTACK_OBSERVER?.matchesEventName;
    if (!matcher) return 0;

    if (code === "lost") {
      return events.filter((event) => {
        const name = event?.eventName;
        return (
          matcher(name, "lost")
          || matcher(name, "ロスト")
          || matcher(name, "ボールロスト")
        );
      }).length;
    }

    return events.filter((event) => matcher(event?.eventName, code)).length;
  }

  function buildPercentItems(items, events) {
    const counts = items.map((item) => ({
      ...item,
      count: countByCode(events, item.code),
    }));
    const total = counts.reduce((sum, item) => sum + item.count, 0);

    return counts.map((item) => ({
      code: item.code,
      label: item.label,
      count: item.count,
      percent: total > 0 ? Math.round((item.count / total) * 100) : 0,
    }));
  }

  function aggregate(events) {
    const matchEvents = normalizeEvents(events);

    return {
      eventCount: matchEvents.length,
      attack: buildPercentItems(ATTACK_ITEMS, matchEvents),
      buildUp: buildPercentItems(BUILD_UP_ITEMS, matchEvents),
      finish: buildPercentItems(FINISH_ITEMS, matchEvents),
    };
  }

  return {
    ATTACK_ITEMS,
    BUILD_UP_ITEMS,
    FINISH_ITEMS,
    countByCode,
    buildPercentItems,
    aggregate,
  };
})();
