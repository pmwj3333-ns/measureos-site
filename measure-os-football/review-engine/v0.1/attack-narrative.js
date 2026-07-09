window.MO_REVIEW_ATTACK_NARRATIVE = (() => {
  const {
    findMetricItem,
    dominantMetricItem,
    joinSentences,
    formatMetricsBlock,
  } = window.MO_REVIEW_HELPERS;

  const ATTACK_DIRECTION_LABELS = {
    left: "左",
    center: "中央",
    right: "右",
  };

  function describeBuildUpSentence(buildUpItems) {
    const possession = findMetricItem(buildUpItems, "possession");
    const long = findMetricItem(buildUpItems, "long");
    const total = possession.count + long.count;
    if (total === 0) return null;

    if (possession.percent >= 65) {
      return "保持前進を中心に攻撃を組み立てました";
    }
    if (long.percent >= 65) {
      return "ロング前進を中心に攻撃を組み立てました";
    }
    if (Math.abs(possession.percent - long.percent) <= 20) {
      return "保持前進とロング前進をバランス良く使いながら攻撃を組み立てました";
    }
    if (possession.percent > long.percent) {
      return "保持前進を多く用いながら攻撃を組み立てました";
    }
    return "ロング前進を多く用いながら攻撃を組み立てました";
  }

  function describeAttackSentence(attackItems) {
    const dominant = dominantMetricItem(attackItems);
    if (!dominant) return null;

    const label = ATTACK_DIRECTION_LABELS[dominant.code] || dominant.label;
    if (dominant.percent >= 50) {
      return `${label}からの侵入を中心に攻撃を展開しました`;
    }
    return `${label}からの侵入が多く見られました`;
  }

  function describeFinishSentence(finishItems) {
    const lost = findMetricItem(finishItems, "lost");
    const shot = findMetricItem(finishItems, "shot");
    const bigChance = findMetricItem(finishItems, "bigChance");
    const finishTotal = lost.count + shot.count + bigChance.count;

    if (finishTotal === 0) return null;

    if (lost.percent >= 55) {
      return "ロストが多く、フィニッシュまで至らない場面が目立ちました";
    }
    if (shot.percent + bigChance.percent >= 40) {
      return "シュート・決定機まで到達する場面が多く見られました";
    }
    return `ロスト率は${lost.percent}%、シュート率は${shot.percent}%、決定機率は${bigChance.percent}%でした`;
  }

  function buildAttackReview({ matchMetrics }) {
    const buildUp = matchMetrics?.buildUp || [];
    const attack = matchMetrics?.attack || [];
    const finish = matchMetrics?.finish || [];

    const buildUpSentence = describeBuildUpSentence(buildUp);
    const attackSentence = describeAttackSentence(attack);
    const finishSentence = describeFinishSentence(finish);

    const narrativeParts = [];
    if (buildUpSentence) narrativeParts.push(buildUpSentence);
    if (attackSentence) narrativeParts.push(attackSentence);
    if (finishSentence) {
      if (narrativeParts.length > 0) {
        const lost = findMetricItem(finish, "lost");
        const prefix = lost.percent >= 55 ? "一方で、" : "";
        narrativeParts.push(`${prefix}${finishSentence}`);
      } else {
        narrativeParts.push(finishSentence);
      }
    }

    let narrative = joinSentences(narrativeParts);
    if (narrative && !narrative.endsWith("。")) {
      narrative += "。";
    }

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
