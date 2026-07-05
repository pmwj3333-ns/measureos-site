(function () {
  const PLAN_CATEGORY_KEYS = ["attack", "defense", "buildUp", "transition"];

  const STATE_STATUS_SCORE = {
    green: 4,
    yellow: 3,
    orange: 2,
    red: 1,
  };

  const ATTACK_EVENTS = ["左侵入", "中央侵入", "右侵入", "クロス", "シュート"];
  const DEFENSE_EVENTS = [
    "被左侵入",
    "被中央侵入",
    "被右侵入",
    "被クロス",
    "被シュート",
    "ボール奪取",
    "前線奪取",
  ];
  const BUILD_UP_EVENTS = [
    "左侵入",
    "中央侵入",
    "右侵入",
    "被左侵入",
    "被中央侵入",
    "被右侵入",
    "カウンター被弾",
    "即時奪回成功",
  ];
  const TRANSITION_EVENTS = ["即時奪回成功", "カウンター開始", "カウンター被弾"];
  const SET_PIECE_EVENTS = ["CK", "FK", "PK", "決定機"];

  const ATTACK_EVENT_LABELS = {
    "左侵入": "Left Attack",
    "中央侵入": "Central Attack",
    "右侵入": "Right Attack",
    "クロス": "Cross",
    "シュート": "Shot",
  };

  const DEFENSE_EVENT_LABELS = {
    "被左侵入": "Left Conceded",
    "被中央侵入": "Central Conceded",
    "被右侵入": "Right Conceded",
    "被クロス": "Cross Conceded",
    "被シュート": "Shot Conceded",
    "ボール奪取": "Ball Won",
    "前線奪取": "High Press",
  };

  const BUILD_UP_EVENT_LABELS = {
    "左侵入": "Left Advance",
    "中央侵入": "Central Advance",
    "右侵入": "Right Advance",
    "被左侵入": "Left Conceded",
    "被中央侵入": "Central Conceded",
    "被右侵入": "Right Conceded",
    "カウンター被弾": "Counter Conceded",
    "即時奪回成功": "Immediate Recovery",
  };

  const TRANSITION_EVENT_LABELS = {
    "即時奪回成功": "Immediate Recovery",
    "カウンター開始": "Counter Attack",
    "カウンター被弾": "Counter Conceded",
  };

  const SET_PIECE_EVENT_LABELS = {
    CK: "Corner Kick",
    FK: "Free Kick",
    PK: "Penalty Kick",
    "決定機": "Chance",
  };

  const PLAN_OPTION_RULE_IDS = {
    attack: {
      "左優位": "rule012",
      "右優位": "rule013",
      "中央攻略": "rule014",
      "クロス攻略": "rule015",
    },
    defense: {
      "ハイプレス": "rule002",
      "ミドルブロック": "rule016",
      "ローブロック": "rule003",
      "サイド誘導": "rule017",
    },
    buildUp: {
      "保持前進": "rule004",
      "ロング前進": "rule005",
      "サイド前進": "rule006",
      "中央前進": "rule007",
    },
    transition: {
      "即時奪回": "rule008",
      "リトリート": "rule009",
      "縦に速く": "rule010",
      "ボール保持": "rule011",
    },
  };

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function normalizeTeam(team) {
    const value = String(team || "").trim().toLowerCase();
    if (value === "home") return "home";
    if (value === "away") return "away";
    return null;
  }

  function readPlanCategory(plan, categoryKey) {
    if (window.MO_STATE_ENGINE?.readPlanCategory) {
      return window.MO_STATE_ENGINE.readPlanCategory(plan, categoryKey);
    }
    const items = plan?.categories?.[categoryKey];
    return Array.isArray(items) ? items : [];
  }

  function filterEventsByNames(events, allowedNames) {
    const allowed = new Set(allowedNames);
    return events.filter((event) => allowed.has(event.eventName));
  }

  function countEventsByName(events) {
    const counts = new Map();
    events.forEach((event) => {
      counts.set(event.eventName, (counts.get(event.eventName) || 0) + 1);
    });
    return counts;
  }

  function filterFirstHalfEvents(events) {
    if (!Array.isArray(events)) return [];
    return events.filter((event) => event?.phase === "前半" || !event?.phase);
  }

  function getEvaluationElapsed(events) {
    return events.reduce((max, event) => Math.max(max, parseMatchTime(event.time)), 0);
  }

  function evaluateStateEngine(plan, events) {
    const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;
    if (typeof evaluate !== "function" || !plan) return [];

    return evaluate({
      plan,
      events,
      elapsed: getEvaluationElapsed(events),
    });
  }

  function indexStatesByRuleId(states) {
    const map = new Map();
    (Array.isArray(states) ? states : []).forEach((state) => {
      if (state?.ruleId) map.set(state.ruleId, state);
    });
    return map;
  }

  function resolveRuleEvaluation(ruleId, engineStatesByRuleId, liveStatesByRuleId) {
    const engineState = engineStatesByRuleId.get(ruleId);
    if (engineState?.status) return engineState;

    const liveState = liveStatesByRuleId?.[ruleId];
    if (liveState?.source === "rule" && liveState?.status) return liveState;

    return null;
  }

  function stateStatusToScore(status) {
    return STATE_STATUS_SCORE[status] ?? null;
  }

  function scoreToPlanRating(score) {
    if (score >= 3.5) return "Excellent";
    if (score >= 2.5) return "Good";
    if (score >= 1.5) return "Average";
    return "Poor";
  }

  function calculateCategoryPlanScore(planOptions, ruleIdsByOption, engineStatesByRuleId, liveStatesByRuleId) {
    const scores = planOptions
      .map((option) => ruleIdsByOption[option])
      .filter(Boolean)
      .map((ruleId) => resolveRuleEvaluation(ruleId, engineStatesByRuleId, liveStatesByRuleId))
      .map((state) => stateStatusToScore(state?.status))
      .filter((score) => score != null);

    if (scores.length === 0) return null;

    return scores.reduce((sum, score) => sum + score, 0) / scores.length;
  }

  function calculatePlanReview(plan, events, liveStatesByRuleId) {
    if (!plan) return "Average";

    const firstHalfEvents = filterFirstHalfEvents(events);
    const engineStatesByRuleId = indexStatesByRuleId(
      evaluateStateEngine(plan, firstHalfEvents),
    );

    const categoryScores = PLAN_CATEGORY_KEYS
      .map((categoryKey) => {
        const planOptions = readPlanCategory(plan, categoryKey);
        if (!planOptions.length) return null;

        return calculateCategoryPlanScore(
          planOptions,
          PLAN_OPTION_RULE_IDS[categoryKey] || {},
          engineStatesByRuleId,
          liveStatesByRuleId,
        );
      })
      .filter((score) => score != null);

    if (categoryScores.length === 0) return "Average";

    const averageScore = categoryScores.reduce((sum, score) => sum + score, 0) / categoryScores.length;
    return scoreToPlanRating(averageScore);
  }

  function countTeamEvents(events, team) {
    return events.filter((event) => normalizeTeam(event.team) === team).length;
  }

  function calculateFlow(events) {
    const teamEvents = events.filter((event) => normalizeTeam(event.team));
    if (teamEvents.length === 0) return "Balanced";

    const homeCount = countTeamEvents(teamEvents, "home");
    const awayCount = countTeamEvents(teamEvents, "away");
    const total = homeCount + awayCount;
    const homeRatio = homeCount / total;

    const timedEvents = teamEvents
      .map((event) => ({ event, seconds: parseMatchTime(event.time) }))
      .filter((item) => item.seconds > 0 || item.event.time === "00:00");

    if (timedEvents.length >= 6) {
      const sortedSeconds = timedEvents.map((item) => item.seconds).sort((a, b) => a - b);
      const midpoint = sortedSeconds[Math.floor(sortedSeconds.length / 2)];
      const firstPeriod = timedEvents.filter((item) => item.seconds <= midpoint);
      const secondPeriod = timedEvents.filter((item) => item.seconds > midpoint);

      const firstHome = countTeamEvents(firstPeriod.map((item) => item.event), "home");
      const firstAway = countTeamEvents(firstPeriod.map((item) => item.event), "away");
      const secondHome = countTeamEvents(secondPeriod.map((item) => item.event), "home");
      const secondAway = countTeamEvents(secondPeriod.map((item) => item.event), "away");

      const firstLeader = firstHome > firstAway * 1.15
        ? "home"
        : firstAway > firstHome * 1.15
          ? "away"
          : "balanced";
      const secondLeader = secondHome > secondAway * 1.15
        ? "home"
        : secondAway > secondHome * 1.15
          ? "away"
          : "balanced";

      if (
        firstLeader !== "balanced"
        && secondLeader !== "balanced"
        && firstLeader !== secondLeader
      ) {
        return "Momentum Shift";
      }
    }

    if (homeRatio >= 0.58) return "Home Dominant";
    if (homeRatio <= 0.42) return "Away Dominant";
    return "Balanced";
  }

  function calculateCategorySummary(events, allowedNames, labelMap) {
    const categoryEvents = filterEventsByNames(events, allowedNames);
    if (categoryEvents.length === 0) return "--";

    const counts = countEventsByName(categoryEvents);
    let topEvent = null;
    let topCount = 0;
    counts.forEach((count, eventName) => {
      if (count > topCount) {
        topEvent = eventName;
        topCount = count;
      }
    });

    if (!topEvent) return "--";
    return labelMap[topEvent] || topEvent;
  }

  function calculateAttackSummary(events) {
    return calculateCategorySummary(events, ATTACK_EVENTS, ATTACK_EVENT_LABELS);
  }

  function calculateDefenseSummary(events) {
    return calculateCategorySummary(events, DEFENSE_EVENTS, DEFENSE_EVENT_LABELS);
  }

  function calculateBuildUpSummary(events) {
    return calculateCategorySummary(events, BUILD_UP_EVENTS, BUILD_UP_EVENT_LABELS);
  }

  function calculateTransitionSummary(events) {
    return calculateCategorySummary(events, TRANSITION_EVENTS, TRANSITION_EVENT_LABELS);
  }

  function calculateSetPieceSummary(events) {
    return calculateCategorySummary(events, SET_PIECE_EVENTS, SET_PIECE_EVENT_LABELS);
  }

  function calculateMiniReview({ plan, events, liveStatesByRuleId, generatedAt } = {}) {
    const firstHalfEvents = filterFirstHalfEvents(events);

    return {
      plan: calculatePlanReview(plan, firstHalfEvents, liveStatesByRuleId),
      flow: calculateFlow(firstHalfEvents),
      attack: calculateAttackSummary(firstHalfEvents),
      defense: calculateDefenseSummary(firstHalfEvents),
      buildUp: calculateBuildUpSummary(firstHalfEvents),
      transition: calculateTransitionSummary(firstHalfEvents),
      setPiece: calculateSetPieceSummary(firstHalfEvents),
      generatedAt: generatedAt || new Date().toISOString(),
    };
  }

  window.MO_MINI_REVIEW = {
    calculateMiniReview,
    calculatePlanReview,
    calculateFlow,
    calculateAttackSummary,
    calculateDefenseSummary,
    calculateBuildUpSummary,
    calculateTransitionSummary,
    calculateSetPieceSummary,
    filterFirstHalfEvents,
    evaluateStateEngine,
  };
})();
