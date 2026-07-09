/* global load, MO_STATE_ENGINE, MO_PLAN_SNAPSHOT */

const base = "/Users/niiyasyogo/Desktop/measureos-site/measure-os-football";

load(`${base}/shared/plan-snapshot.js`);
load(`${base}/shared/attack-plan.js`);
load(`${base}/shared/attack-observer.js`);
load(`${base}/state-engine/v0.1/engine.js`);
load(`${base}/state-engine/v0.1/shared/attack-finish-rate.js`);
[
  "rule012-attack-left-dominance.js",
  "rule013-attack-right-dominance.js",
  "rule014-attack-central-attack.js",
  "rule015-attack-cross-strategy.js",
  "rule018-attack-behind-strategy.js",
  "rule002-defense-high-press.js",
  "rule003-defense-low-block.js",
  "rule016-defense-middle-block.js",
  "rule017-defense-side-guiding.js",
  "rule004-build-up-hold-and-advance.js",
  "rule005-build-up-long-advance.js",
  "rule006-build-up-side-advance.js",
  "rule007-build-up-central-advance.js",
  "rule008-transition-immediate-recovery.js",
  "rule009-transition-retreat.js",
  "rule010-transition-fast-vertical.js",
  "rule011-transition-ball-retention.js",
].forEach((file) => {
  load(`${base}/state-engine/v0.1/rules/${file}`);
});

const plan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  categories: {
    attack: ["左優位"],
    defense: ["ハイプレス"],
    buildUp: ["保持前進", "ロング前進"],
    transition: ["即時奪回"],
  },
});

const events = [
  { eventName: "左侵入", time: "01:00" },
  { eventName: "前線奪取", time: "01:30" },
  { eventName: "被中央侵入", time: "02:00" },
  { eventName: "即時奪回成功", time: "02:30" },
];

const result = MO_STATE_ENGINE.evaluateLiveState({ plan, events, elapsed: 180 });

print("=== normalized plan categories ===");
print(JSON.stringify(plan.categories, null, 2));
print("=== evaluateLiveState result count: " + result.length + " ===");
result.forEach((item) => {
  print(JSON.stringify({
    ruleId: item.ruleId,
    category: item.category,
    planCategoryKey: item.planCategoryKey,
    label: item.label,
    status: item.status,
  }));
});

const liveStateCategories = [
  { key: "attack", aliases: ["Attack", "attack"] },
  { key: "defense", aliases: ["Defense", "defense"] },
  { key: "buildUp", aliases: ["Build Up", "buildUp", "BuildUp"] },
  { key: "transition", aliases: ["Transition", "transition"] },
];

function resolveLiveStateCategoryKey(category, planCategoryKey) {
  if (planCategoryKey && liveStateCategories.some((item) => item.key === planCategoryKey)) {
    return planCategoryKey;
  }
  const normalized = String(category || "").trim();
  if (!normalized) return null;
  const matched = liveStateCategories.find((item) => item.aliases.includes(normalized));
  if (matched) return matched.key;
  const lower = normalized.toLowerCase();
  if (lower === "build up" || lower === "buildup") return "buildUp";
  return liveStateCategories.find((item) => item.key.toLowerCase() === lower)?.key || null;
}

print("=== grouped ===");
const grouped = { attack: [], defense: [], buildUp: [], transition: [] };
result.forEach((item) => {
  const key = resolveLiveStateCategoryKey(item.category, item.planCategoryKey);
  print(`map ${item.ruleId}: category=${item.category} planCategoryKey=${item.planCategoryKey} -> ${key}`);
  if (key) grouped[key].push(item.ruleId);
});
print(JSON.stringify(grouped, null, 2));
