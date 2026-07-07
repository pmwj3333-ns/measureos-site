(function () {
  // 戦略定義:
  // 「リトリート」という戦略が、
  // ボールロスト後に素早く守備ブロックを整え、
  // 相手の攻撃を遅らせ、危険なエリアへの侵入を抑えられているかを評価する。
  //
  // Rule008（即時奪回）= 主導権を素早く取り戻す / Rule009（リトリート）= 危険な攻撃を遅らせ、守備を整える
  const RULE_ID = "rule009";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "リトリート";
  const STATE_CATEGORY = "Transition";
  const WINDOW_MINUTES = 5;

  const EVENT_CENTRAL_CONCEDED = "被中央侵入";
  const EVENT_SHOT_CONCEDED = "被シュート";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";
  const EVENT_BALL_WON = "ボール奪取";
  const EVENT_LEFT_CONCEDED = "被左侵入";
  const EVENT_RIGHT_CONCEDED = "被右侵入";

  const EVENT_RETREAT = "リトリート";

  const RELEVANT_EVENTS = [
    EVENT_CENTRAL_CONCEDED,
    EVENT_SHOT_CONCEDED,
    EVENT_COUNTER_CONCEDED,
    EVENT_BALL_WON,
    EVENT_LEFT_CONCEDED,
    EVENT_RIGHT_CONCEDED,
    "被背後",
    EVENT_RETREAT,
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
      [EVENT_CENTRAL_CONCEDED]: countEvents(events, EVENT_CENTRAL_CONCEDED),
      [EVENT_SHOT_CONCEDED]: countEvents(events, EVENT_SHOT_CONCEDED),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
      [EVENT_BALL_WON]: countEvents(events, EVENT_BALL_WON),
      [EVENT_LEFT_CONCEDED]: countEvents(events, EVENT_LEFT_CONCEDED),
      [EVENT_RIGHT_CONCEDED]: countEvents(events, EVENT_RIGHT_CONCEDED),
    };
  }

  function resolveState(counts) {
    const centralConceded = counts[EVENT_CENTRAL_CONCEDED];
    const shotConceded = counts[EVENT_SHOT_CONCEDED];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (
      counterConceded >= 2
      || shotConceded >= 2
      || centralConceded >= 5
      || (counterConceded >= 1 && centralConceded >= 2)
    ) {
      return { label: "🔴 リトリート崩壊", status: "red" };
    }
    if (
      counterConceded === 1
      || shotConceded === 1
      || centralConceded >= 3
    ) {
      return { label: "🟠 リトリート不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && shotConceded === 0
      && centralConceded <= 1
    ) {
      return { label: "🟢 リトリート維持", status: "green" };
    }
    if (
      counterConceded === 0
      && shotConceded === 0
      && centralConceded === 2
    ) {
      return { label: "🟡 リトリート停滞", status: "yellow" };
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
