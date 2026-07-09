window.MO_REVIEW_MINI_ADAPTER = (() => {
  const MINI_REVIEW_FORMAT_VERSION = 7;
  const MINI_REVIEW_PLACEHOLDER = "--";

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function filterEventsByHalf(events, half) {
    if (!Array.isArray(events)) return [];
    if (half === "second") {
      return events.filter((event) => event?.phase === "後半");
    }
    return events.filter((event) => event?.phase === "前半" || !event?.phase);
  }

  function getEvaluationElapsed(events) {
    return events.reduce((max, event) => Math.max(max, parseMatchTime(event.time)), 0);
  }

  function createEntry(text, tone = "neutral") {
    const normalized = String(text || "").trim();
    return {
      text: normalized || MINI_REVIEW_PLACEHOLDER,
      tone: tone || "neutral",
    };
  }

  function shortenFlowTextForCard(flowText, compositeReason) {
    const key = compositeReason?.compositeReasonKey || "";
    const short = String(compositeReason?.shortSummary || "").trim();
    const text = String(flowText || "").trim();

    const FLOW_BY_KEY = {
      "composite.attack.green.attack_flow_working": "攻撃が継続しています。",
      "composite.attack.yellow.attack_stalled_build_up_working": "攻撃が継続しています。",
      "composite.attack.yellow.attack_working_build_up_stalled": "攻撃が継続しています。",
      "composite.attack.yellow.mixed_pressure": short ? `${short}の流れです。` : "攻撃の流れです。",
      "composite.attack.orange.pressure": short ? `${short}の流れです。` : "攻撃の流れです。",
      "composite.attack.red.breakdown": short ? `${short}の流れです。` : "攻撃の流れです。",
      "composite.attack.unknown.aggregated_rule_summaries": short ? `${short}の流れです。` : "攻撃の流れです。",
      "composite.defense.green.defense_switch_working": "守備が機能しています。",
      "composite.defense.yellow.central_penetration_allowed": "中央侵入を許しています。",
      "composite.defense.yellow.mixed_pressure": short ? `${short}の流れです。` : "守備の流れです。",
      "composite.defense.orange.counter_or_shot_pressure": short ? `${short}の流れです。` : "守備の流れです。",
      "composite.defense.orange.mixed_pressure": short ? `${short}の流れです。` : "守備の流れです。",
      "composite.defense.red.breakdown": short ? `${short}の流れです。` : "守備の流れです。",
      "composite.defense.unknown.aggregated_rule_summaries": short ? `${short}の流れです。` : "守備の流れです。",
      "composite.both.green.balanced": "攻守が機能しています。",
      "composite.both.mixed.attack_working_defense_central_pressure": "攻守が拮抗しています。",
      "composite.both.mixed.attack_working_defense_counter_pressure": "攻守が拮抗しています。",
      "composite.both.mixed.attack_working_defense_pressure": "攻守が拮抗しています。",
      "composite.both.mixed.attack_without_finish_defense_working": "攻守が拮抗しています。",
      "composite.both.mixed.attack_pressure_defense_working": "攻守が拮抗しています。",
      "composite.both.yellow.mixed_pressure": "攻守が拮抗しています。",
      "composite.both.orange.pressure": short ? `${short}の流れです。` : "攻守の流れです。",
      "composite.both.red.breakdown": short ? `${short}の流れです。` : "攻守の流れです。",
      "composite.unknown.aggregated_rule_summaries": short ? `${short}の流れです。` : "攻守の流れです。",
    };

    if (FLOW_BY_KEY[key]) {
      return FLOW_BY_KEY[key];
    }

    const patterns = [
      [/が継続し、.+?(?:しています|到達しています)。/, "攻撃が継続しています。"],
      [/が継続していますが、.+?(?:していません|届いていません)。/, "攻撃が継続しています。"],
      [/は機能していますが、.+?(?:していません|届いていません)。/, "攻撃が継続しています。"],
      [/と.+?により、相手の継続した攻撃を抑えています。/, "守備が機能しています。"],
      [/攻撃と守備の切り替えが機能し、相手の前進を抑えています。/, "攻守が機能しています。"],
      [/(.+?)の展開です。$/, "$1の流れです。"],
      [/(.+?)の場面が見られます。$/, "$1の流れです。"],
    ];

    for (const [pattern, replacement] of patterns) {
      if (pattern.test(text)) {
        return text.replace(pattern, replacement);
      }
    }

    if (text.length > 16 && short) {
      return `${short}の流れです。`;
    }

    return text || (short ? `${short}の流れです。` : null);
  }

  function buildSetPieceEntry(events) {
    const matchesEventName = window.MO_SET_PIECE_OBSERVER?.matchesEventName;
    const getEventLabel = window.MO_SET_PIECE_OBSERVER?.getEventLabel;
    const codes = ["corner_kick", "free_kick", "penalty_kick"];
    const parts = [];

    codes.forEach((code) => {
      const count = events.filter((event) => {
        const eventName = event?.eventName;
        const observerEventCode = event?.observerEventCode;
        return matchesEventName?.(eventName, code)
          || matchesEventName?.(observerEventCode, code);
      }).length;

      if (count > 0) {
        parts.push(`${getEventLabel?.(code) || code} ${count}回`);
      }
    });

    return createEntry(parts.length > 0 ? parts.join("、") : null);
  }

  function mapReviewToMiniReviewCards(review, compositeReason, events) {
    const planText = window.MO_REVIEW_MINI_NARRATIVE?.planMiniNarrative?.(compositeReason);
    const flowText = shortenFlowTextForCard(
      window.MO_REVIEW_MINI_NARRATIVE?.flowMiniNarrative?.(compositeReason)
        || compositeReason?.summary,
      compositeReason,
    );
    const combineAttackCardText = window.MO_REVIEW_MINI_NARRATIVE?.combineAttackCardText;

    const cards = {
      plan: createEntry(planText || compositeReason?.shortSummary),
      flow: createEntry(flowText),
      attack: createEntry(null),
      defense: createEntry(null),
      buildUp: createEntry(null),
      transition: createEntry(null),
      setPiece: buildSetPieceEntry(events),
    };

    (review?.sections || []).forEach((section) => {
      if (section.key === "attack") {
        const miniReview = section.miniReview || {};
        cards.buildUp = createEntry(miniReview.buildUp);
        cards.attack = createEntry(combineAttackCardText?.(miniReview) || miniReview.attack);
        return;
      }

      if (section.key === "defense") {
        const miniReview = section.miniReview || {};
        cards.defense = createEntry(miniReview.defense);
        cards.transition = createEntry(miniReview.transition);
      }
    });

    return cards;
  }

  function generateMiniReviewSnapshot({
    plan,
    events,
    half = "first",
    generatedAt,
  } = {}) {
    const normalizedPlan = window.MO_PLAN_SNAPSHOT?.normalizePlanSnapshot(plan);
    if (!normalizedPlan) return null;

    const halfEvents = filterEventsByHalf(events, half);
    const elapsed = getEvaluationElapsed(halfEvents);
    const evaluate = window.MO_STATE_ENGINE?.evaluateLiveState;
    const stateResults = typeof evaluate === "function"
      ? evaluate({ plan: normalizedPlan, events: halfEvents, elapsed })
      : [];

    const explainLiveState = window.MO_REASON_ENGINE?.explainLiveState;
    const reasonResults = typeof explainLiveState === "function"
      ? explainLiveState({ plan: normalizedPlan, stateResults, context: { elapsed } })
      : [];

    const analyzeMode = normalizedPlan.analyzeMode || "both";
    const compositeReason = window.MO_REVIEW_ENGINE?.buildCompositeForAnalyzeMode?.(
      reasonResults,
      analyzeMode,
    ) || null;

    const reviewInput = window.MO_REVIEW_ENGINE?.buildReviewInput?.({
      plan: normalizedPlan,
      events: halfEvents,
      elapsed,
      stateResults,
      reasonResults,
      compositeReason,
    });

    const review = window.MO_REVIEW_ENGINE?.generateReview?.(reviewInput) || { sections: [] };
    const cards = mapReviewToMiniReviewCards(review, compositeReason, halfEvents);

    return {
      formatVersion: MINI_REVIEW_FORMAT_VERSION,
      half: half === "second" ? "second" : "first",
      analyzeMode: review.analyzeMode || analyzeMode,
      ...cards,
      generatedAt: generatedAt || new Date().toISOString(),
    };
  }

  function normalizeMiniReviewEntry(value) {
    if (!value) {
      return { text: MINI_REVIEW_PLACEHOLDER, tone: "neutral" };
    }

    if (typeof value === "string") {
      return { text: value, tone: "neutral" };
    }

    return {
      text: value.text || MINI_REVIEW_PLACEHOLDER,
      tone: value.tone || "neutral",
    };
  }

  function isLegacyMiniReviewSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return true;
    return Number(snapshot.formatVersion) !== MINI_REVIEW_FORMAT_VERSION;
  }

  return {
    MINI_REVIEW_FORMAT_VERSION,
    MINI_REVIEW_PLACEHOLDER,
    filterEventsByHalf,
    generateMiniReviewSnapshot,
    normalizeMiniReviewEntry,
    isLegacyMiniReviewSnapshot,
  };
})();
