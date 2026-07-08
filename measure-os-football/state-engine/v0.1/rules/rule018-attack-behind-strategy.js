(function () {
  // 戦略定義:
  // 「背後攻略」という戦略が、
  // 背後ルートを主な攻撃手段として活用し、
  // 背後からフィニッシュまで到達できているかを評価する。
  //
  // Attack Rule = どの攻撃ルートを主な勝ち筋として機能させられているか（How は評価しない）
  // Rule012（左優位）= 左サイド主軸 / Rule013（右優位）= 右サイド主軸 / Rule014（中央攻略）= 中央主軸 / Rule018（背後攻略）= 背後主軸
  const RULE_ID = "rule018";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "背後攻略";
  const STATE_CATEGORY = "Attack";
  const WINDOW_MINUTES = 5;

  const EVENT_BEHIND = "behind";
  const EVENT_SHOT = "shot";
  const EVENT_CHANCE = "bigChance";
  const EVENT_COUNTER = "counter";

  const RELEVANT_EVENT_CODES = [
    EVENT_BEHIND,
    EVENT_SHOT,
    EVENT_CHANCE,
    EVENT_COUNTER,
  ];

  const REASON_LABEL_BEHIND = "背後";
  const REASON_LABEL_SHOT = "シュート";
  const REASON_LABEL_CHANCE = "決定機";
  const REASON_LABEL_COUNTER = "被カウンター";

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

  function matchesEventName(actual, expected) {
    const matcher = window.MO_ATTACK_OBSERVER?.matchesEventName
      || window.MO_ATTACK_PLAN?.matchesEventName;
    if (typeof matcher === "function") {
      return matcher(actual, expected);
    }
    return String(actual || "") === String(expected || "");
  }

  function countEvents(events, eventCode) {
    const counter = window.MO_ATTACK_OBSERVER?.countMatchingEvents
      || window.MO_ATTACK_PLAN?.countMatchingEvents;
    if (typeof counter === "function") return counter(events, eventCode);
    return events.filter((event) => matchesEventName(event.eventName, eventCode)).length;
  }

  function isRelevantEvent(event) {
    return RELEVANT_EVENT_CODES.some((code) => matchesEventName(event?.eventName, code));
  }

  function buildReasonEventCounts(events) {
    return {
      [REASON_LABEL_BEHIND]: countEvents(events, EVENT_BEHIND),
      [REASON_LABEL_SHOT]: countEvents(events, EVENT_SHOT),
      [REASON_LABEL_CHANCE]: countEvents(events, EVENT_CHANCE),
      [REASON_LABEL_COUNTER]: countEvents(events, EVENT_COUNTER),
    };
  }

  function resolveState(counts) {
    const behind = counts[REASON_LABEL_BEHIND];
    const shot = counts[REASON_LABEL_SHOT];
    const chance = counts[REASON_LABEL_CHANCE];
    const counter = counts[REASON_LABEL_COUNTER];
    const finish = shot + chance;

    if (
      counter >= 2
      || (behind === 0 && shot === 0 && chance === 0 && counter >= 1)
    ) {
      return { label: "🔴 背後攻略崩壊", status: "red" };
    }
    if (
      (behind === 0 && shot >= 1)
      || counter === 1
    ) {
      return { label: "🟠 背後攻略不安定", status: "orange" };
    }
    if (
      behind >= 2
      && finish >= 1
      && counter <= 1
    ) {
      return { label: "🟢 背後攻略維持", status: "green" };
    }
    if (
      (behind >= 1 && shot === 0 && chance === 0)
      || (behind === 0 && shot === 0 && chance === 0 && counter === 0)
    ) {
      return { label: "🟡 背後攻略停滞", status: "yellow" };
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
        .filter(isRelevantEvent);
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
