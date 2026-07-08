/* global load, MO_STATE_ENGINE, MO_REASON_ENGINE, MO_COMPOSITE_REASON_ENGINE, MO_PLAN_SNAPSHOT */

const base = "/Users/niiyasyogo/Desktop/measureos-site/measure-os-football";

load(`${base}/shared/plan-snapshot.js`);
load(`${base}/shared/attack-plan.js`);
load(`${base}/shared/attack-observer.js`);
load(`${base}/shared/defense-plan.js`);
load(`${base}/state-engine/v0.1/engine.js`);
load(`${base}/reason-engine/v0.1/shared/event-vocabulary.js`);
load(`${base}/reason-engine/v0.1/shared/fact-builder.js`);
load(`${base}/reason-engine/v0.1/engine.js`);
load(`${base}/composite-reason-engine/v0.1/analyze-modes.js`);
load(`${base}/composite-reason-engine/v0.1/shared/helpers.js`);
load(`${base}/composite-reason-engine/v0.1/shared/fact-builder.js`);
load(`${base}/composite-reason-engine/v0.1/severity-resolver.js`);
load(`${base}/composite-reason-engine/v0.1/reason-key-resolver.js`);
load(`${base}/composite-reason-engine/v0.1/summary-builder.js`);
load(`${base}/composite-reason-engine/v0.1/engine.js`);

[
  "rule018-attack-behind-strategy.js",
  "rule012-attack-left-dominance.js",
  "rule014-attack-central-attack.js",
  "rule004-build-up-hold-and-advance.js",
  "rule002-defense-high-press.js",
  "rule016-defense-middle-block.js",
  "rule008-transition-immediate-recovery.js",
  "rule009-transition-retreat.js",
].forEach((file) => {
  load(`${base}/state-engine/v0.1/rules/${file}`);
});

[
  "reason018-attack-behind-strategy.js",
  "reason012-attack-left-dominance.js",
  "reason014-attack-central-attack.js",
  "reason004-build-up-hold-and-advance.js",
  "reason002-defense-high-press.js",
  "reason016-defense-middle-block.js",
  "reason008-transition-immediate-recovery.js",
  "reason009-transition-retreat.js",
].forEach((file) => {
  load(`${base}/reason-engine/v0.1/reasons/${file}`);
});

const attackPlan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  analyzeMode: "attack",
  categories: {
    attack: ["左優位"],
    buildUp: ["保持前進"],
  },
});

const defensePlan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  analyzeMode: "defense",
  categories: {
    defense: ["ミドルブロック"],
    transition: ["リトリート"],
  },
});

const bothPlan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  analyzeMode: "both",
  categories: {
    attack: ["左優位"],
    buildUp: ["保持前進"],
    defense: ["ミドルブロック"],
    transition: ["リトリート"],
  },
});

const attackEvents = [
  { eventName: "左侵入", time: "04:00" },
  { eventName: "左侵入", time: "04:10" },
  { eventName: "シュート", time: "04:20" },
  { eventName: "左侵入", time: "04:30" },
  { eventName: "中央侵入", time: "04:40" },
  { eventName: "右侵入", time: "04:50" },
];

const defenseEvents = [
  { eventName: "被左侵入", time: "04:00" },
  { eventName: "ボール奪取", time: "04:10" },
  { eventName: "被中央侵入", time: "04:20" },
  { eventName: "被中央侵入", time: "04:30" },
];

const bothEvents = [...attackEvents, ...defenseEvents];

const scenarios = [
  {
    name: "attack mode overall",
    plan: attackPlan,
    events: attackEvents,
    expectAnalyzeMode: "attack",
    expectCategoryKeys: ["attack", "buildUp"],
    expectCompositeReasonKey: "composite.attack.green.attack_flow_working",
    expectCategory: "attack",
    expectShortSummary: "攻撃優勢",
    expectSeverity: "green",
  },
  {
    name: "defense mode overall",
    plan: defensePlan,
    events: defenseEvents,
    expectAnalyzeMode: "defense",
    expectCategoryKeys: ["defense", "transition"],
    expectCompositeReasonKey: "composite.defense.yellow.central_penetration_allowed",
    expectCategory: "defense",
    expectShortSummary: "守備警戒",
    expectSeverity: "yellow",
  },
  {
    name: "both mode overall",
    plan: bothPlan,
    events: bothEvents,
    expectAnalyzeMode: "both",
    expectCategoryKeys: ["attack", "buildUp", "defense", "transition"],
    expectCompositeReasonKey: "composite.both.mixed.attack_working_defense_central_pressure",
    expectCategory: "both",
    expectShortSummary: "攻守拮抗",
    expectSeverity: "yellow",
  },
];

