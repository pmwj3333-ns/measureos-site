(function () {
  const RULE_ID = "rule003";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ローブロック";
  const STATE_CATEGORY = "Defense";
  const WINDOW_MINUTES = 5;

  const EVENT_LEFT_PENETRATION = "被左侵入";
  const EVENT_CENTRAL_PENETRATION = "被中央侵入";
  const EVENT_RIGHT_PENETRATION = "被右侵入";
  const EVENT_CROSS = "被クロス";
  const EVENT_SHOT = "被シュート";
  const EVENT_BALL_WON = "ボール奪取";

  const RELEVANT_EVENTS = [
    EVENT_LEFT_PENETRATION,
    EVENT_CENTRAL_PENETRATION,
    EVENT_RIGHT_PENETRATION,
    EVENT_CROSS,
    EVENT_SHOT,
    EVENT_BALL_WON,
  ];

  function parseEventTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return null;
    return minutes * 60 + seconds;
  }

  function eventsInWindow(events, elapsedSeconds) {
    const windowStart = Math.max(0, elapsedSeconds - WINDOW_MINUTES * 60);
    return events.filter((event) => {
      const eventSeconds = parseEventTime(event.time);
      return eventSeconds != null && eventSeconds >= windowStart && eventSeconds <= elapsedSeconds;
    });
  }

  function countEvents(events, eventName) {
    const counter = window.MO_DEFENSE_PLAN?.countMatchingEvents;
    if (typeof counter === "function") return counter(events, eventName);
    return events.filter((event) => event.eventName === eventName).length;
  }

  function buildReasonEventCounts(events) {
    return {
      [EVENT_LEFT_PENETRATION]: countEvents(events, EVENT_LEFT_PENETRATION),
      [EVENT_CENTRAL_PENETRATION]: countEvents(events, EVENT_CENTRAL_PENETRATION),
      [EVENT_RIGHT_PENETRATION]: countEvents(events, EVENT_RIGHT_PENETRATION),
      [EVENT_CROSS]: countEvents(events, EVENT_CROSS),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
      [EVENT_BALL_WON]: countEvents(events, EVENT_BALL_WON),
    };
  }

  function resolveState(counts) {
    const leftPenetration = counts[EVENT_LEFT_PENETRATION];
    const centralPenetration = counts[EVENT_CENTRAL_PENETRATION];
    const rightPenetration = counts[EVENT_RIGHT_PENETRATION];
    const cross = counts[EVENT_CROSS];
    const shot = counts[EVENT_SHOT];
    const flankPenetration = leftPenetration + rightPenetration;

    if (shot >= 2 || centralPenetration >= 5) {
      return { label: "🔴 ローブロック崩壊", status: "red" };
    }
    if (centralPenetration >= 2 || shot >= 1) {
      return { label: "🟠 ローブロック不安定", status: "orange" };
    }
    if (flankPenetration >= 2 || cross >= 2) {
      return { label: "🟡 ローブロック停滞", status: "yellow" };
    }
    if (centralPenetration <= 1 && shot === 0 && flankPenetration <= 1 && cross <= 1) {
      return { label: "🟢 ローブロック維持", status: "green" };
    }
    return null;
  }

  window.MO_STATE_ENGINE.registerRule({
    id: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const defensePlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(defensePlan) && defensePlan.includes(PLAN_OPTION);
    },

    evaluate(events, context = {}) {
      const elapsedSeconds = Math.max(0, Number(context.elapsed) || 0);
      const relevantEvents = eventsInWindow(events, elapsedSeconds)
        .filter((event) => {
          const matcher = window.MO_DEFENSE_PLAN?.matchesEventName;
          if (typeof matcher === "function") {
            return RELEVANT_EVENTS.some((name) => matcher(event.eventName, name));
          }
          return RELEVANT_EVENTS.includes(event.eventName);
        });
      const reasonEventCounts = buildReasonEventCounts(relevantEvents);
      const resolved = resolveState(reasonEventCounts);
      if (!resolved) return null;

      return {
        ruleId: RULE_ID,
        category: STATE_CATEGORY,
        label: resolved.label,
        status: resolved.status,
        reasonEventCounts,
        evaluationWindowMinutes: WINDOW_MINUTES,
      };
    },
  });
})();
