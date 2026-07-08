(function () {
  const factBuilder = () => window.MO_COMPOSITE_FACT_BUILDER;

  function getStatus(facts, code) {
    return factBuilder()?.getFactValue(facts, code) || "green";
  }

  function hasPattern(facts, code) {
    return factBuilder()?.hasFact(facts, code) || false;
  }

  function resolveAttackCompositeReasonKey(facts) {
    const overall = getStatus(facts, "overall_worst_status");
    const attackWorst = getStatus(facts, "attack_category_worst_status");
    const buildUpWorst = getStatus(facts, "build_up_category_worst_status");

    if (overall === "green") {
      return "composite.attack.green.attack_flow_working";
    }
    if (overall === "yellow") {
      if (attackWorst === "yellow" && buildUpWorst === "green") {
        return "composite.attack.yellow.attack_stalled_build_up_working";
      }
      if (attackWorst === "green" && buildUpWorst === "yellow") {
        return "composite.attack.yellow.attack_working_build_up_stalled";
      }
      return "composite.attack.yellow.mixed_pressure";
    }
    if (overall === "orange") {
      return "composite.attack.orange.pressure";
    }
    if (overall === "red") {
      return "composite.attack.red.breakdown";
    }
    return "composite.attack.unknown.aggregated_rule_summaries";
  }

  function resolveDefenseCompositeReasonKey(facts) {
    const overall = getStatus(facts, "overall_worst_status");

    if (overall === "green") {
      return "composite.defense.green.defense_switch_working";
    }
    if (overall === "yellow") {
      if (hasPattern(facts, "central_penetration_observed")) {
        return "composite.defense.yellow.central_penetration_allowed";
      }
      return "composite.defense.yellow.mixed_pressure";
    }
    if (overall === "orange") {
      if (hasPattern(facts, "counter_observed") || hasPattern(facts, "shot_conceded_observed")) {
        return "composite.defense.orange.counter_or_shot_pressure";
      }
      return "composite.defense.orange.mixed_pressure";
    }
    if (overall === "red") {
      return "composite.defense.red.breakdown";
    }
    return "composite.defense.unknown.aggregated_rule_summaries";
  }

  function resolveBothCompositeReasonKey(facts) {
    const attackSide = getStatus(facts, "attack_side_worst_status");
    const defenseSide = getStatus(facts, "defense_side_worst_status");

    if (attackSide === "green" && defenseSide === "green") {
      return "composite.both.green.balanced";
    }
    if (attackSide === "green" && (defenseSide === "yellow" || defenseSide === "orange")) {
      if (hasPattern(facts, "central_penetration_observed")) {
        return "composite.both.mixed.attack_working_defense_central_pressure";
      }
      if (hasPattern(facts, "counter_observed")) {
        return "composite.both.mixed.attack_working_defense_counter_pressure";
      }
      return "composite.both.mixed.attack_working_defense_pressure";
    }
    if ((attackSide === "yellow" || attackSide === "orange") && defenseSide === "green") {
      if (hasPattern(facts, "without_finish_observed")) {
        return "composite.both.mixed.attack_without_finish_defense_working";
      }
      return "composite.both.mixed.attack_pressure_defense_working";
    }
    if (attackSide === "red" || defenseSide === "red") {
      return "composite.both.red.breakdown";
    }
    if (attackSide === "orange" || defenseSide === "orange") {
      return "composite.both.orange.pressure";
    }
    return "composite.both.yellow.mixed_pressure";
  }

  function resolveCompositeReasonKey({ analyzeMode, facts = [] }) {
    switch (analyzeMode) {
      case "attack":
        return resolveAttackCompositeReasonKey(facts);
      case "defense":
        return resolveDefenseCompositeReasonKey(facts);
      case "both":
        return resolveBothCompositeReasonKey(facts);
      default:
        return "composite.unknown.aggregated_rule_summaries";
    }
  }

  window.MO_COMPOSITE_REASON_KEY_RESOLVER = {
    resolveCompositeReasonKey,
  };
})();
