(function () {
  // 戦略定義:
  // 「中央攻略」という戦略が、
  // 中央を主な攻撃ルートとして活用し、
  // 中央攻撃から継続的に決定機を創出できているかを評価する。
  //
  // Attack Rule = どの攻撃ルートを主な勝ち筋として機能させられているか（How は評価しない）
  // Rule012（左優位）= 左サイド主軸 / Rule013（右優位）= 右サイド主軸 / Rule014（中央攻略）= 中央主軸
  const RULE_ID = "rule014";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "中央攻略";
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
      [EVENT_CENTRAL_ADVANCE]: countEvents(events, EVENT_CENTRAL_ADVANCE),
      [EVENT_LEFT_ADVANCE]: countEvents(events, EVENT_LEFT_ADVANCE),
      [EVENT_RIGHT_ADVANCE]: countEvents(events, EVENT_RIGHT_ADVANCE),
      [EVENT_CROSS]: countEvents(events, EVENT_CROSS),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
    };
  }

  function resolveState(counts) {
    const leftAdvance = counts[EVENT_LEFT_ADVANCE];
    const centralAdvance = counts[EVENT_CENTRAL_ADVANCE];
    const rightAdvance = counts[EVENT_RIGHT_ADVANCE];
    const cross = counts[EVENT_CROSS];
    const shot = counts[EVENT_SHOT];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (
      counterConceded >= 2
      || (counterConceded >= 1 && centralAdvance === 0)
    ) {
      return { label: "🔴 中央攻略崩壊", status: "red" };
    }
    if (counterConceded === 1) {
      return { label: "🟠 中央攻略不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && centralAdvance > leftAdvance
      && centralAdvance > rightAdvance
      && (shot >= 1 || cross >= 1)
    ) {
      return { label: "🟢 中央攻略維持", status: "green" };
    }
    if (
      centralAdvance === 0
      || centralAdvance === leftAdvance
      || centralAdvance === rightAdvance
      || (centralAdvance > leftAdvance && centralAdvance > rightAdvance && cross === 0 && shot === 0)
    ) {
      return { label: "🟡 中央攻略停滞", status: "yellow" };
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
