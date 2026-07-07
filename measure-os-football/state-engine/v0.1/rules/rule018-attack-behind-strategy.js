(function () {
  const RULE_ID = "rule018";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "背後攻略";
  const STATE_CATEGORY = "Attack";
  const WINDOW_MINUTES = 5;

  const EVENT_BEHIND = "behind";
  const EVENT_SHOT = "shot";
  const EVENT_CHANCE = "bigChance";
  const EVENT_LEFT = "left";
  const EVENT_CENTRAL = "center";
  const EVENT_RIGHT = "right";

  const RELEVANT_EVENTS = [
    EVENT_BEHIND,
    EVENT_SHOT,
    EVENT_CHANCE,
    EVENT_LEFT,
    EVENT_CENTRAL,
    EVENT_RIGHT,
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
    const counter = window.MO_ATTACK_OBSERVER?.countMatchingEvents
      || window.MO_ATTACK_PLAN?.countMatchingEvents;
    if (typeof counter === "function") return counter(events, eventName);
    return events.filter((event) => event.eventName === eventName).length;
  }

  function buildReasonEventCounts(events) {
    return {
      [EVENT_BEHIND]: countEvents(events, EVENT_BEHIND),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
      [EVENT_CHANCE]: countEvents(events, EVENT_CHANCE),
      [EVENT_LEFT]: countEvents(events, EVENT_LEFT),
      [EVENT_CENTRAL]: countEvents(events, EVENT_CENTRAL),
      [EVENT_RIGHT]: countEvents(events, EVENT_RIGHT),
    };
  }

  function resolveState(counts) {
    const behind = counts[EVENT_BEHIND];
    const shot = counts[EVENT_SHOT];
    const chance = counts[EVENT_CHANCE];
    const finish = shot + chance;

    if (behind >= 2 && finish >= 1) {
      return { label: "🟢 背後攻略維持", status: "green" };
    }
    if (behind >= 1 && finish === 0) {
      return { label: "🟡 背後攻略停滞", status: "yellow" };
    }
    if (behind === 0 && finish >= 1) {
      return { label: "🟠 背後攻略不安定", status: "orange" };
    }
    if (behind === 0) {
      return { label: "🔴 背後攻略崩壊", status: "red" };
    }
    return null;
  }

  window.MO_STATE_ENGINE.registerRule({
    id: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const attackPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(attackPlan) && attackPlan.includes(PLAN_OPTION);
    },

    evaluate(events, context = {}) {
      const elapsedSeconds = Math.max(0, Number(context.elapsed) || 0);
      const relevantEvents = eventsInWindow(events, elapsedSeconds)
        .filter((event) => {
          const matcher = window.MO_ATTACK_OBSERVER?.matchesEventName
            || window.MO_ATTACK_PLAN?.matchesEventName;
          if (typeof matcher === "function") {
            return RELEVANT_EVENTS.some((name) => matcher(event.eventName, name));
          }
          return RELEVANT_EVENTS.includes(event.eventName);
        });
      if (relevantEvents.length === 0) return null;
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
