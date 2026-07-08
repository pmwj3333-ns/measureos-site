/* global load, MO_STATE_ENGINE, MO_REASON_ENGINE, MO_COMPOSITE_REASON_ENGINE, MO_PLAN_MATCH_ENGINE, MO_PLAN_SNAPSHOT */

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
load(`${base}/plan-match-engine/v0.1/plan-catalog.js`);
load(`${base}/plan-match-engine/v0.1/plan-match-key-resolver.js`);
load(`${base}/plan-match-engine/v0.1/score-calculator.js`);
load(`${base}/plan-match-engine/v0.1/engine.js`);

[
  "rule012-attack-left-dominance.js",
  "rule004-build-up-hold-and-advance.js",
].forEach((file) => {
  load(`${base}/state-engine/v0.1/rules/${file}`);
});

[
  "reason012-attack-left-dominance.js",
  "reason004-build-up-hold-and-advance.js",
].forEach((file) => {
  load(`${base}/reason-engine/v0.1/reasons/${file}`);
});

const plan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  analyzeMode: "attack",
  categories: {
    attack: ["左優位"],
    buildUp: ["保持前進"],
  },
});

const events = [
  { eventName: "左侵入", time: "04:00" },
  { eventName: "左侵入", time: "04:10" },
  { eventName: "シュート", time: "04:20" },
  { eventName: "左侵入", time: "04:30" },
  { eventName: "中央侵入", time: "04:40" },
  { eventName: "右侵入", time: "04:50" },
];

const elapsed = 300;
const stateResults = MO_STATE_ENGINE.evaluateLiveState({ plan, events, elapsed });
const reasonResults = MO_REASON_ENGINE.explainLiveState({ plan, stateResults, context: { elapsed } });
const compositeReason = MO_COMPOSITE_REASON_ENGINE.composeOverallReason({
  analyzeMode: plan.analyzeMode,
  reasonResults,
});
const planMatch = MO_PLAN_MATCH_ENGINE.matchPlan(compositeReason);

let failed = 0;

if (!planMatch?.planMatchKey || !planMatch.bestMatch || !Array.isArray(planMatch.matches)) {
  failed += 1;
  print("FAIL: invalid plan match result");
  process.exit(failed);
}

if (planMatch.analyzeMode !== "attack") {
  failed += 1;
  print(`FAIL: analyzeMode=${planMatch.analyzeMode}`);
}

if (planMatch.matches.some((item) => item.score < 0 || item.score > 100)) {
  failed += 1;
  print("FAIL: score out of range");
}

if (!["green", "yellow", "orange", "red"].includes(planMatch.bestMatch.severity)) {
  failed += 1;
  print(`FAIL: severity=${planMatch.bestMatch.severity}`);
}

const currentLabel = planMatch.currentPlan?.label || "";
const bestLabel = planMatch.bestMatch?.plan?.label || "";
if (!currentLabel.includes("左優位") || !bestLabel.includes("左優位")) {
  failed += 1;
  print(`FAIL: expected left-dominance alignment current=${currentLabel} best=${bestLabel}`);
}

if (!String(planMatch.planMatchKey).startsWith("planMatch.")) {
  failed += 1;
  print(`FAIL: planMatchKey=${planMatch.planMatchKey}`);
}

print("OK plan match engine");
print(JSON.stringify({
  planMatchKey: planMatch.planMatchKey,
  currentPlan: planMatch.currentPlan,
  bestMatch: planMatch.bestMatch,
  topMatches: planMatch.matches.slice(0, 3),
}, null, 2));

process.exit(failed);
