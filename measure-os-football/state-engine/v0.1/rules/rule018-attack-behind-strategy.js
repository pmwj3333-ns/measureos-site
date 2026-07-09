(function () {
  // Attack State v2: Finish率（ロスト率）ベース評価 — 背後ルート
  window.MO_ATTACK_FINISH_RATE.registerAttackFinishRateRule({
    ruleId: "rule018",
    planCategoryKey: "attack",
    planOption: "背後攻略",
    attackEventCodes: ["behind"],
  });
})();
