(function () {
  const ANALYZE_MODES = new Set(["attack", "defense", "both"]);

  const ANALYZE_MODE_CATEGORIES = {
    attack: ["attack", "buildUp"],
    defense: ["defense", "transition"],
    both: ["attack", "buildUp", "defense", "transition"],
  };

  const CATEGORY_LABELS = {
    attack: "Attack",
    defense: "Defense",
    buildUp: "Build Up",
    transition: "Transition",
  };

  const PLAN_OPTION_RULE_IDS = {
    attack: {
      "左優位": "rule012",
      "右優位": "rule013",
      "中央攻略": "rule014",
      "クロス攻略": "rule015",
      "背後攻略": "rule018",
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

  function normalizeAnalyzeMode(mode) {
    return ANALYZE_MODES.has(mode) ? mode : "both";
  }

  function getCategoryKeysForMode(analyzeMode) {
    return ANALYZE_MODE_CATEGORIES[normalizeAnalyzeMode(analyzeMode)] || ANALYZE_MODE_CATEGORIES.both;
  }

  function resolveCategoryKeyForRuleId(ruleId) {
    for (const [categoryKey, options] of Object.entries(PLAN_OPTION_RULE_IDS)) {
      for (const optionRuleId of Object.values(options)) {
        if (optionRuleId === ruleId) return categoryKey;
      }
    }
    return null;
  }

  window.MO_COMPOSITE_ANALYZE_MODES = {
    ANALYZE_MODES,
    ANALYZE_MODE_CATEGORIES,
    CATEGORY_LABELS,
    PLAN_OPTION_RULE_IDS,
    normalizeAnalyzeMode,
    getCategoryKeysForMode,
    resolveCategoryKeyForRuleId,
  };
})();
