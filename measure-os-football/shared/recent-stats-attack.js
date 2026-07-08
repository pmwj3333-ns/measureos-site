window.MO_RECENT_STATS_ATTACK = (() => {
  const WINDOW_SECONDS = 5 * 60;

  const ATTACK_ITEMS = [
    { code: "left", label: "左" },
    { code: "center", label: "中央" },
    { code: "right", label: "右" },
    { code: "behind", label: "背後" },
  ];

  const BUILD_UP_ITEMS = [
    { code: "possession", label: "保持前進" },
    { code: "long", label: "ロング前進" },
  ];

  const CHANCE_ITEMS = [
    { code: "shot", label: "シュート", unit: "本" },
    { code: "bigChance", label: "決定機", unit: "回" },
  ];

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function filterRecentEvents(events, currentElapsed, windowSeconds = WINDOW_SECONDS) {
    const current = Math.max(0, Number(currentElapsed) || 0);
    const window = Math.max(0, Number(windowSeconds) || WINDOW_SECONDS);

    return (Array.isArray(events) ? events : []).filter((event) => {
      const eventElapsed = parseMatchTime(event?.time);
      const age = current - eventElapsed;
      return age >= 0 && age <= window;
    });
  }

  function countByCode(events, code) {
    const matcher = window.MO_ATTACK_OBSERVER?.matchesEventName;
    if (!matcher) return 0;
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

  function buildCountItems(items, events) {
    return items.map((item) => ({
      code: item.code,
      label: item.label,
      unit: item.unit,
      count: countByCode(events, item.code),
    }));
  }

  function aggregate(events, currentElapsed, windowSeconds = WINDOW_SECONDS) {
    const recentEvents = filterRecentEvents(events, currentElapsed, windowSeconds);

    return {
      windowSeconds,
      eventCount: recentEvents.length,
      attack: buildPercentItems(ATTACK_ITEMS, recentEvents),
      buildUp: buildPercentItems(BUILD_UP_ITEMS, recentEvents),
      chance: buildCountItems(CHANCE_ITEMS, recentEvents),
    };
  }

  return {
    WINDOW_SECONDS,
    ATTACK_ITEMS,
    BUILD_UP_ITEMS,
    CHANCE_ITEMS,
    parseMatchTime,
    filterRecentEvents,
    aggregate,
  };
})();
