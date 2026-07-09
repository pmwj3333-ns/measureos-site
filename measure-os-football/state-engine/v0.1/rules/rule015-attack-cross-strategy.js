(function () {
  // Attack State v2: Finish率（ロスト率）ベース評価 — 全攻撃ルート（左・中央・右）
  window.MO_ATTACK_FINISH_RATE.registerAttackFinishRateRule({
    ruleId: "rule015",
    planCategoryKey: "attack",
    planOption: "クロス攻略",
    attackEventCodes: ["left", "center", "right"],
  });
})();
