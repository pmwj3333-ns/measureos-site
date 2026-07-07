(function () {
  // 戦略定義:
  // 「ミドルブロック」という戦略が、
  // 自陣と敵陣の中間エリアで守備ブロックを形成し、
  // 相手の前進を制限しながら危険な侵入を抑制できているかを評価する。
  //
  // Rule002（ハイプレス）= 前線から奪う / Rule003（ローブロック）= 深く守る
  // Rule016（ミドルブロック）= 中間でブロックし、中央が単独最多ルートでない状態を維持して奪取へ繋げる
  const RULE_ID = "rule016";
  const PLAN_CATEGORY_KEY = "defense";
  const PLAN_OPTION = "ミドルブロック";
  const STATE_CATEGORY = "Defense";
  const WINDOW_MINUTES = 5;

  const EVENT_CENTRAL_CONCEDED = "被中央侵入";
  const EVENT_LEFT_CONCEDED = "被左侵入";
  const EVENT_RIGHT_CONCEDED = "被右侵入";
  const EVENT_CROSS_CONCEDED = "被クロス";
  const EVENT_SHOT_CONCEDED = "被シュート";
  const EVENT_BALL_WON = "ボール奪取";
  const EVENT_FRONT_LINE = "前線奪取";

  const RELEVANT_EVENTS = [
    EVENT_CENTRAL_CONCEDED,
    EVENT_LEFT_CONCEDED,
    EVENT_RIGHT_CONCEDED,
    EVENT_CROSS_CONCEDED,
    EVENT_SHOT_CONCEDED,
    EVENT_BALL_WON,
    EVENT_FRONT_LINE,
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
      [EVENT_LEFT_CONCEDED]: countEvents(events, EVENT_LEFT_CONCEDED),
      [EVENT_RIGHT_CONCEDED]: countEvents(events, EVENT_RIGHT_CONCEDED),
      [EVENT_CROSS_CONCEDED]: countEvents(events, EVENT_CROSS_CONCEDED),
      [EVENT_SHOT_CONCEDED]: countEvents(events, EVENT_SHOT_CONCEDED),
      [EVENT_BALL_WON]: countEvents(events, EVENT_BALL_WON),
      [EVENT_FRONT_LINE]: countEvents(events, EVENT_FRONT_LINE),
    };
  }

  function isCentralSoleMost(central, left, right) {
    return central > 0 && central > left && central > right;
  }

  function resolveState(counts) {
    const centralConceded = counts[EVENT_CENTRAL_CONCEDED];
    const leftConceded = counts[EVENT_LEFT_CONCEDED];
    const rightConceded = counts[EVENT_RIGHT_CONCEDED];
    const shotConceded = counts[EVENT_SHOT_CONCEDED];
    const ballWon = counts[EVENT_BALL_WON];
    const frontLine = counts[EVENT_FRONT_LINE];
    const centralIsSoleMost = isCentralSoleMost(centralConceded, leftConceded, rightConceded);

    if (shotConceded >= 2) {
      return { label: "🔴 ミドルブロック崩壊", status: "red" };
    }
    if (shotConceded === 1) {
      return { label: "🟠 ミドルブロック不安定", status: "orange" };
    }
    if (
      shotConceded === 0
      && (ballWon >= 1 || frontLine >= 1)
      && !centralIsSoleMost
    ) {
      return { label: "🟢 ミドルブロック維持", status: "green" };
    }
    if (
      (ballWon === 0 && frontLine === 0)
      || centralIsSoleMost
    ) {
      return { label: "🟡 ミドルブロック停滞", status: "yellow" };
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
