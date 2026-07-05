(function () {
  const RULE_ID = "rule001";
  const PLAN_CATEGORY_KEY = "attack";
  const PLAN_OPTION = "左優位";
  const TRIGGER_EVENT = "左侵入";
  const STATE_CATEGORY = "Attack";
  const STATE_LABEL = "🟢 左優位維持";

  window.MO_STATE_ENGINE.registerRule({
    id: RULE_ID,
    planCategoryKey: PLAN_CATEGORY_KEY,
    planOption: PLAN_OPTION,

    isEnabled(plan) {
      const attackPlan = plan?.categories?.[PLAN_CATEGORY_KEY];
      return Array.isArray(attackPlan) && attackPlan.includes(PLAN_OPTION);
    },

    evaluate(events) {
      const leftPenetrationCount = events.filter((event) => event.eventName === TRIGGER_EVENT).length;
      if (leftPenetrationCount === 0) return null;

      return {
        ruleId: RULE_ID,
        category: STATE_CATEGORY,
        label: STATE_LABEL,
        status: "green",
        reasonEventCounts: {
          [TRIGGER_EVENT]: leftPenetrationCount,
        },
      };
    },
  });
})();
