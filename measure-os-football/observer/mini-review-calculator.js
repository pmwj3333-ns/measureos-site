(function () {
  const MINI_REVIEW_FORMAT_VERSION = 3;
  const MINI_REVIEW_FIELD_KEYS = [
    "plan",
    "flow",
    "attack",
    "defense",
    "buildUp",
    "transition",
    "setPiece",
  ];

  const LEGACY_MINI_REVIEW_TEXT = {
    Excellent: { text: "計画通り好調", tone: "positive" },
    Good: { text: "ゲームプラン通り", tone: "positive" },
    Average: { text: "プランおおむね維持", tone: "neutral" },
    Poor: { text: "ゲームプラン逸脱", tone: "negative" },
    "Home Dominant": { text: "主導権を握る", tone: "positive" },
    "Away Dominant": { text: "押し込まれる展開", tone: "negative" },
    Balanced: { text: "拮抗した前半", tone: "neutral" },
    "Momentum Shift": { text: "流れが入れ替わ", tone: "neutral" },
    Dominant: { text: "主導権を握る", tone: "positive" },
    SlightlyAdvantaged: { text: "やや優勢", tone: "positive" },
    SlightlyDisadvantaged: { text: "やや劣勢", tone: "negative" },
    Pressed: { text: "押し込まれる展開", tone: "negative" },
    "Left Attack": { text: "左攻撃が機能", tone: "positive" },
    "Central Attack": { text: "中央突破が有効", tone: "positive" },
    "Right Attack": { text: "右攻撃が機能", tone: "positive" },
    "Cross Attack": { text: "クロス攻撃有効", tone: "positive" },
    Shot: { text: "決定力が機能", tone: "positive" },
    "Left Conceded": { text: "左守備に苦戦", tone: "negative" },
    "Central Conceded": { text: "中央突破を許す", tone: "negative" },
    "Right Conceded": { text: "右守備に苦戦", tone: "negative" },
    "Cross Conceded": { text: "クロス対応に苦戦", tone: "negative" },
    "Shot Conceded": { text: "シュート許し多い", tone: "negative" },
    "Ball Won": { text: "守備が安定", tone: "positive" },
    "High Win": { text: "前線守備が安定", tone: "positive" },
    "Front Win": { text: "前線守備が安定", tone: "positive" },
    "Quick Recovery": { text: "即奪回が機能", tone: "positive" },
    "Counter Started": { text: "カウンター有効", tone: "positive" },
    "Counter Conceded": { text: "被カウンター多発", tone: "negative" },
    CK: { text: "CK機会が多い", tone: "neutral" },
    FK: { text: "FK機会が多い", tone: "neutral" },
    PK: { text: "PK判定あり", tone: "neutral" },
    Chance: { text: "決定機を創出", tone: "positive" },
    決定機: { text: "決定機を創出", tone: "positive" },
  };

  const PLAN_CATEGORY_KEYS = ["attack", "defense", "buildUp", "transition"];

  const FLOW_CATEGORY_WEIGHTS = {
    attack: 0.3,
    buildUp: 0.3,
    transition: 0.2,
    defense: 0.2,
  };

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

  function createReviewEntry(text, tone = "neutral") {
    return { text, tone };
  }

  function containsJapanese(text) {
    return /[ぁ-んァ-ン一-龯]/.test(String(text || ""));
  }

  function isLegacyMiniReviewSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return false;
    return Number(snapshot.formatVersion) !== MINI_REVIEW_FORMAT_VERSION;
  }

  function normalizeMiniReviewEntry(value) {
    if (!value) {
      return createReviewEntry("--", "neutral");
    }

    if (typeof value === "string") {
      return LEGACY_MINI_REVIEW_TEXT[value]
        || createReviewEntry(containsJapanese(value) ? value : "--", "neutral");
    }

    if (value.text) {
      const legacy = LEGACY_MINI_REVIEW_TEXT[value.text];
      if (legacy) return legacy;
      if (!containsJapanese(value.text)) {
        return createReviewEntry("--", "neutral");
      }
      return createReviewEntry(value.text, value.tone || "neutral");
    }

    return createReviewEntry("--", "neutral");
  }

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
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

  function formatPlanReview(rating) {
    switch (rating) {
      case "Excellent":
        return createReviewEntry("計画通り好調", "positive");
      case "Good":
        return createReviewEntry("ゲームプラン通り", "positive");
      case "Average":
        return createReviewEntry("プランおおむね維持", "neutral");
      case "Poor":
        return createReviewEntry("ゲームプラン逸脱", "negative");
      default:
        return createReviewEntry("プランおおむね維持", "neutral");
    }
  }

  function scoreToFlowRating(score) {
    if (score >= 3.5) return "Dominant";
    if (score >= 3.15) return "SlightlyAdvantaged";
    if (score >= 2.85) return "Balanced";
    if (score >= 2.35) return "SlightlyDisadvantaged";
    return "Pressed";
  }

  function calculateFlow(plan, events, liveStatesByRuleId) {
    if (!plan) return "Balanced";

    const firstHalfEvents = filterFirstHalfEvents(events);
    const engineStatesByRuleId = indexStatesByRuleId(
      evaluateStateEngine(plan, firstHalfEvents),
    );

    let weightedSum = 0;
    let totalWeight = 0;

    Object.entries(FLOW_CATEGORY_WEIGHTS).forEach(([categoryKey, weight]) => {
      const planOptions = readPlanCategory(plan, categoryKey);
      if (!planOptions.length) return;

      const categoryScore = calculateCategoryPlanScore(
        planOptions,
        PLAN_OPTION_RULE_IDS[categoryKey] || {},
        engineStatesByRuleId,
        liveStatesByRuleId,
      );

      if (categoryScore == null) return;

      weightedSum += categoryScore * weight;
      totalWeight += weight;
    });

    if (totalWeight === 0) return "Balanced";

    return scoreToFlowRating(weightedSum / totalWeight);
  }

  function formatFlowReview(flowType) {
    switch (flowType) {
      case "Dominant":
      case "Home Dominant":
        return createReviewEntry("主導権を握る", "positive");
      case "SlightlyAdvantaged":
        return createReviewEntry("やや優勢", "positive");
      case "Balanced":
        return createReviewEntry("拮抗した前半", "neutral");
      case "SlightlyDisadvantaged":
        return createReviewEntry("やや劣勢", "negative");
      case "Pressed":
      case "Away Dominant":
        return createReviewEntry("押し込まれる展開", "negative");
      case "Momentum Shift":
        return createReviewEntry("流れが入れ替わ", "neutral");
      default:
        return createReviewEntry("拮抗した前半", "neutral");
    }
  }

  function getTopCategoryEvent(events, allowedNames) {
    const categoryEvents = filterEventsByNames(events, allowedNames);
    if (categoryEvents.length === 0) return null;

    const counts = countEventsByName(categoryEvents);
    let topEvent = null;
    let topCount = 0;
    counts.forEach((count, eventName) => {
      if (count > topCount) {
        topEvent = eventName;
        topCount = count;
      }
    });

    return topEvent;
  }

  function countCategoryEvents(events, allowedNames) {
    return filterEventsByNames(events, allowedNames).length;
  }

  function formatAttackReview(topEvent, events) {
    const total = countCategoryEvents(events, ATTACK_EVENTS);
    if (!topEvent || total <= 2) {
      return createReviewEntry("攻撃が停滞", "neutral");
    }

    const sentences = {
      左侵入: createReviewEntry("左攻撃が機能", "positive"),
      右侵入: createReviewEntry("右攻撃が機能", "positive"),
      中央侵入: createReviewEntry("中央突破が有効", "positive"),
      クロス: createReviewEntry("クロス攻撃有効", "positive"),
      シュート: createReviewEntry("決定力が機能", "positive"),
    };

    return sentences[topEvent] || createReviewEntry("攻撃が停滞", "neutral");
  }

  function formatDefenseReview(topEvent, events) {
    const total = countCategoryEvents(events, DEFENSE_EVENTS);
    if (!topEvent || total <= 2) {
      return createReviewEntry("守備は様子見", "neutral");
    }

    const sentences = {
      被左侵入: createReviewEntry("左守備に苦戦", "negative"),
      被中央侵入: createReviewEntry("中央突破を許す", "negative"),
      被右侵入: createReviewEntry("右守備に苦戦", "negative"),
      被クロス: createReviewEntry("クロス対応に苦戦", "negative"),
      被シュート: createReviewEntry("シュート許し多い", "negative"),
      ボール奪取: createReviewEntry("守備が安定", "positive"),
      前線奪取: createReviewEntry("前線守備が安定", "positive"),
    };

    return sentences[topEvent] || createReviewEntry("守備は様子見", "neutral");
  }

  function formatBuildUpReview(topEvent, events) {
    const total = countCategoryEvents(events, BUILD_UP_EVENTS);
    if (!topEvent || total <= 2) {
      return createReviewEntry("前進できない", "neutral");
    }

    const sentences = {
      左侵入: createReviewEntry("左から前進成功", "positive"),
      右侵入: createReviewEntry("右から前進成功", "positive"),
      中央侵入: createReviewEntry("中央前進が成功", "positive"),
      即時奪回成功: createReviewEntry("保持が安定", "positive"),
      被左侵入: createReviewEntry("前進できない", "negative"),
      被中央侵入: createReviewEntry("前進できない", "negative"),
      被右侵入: createReviewEntry("前進できない", "negative"),
      カウンター被弾: createReviewEntry("前進できない", "negative"),
    };

    return sentences[topEvent] || createReviewEntry("保持が安定", "neutral");
  }

  function formatTransitionReview(topEvent, events) {
    const total = countCategoryEvents(events, TRANSITION_EVENTS);
    if (!topEvent || total <= 2) {
      return createReviewEntry("切り替えに課題", "neutral");
    }

    const sentences = {
      即時奪回成功: createReviewEntry("即奪回が機能", "positive"),
      カウンター開始: createReviewEntry("カウンター有効", "positive"),
      カウンター被弾: createReviewEntry("被カウンター多発", "negative"),
    };

    return sentences[topEvent] || createReviewEntry("切り替えに課題", "neutral");
  }

  function formatSetPieceReview(topEvent, events) {
    const total = countCategoryEvents(events, SET_PIECE_EVENTS);
    if (!topEvent || total <= 1) {
      return createReviewEntry("セットプレー少", "neutral");
    }

    const sentences = {
      CK: createReviewEntry("CK機会が多い", "neutral"),
      FK: createReviewEntry("FK機会が多い", "neutral"),
      PK: createReviewEntry("PK判定あり", "neutral"),
      決定機: createReviewEntry("決定機を創出", "positive"),
    };

    return sentences[topEvent] || createReviewEntry("セットプレー少", "neutral");
  }

  function calculateAttackSummary(events) {
    return getTopCategoryEvent(events, ATTACK_EVENTS);
  }

  function calculateDefenseSummary(events) {
    return getTopCategoryEvent(events, DEFENSE_EVENTS);
  }

  function calculateBuildUpSummary(events) {
    return getTopCategoryEvent(events, BUILD_UP_EVENTS);
  }

  function calculateTransitionSummary(events) {
    return getTopCategoryEvent(events, TRANSITION_EVENTS);
  }

  function calculateSetPieceSummary(events) {
    return getTopCategoryEvent(events, SET_PIECE_EVENTS);
  }

  function calculateMiniReview({ plan, events, liveStatesByRuleId, generatedAt } = {}) {
    const firstHalfEvents = filterFirstHalfEvents(events);
    const planRating = calculatePlanReview(plan, firstHalfEvents, liveStatesByRuleId);
    const flowType = calculateFlow(plan, firstHalfEvents, liveStatesByRuleId);

    return {
      formatVersion: MINI_REVIEW_FORMAT_VERSION,
      plan: formatPlanReview(planRating),
      flow: formatFlowReview(flowType),
      attack: formatAttackReview(calculateAttackSummary(firstHalfEvents), firstHalfEvents),
      defense: formatDefenseReview(calculateDefenseSummary(firstHalfEvents), firstHalfEvents),
      buildUp: formatBuildUpReview(calculateBuildUpSummary(firstHalfEvents), firstHalfEvents),
      transition: formatTransitionReview(calculateTransitionSummary(firstHalfEvents), firstHalfEvents),
      setPiece: formatSetPieceReview(calculateSetPieceSummary(firstHalfEvents), firstHalfEvents),
      generatedAt: generatedAt || new Date().toISOString(),
    };
  }

  window.MO_MINI_REVIEW = {
    MINI_REVIEW_FORMAT_VERSION,
    calculateMiniReview,
    calculatePlanReview,
    calculateFlow,
    scoreToFlowRating,
    calculateAttackSummary,
    calculateDefenseSummary,
    calculateBuildUpSummary,
    calculateTransitionSummary,
    calculateSetPieceSummary,
    filterFirstHalfEvents,
    evaluateStateEngine,
    formatPlanReview,
    formatFlowReview,
    formatAttackReview,
    formatDefenseReview,
    formatBuildUpReview,
    formatTransitionReview,
    formatSetPieceReview,
    isLegacyMiniReviewSnapshot,
    normalizeMiniReviewEntry,
  };
})();
