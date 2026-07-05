(function () {
  // 戦略定義:
  // 「サイド前進」という戦略が、
  // 幅を使って相手陣地へ前進できているかを評価する。
  //
  // Rule004（保持前進）= 安定性・主導権 / Rule005（ロング前進）= 突破力・スピード
  // Rule006（サイド前進）= 左・右サイドからの幅を使った前進（中央侵入は判定に不使用）
  const RULE_ID = "rule006";
  const PLAN_CATEGORY_KEY = "buildUp";
  const PLAN_OPTION = "サイド前進";
  const STATE_CATEGORY = "Build Up";
  const WINDOW_MINUTES = 5;

  const EVENT_LEFT_ADVANCE = "左侵入";
  const EVENT_RIGHT_ADVANCE = "右侵入";
  const EVENT_CENTRAL_ADVANCE = "中央侵入";
  const EVENT_LEFT_CONCEDED = "被左侵入";
  const EVENT_RIGHT_CONCEDED = "被右侵入";
  const EVENT_CENTRAL_CONCEDED = "被中央侵入";
  const EVENT_COUNTER_CONCEDED = "カウンター被弾";
  const EVENT_QUICK_RECOVERY = "即時奪回成功";

  const RELEVANT_EVENTS = [
    EVENT_LEFT_ADVANCE,
    EVENT_RIGHT_ADVANCE,
    EVENT_CENTRAL_ADVANCE,
    EVENT_LEFT_CONCEDED,
    EVENT_RIGHT_CONCEDED,
    EVENT_CENTRAL_CONCEDED,
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
      [EVENT_LEFT_ADVANCE]: countEvents(events, EVENT_LEFT_ADVANCE),
      [EVENT_RIGHT_ADVANCE]: countEvents(events, EVENT_RIGHT_ADVANCE),
      [EVENT_CENTRAL_ADVANCE]: countEvents(events, EVENT_CENTRAL_ADVANCE),
      [EVENT_LEFT_CONCEDED]: countEvents(events, EVENT_LEFT_CONCEDED),
      [EVENT_RIGHT_CONCEDED]: countEvents(events, EVENT_RIGHT_CONCEDED),
      [EVENT_CENTRAL_CONCEDED]: countEvents(events, EVENT_CENTRAL_CONCEDED),
      [EVENT_COUNTER_CONCEDED]: countEvents(events, EVENT_COUNTER_CONCEDED),
      [EVENT_QUICK_RECOVERY]: countEvents(events, EVENT_QUICK_RECOVERY),
    };
  }

  function resolveState(counts) {
    const sideForward = counts[EVENT_LEFT_ADVANCE] + counts[EVENT_RIGHT_ADVANCE];
    const sidePushedBack = counts[EVENT_LEFT_CONCEDED] + counts[EVENT_RIGHT_CONCEDED];
    const counterConceded = counts[EVENT_COUNTER_CONCEDED];

    if (counterConceded >= 2 || sidePushedBack >= 5 || (counterConceded >= 1 && sidePushedBack >= 2)) {
      return { label: "🔴 サイド前進崩壊", status: "red" };
    }
    if (
      counterConceded >= 1
      || sidePushedBack >= 4
      || (sidePushedBack >= 3 && sideForward <= 1)
      || (sidePushedBack >= 2 && sideForward <= 1)
    ) {
      return { label: "🟠 サイド前進不安定", status: "orange" };
    }
    if (
      counterConceded === 0
      && sideForward >= 2
      && (sideForward > sidePushedBack || (sideForward >= 2 && sidePushedBack <= 2))
    ) {
      return { label: "🟢 サイド前進維持", status: "green" };
    }
    if (
      (sideForward === 0 && sidePushedBack >= 1)
      || (sideForward === 1 && sidePushedBack >= 2)
      || (sideForward >= 2 && sidePushedBack >= 3)
      || (sideForward >= 1 && sideForward <= sidePushedBack)
    ) {
      return { label: "🟡 サイド前進停滞", status: "yellow" };
    }
    if (sideForward === 0 && sidePushedBack === 0 && counterConceded === 0) {
      return { label: "🟡 サイド前進停滞", status: "yellow" };
    }
    return null;
  }

  window.MO_STATE_ENGINE.registerRule({
    id: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      return window.MO_STATE_ENGINE?.planIncludesOption(plan, PLAN_CATEGORY_KEY, PLAN_OPTION) ?? false;
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
        planCategoryKey: PLAN_CATEGORY_KEY,
        category: STATE_CATEGORY,
        label: resolved.label,
        status: resolved.status,
        reasonEventCounts,
        evaluationWindowMinutes: WINDOW_MINUTES,
      };
    },
  });
})();
