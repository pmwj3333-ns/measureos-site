window.MO_REVIEW_MINI_NARRATIVE = (() => {
  const {
    findMetricItem,
    dominantMetricItem,
    filterReasonResultsByCategories,
    filterStatesByCategories,
  } = window.MO_REVIEW_HELPERS;

  const ATTACK_DIRECTION_LABELS = {
    left: "左",
    center: "中央",
    right: "右",
  };

  const STATE_STATUS_RANK = {
    green: 0,
    yellow: 1,
    orange: 2,
    red: 3,
  };

  const EVALUATIVE_PATTERN = /良好|改善|必要|しましょう|高めたい|優秀|劣勢|優勢|すべき|望ましい/;

  const TRANSITION_PHRASE_MAP = [
    [/ボールロスト後に素早く奪い返しています。/, "切り替えで素早くボールを回収しています。"],
    [/被カウンターが発生しています。/, "切り替え後に押し込まれています。"],
    [/被カウンターが複数回発生しています。/, "切り替え後に繰り返し押し込まれています。"],
    [/即時奪回の場面は記録されていません。/, "切り替え後の即時奪回は記録されていません。"],
  ];

  const DEFENSE_PHRASE_MAP = [
    [/前線でボールを奪い、被中央侵入・被シュートを抑えています。/, "前線でボールを奪い、被シュートは発生していません。"],
    [/守備への切り替えが速く、相手の前進を抑えています。/, "守備への切り替え後、相手の前進を抑えています。"],
  ];

  function ensurePeriod(text) {
    const normalized = String(text || "").trim();
    if (!normalized) return null;
    return normalized.endsWith("。") ? normalized : `${normalized}。`;
  }

  function takeFirstSentence(text) {
    const normalized = String(text || "").trim();
    if (!normalized) return null;

    const sentence = normalized.split("。")[0];
    if (!sentence) return null;
    return ensurePeriod(sentence);
  }

  function stripReasonPrefix(text) {
    const strip = window.MO_COMPOSITE_REASON_HELPERS?.stripWindowPrefix;
    return strip ? strip(text) : String(text || "");
  }

  function stripStateLabelPrefix(label) {
    const normalized = String(label || "").trim();
    if (!normalized) return null;

    const parts = normalized.split(/\s+/);
    if (parts.length > 1) {
      return parts.slice(1).join(" ");
    }

    return normalized.replace(/^[^\u3040-\u9FFF\u30A0-\u30FF]+/u, "").trim() || normalized;
  }

  function normalizeObserverNarrative(text, categoryKey) {
    let result = takeFirstSentence(stripReasonPrefix(text));
    if (!result) return null;

    const phraseMap = categoryKey === "transition"
      ? TRANSITION_PHRASE_MAP
      : categoryKey === "defense"
        ? DEFENSE_PHRASE_MAP
        : [];

    for (const [pattern, replacement] of phraseMap) {
      if (pattern.test(result)) {
        return replacement;
      }
    }

    if (EVALUATIVE_PATTERN.test(result)) {
      return null;
    }

    return result;
  }

  function buildUpMiniNarrative(buildUpItems) {
    const possession = findMetricItem(buildUpItems, "possession");
    const long = findMetricItem(buildUpItems, "long");
    const total = possession.count + long.count;
    if (total === 0) return null;

    if (possession.percent >= 65) {
      return "保持前進を中心に攻撃を組み立てています。";
    }
    if (long.percent >= 65) {
      return "ロング前進を中心に前進しています。";
    }
    if (Math.abs(possession.percent - long.percent) <= 20) {
      return "保持前進とロング前進を使い分けています。";
    }
    if (possession.percent > long.percent) {
      return "保持前進を中心に前進しています。";
    }
    return "ロング前進を中心に前進しています。";
  }

  function describeAttackDirectionClause(attackItems) {
    const dominant = dominantMetricItem(attackItems);
    if (!dominant) return null;

    const label = ATTACK_DIRECTION_LABELS[dominant.code] || dominant.label;
    if (dominant.percent >= 50) {
      return `${label}からの侵入が中心`;
    }
    return `${label}からの侵入が多く見られ`;
  }

  function finishAttackDirectionClause(clause) {
    if (!clause) return null;
    if (clause.endsWith("中心")) {
      return `${clause}です。`;
    }
    return `${clause}ます。`;
  }

  function attackFinishMiniNarrative(attackItems, finishItems) {
    const directionClause = describeAttackDirectionClause(attackItems);
    const lost = findMetricItem(finishItems, "lost");
    const shot = findMetricItem(finishItems, "shot");
    const bigChance = findMetricItem(finishItems, "bigChance");
    const finishTotal = lost.count + shot.count + bigChance.count;
    const hasHighLost = finishTotal > 0 && lost.percent >= 55;
    const hasGoodFinish = finishTotal > 0 && shot.percent + bigChance.percent >= 40;

    if (directionClause && hasHighLost) {
      if (lost.percent >= 70) {
        return `${directionClause}ですが、フィニッシュまで届いていません。`;
      }
      return `${directionClause}ですが、多くはロストで終了しています。`;
    }

    if (directionClause && hasGoodFinish) {
      return `${directionClause}で、シュートまで到達しています。`;
    }

    if (directionClause) {
      return finishAttackDirectionClause(directionClause);
    }

    if (finishTotal > 0 && hasHighLost) {
      if (lost.percent >= 70) {
        return "フィニッシュまで届いていません。";
      }
      return "多くの攻撃がロストで終了しています。";
    }

    if (finishTotal > 0 && hasGoodFinish) {
      return "シュート・決定機まで到達しています。";
    }

    return null;
  }

  function stateLabelToMiniNarrative(label, categoryKey) {
    const stripped = stripStateLabelPrefix(label);
    if (!stripped || EVALUATIVE_PATTERN.test(stripped)) return null;

    if (/維持$/.test(stripped)) {
      const subject = stripped.replace(/維持$/, "");
      if (categoryKey === "defense") {
        return `${subject}の形が続いています。`;
      }
      if (categoryKey === "transition") {
        return `${subject}が続いています。`;
      }
    }

    if (/停滞$/.test(stripped)) {
      const subject = stripped.replace(/停滞$/, "");
      return `${subject}が停滞しています。`;
    }

    if (/崩壊$/.test(stripped)) {
      const subject = stripped.replace(/崩壊$/, "");
      return `${subject}が崩れています。`;
    }

    if (/しています$/.test(stripped)) {
      return ensurePeriod(stripped);
    }

    return null;
  }

  function pickTopReasonSummary(reasonResults, stateResults, categoryKey) {
    const rank = window.MO_COMPOSITE_REASON_HELPERS?.statusRank
      || ((status) => STATE_STATUS_RANK[status] ?? 0);

    const reasons = filterReasonResultsByCategories(reasonResults, stateResults, [categoryKey])
      .filter((reason) => reason?.summary)
      .sort((left, right) => rank(right.status) - rank(left.status));

    for (const reason of reasons) {
      const normalized = normalizeObserverNarrative(reason.summary, categoryKey);
      if (normalized) return normalized;
    }

    const states = filterStatesByCategories(stateResults, [categoryKey]);
    const topState = [...states].sort(
      (left, right) => (STATE_STATUS_RANK[right.status] ?? 0) - (STATE_STATUS_RANK[left.status] ?? 0),
    )[0];

    if (topState?.label) {
      return stateLabelToMiniNarrative(topState.label, categoryKey);
    }

    return null;
  }

  function defenseMiniNarrative(stateResults, reasonResults) {
    return pickTopReasonSummary(reasonResults, stateResults, "defense");
  }

  function transitionMiniNarrative(stateResults, reasonResults) {
    return pickTopReasonSummary(reasonResults, stateResults, "transition");
  }

  function planMiniNarrative(compositeReason) {
    const short = String(compositeReason?.shortSummary || "").trim();
    return short || null;
  }

  function flowMiniNarrative(compositeReason) {
    const summary = stripReasonPrefix(compositeReason?.summary);
    const first = takeFirstSentence(summary);

    if (first && first.length <= 36 && !EVALUATIVE_PATTERN.test(first)) {
      return first;
    }

    const short = planMiniNarrative(compositeReason);
    if (short) {
      return `${short}の展開です。`;
    }

    return first;
  }

  function buildAttackMiniNarrative({ matchMetrics }) {
    const buildUp = matchMetrics?.buildUp || [];
    const attack = matchMetrics?.attack || [];
    const finish = matchMetrics?.finish || [];

    return {
      buildUp: buildUpMiniNarrative(buildUp),
      attack: attackFinishMiniNarrative(attack, finish),
    };
  }

  function buildDefenseMiniNarrative({ stateResults, reasonResults }) {
    return {
      defense: defenseMiniNarrative(stateResults, reasonResults),
      transition: transitionMiniNarrative(stateResults, reasonResults),
    };
  }

  function combineAttackCardText(miniReview) {
    return miniReview?.attack || null;
  }

  return {
    buildUpMiniNarrative,
    attackFinishMiniNarrative,
    defenseMiniNarrative,
    transitionMiniNarrative,
    planMiniNarrative,
    flowMiniNarrative,
    buildAttackMiniNarrative,
    buildDefenseMiniNarrative,
    combineAttackCardText,
  };
})();
