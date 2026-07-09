window.MO_REVIEW_ATTACK_NARRATIVE = (() => {
  const {
    findMetricItem,
    dominantMetricItem,
    formatMetricsBlock,
  } = window.MO_REVIEW_HELPERS;

  const ATTACK_DIRECTION_LABELS = {
    left: "左サイド",
    center: "中央",
    right: "右サイド",
  };

  function joinParagraphs(parts) {
    return parts.filter(Boolean).join("\n\n");
  }

  function ensurePeriod(text) {
    if (!text) return text;
    return text.endsWith("。") ? text : `${text}。`;
  }

  function metricTotal(items) {
    return (Array.isArray(items) ? items : []).reduce((sum, item) => sum + (item.count || 0), 0);
  }

  function isAttackBalanced(attackItems) {
    const active = (Array.isArray(attackItems) ? attackItems : []).filter((item) => item.count > 0);
    if (active.length < 2) return false;

    const percents = active.map((item) => item.percent);
    const max = Math.max(...percents);
    const min = Math.min(...percents);
    return max < 50 && (max - min) <= 15;
  }

  function describeBuildUpParagraph(buildUpItems) {
    const possession = findMetricItem(buildUpItems, "possession");
    const long = findMetricItem(buildUpItems, "long");
    const total = possession.count + long.count;
    if (total === 0) return null;

    if (possession.percent >= 65) {
      return "保持前進を主体に攻撃を組み立てました";
    }
    if (long.percent >= 65) {
      return "ロング前進を主体に攻撃を組み立てました";
    }
    if (Math.abs(possession.percent - long.percent) <= 20) {
      return "保持前進とロング前進が拮抗し、使い分けながら攻撃しました";
    }
    if (possession.percent > long.percent) {
      return "保持前進を多く使いながら攻撃を組み立てました";
    }
    return "ロング前進を多く使いながら攻撃を組み立てました";
  }

  function describeAttackParagraph(attackItems) {
    const total = metricTotal(attackItems);
    if (total === 0) return null;

    if (isAttackBalanced(attackItems)) {
      return "左・中央・右への侵入が分散していました";
    }

    const dominant = dominantMetricItem(attackItems);
    if (!dominant) return null;

    const label = ATTACK_DIRECTION_LABELS[dominant.code] || dominant.label;
    if (dominant.code === "center") {
      if (dominant.percent >= 50) {
        return "中央からの侵入が最も多く見られました";
      }
      return "中央からの侵入がやや多く見られました";
    }

    if (dominant.percent >= 50) {
      return `侵入は${label}が最も多く見られました`;
    }
    return `侵入は${label}がやや多く見られました`;
  }

  function describeFinishParagraph(finishItems, { hasPriorParagraphs = false } = {}) {
    const lost = findMetricItem(finishItems, "lost");
    const shot = findMetricItem(finishItems, "shot");
    const bigChance = findMetricItem(finishItems, "bigChance");
    const finishTotal = lost.count + shot.count + bigChance.count;

    if (finishTotal === 0) return null;

    if (lost.percent >= 55) {
      const body = `ロストが${lost.percent}%を占め、フィニッシュまで至らない場面が目立ちました`;
      return hasPriorParagraphs ? `一方で、${body}` : body;
    }

    if (shot.percent + bigChance.percent >= 40) {
      if (bigChance.percent >= 25 && bigChance.percent > shot.percent) {
        return "決定機を作る場面が多く見られました";
      }
      if (shot.percent >= 25 && shot.percent >= bigChance.percent) {
        return "シュートまで到達した割合が高く、フィニッシュまで繋がる場面が多く見られました";
      }
      return "シュート・決定機まで到達した割合が高く、多くの攻撃がフィニッシュまで繋がりました";
    }

    return `ロスト${lost.percent}%、シュート${shot.percent}%、決定機${bigChance.percent}%と、フィニッシュまでの行き先は全体的にバランス型でした`;
  }

  function describeBuildUpSentence(buildUpItems) {
    return describeBuildUpParagraph(buildUpItems);
  }

  function describeAttackSentence(attackItems) {
    return describeAttackParagraph(attackItems);
  }

  function describeFinishSentence(finishItems) {
    return describeFinishParagraph(finishItems);
  }

  function buildAttackReview({ matchMetrics }) {
    const buildUp = matchMetrics?.buildUp || [];
    const attack = matchMetrics?.attack || [];
    const finish = matchMetrics?.finish || [];

    const buildUpParagraph = describeBuildUpParagraph(buildUp);
    const attackParagraph = describeAttackParagraph(attack);
    const finishParagraph = describeFinishParagraph(finish, {
      hasPriorParagraphs: Boolean(buildUpParagraph || attackParagraph),
    });

    const narrative = joinParagraphs([
      ensurePeriod(buildUpParagraph),
      ensurePeriod(attackParagraph),
      ensurePeriod(finishParagraph),
    ]);

    const miniReview = window.MO_REVIEW_MINI_NARRATIVE?.buildAttackMiniNarrative?.({
      matchMetrics: { buildUp, attack, finish },
    }) || {
      buildUp: null,
      attack: null,
      finish: null,
    };

    return {
      key: "attack",
      title: "Attack Review",
      metrics: [
        formatMetricsBlock("Build Up", buildUp),
        formatMetricsBlock("Attack", attack),
        formatMetricsBlock("Finish", finish),
      ],
      narrative,
      summary: null,
      miniReview,
    };
  }

  return {
    describeBuildUpSentence,
    describeAttackSentence,
    describeFinishSentence,
    buildAttackReview,
  };
})();