let failed = 0;

scenarios.forEach((scenario) => {
  const elapsed = 300;
  const stateResults = MO_STATE_ENGINE.evaluateLiveState({
    plan: scenario.plan,
    events: scenario.events,
    elapsed,
  });
  const reasonResults = MO_REASON_ENGINE.explainLiveState({
    plan: scenario.plan,
    stateResults,
    context: { elapsed },
  });
  const composite = MO_COMPOSITE_REASON_ENGINE.composeOverallReason({
    analyzeMode: scenario.plan.analyzeMode,
    reasonResults,
  });

  if (
    !composite?.compositeReasonKey
    || !composite?.shortSummary
    || !composite?.summary
    || !composite?.category
    || !composite?.severity
    || !Array.isArray(composite.reasonKeys)
    || !Array.isArray(composite.categories)
    || !Array.isArray(composite.facts)
  ) {
    failed += 1;
    print(`FAIL ${scenario.name}: invalid composite result`);
    return;
  }

  if (!String(composite.compositeReasonKey).startsWith("composite.")) {
    failed += 1;
    print(`FAIL ${scenario.name}: compositeReasonKey=${composite.compositeReasonKey}`);
    return;
  }

  if (composite.analyzeMode !== scenario.expectAnalyzeMode) {
    failed += 1;
    print(`FAIL ${scenario.name}: analyzeMode=${composite.analyzeMode}`);
    return;
  }

  if (scenario.expectCategory && composite.category !== scenario.expectCategory) {
    failed += 1;
    print(`FAIL ${scenario.name}: category=${composite.category}`);
    return;
  }

  if (composite.category !== composite.analyzeMode) {
    failed += 1;
    print(`FAIL ${scenario.name}: category/analyzeMode mismatch`);
    return;
  }

  if (scenario.expectShortSummary && composite.shortSummary !== scenario.expectShortSummary) {
    failed += 1;
    print(`FAIL ${scenario.name}: shortSummary=${composite.shortSummary}`);
    return;
  }

  if (scenario.expectSeverity && composite.severity !== scenario.expectSeverity) {
    failed += 1;
    print(`FAIL ${scenario.name}: severity=${composite.severity}`);
    return;
  }

  const overallWorstStatus = composite.facts.find((fact) => fact.code === "overall_worst_status")?.value;
  if (composite.severity !== overallWorstStatus) {
    failed += 1;
    print(`FAIL ${scenario.name}: severity mismatch with overall_worst_status`);
    return;
  }

  const categoryKeys = composite.categories.map((item) => item.categoryKey);
  const missingCategory = scenario.expectCategoryKeys.some((key) => !categoryKeys.includes(key));
  if (missingCategory || composite.reasonKeys.length === 0) {
    failed += 1;
    print(`FAIL ${scenario.name}: categories=${categoryKeys.join(",")}`);
    return;
  }

  if (scenario.expectCompositeReasonKey && composite.compositeReasonKey !== scenario.expectCompositeReasonKey) {
    failed += 1;
    print(`FAIL ${scenario.name}: compositeReasonKey=${composite.compositeReasonKey}`);
    return;
  }

  const reasonKeySet = new Set(reasonResults.map((item) => item.reasonKey));
  const reusedOnly = composite.reasonKeys.every((key) => reasonKeySet.has(key));
  if (!reusedOnly) {
    failed += 1;
    print(`FAIL ${scenario.name}: composite regenerated reasonKeys`);
    return;
  }

  print(`OK ${scenario.name}`);
  print(JSON.stringify(composite, null, 2));
});

process.exit(failed);
