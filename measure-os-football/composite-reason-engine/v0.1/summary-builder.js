(function () {
  // shortSummary は compositeReasonKey から生成する派生データです。
  // summary は shortSummary と compositeReasonKey から生成する派生データ（UI 表示用）です。
  const factBuilder = () => window.MO_COMPOSITE_FACT_BUILDER;

  function describeAttackOrigin(facts) {
    if (factBuilder()?.hasFact(facts, "attack_origin_left")) return "左を起点とした攻撃";
    if (factBuilder()?.hasFact(facts, "attack_origin_right")) return "右を起点とした攻撃";
    if (factBuilder()?.hasFact(facts, "attack_origin_central")) return "中央を起点とした攻撃";
    if (factBuilder()?.hasFact(facts, "attack_origin_behind")) return "背後を起点とした攻撃";
    if (factBuilder()?.hasFact(facts, "attack_origin_cross")) return "クロスを起点とした攻撃";
    return "攻撃";
  }

  function describeBuildUpProgress(facts) {
    if (factBuilder()?.hasFact(facts, "long_build_up_progressing")) {
      return "ロング前進から前線への到達";
    }
    if (factBuilder()?.hasFact(facts, "build_up_progressing")) {
      return "前進からシュートまで到達";
    }
    return "前進";
  }

  function describeDefenseBlock(facts) {
    if (factBuilder()?.hasFact(facts, "defense_press_working")) return "前線プレス";
    if (factBuilder()?.hasFact(facts, "defense_middle_block_working")) return "ミドルブロック";
    if (factBuilder()?.hasFact(facts, "defense_low_block_working")) return "守備ブロック";
    return "守備ブロック";
  }

  function describeTransitionSwitch(facts) {
    if (factBuilder()?.hasFact(facts, "transition_recovery_working")) return "即時奪回";
    if (factBuilder()?.hasFact(facts, "transition_retreat_working")) return "守備への切り替え";
    return "切り替え";
  }

  function fallbackSummary(facts) {
    const bodies = factBuilder()?.getRuleSummaryBodies(facts);
    return bodies || "観測事実を整理しています。";
  }

  function buildCompositeShortSummary(compositeReasonKey, facts = [], context = {}) {
    switch (compositeReasonKey) {
      case "composite.attack.green.attack_flow_working":
        return "攻撃優勢";

      case "composite.attack.yellow.attack_stalled_build_up_working":
      case "composite.attack.yellow.attack_working_build_up_stalled":
        return "攻撃停滞";

      case "composite.attack.yellow.mixed_pressure":
        return "攻撃停滞";

      case "composite.attack.orange.pressure":
        return "攻撃不安";

      case "composite.attack.red.breakdown":
        return "攻撃崩壊";

      case "composite.attack.unknown.aggregated_rule_summaries":
        return "攻撃要約";

      case "composite.defense.green.defense_switch_working":
        return "守備安定";

      case "composite.defense.yellow.central_penetration_allowed":
        return "守備警戒";

      case "composite.defense.yellow.mixed_pressure":
        return "守備停滞";

      case "composite.defense.orange.counter_or_shot_pressure":
      case "composite.defense.orange.mixed_pressure":
        return "守備不安";

      case "composite.defense.red.breakdown":
        return "守備崩壊";

      case "composite.defense.unknown.aggregated_rule_summaries":
        return "守備要約";

      case "composite.both.green.balanced":
        return "攻守安定";

      case "composite.both.mixed.attack_working_defense_central_pressure":
      case "composite.both.mixed.attack_working_defense_counter_pressure":
      case "composite.both.mixed.attack_working_defense_pressure":
      case "composite.both.mixed.attack_without_finish_defense_working":
      case "composite.both.mixed.attack_pressure_defense_working":
      case "composite.both.yellow.mixed_pressure":
        return "攻守拮抗";

      case "composite.both.orange.pressure":
        return "攻守不安";

      case "composite.both.red.breakdown":
        return "攻守崩壊";

      case "composite.unknown.aggregated_rule_summaries":
        return "攻守要約";

      default:
        if (context.analyzeMode === "attack") return "攻撃要約";
        if (context.analyzeMode === "defense") return "守備要約";
        return "攻守要約";
    }
  }

  function buildCompositeSummary(compositeReasonKey, shortSummary = "", facts = [], context = {}) {
    const origin = describeAttackOrigin(facts);
    const progression = describeBuildUpProgress(facts);
    const block = describeDefenseBlock(facts);
    const transition = describeTransitionSwitch(facts);

    switch (compositeReasonKey) {
      case "composite.attack.green.attack_flow_working":
        return `${origin}が継続し、${progression}しています。`;

      case "composite.attack.yellow.attack_stalled_build_up_working":
        return `${origin}は継続していますが、${progression}していません。`;

      case "composite.attack.yellow.attack_working_build_up_stalled":
        return `${origin}は機能していますが、${progression}していません。`;

      case "composite.attack.yellow.mixed_pressure":
      case "composite.attack.orange.pressure":
      case "composite.attack.red.breakdown":
      case "composite.attack.unknown.aggregated_rule_summaries":
        return fallbackSummary(facts) || `${shortSummary}の場面が見られます。`;

      case "composite.defense.green.defense_switch_working":
        return `${block}と${transition}により、相手の継続した攻撃を抑えています。`;

      case "composite.defense.yellow.central_penetration_allowed":
        return `${block}と${transition}は行われていますが、中央侵入を許す場面が見られます。`;

      case "composite.defense.yellow.mixed_pressure":
      case "composite.defense.orange.counter_or_shot_pressure":
      case "composite.defense.orange.mixed_pressure":
      case "composite.defense.red.breakdown":
      case "composite.defense.unknown.aggregated_rule_summaries":
        return fallbackSummary(facts) || `${shortSummary}の場面が見られます。`;

      case "composite.both.green.balanced":
        return "攻撃と守備の切り替えが機能し、相手の前進を抑えています。";

      case "composite.both.mixed.attack_working_defense_central_pressure":
        return "攻撃ではチャンスを作れていますが、守備では中央侵入を許す場面が見られます。";

      case "composite.both.mixed.attack_working_defense_counter_pressure":
        return "攻撃ではチャンスを作れていますが、守備では被カウンターを受ける場面が見られます。";

      case "composite.both.mixed.attack_working_defense_pressure":
        return "攻撃ではチャンスを作れていますが、守備では前進を許す場面が見られます。";

      case "composite.both.mixed.attack_without_finish_defense_working":
        return "攻撃では前進はあるものの仕上げまで至っていない場面がありますが、守備では相手の前進を抑えています。";

      case "composite.both.mixed.attack_pressure_defense_working":
        return "攻撃では前進に課題が見られますが、守備では相手の前進を抑えています。";

      case "composite.both.yellow.mixed_pressure":
      case "composite.both.orange.pressure":
      case "composite.both.red.breakdown":
      case "composite.unknown.aggregated_rule_summaries":
        return fallbackSummary(facts) || `${shortSummary}の場面が見られます。`;

      default:
        return fallbackSummary(facts) || `${shortSummary}の場面が見られます。`;
    }
  }

  window.MO_COMPOSITE_SUMMARY_BUILDER = {
    buildCompositeShortSummary,
    buildCompositeSummary,
  };
})();
