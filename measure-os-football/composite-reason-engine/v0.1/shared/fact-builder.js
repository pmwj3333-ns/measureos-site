(function () {
  // Composite Fact は Composite Reason Engine の中心データです。
  // Rule Reason（summary / reasonKey / status / facts）を入力として構造化します。
  const helpers = () => window.MO_COMPOSITE_REASON_HELPERS;
  const ruleFacts = () => window.MO_REASON_FACT_BUILDER;

  function buildCompositeFacts({ analyzeMode, includedReasons = [], groupedReasons = {} }) {
    const { countFact, thresholdFact, createFact } = ruleFacts() || {};
    const { worstStatus, hasSuffixPattern, stripWindowPrefix } = helpers() || {};
    const built = [];

    const attackReasons = groupedReasons.attack || [];
    const buildUpReasons = groupedReasons.buildUp || [];
    const defenseReasons = groupedReasons.defense || [];
    const transitionReasons = groupedReasons.transition || [];
    const attackSideReasons = [...attackReasons, ...buildUpReasons];
    const defenseSideReasons = [...defenseReasons, ...transitionReasons];
    const allReasons = includedReasons;

    if (countFact) {
      built.push(countFact("rule_reason_count", "Rule Reason", allReasons.length));
    }

    allReasons.forEach((reason) => {
      if (!createFact) return;
      built.push(createFact({
        code: "included_rule_reason",
        label: reason.ruleId,
        value: reason.reasonKey,
      }));
      built.push(createFact({
        code: "included_rule_status",
        label: reason.ruleId,
        value: reason.status,
      }));
      if (reason.summary) {
        built.push(createFact({
          code: "rule_summary_body",
          label: reason.ruleId,
          value: stripWindowPrefix(reason.summary),
        }));
      }
    });

    const statusFacts = [
      ["overall_worst_status", "全体", worstStatus(allReasons)],
      ["attack_category_worst_status", "Attack", worstStatus(attackReasons)],
      ["build_up_category_worst_status", "Build Up", worstStatus(buildUpReasons)],
      ["defense_category_worst_status", "Defense", worstStatus(defenseReasons)],
      ["transition_category_worst_status", "Transition", worstStatus(transitionReasons)],
      ["attack_side_worst_status", "攻撃側", worstStatus(attackSideReasons)],
      ["defense_side_worst_status", "守備側", worstStatus(defenseSideReasons)],
    ];

    statusFacts.forEach(([code, label, status]) => {
      if (createFact) {
        built.push(createFact({ code, label, value: status }));
      }
    });

    const patternFacts = [
      ["attack_origin_left", attackReasons, "left"],
      ["attack_origin_right", attackReasons, "right"],
      ["attack_origin_central", attackReasons, "central"],
      ["attack_origin_behind", attackReasons, "behind"],
      ["attack_origin_cross", attackReasons, "cross"],
      ["build_up_progressing", buildUpReasons, "build_up_progressing"],
      ["long_build_up_progressing", buildUpReasons, "long_build_up_progressing"],
      ["defense_block_working", defenseReasons, "block_working"],
      ["defense_press_working", defenseReasons, "press_working"],
      ["defense_middle_block_working", defenseReasons, "middle_block_working"],
      ["defense_low_block_working", defenseReasons, "low_block_working"],
      ["transition_recovery_working", transitionReasons, "immediate_recovery_working"],
      ["transition_retreat_working", transitionReasons, "retreat_working"],
      ["central_penetration_observed", [...defenseReasons, ...transitionReasons], "central"],
      ["counter_observed", allReasons, "counter"],
      ["shot_conceded_observed", defenseSideReasons, "shot_conceded"],
      ["without_finish_observed", attackSideReasons, "without_finish"],
    ];

    patternFacts.forEach(([code, reasons, pattern]) => {
      if (hasSuffixPattern(reasons, pattern) && thresholdFact) {
        built.push(thresholdFact(code, code, 1, ">=", 1));
      }
    });

    if (createFact) {
      built.push(createFact({ code: "analyze_mode", label: "Analyze Mode", value: analyzeMode }));
    }

    return built;
  }

  function getFactValue(facts, code) {
    const fact = (facts || []).find((item) => item.code === code);
    return fact?.value ?? null;
  }

  function hasFact(facts, code) {
    return (facts || []).some((item) => item.code === code);
  }

  function getRuleSummaryBodies(facts, separator = "また、") {
    return (facts || [])
      .filter((item) => item.code === "rule_summary_body" && item.value)
      .map((item) => String(item.value))
      .join(separator);
  }

  window.MO_COMPOSITE_FACT_BUILDER = {
    buildCompositeFacts,
    getFactValue,
    hasFact,
    getRuleSummaryBodies,
  };
})();
