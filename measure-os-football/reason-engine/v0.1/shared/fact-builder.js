(function () {
  // Fact は Reason Engine の中心データです。
  // このモジュールは Fact 生成の共通ヘルパを提供します。
  // summary 用の windowPrefix / joinSentences もここに置きますが、表示文生成は Fact の派生処理です。
  function createFact({ code, label, value = null, comparator = null, threshold = null }) {
    const fact = { code, label };
    if (value != null) fact.value = value;
    if (comparator != null) fact.comparator = comparator;
    if (threshold != null) fact.threshold = threshold;
    return fact;
  }

  function countFact(code, label, value) {
    return createFact({ code, label, value: Math.max(0, Number(value) || 0) });
  }

  function thresholdFact(code, label, value, comparator, threshold) {
    return createFact({
      code,
      label,
      value: Math.max(0, Number(value) || 0),
      comparator,
      threshold,
    });
  }

  function windowPrefix(minutes) {
    const windowMinutes = Math.max(1, Number(minutes) || 5);
    return `直近${windowMinutes}分、`;
  }

  function joinSentences(parts) {
    return parts.filter(Boolean).join("");
  }

  function formatCountPhrase(label, value, unit = "回") {
    const count = Math.max(0, Number(value) || 0);
    if (count <= 0) return null;
    return `${label}${count}${unit}`;
  }

  window.MO_REASON_FACT_BUILDER = {
    createFact,
    countFact,
    thresholdFact,
    windowPrefix,
    joinSentences,
    formatCountPhrase,
  };
})();
