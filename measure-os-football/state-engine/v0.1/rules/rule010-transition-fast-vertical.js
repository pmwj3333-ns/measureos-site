(function () {
  // 戦略定義:
  // 「縦に速く」という戦略が、
  // ボール奪取後に素早く相手ゴール方向へ前進できているかを評価する。
  //
  // Rule008（即時奪回）= 主導権を取り戻す / Rule009（リトリート）= 時間を作り危険を減らす
  // Rule010（縦に速く）= 奪った主導権を素早く攻撃へつなげる
  //
  // Rule005（ロング前進）= Build Up / 自陣からどう前進するか（被侵入も評価）
  // Rule010（縦に速く）= Transition / ボール奪取後にどれだけ素早く攻撃へ移行できているか
  const RULE_ID = "rule010";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "縦に速く";
  const STATE_CATEGORY = "Transition";
  const WINDOW_MINUTES = 5;

  const EVENT_COUNTER_STARTED = "カウンター開始";
  const EVENT_LEFT_ADVANCE = "左侵入";
  const EVENT_CENTRAL_ADVANCE = "中央侵入";
  const EVENT_RIGHT_ADVANCE = "右侵入";
  const EVENT_SHOT = "シュート";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";
  const EVENT_QUICK_RECOVERY = "即時奪回成功";

  const RELEVANT_EVENTS = [
    EVENT_COUNTER_STARTED,
    EVENT_LEFT_ADVANCE,
    EVENT_CENTRAL_ADVANCE,
    EVENT_RIGHT_ADVANCE,
    EVENT_SHOT,
    EVENT_COUNTER_CONCEDED,
    EVENT_QUICK_RECOVERY,
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
      [EVENT_COUNTER_STARTED]: countEvents(events, EVENT_COUNTER_STARTED),
      [EVENT_LEFT_ADVANCE]: countEvents(events, EVENT_LEFT_ADVANCE),
      [EVENT_CENTRAL_ADVANCE]: countEvents(events, EVENT_CENTRAL_ADVANCE),
      [EVENT_RIGHT_ADVANCE]: countEvents(events, EVENT_RIGHT_ADVANCE),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
      [EVENT_QUICK_RECOVERY]: countEvents(events, EVENT_QUICK_RECOVERY),
    };
  }

  function resolveState(counts) {
    const counterStarted = counts[EVENT_COUNTER_STARTED];
    const forward = counts[EVENT_LEFT_ADVANCE]
      + counts[EVENT_CENTRAL_ADVANCE]
      + counts[EVENT_RIGHT_ADVANCE];
    const shot = counts[EVENT_SHOT];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (
      counterConceded >= 2
      || (counterConceded >= 1 && forward === 0 && shot === 0 && counterStarted <= 1)
    ) {
      return { label: "🔴 縦に速く崩壊", status: "red" };
    }
    if (
      counterConceded === 1
      || (counterStarted >= 3 && forward <= 1 && shot === 0)
    ) {
      return { label: "🟠 縦に速く不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && counterStarted >= 1
      && (forward >= 1 || shot >= 1)
    ) {
      return { label: "🟢 縦に速く維持", status: "green" };
    }
    if (
      (counterStarted >= 1 && forward === 0 && shot === 0)
      || (counterStarted === 0 && forward >= 1)
    ) {
      return { label: "🟡 縦に速く停滞", status: "yellow" };
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
