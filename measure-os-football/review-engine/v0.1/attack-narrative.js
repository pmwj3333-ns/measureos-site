window.MO_REVIEW_ATTACK_NARRATIVE = (() => {
  const {
    findMetricItem,
    dominantMetricItem,
    joinSentences,
    filterReasonResultsByCategories,
    filterStatesByCategories,
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
      return "保持による前進を中心に攻撃を組み立て";
    }
    if (long.percent >= 65) {
      return "ロング前進を中心に攻撃を組み立て";
    }
    if (Math.abs(possession.percent - long.percent) <= 20) {
      return "保持前進とロング前進をバランス良く使いながら";
    }
    if (possession.percent > long.percent) {
      return "保持前進を多く用いながら";
    }
    return "ロング前進を多く用いながら";
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

  function describeFinishSentence(finishItems, reasonResults, stateResults) {
    const lost = findMetricItem(finishItems, "lost");
    const shot = findMetricItem(finishItems, "shot");
    const bigChance = findMetricItem(finishItems, "bigChance");
    const finishTotal = lost.count + shot.count + bigChance.count;

    const attackReasons = filterReasonResultsByCategories(reasonResults, stateResults, ["attack"]);
    const finishReasonSummary = attackReasons.find((reason) => /ロスト/.test(reason.summary))?.summary;

    if (finishTotal === 0 && !finishReasonSummary) {
      return null;
    }

    if (finishReasonSummary) {
      if (lost.percent >= 55) {
        return `一方で、${finishReasonSummary.replace(/。$/, "")}、フィニッシュまで到達する割合は高くありませんでした。`;
      }
      if (lost.percent < 55 && shot.percent + bigChance.percent >= 40) {
        return `${finishReasonSummary.replace(/。$/, "")}、多くの攻撃がシュート・決定機まで到達しました。`;
      }
      return finishReasonSummary.endsWith("。") ? finishReasonSummary : `${finishReasonSummary}。`;
    }

    if (lost.percent >= 55) {
      return `一方で、攻撃の${lost.percent}%がロストで終了しており、フィニッシュまで到達する割合は高くありませんでした。`;
    }
    if (shot.percent + bigChance.percent >= 40) {
      return `ロスト率は${lost.percent}%に抑えられ、多くの攻撃がシュート・決定機まで到達しました。`;
    }
    return `ロスト率は${lost.percent}%、シュート率は${shot.percent}%、決定機率は${bigChance.percent}%でした。`;
  }

  function buildStateSummary(stateResults, compositeReason) {
    if (compositeReason?.summary) {
      return compositeReason.summary;
    }

    const labels = filterStatesByCategories(stateResults, ["buildUp", "attack"])
      .map((state) => state.label)
      .filter(Boolean);

    if (labels.length === 0) return null;
    return labels.join("。") + (labels.length > 0 ? "。" : "");
  }

  function buildAttackReview({ matchMetrics, stateResults, reasonResults, compositeReason }) {
    const buildUp = matchMetrics?.buildUp || [];
    const attack = matchMetrics?.attack || [];
    const finish = matchMetrics?.finish || [];

    const buildUpSentence = describeBuildUpSentence(buildUp);
    const attackSentence = describeAttackSentence(attack);
    const finishSentence = describeFinishSentence(finish, reasonResults, stateResults);

    const narrativeParts = [];
    if (buildUpSentence && attackSentence) {
      narrativeParts.push(`${buildUpSentence}、${attackSentence.replace(/。$/, "")}`);
    } else if (buildUpSentence) {
      narrativeParts.push(buildUpSentence);
    } else if (attackSentence) {
      narrativeParts.push(attackSentence.replace(/。$/, ""));
    }

    if (finishSentence) {
      if (narrativeParts.length > 0) {
        narrativeParts.push(finishSentence.startsWith("一方") ? finishSentence : `。${finishSentence}`);
      } else {
        narrativeParts.push(finishSentence);
      }
    }

    let narrative = joinSentences(narrativeParts);
    if (narrative && !narrative.endsWith("。")) {
      narrative += "。";
    }

    const summary = buildStateSummary(stateResults, compositeReason);

    return {
      key: "attack",
      title: "Attack Review",
      metrics: [
        formatMetricsBlock("Build Up", buildUp),
        formatMetricsBlock("Attack", attack),
        formatMetricsBlock("Finish", finish),
      ],
      narrative,
      summary,
    };
  }

  return {
    describeBuildUpSentence,
    describeAttackSentence,
    describeFinishSentence,
    buildAttackReview,
  };
})();
