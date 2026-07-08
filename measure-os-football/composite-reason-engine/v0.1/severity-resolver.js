(function () {
  const SEVERITIES = new Set(["green", "yellow", "orange", "red"]);

  const factBuilder = () => window.MO_COMPOSITE_FACT_BUILDER;

  function resolveCompositeSeverity(facts = []) {
    const overall = factBuilder()?.getFactValue(facts, "overall_worst_status");
    if (SEVERITIES.has(overall)) return overall;

    const ruleStatuses = (facts || [])
      .filter((fact) => fact.code === "included_rule_status" && SEVERITIES.has(fact.value))
      .map((fact) => fact.value);

    if (ruleStatuses.length === 0) return "green";

    const helpers = window.MO_COMPOSITE_REASON_HELPERS;
    if (helpers?.worstStatus) {
      return helpers.worstStatus(ruleStatuses.map((status) => ({ status })));
    }

    return ruleStatuses.reduce((worst, status) => {
      const rank = { green: 0, yellow: 1, orange: 2, red: 3 };
      return (rank[status] ?? 0) > (rank[worst] ?? 0) ? status : worst;
    }, "green");
  }

  window.MO_COMPOSITE_SEVERITY_RESOLVER = {
    SEVERITIES,
    resolveCompositeSeverity,
  };
})();
