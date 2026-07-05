window.MO_PLAN_SNAPSHOT = (() => {
  const PLAN_SCHEMA = {
    attack: ["左優位", "右優位", "中央攻略", "クロス攻略"],
    defense: ["ハイプレス", "ミドルブロック", "ローブロック", "サイド誘導"],
    buildUp: ["保持前進", "ロング前進", "サイド前進", "中央前進"],
    transition: ["即時奪回", "リトリート", "縦に速く", "ボール保持"],
  };

  const CATEGORY_KEYS = Object.keys(PLAN_SCHEMA);

  function normalizePlanSnapshot(raw) {
    if (!raw || raw.version !== "0.1" || raw.confirmed !== true || !raw.categories) {
      return null;
    }

    const categories = {};
    let hasSelection = false;

    CATEGORY_KEYS.forEach((key) => {
      const allowed = new Set(PLAN_SCHEMA[key]);
      const source = Array.isArray(raw.categories[key]) ? raw.categories[key] : [];
      const next = [];
      source.forEach((label) => {
        if (typeof label === "string" && allowed.has(label)) {
          next.push(label);
        }
      });
      categories[key] = next;
      if (next.length > 0) hasSelection = true;
    });

    if (!hasSelection) return null;

    return {
      version: "0.1",
      confirmed: true,
      confirmedAt: typeof raw.confirmedAt === "string" ? raw.confirmedAt : new Date().toISOString(),
      categories,
      memo: typeof raw.memo === "string" ? raw.memo : "",
    };
  }

  function clonePlanSnapshot(raw) {
    const normalized = normalizePlanSnapshot(raw);
    if (!normalized) return null;
    return JSON.parse(JSON.stringify(normalized));
  }

  function isValidPlanSnapshot(raw) {
    return normalizePlanSnapshot(raw) !== null;
  }

  return {
    PLAN_SCHEMA,
    CATEGORY_KEYS,
    normalizePlanSnapshot,
    clonePlanSnapshot,
    isValidPlanSnapshot,
  };
})();
