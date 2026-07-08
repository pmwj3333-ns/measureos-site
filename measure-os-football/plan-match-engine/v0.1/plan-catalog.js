(function () {
  const PLAN_SCHEMA = {
    attack: ["左優位", "右優位", "中央攻略", "クロス攻略", "背後攻略"],
    defense: ["ハイプレス", "ミドルブロック", "ローブロック", "サイド誘導"],
    buildUp: ["保持前進", "ロング前進", "サイド前進", "中央前進"],
    transition: ["即時奪回", "リトリート", "縦に速く", "ボール保持"],
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

  const PLAN_SIGNATURES = {
    rule012: {
      positive: ["attack_origin_left"],
      negative: ["attack_origin_right", "attack_origin_behind", "counter_observed"],
    },
    rule013: {
      positive: ["attack_origin_right"],
      negative: ["attack_origin_left", "attack_origin_behind", "counter_observed"],
    },
    rule014: {
      positive: ["attack_origin_central"],
      negative: ["attack_origin_left", "attack_origin_right", "counter_observed"],
    },
    rule015: {
      positive: ["attack_origin_cross"],
      negative: ["counter_observed"],
    },
    rule018: {
      positive: ["attack_origin_behind"],
      negative: ["counter_observed", "without_finish_observed"],
    },
    rule004: {
      positive: ["build_up_progressing"],
      negative: ["long_build_up_progressing", "counter_observed"],
    },
    rule005: {
      positive: ["long_build_up_progressing"],
      negative: ["build_up_progressing", "counter_observed"],
    },
    rule006: {
      positive: ["attack_origin_left", "attack_origin_right"],
      negative: ["counter_observed"],
    },
    rule007: {
      positive: ["attack_origin_central", "build_up_progressing"],
      negative: ["counter_observed"],
    },
    rule002: {
      positive: ["defense_press_working"],
      negative: ["central_penetration_observed", "shot_conceded_observed", "counter_observed"],
    },
    rule016: {
      positive: ["defense_middle_block_working"],
      negative: ["central_penetration_observed", "shot_conceded_observed"],
    },
    rule003: {
      positive: ["defense_low_block_working"],
      negative: ["central_penetration_observed", "shot_conceded_observed"],
    },
    rule017: {
      positive: ["defense_block_working"],
      negative: ["central_penetration_observed", "counter_observed"],
    },
    rule008: {
      positive: ["transition_recovery_working"],
      negative: ["counter_observed"],
    },
    rule009: {
      positive: ["transition_retreat_working"],
      negative: ["counter_observed", "central_penetration_observed"],
    },
    rule010: {
      positive: ["build_up_progressing", "attack_origin_central"],
      negative: ["counter_observed"],
    },
    rule011: {
      positive: ["transition_recovery_working"],
      negative: ["counter_observed"],
    },
  };

  function getCategoryKeysForMode(analyzeMode) {
    return window.MO_COMPOSITE_ANALYZE_MODES?.getCategoryKeysForMode(analyzeMode)
      || PLAN_SCHEMA[analyzeMode]
      || ["attack", "buildUp", "defense", "transition"];
  }

  function resolveRuleId(categoryKey, optionLabel) {
    return PLAN_OPTION_RULE_IDS[categoryKey]?.[optionLabel] || null;
  }

  function resolveOptionLabel(categoryKey, ruleId) {
    const options = PLAN_OPTION_RULE_IDS[categoryKey] || {};
    return Object.entries(options).find(([, id]) => id === ruleId)?.[0] || null;
  }

  function formatPlanLabel(categories, categoryKeys) {
    return categoryKeys
      .flatMap((key) => (Array.isArray(categories[key]) ? categories[key] : []))
      .join(" / ");
  }

  function buildCandidatePlans(analyzeMode) {
    const categoryKeys = getCategoryKeysForMode(analyzeMode);
    const optionLists = categoryKeys.map((key) => (
      (PLAN_SCHEMA[key] || []).map((option) => ({ categoryKey: key, option }))
    ));

    if (optionLists.length === 0) return [];

    const combinations = optionLists.reduce(
      (acc, list) => acc.flatMap((combo) => list.map((item) => [...combo, item])),
      [[]],
    );

    return combinations.map((combo) => {
      const categories = {};
      combo.forEach(({ categoryKey, option }) => {
        categories[categoryKey] = [option];
      });
      return {
        analyzeMode,
        categories,
        label: formatPlanLabel(categories, categoryKeys),
      };
    });
  }

  window.MO_PLAN_MATCH_CATALOG = {
    PLAN_SCHEMA,
    PLAN_OPTION_RULE_IDS,
    PLAN_SIGNATURES,
    getCategoryKeysForMode,
    resolveRuleId,
    resolveOptionLabel,
    formatPlanLabel,
    buildCandidatePlans,
  };
})();
