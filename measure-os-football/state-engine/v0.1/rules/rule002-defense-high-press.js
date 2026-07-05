(function () {
  const RULE_ID = "rule002";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ハイプレス";
  const STATE_CATEGORY = "Defense";
  const WINDOW_MINUTES = 5;

  const EVENT_FRONT_LINE = "前線奪取";
  const EVENT_CENTRAL_PENETRATION = "被中央侵入";
  const EVENT_SHOT = "被シュート";

  const RELEVANT_EVENTS = [
    EVENT_FRONT_LINE,
    EVENT_CENTRAL_PENETRATION,
    EVENT_SHOT,
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
    return events.filter((event) => event.eventName === eventName).length;
  }

  function buildReasonEventCounts(events) {
    return {
      [EVENT_FRONT_LINE]: countEvents(events, EVENT_FRONT_LINE),
      [EVENT_CENTRAL_PENETRATION]: countEvents(events, EVENT_CENTRAL_PENETRATION),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
    };
  }

  function resolveState(counts) {
    const frontLine = counts[EVENT_FRONT_LINE];
    const centralPenetration = counts[EVENT_CENTRAL_PENETRATION];
    const shot = counts[EVENT_SHOT];

    if (shot >= 2 || centralPenetration >= 5) {
      return { label: "🔴 ハイプレス崩壊", status: "red" };
    }
    if (centralPenetration >= 3 || shot >= 1) {
      return { label: "🟠 ハイプレス不安定", status: "orange" };
    }
    if (frontLine === 1 || centralPenetration === 2) {
      return { label: "🟡 ハイプレス停滞", status: "yellow" };
    }
    if (frontLine >= 2 && centralPenetration <= 1 && shot === 0) {
      return { label: "🟢 ハイプレス維持", status: "green" };
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
        .filter((event) => RELEVANT_EVENTS.includes(event.eventName));
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
