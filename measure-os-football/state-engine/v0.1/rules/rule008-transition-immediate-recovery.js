(function () {
  // 戦略定義:
  // 「即時奪回」という戦略が、
  // ボールロスト直後に主導権を素早く取り戻せているかを評価する。
  //
  // Build Up = どう前進するか / Transition = 攻守切り替えの瞬間に何を実現できているか
  const RULE_ID = "rule008";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "即時奪回";
  const STATE_CATEGORY = "Transition";
  const WINDOW_MINUTES = 5;

  const EVENT_QUICK_RECOVERY = "即時奪回成功";
  const EVENT_COUNTER_STARTED = "カウンター開始";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";

  const RELEVANT_EVENTS = [
    EVENT_QUICK_RECOVERY,
    EVENT_COUNTER_STARTED,
    EVENT_COUNTER_CONCEDED,
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
      [EVENT_QUICK_RECOVERY]: countEvents(events, EVENT_QUICK_RECOVERY),
      [EVENT_COUNTER_STARTED]: countEvents(events, EVENT_COUNTER_STARTED),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
    };
  }

  function resolveState(counts) {
    const recovery = counts[EVENT_QUICK_RECOVERY];
    const counterStarted = counts[EVENT_COUNTER_STARTED];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (
      counterConceded >= 2
      || (counterConceded >= 1 && counterStarted >= 2)
      || (counterConceded >= 1 && recovery === 0)
    ) {
      return { label: "🔴 即時奪回崩壊", status: "red" };
    }
    if (
      counterConceded === 1
      || counterStarted >= 4
      || (counterStarted >= 3 && recovery <= 1)
      || (counterStarted >= 2 && recovery === 0)
    ) {
      return { label: "🟠 即時奪回不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && recovery === 1
      && counterStarted === 0
    ) {
      return { label: "🟢 即時奪回維持", status: "green" };
    }
    if (
      counterConceded === 0
      && recovery >= 2
      && (recovery > counterStarted || (recovery >= 2 && counterStarted <= 1))
    ) {
      return { label: "🟢 即時奪回維持", status: "green" };
    }
    if (
      (recovery === 0 && counterStarted >= 1)
      || (recovery === 1 && counterStarted >= 1)
      || (recovery >= 1 && recovery <= counterStarted)
    ) {
      return { label: "🟡 即時奪回停滞", status: "yellow" };
    }
    return null;
  }

  window.MO_STATE_ENGINE.registerRule({
    id: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const transitionPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(transitionPlan) && transitionPlan.includes(PLAN_OPTION);
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
