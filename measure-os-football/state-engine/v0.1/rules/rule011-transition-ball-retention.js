(function () {
  // 戦略定義:
  // 「ボール保持」という戦略が、
  // ボール奪取後に主導権を維持しながら攻撃を継続できているかを評価する。
  //
  // Rule008（即時奪回）= 主導権を取り戻す / Rule009（リトリート）= 時間を作り危険を減らす
  // Rule010（縦に速く）= 奪った主導権を素早く攻撃へつなげる
  // Rule011（ボール保持）= 奪った主導権を維持しながら試合を落ち着かせる
  //
  // Rule004（保持前進）= Build Up / 自陣から主導権を持って前進できているか（被侵入も評価）
  // Rule011（ボール保持）= Transition / ボール奪取直後に主導権を失わず試合を落ち着かせる
  //
  // Version0.1 判定: カウンター被弾（主導権喪失）を中心に評価。侵入は State 判定に不使用（Reason Events の補助指標）。
  // Version0.2 予定: 保持成功 / 保持失敗 / パス継続 等で精度向上。
  const RULE_ID = "rule011";
  const PLAN_CATEGORY_KEY = "transition";
  const PLAN_OPTION = "ボール保持";
  const STATE_CATEGORY = "Transition";
  const WINDOW_MINUTES = 5;

  const EVENT_LEFT_ADVANCE = "左侵入";
  const EVENT_CENTRAL_ADVANCE = "中央侵入";
  const EVENT_RIGHT_ADVANCE = "右侵入";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";
  const EVENT_QUICK_RECOVERY = "即時奪回成功";
  const EVENT_COUNTER_STARTED = "カウンター開始";
  const EVENT_SHOT = "シュート";

  const RELEVANT_EVENTS = [
    EVENT_LEFT_ADVANCE,
    EVENT_CENTRAL_ADVANCE,
    EVENT_RIGHT_ADVANCE,
    EVENT_COUNTER_CONCEDED,
    EVENT_QUICK_RECOVERY,
    EVENT_COUNTER_STARTED,
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
      [EVENT_LEFT_ADVANCE]: countEvents(events, EVENT_LEFT_ADVANCE),
      [EVENT_CENTRAL_ADVANCE]: countEvents(events, EVENT_CENTRAL_ADVANCE),
      [EVENT_RIGHT_ADVANCE]: countEvents(events, EVENT_RIGHT_ADVANCE),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
      [EVENT_QUICK_RECOVERY]: countEvents(events, EVENT_QUICK_RECOVERY),
      [EVENT_COUNTER_STARTED]: countEvents(events, EVENT_COUNTER_STARTED),
      [EVENT_SHOT]: countEvents(events, EVENT_SHOT),
    };
  }

  function resolveState(counts) {
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (counterConceded >= 2) {
      return { label: "🔴 ボール保持崩壊", status: "red" };
    }
    if (counterConceded === 1) {
      return { label: "🟠 ボール保持不安定", status: "orange" };
    }
    if (counterConceded === 0) {
      return { label: "🟢 ボール保持維持", status: "green" };
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
      if (relevantEvents.length === 0) return null;
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
