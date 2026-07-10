window.MO_TEAM_REVIEW_STATE_TIMELINE = (() => {
  const CATEGORY_ORDER = [
    { key: "attack", label: "Attack" },
    { key: "buildUp", label: "Build Up" },
    { key: "defense", label: "Defense" },
    { key: "transition", label: "Transition" },
  ];

  const STATUS_RANK = {
    green: 1,
    yellow: 2,
    orange: 3,
    red: 4,
  };

  const STATUS_META = {
    green: { emoji: "🟢", label: "Good" },
    yellow: { emoji: "🟡", label: "Watch" },
    orange: { emoji: "🟠", label: "Warning" },
    red: { emoji: "🔴", label: "Critical" },
  };

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return minutes * 60 + seconds;
  }

  function resolveMatchElapsed(record) {
    const events = Array.isArray(record?.events) ? record.events : [];
    const lastEvent = events[events.length - 1];
    if (lastEvent?.time) return parseMatchTime(lastEvent.time);
    const history = Array.isArray(record?.match?.planHistory) ? record.match.planHistory : [];
    const lastEntry = history[history.length - 1];
    return parseMatchTime(lastEntry?.matchTime);
  }

  function normalizeStatus(status) {
    const value = String(status || "").toLowerCase();
    if (value in STATUS_META) return value;
    return "yellow";
  }

  function pickCategoryState(states, categoryKey) {
    const matched = (Array.isArray(states) ? states : []).filter((state) => {
      const key = state.planCategoryKey
        || window.MO_REVIEW_HELPERS?.resolveStateCategoryKey?.(state.category);
      return key === categoryKey;
    });

    if (matched.length === 0) return null;

    return matched.reduce((worst, state) => {
      const currentRank = STATUS_RANK[normalizeStatus(state.status)] || 0;
      const worstRank = STATUS_RANK[normalizeStatus(worst.status)] || 0;
      return currentRank > worstRank ? state : worst;
    });
  }

  function evaluateRecordStates(record, plan) {
    const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;
    if (typeof evaluate !== "function" || !plan) return [];

    const events = Array.isArray(record.events) ? record.events : [];
    return evaluate({
      plan,
      events,
      elapsed: resolveMatchElapsed(record),
    });
  }

  function sortRecordsChronological(records) {
    return [...records].sort((a, b) => {
      const dateA = String(a.setup?.match_date || "");
      const dateB = String(b.setup?.match_date || "");
      if (dateA !== dateB) return dateA.localeCompare(dateB);
      return String(a.archived_at || "").localeCompare(String(b.archived_at || ""));
    });
  }

  function buildStateTimeline(records, contextMap) {
    const chronological = sortRecordsChronological(records);

    const categories = CATEGORY_ORDER.map(({ key, label }) => ({
      key,
      label,
      points: chronological.map((record) => {
        const ctx = contextMap?.[record.id];
        const plan = ctx?.plan || window.MO_TEAM_REVIEW_FILTERS?.getLastPlan?.(record);
        const states = evaluateRecordStates(record, plan);
        const categoryState = pickCategoryState(states, key);
        const status = normalizeStatus(categoryState?.status);
        const meta = STATUS_META[status];

        return {
          recordId: record.id,
          matchDate: record.setup?.match_date || "",
          opponent: record.setup?.opponent || "対戦相手",
          status,
          emoji: meta.emoji,
          statusLabel: meta.label,
          stateLabel: categoryState?.label || "—",
          href: `#match/${encodeURIComponent(record.id)}`,
        };
      }),
    }));

    return { categories };
  }

  return {
    buildStateTimeline,
    STATUS_META,
  };
})();
