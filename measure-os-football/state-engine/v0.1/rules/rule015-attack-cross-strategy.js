(function () {
  // 戦略定義:
  // 「クロス攻略」という戦略が、
  // クロスを主な決定機創出手段として活用し、
  // クロスから継続的にシュートへ繋げられているかを評価する。
  //
  // Attack Rule = どの攻撃ルート・決定機創出手段を勝ち筋として機能させられているか（How は評価しない）
  // Rule012〜014 = 侵入ルート主軸 + 決定機 / Rule015（クロス攻略）= クロス主軸 + シュート
  const RULE_ID = "rule015";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "クロス攻略";
  const STATE_CATEGORY = "Attack";
  const WINDOW_MINUTES = 5;

  const EVENT_LEFT_ADVANCE = "左侵入";
  const EVENT_CENTRAL_ADVANCE = "中央侵入";
  const EVENT_RIGHT_ADVANCE = "右侵入";
  const EVENT_CROSS = "クロス";
  const EVENT_SHOT = "シュート";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";

  const RELEVANT_EVENTS = [
    EVENT_LEFT_ADVANCE,
    EVENT_CENTRAL_ADVANCE,
    EVENT_RIGHT_ADVANCE,
    EVENT_CROSS,
    EVENT_SHOT,
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
      [EVENT_CROSS]: countEvents(events, EVENT_CROSS),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
      [EVENT_LEFT_ADVANCE]: countEvents(events, EVENT_LEFT_ADVANCE),
      [EVENT_CENTRAL_ADVANCE]: countEvents(events, EVENT_CENTRAL_ADVANCE),
      [EVENT_RIGHT_ADVANCE]: countEvents(events, EVENT_RIGHT_ADVANCE),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
    };
  }

  function resolveState(counts) {
    const cross = counts[EVENT_CROSS];
    const shot = counts[EVENT_SHOT];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (
      counterConceded >= 2
      || (counterConceded >= 1 && cross === 0)
    ) {
      return { label: "🔴 クロス攻略崩壊", status: "red" };
    }
    if (counterConceded === 1) {
      return { label: "🟠 クロス攻略不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && cross >= 1
      && shot >= 1
    ) {
      return { label: "🟢 クロス攻略維持", status: "green" };
    }
    if (cross === 0 || (cross >= 1 && shot === 0)) {
      return { label: "🟡 クロス攻略停滞", status: "yellow" };
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
