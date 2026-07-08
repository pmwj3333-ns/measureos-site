(function () {
  // reasonEventCounts を code 正規化し、Fact 生成の入力を揃える
  const LABEL_TO_CODE = {
    背後: "behind",
    シュート: "shot",
    決定機: "bigChance",
    被カウンター: "counter",
    左侵入: "leftAdvance",
    左: "leftAdvance",
    left: "leftAdvance",
    中央侵入: "centralAdvance",
    中央: "centralAdvance",
    center: "centralAdvance",
    右侵入: "rightAdvance",
    右: "rightAdvance",
    right: "rightAdvance",
    クロス: "cross",
    カウンター被弾: "counterConceded",
    counter: "counterConceded",
    前線奪取: "frontLineRecovery",
    被中央侵入: "centralPenetration",
    被中央: "centralPenetration",
    被シュート: "shotConceded",
    被左侵入: "leftConceded",
    被左: "leftConceded",
    被右侵入: "rightConceded",
    被右: "rightConceded",
    被クロス: "crossConceded",
    ボール奪取: "ballWon",
    即時奪回成功: "quickRecovery",
    即時奪回: "quickRecovery",
    counterpress: "quickRecovery",
    カウンター開始: "counterStarted",
  };

  const CODE_TO_LABEL = {
    behind: "背後",
    shot: "シュート",
    bigChance: "決定機",
    counter: "被カウンター",
    leftAdvance: "左侵入",
    centralAdvance: "中央侵入",
    rightAdvance: "右侵入",
    cross: "クロス",
    counterConceded: "被カウンター",
    frontLineRecovery: "前線奪取",
    centralPenetration: "被中央侵入",
    shotConceded: "被シュート",
    leftConceded: "被左侵入",
    centralConceded: "被中央侵入",
    rightConceded: "被右侵入",
    crossConceded: "被クロス",
    ballWon: "ボール奪取",
    quickRecovery: "即時奪回",
    counterStarted: "カウンター開始",
  };

  const RULE_LABEL_TO_CODE = {
    rule004: {
      被中央侵入: "centralConceded",
      被中央: "centralConceded",
    },
    rule005: {
      被中央侵入: "centralConceded",
      被中央: "centralConceded",
    },
    rule002: {
      被中央侵入: "centralPenetration",
      被中央: "centralPenetration",
    },
    rule016: {
      被中央侵入: "centralPenetration",
      被中央: "centralPenetration",
    },
    rule003: {
      被中央侵入: "centralPenetration",
      被中央: "centralPenetration",
    },
    rule009: {
      被中央侵入: "centralPenetration",
      被中央: "centralPenetration",
    },
  };

  const RULE_COUNT_SCHEMAS = {
    rule018: ["behind", "shot", "bigChance", "counter"],
    rule012: ["leftAdvance", "centralAdvance", "rightAdvance", "cross", "shot", "counterConceded"],
    rule013: ["leftAdvance", "centralAdvance", "rightAdvance", "cross", "shot", "counterConceded"],
    rule014: ["leftAdvance", "centralAdvance", "rightAdvance", "cross", "shot", "counterConceded"],
    rule002: ["frontLineRecovery", "centralPenetration", "shotConceded"],
    rule016: [
      "centralPenetration",
      "leftConceded",
      "rightConceded",
      "crossConceded",
      "shotConceded",
      "ballWon",
      "frontLineRecovery",
    ],
    rule003: [
      "centralPenetration",
      "leftConceded",
      "rightConceded",
      "crossConceded",
      "shotConceded",
      "ballWon",
    ],
    rule004: [
      "leftAdvance",
      "centralAdvance",
      "rightAdvance",
      "leftConceded",
      "centralConceded",
      "rightConceded",
      "counterConceded",
      "quickRecovery",
    ],
    rule005: [
      "leftAdvance",
      "centralAdvance",
      "rightAdvance",
      "leftConceded",
      "centralConceded",
      "rightConceded",
      "counterConceded",
      "quickRecovery",
    ],
    rule008: ["quickRecovery", "counterStarted", "counterConceded"],
    rule009: [
      "centralPenetration",
      "shotConceded",
      "counterConceded",
      "ballWon",
      "leftConceded",
      "rightConceded",
    ],
  };

  function toCodeForRule(key, ruleId) {
    const ruleMap = RULE_LABEL_TO_CODE[ruleId];
    const normalized = String(key || "").trim();
    if (ruleMap?.[normalized]) return ruleMap[normalized];
    return toCode(normalized);
  }

  function toCode(key) {
    const normalized = String(key || "").trim();
    if (!normalized) return null;
    if (CODE_TO_LABEL[normalized]) return normalized;
    return LABEL_TO_CODE[normalized] || normalized;
  }

  function toLabel(code) {
    return CODE_TO_LABEL[code] || code;
  }

  function normalizeReasonEventCounts(counts, ruleId) {
    const schema = RULE_COUNT_SCHEMAS[ruleId] || [];
    const normalized = {};
    schema.forEach((code) => {
      normalized[code] = 0;
    });

    if (!counts || typeof counts !== "object") {
      return normalized;
    }

    Object.entries(counts).forEach(([key, rawValue]) => {
      const code = toCodeForRule(key, ruleId);
      const value = Math.max(0, Number(rawValue) || 0);
      if (!code) return;
      if (schema.includes(code)) {
        normalized[code] = value;
      } else if (normalized[code] == null) {
        normalized[code] = value;
      }
    });

    return normalized;
  }

  window.MO_REASON_EVENT_VOCABULARY = {
    LABEL_TO_CODE,
    CODE_TO_LABEL,
    RULE_COUNT_SCHEMAS,
    toCode,
    toLabel,
    normalizeReasonEventCounts,
  };
})();
