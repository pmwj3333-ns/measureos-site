window.MO_ATTACK_FINISH_RATE = (() => {
  const WINDOW_MINUTES = 5;
  const MIN_ATTACK_COUNT = 5;
  const STATE_CATEGORY = "Attack";

  const LABEL_LEFT = "左侵入";
  const LABEL_CENTER = "中央侵入";
  const LABEL_RIGHT = "右侵入";
  const LABEL_BEHIND = "背後";
  const LABEL_SHOT = "シュート";
  const LABEL_BIG_CHANCE = "決定機";
  const LABEL_LOST = "ロスト";

  function parseEventTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return null;
    return minutes * 60 + seconds;
  }

  function eventsInWindow(events, elapsedSeconds, windowMinutes = WINDOW_MINUTES) {
    const windowStart = Math.max(0, elapsedSeconds - windowMinutes * 60);
    return (Array.isArray(events) ? events : []).filter((event) => {
      const eventSeconds = parseEventTime(event?.time);
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

  function isAttackEvent(eventName, attackEventCodes) {
    return attackEventCodes.some((code) => matchesEventName(eventName, code));
  }

  function classifyFinish(eventName) {
    if (matchesEventName(eventName, "shot") || matchesEventName(eventName, LABEL_SHOT)) {
      return "shot";
    }
    if (matchesEventName(eventName, "bigChance") || matchesEventName(eventName, LABEL_BIG_CHANCE)) {
      return "bigChance";
    }
    if (
      matchesEventName(eventName, "lost")
      || matchesEventName(eventName, LABEL_LOST)
      || matchesEventName(eventName, "ボールロスト")
    ) {
      return "lost";
    }
    return null;
  }

  function sortEvents(events) {
    return [...events].sort((left, right) => {
      const leftSeconds = parseEventTime(left?.time) ?? 0;
      const rightSeconds = parseEventTime(right?.time) ?? 0;
      if (leftSeconds !== rightSeconds) return leftSeconds - rightSeconds;
      return (Number(left?.inputOrder) || 0) - (Number(right?.inputOrder) || 0);
    });
  }

  function countDirectionAttacks(events, code) {
    return events.filter((event) => matchesEventName(event?.eventName, code)).length;
  }

  function analyzeAttackSequences(events, attackEventCodes) {
    const sorted = sortEvents(events);
    let attackCount = 0;
    let openAttacks = 0;
    let lostCount = 0;
    let shotCount = 0;
    let bigChanceCount = 0;

    sorted.forEach((event) => {
      const eventName = event?.eventName;
      if (!eventName) return;

      if (isAttackEvent(eventName, attackEventCodes)) {
        attackCount += 1;
        openAttacks += 1;
        return;
      }

      const finishType = classifyFinish(eventName);
      if (!finishType || openAttacks <= 0) return;

      openAttacks -= 1;
      if (finishType === "lost") lostCount += 1;
      if (finishType === "shot") shotCount += 1;
      if (finishType === "bigChance") bigChanceCount += 1;
    });

    lostCount += openAttacks;

    const lostRate = attackCount > 0 ? (lostCount / attackCount) * 100 : 0;
    const shotRate = attackCount > 0 ? (shotCount / attackCount) * 100 : 0;
    const bigChanceRate = attackCount > 0 ? (bigChanceCount / attackCount) * 100 : 0;

    return {
      attackCount,
      lostCount,
      shotCount,
      bigChanceCount,
      lostRate,
      shotRate,
      bigChanceRate,
    };
  }

  function resolveStateFromLostRate(lostRate, planOption) {
    if (lostRate < 55) {
      return { label: `🟢 ${planOption}維持`, status: "green" };
    }
    if (lostRate <= 70) {
      return { label: `🟡 ${planOption}停滞`, status: "yellow" };
    }
    if (lostRate <= 85) {
      return { label: `🟠 ${planOption}不安定`, status: "orange" };
    }
    return { label: `🔴 ${planOption}崩壊`, status: "red" };
  }

  function buildReasonEventCounts(events, metrics, attackEventCodes) {
    return {
      [LABEL_LEFT]: countDirectionAttacks(events, "left"),
      [LABEL_CENTER]: countDirectionAttacks(events, "center"),
      [LABEL_RIGHT]: countDirectionAttacks(events, "right"),
      [LABEL_BEHIND]: countDirectionAttacks(events, "behind"),
      [LABEL_SHOT]: metrics.shotCount,
      [LABEL_BIG_CHANCE]: metrics.bigChanceCount,
      [LABEL_LOST]: metrics.lostCount,
      attackCount: metrics.attackCount,
      lostRate: Math.round(metrics.lostRate),
      shotRate: Math.round(metrics.shotRate),
      bigChanceRate: Math.round(metrics.bigChanceRate),
      attackEventCodes: attackEventCodes.join(","),
    };
  }

  function registerAttackFinishRateRule({
    ruleId,
    planCategoryKey,
    planOption,
    attackEventCodes,
  }) {
    if (!ruleId || !planCategoryKey || !planOption || !Array.isArray(attackEventCodes)) {
      return;
    }

    window.MO_STATE_ENGINE.registerRule({
      id: ruleId,
      planCategoryKey,
      planOption,

      isEnabled(plan) {
        const categoryPlan = plan?.categories?.[planCategoryKey];
        return Array.isArray(categoryPlan) && categoryPlan.includes(planOption);
      },

      evaluate(events, context = {}) {
        const elapsedSeconds = Math.max(0, Number(context.elapsed) || 0);
        const windowEvents = eventsInWindow(events, elapsedSeconds);
        const sequenceEvents = windowEvents.filter((event) => {
          const eventName = event?.eventName;
          if (!eventName) return false;
          return isAttackEvent(eventName, attackEventCodes) || classifyFinish(eventName) != null;
        });

        if (sequenceEvents.length === 0) return null;

        const metrics = analyzeAttackSequences(sequenceEvents, attackEventCodes);
        if (metrics.attackCount === 0) return null;

        if (metrics.attackCount < MIN_ATTACK_COUNT) {
          return {
            ruleId,
            category: STATE_CATEGORY,
            label: `⏳ ${planOption} 判定保留`,
            status: "pending",
            reasonEventCounts: buildReasonEventCounts(sequenceEvents, metrics, attackEventCodes),
            evaluationWindowMinutes: WINDOW_MINUTES,
            finishRateMetrics: metrics,
          };
        }

        const resolved = resolveStateFromLostRate(metrics.lostRate, planOption);

        return {
          ruleId,
          category: STATE_CATEGORY,
          label: resolved.label,
          status: resolved.status,
          reasonEventCounts: buildReasonEventCounts(sequenceEvents, metrics, attackEventCodes),
          evaluationWindowMinutes: WINDOW_MINUTES,
          finishRateMetrics: metrics,
        };
      },
    });
  }

  return {
    WINDOW_MINUTES,
    MIN_ATTACK_COUNT,
    parseEventTime,
    eventsInWindow,
    matchesEventName,
    analyzeAttackSequences,
    resolveStateFromLostRate,
    buildReasonEventCounts,
    registerAttackFinishRateRule,
  };
})();
