window.MO_PLAN_SNAPSHOT = (() => {
  const PLAN_SCHEMA = {
    attack: ["左優位", "右優位", "中央攻略", "クロス攻略", "背後攻略"],
    defense: ["ハイプレス", "ミドルブロック", "ローブロック", "サイド誘導"],
    buildUp: ["保持前進", "ロング前進", "サイド前進", "中央前進"],
    transition: ["即時奪回", "リトリート", "縦に速く", "ボール保持"],
  };

  const ATTACK_MODE_CATEGORY_KEYS = ["attack", "buildUp"];
  const DEFENSE_MODE_CATEGORY_KEYS = ["defense", "transition"];
  const BOTH_MODE_CATEGORY_KEYS = ["attack", "buildUp", "defense", "transition"];
  const CATEGORY_KEYS = Object.keys(PLAN_SCHEMA);

  function getBothModeLabels(categoryKey) {
    if (categoryKey === "attack" || categoryKey === "buildUp") {
      return window.MO_ATTACK_PLAN?.getLabels(categoryKey) || [];
    }
    if (categoryKey === "defense" || categoryKey === "transition") {
      return window.MO_DEFENSE_PLAN?.getLabels(categoryKey) || [];
    }
    return [];
  }

  function bothLabelToCode(categoryKey, label) {
    if (categoryKey === "attack" || categoryKey === "buildUp") {
      return window.MO_ATTACK_PLAN?.labelToCode(categoryKey, label) || null;
    }
    if (categoryKey === "defense" || categoryKey === "transition") {
      return window.MO_DEFENSE_PLAN?.labelToCode(categoryKey, label) || null;
    }
    return null;
  }

  function bothCodeToLabel(categoryKey, code) {
    if (categoryKey === "attack" || categoryKey === "buildUp") {
      return window.MO_ATTACK_PLAN?.codeToLabel(categoryKey, code) || null;
    }
    if (categoryKey === "defense" || categoryKey === "transition") {
      return window.MO_DEFENSE_PLAN?.codeToLabel(categoryKey, code) || null;
    }
    return null;
  }

  const CATEGORY_LEGACY_KEYS = {
    buildUp: ["build_up", "BuildUp", "buildup", "Build Up"],
  };

  function readRawCategory(rawCategories, key) {
    if (!rawCategories || typeof rawCategories !== "object") return [];
    if (Array.isArray(rawCategories[key])) return rawCategories[key];
    if (typeof rawCategories[key] === "string") return [rawCategories[key]];

    const legacyKeys = CATEGORY_LEGACY_KEYS[key] || [];
    for (const legacyKey of legacyKeys) {
      if (Array.isArray(rawCategories[legacyKey])) return rawCategories[legacyKey];
      if (typeof rawCategories[legacyKey] === "string") return [rawCategories[legacyKey]];
    }

    return [];
  }

  function resolveAnalyzeMode(raw) {
    if (raw?.analyzeMode === "attack") return "attack";
    if (raw?.analyzeMode === "defense") return "defense";
    if (window.MO_ATTACK_PLAN?.isAttackAnalyzeMode?.(raw?.analyzeMode)) return "attack";
    if (window.MO_DEFENSE_PLAN?.isDefenseAnalyzeMode?.(raw?.analyzeMode)) return "defense";
    return raw?.analyzeMode || "both";
  }

  function codeSelectionToLabels(raw, modePlan, categoryKeys) {
    if (!modePlan) return null;

    const categories = {};
    categoryKeys.forEach((key) => {
      const code = typeof raw[key] === "string" ? raw[key] : null;
      if (!code) return;
      const label = modePlan.codeToLabel(key, code);
      if (label) categories[key] = [label];
    });

    return Object.keys(categories).length > 0 ? categories : null;
  }

  function normalizeModeSelection(raw, {
    analyzeMode,
    categoryKeys,
    modePlan,
  }) {
    const fromCodes = codeSelectionToLabels(raw, modePlan, categoryKeys);
    const categories = fromCodes || {};
    const sourceCategories = raw?.categories && typeof raw.categories === "object"
      ? raw.categories
      : {};

    categoryKeys.forEach((key) => {
      if (categories[key]) return;
      const allowed = new Set(modePlan?.getLabels(key) || PLAN_SCHEMA[key]);
      const source = readRawCategory(sourceCategories, key);
      const next = [];
      source.forEach((value) => {
        if (typeof value !== "string") return;
        const label = allowed.has(value)
          ? value
          : modePlan?.codeToLabel(key, value);
        if (label && allowed.has(label)) next.push(label);
      });
      if (next.length > 0) categories[key] = next.slice(0, 1);
    });

    let hasSelection = false;
    categoryKeys.forEach((key) => {
      if (Array.isArray(categories[key]) && categories[key].length > 0) {
        hasSelection = true;
      }
    });
    if (!hasSelection) return null;

    const snapshot = {
      version: "0.1",
      confirmed: true,
      confirmedAt: typeof raw.confirmedAt === "string" ? raw.confirmedAt : new Date().toISOString(),
      analyzeMode,
      categories,
      memo: typeof raw.memo === "string" ? raw.memo : "",
    };

    categoryKeys.forEach((key) => {
      const label = categories[key]?.[0];
      snapshot[key] = label ? modePlan?.labelToCode(key, label) : null;
    });

    return snapshot;
  }

  function normalizeAttackSelection(raw) {
    return normalizeModeSelection(raw, {
      analyzeMode: "attack",
      categoryKeys: ATTACK_MODE_CATEGORY_KEYS,
      modePlan: window.MO_ATTACK_PLAN,
    });
  }

  function normalizeDefenseSelection(raw) {
    return normalizeModeSelection(raw, {
      analyzeMode: "defense",
      categoryKeys: DEFENSE_MODE_CATEGORY_KEYS,
      modePlan: window.MO_DEFENSE_PLAN,
    });
  }

  function normalizeBothSelection(raw) {
    const categories = {};
    const sourceCategories = raw?.categories && typeof raw.categories === "object"
      ? raw.categories
      : {};

    BOTH_MODE_CATEGORY_KEYS.forEach((key) => {
      const allowed = new Set(getBothModeLabels(key));
      let label = null;

      if (typeof raw?.[key] === "string") {
        const fromCode = bothCodeToLabel(key, raw[key]);
        if (fromCode && allowed.has(fromCode)) label = fromCode;
      }

      if (!label) {
        const source = readRawCategory(sourceCategories, key);
        source.forEach((value) => {
          if (label || typeof value !== "string") return;
          if (allowed.has(value)) {
            label = value;
            return;
          }
          const fromCode = bothCodeToLabel(key, value);
          if (fromCode && allowed.has(fromCode)) label = fromCode;
        });
      }

      if (label) categories[key] = [label];
    });

    const hasSelection = BOTH_MODE_CATEGORY_KEYS.some(
      (key) => Array.isArray(categories[key]) && categories[key].length > 0,
    );
    if (!hasSelection) return null;

    const snapshot = {
      version: "0.1",
      confirmed: true,
      confirmedAt: typeof raw.confirmedAt === "string" ? raw.confirmedAt : new Date().toISOString(),
      analyzeMode: "both",
      categories,
      memo: typeof raw.memo === "string" ? raw.memo : "",
    };

    BOTH_MODE_CATEGORY_KEYS.forEach((key) => {
      const selectedLabel = categories[key]?.[0];
      snapshot[key] = selectedLabel ? bothLabelToCode(key, selectedLabel) : null;
    });

    return snapshot;
  }

  function normalizePlanSnapshot(raw) {
    if (!raw) return null;

    const analyzeMode = resolveAnalyzeMode(raw);
    if (analyzeMode === "attack") {
      const normalizedAttack = normalizeAttackSelection(raw);
      if (normalizedAttack) return normalizedAttack;
    }
    if (analyzeMode === "defense") {
      const normalizedDefense = normalizeDefenseSelection(raw);
      if (normalizedDefense) return normalizedDefense;
    }
    if (analyzeMode === "both") {
      const normalizedBoth = normalizeBothSelection(raw);
      if (normalizedBoth) return normalizedBoth;
    }

    if (raw.version !== "0.1" || raw.confirmed !== true || !raw.categories) {
      const fallbackAttack = normalizeAttackSelection(raw);
      if (fallbackAttack) return fallbackAttack;
      const fallbackDefense = normalizeDefenseSelection(raw);
      if (fallbackDefense) return fallbackDefense;
      const fallbackBoth = normalizeBothSelection(raw);
      if (fallbackBoth) return fallbackBoth;
      return null;
    }

    const categories = {};
    let hasSelection = false;

    BOTH_MODE_CATEGORY_KEYS.forEach((key) => {
      const allowed = new Set(getBothModeLabels(key));
      const source = readRawCategory(raw.categories, key);
      const next = [];
      source.forEach((label) => {
        if (typeof label !== "string") return;
        if (allowed.has(label)) {
          next.push(label);
          return;
        }
        const fromCode = bothCodeToLabel(key, label);
        if (fromCode && allowed.has(fromCode)) next.push(fromCode);
      });
      categories[key] = next.slice(0, 1);
      if (categories[key].length > 0) hasSelection = true;
    });

    if (!hasSelection) return null;

    const snapshot = {
      version: "0.1",
      confirmed: true,
      confirmedAt: typeof raw.confirmedAt === "string" ? raw.confirmedAt : new Date().toISOString(),
      analyzeMode: "both",
      categories,
      memo: typeof raw.memo === "string" ? raw.memo : "",
    };

    BOTH_MODE_CATEGORY_KEYS.forEach((key) => {
      const selectedLabel = categories[key]?.[0];
      snapshot[key] = selectedLabel ? bothLabelToCode(key, selectedLabel) : null;
    });

    return snapshot;
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
    ATTACK_MODE_CATEGORY_KEYS,
    DEFENSE_MODE_CATEGORY_KEYS,
    BOTH_MODE_CATEGORY_KEYS,
    normalizePlanSnapshot,
    clonePlanSnapshot,
    isValidPlanSnapshot,
  };
})();
