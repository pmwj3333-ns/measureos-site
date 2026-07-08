/* global load, MO_STATE_ENGINE, MO_REASON_ENGINE, MO_PLAN_SNAPSHOT */

const base = "/Users/niiyasyogo/Desktop/measureos-site/measure-os-football";

load(`${base}/shared/plan-snapshot.js`);
load(`${base}/shared/attack-plan.js`);
load(`${base}/shared/attack-observer.js`);
load(`${base}/shared/defense-plan.js`);
load(`${base}/state-engine/v0.1/engine.js`);
load(`${base}/reason-engine/v0.1/shared/event-vocabulary.js`);
load(`${base}/reason-engine/v0.1/shared/fact-builder.js`);
load(`${base}/reason-engine/v0.1/engine.js`);

[
  "rule018-attack-behind-strategy.js",
  "rule012-attack-left-dominance.js",
  "rule013-attack-right-dominance.js",
  "rule014-attack-central-attack.js",
  "rule004-build-up-hold-and-advance.js",
  "rule005-build-up-long-advance.js",
  "rule002-defense-high-press.js",
  "rule016-defense-middle-block.js",
  "rule003-defense-low-block.js",
  "rule008-transition-immediate-recovery.js",
  "rule009-transition-retreat.js",
].forEach((file) => {
  load(`${base}/state-engine/v0.1/rules/${file}`);
});

[
  "reason018-attack-behind-strategy.js",
  "reason012-attack-left-dominance.js",
  "reason013-attack-right-dominance.js",
  "reason014-attack-central-attack.js",
  "reason004-build-up-hold-and-advance.js",
  "reason005-build-up-long-advance.js",
  "reason002-defense-high-press.js",
  "reason016-defense-middle-block.js",
  "reason003-defense-low-block.js",
  "reason008-transition-immediate-recovery.js",
  "reason009-transition-retreat.js",
].forEach((file) => {
  load(`${base}/reason-engine/v0.1/reasons/${file}`);
});

const plan = MO_PLAN_SNAPSHOT.normalizePlanSnapshot({
  version: "0.1",
  confirmed: true,
  categories: {
    attack: ["背後攻略", "左優位", "右優位", "中央攻略"],
    defense: ["ハイプレス", "ミドルブロック", "ローブロック"],
    buildUp: ["保持前進", "ロング前進"],
    transition: ["即時奪回", "リトリート"],
  },
});

const scenarios = [
  {
    name: "rule018 green",
    events: [
      { eventName: "behind", time: "04:00" },
      { eventName: "behind", time: "04:10" },
      { eventName: "shot", time: "04:20" },
    ],
    expectRuleId: "rule018",
    expectStatus: "green",
  },
  {
    name: "rule018 yellow no activity",
    events: [{ eventName: "behind", time: "00:10" }],
    elapsed: 20,
    expectRuleId: "rule018",
    expectStatus: "yellow",
    expectReasonKey: "rule018.yellow.no_finish_yet",
  },
  {
    name: "rule012 green",
    events: [
      { eventName: "左侵入", time: "04:00" },
      { eventName: "左侵入", time: "04:10" },
      { eventName: "シュート", time: "04:20" },
    ],
    expectRuleId: "rule012",
    expectStatus: "green",
  },
  {
    name: "rule013 green",
    events: [
      { eventName: "右侵入", time: "04:00" },
      { eventName: "右侵入", time: "04:10" },
      { eventName: "シュート", time: "04:20" },
    ],
    expectRuleId: "rule013",
    expectStatus: "green",
    expectReasonKey: "rule013.green.right_to_finish",
  },
  {
    name: "rule014 green",
    events: [
      { eventName: "中央侵入", time: "04:00" },
      { eventName: "中央侵入", time: "04:10" },
      { eventName: "シュート", time: "04:20" },
    ],
    expectRuleId: "rule014",
    expectStatus: "green",
    expectReasonKey: "rule014.green.central_to_finish",
  },
  {
    name: "rule004 green",
    events: [
      { eventName: "左侵入", time: "04:00" },
      { eventName: "中央侵入", time: "04:10" },
      { eventName: "右侵入", time: "04:20" },
    ],
    expectRuleId: "rule004",
    expectStatus: "green",
    expectReasonKey: "rule004.green.build_up_progressing",
  },
  {
    name: "rule005 green",
    events: [
      { eventName: "中央侵入", time: "04:00" },
      { eventName: "右侵入", time: "04:10" },
    ],
    expectRuleId: "rule005",
    expectStatus: "green",
    expectReasonKey: "rule005.green.long_build_up_progressing",
  },
  {
    name: "rule016 green",
    events: [
      { eventName: "被左侵入", time: "04:00" },
      { eventName: "ボール奪取", time: "04:10" },
    ],
    expectRuleId: "rule016",
    expectStatus: "green",
    expectReasonKey: "rule016.green.middle_block_working",
  },
  {
    name: "rule003 green",
    events: [
      { eventName: "被中央侵入", time: "04:00" },
    ],
    expectRuleId: "rule003",
    expectStatus: "green",
    expectReasonKey: "rule003.green.low_block_working",
  },
  {
    name: "rule008 green",
    events: [
      { eventName: "即時奪回成功", time: "04:00" },
      { eventName: "即時奪回成功", time: "04:10" },
    ],
    expectRuleId: "rule008",
    expectStatus: "green",
    expectReasonKey: "rule008.green.immediate_recovery_working",
  },
  {
    name: "rule009 green",
    events: [
      { eventName: "被中央侵入", time: "04:00" },
      { eventName: "ボール奪取", time: "04:10" },
    ],
    expectRuleId: "rule009",
    expectStatus: "green",
    expectReasonKey: "rule009.green.retreat_working",
  },
  {
    name: "rule009 yellow",
    events: [
      { eventName: "被中央侵入", time: "04:00" },
      { eventName: "被中央侵入", time: "04:10" },
    ],
    expectRuleId: "rule009",
    expectStatus: "yellow",
    expectReasonKey: "rule009.yellow.retreat_in_progress",
  },
  {
    name: "rule009 orange counter",
    events: [
      { eventName: "カウンター被弾", time: "04:00" },
    ],
    expectRuleId: "rule009",
    expectStatus: "orange",
    expectReasonKey: "rule009.orange.counter_pressure",
  },
  {
    name: "rule002 green",
    events: [
      { eventName: "前線奪取", time: "04:00" },
      { eventName: "前線奪取", time: "04:10" },
    ],
    expectRuleId: "rule002",
    expectStatus: "green",
    expectReasonKey: "rule002.green.press_working",
  },
];

let failed = 0;

scenarios.forEach((scenario) => {
  const elapsed = scenario.elapsed ?? 300;
  const states = MO_STATE_ENGINE.evaluateLiveState({
    plan,
    events: scenario.events,
    elapsed,
  });
  const state = states.find((item) => item.ruleId === scenario.expectRuleId);
  if (!state || state.status !== scenario.expectStatus) {
    failed += 1;
    print(`FAIL ${scenario.name}: state=${state?.status || "missing"}`);
    return;
  }

  const reason = MO_REASON_ENGINE.explainState({ plan, state, context: { elapsed } });
  if (!reason?.summary || !reason.reasonKey || !Array.isArray(reason.facts)) {
    failed += 1;
    print(`FAIL ${scenario.name}: invalid reason result`);
    return;
  }

  if (scenario.expectReasonKey && reason.reasonKey !== scenario.expectReasonKey) {
    failed += 1;
    print(`FAIL ${scenario.name}: reasonKey=${reason.reasonKey}`);
    return;
  }

  print(`OK ${scenario.name}`);
  print(JSON.stringify({
    ruleId: reason.ruleId,
    status: reason.status,
    reasonKey: reason.reasonKey,
    facts: reason.facts,
    summary: reason.summary,
  }, null, 2));
});

const allReasons = MO_REASON_ENGINE.explainLiveState({
  plan,
  stateResults: MO_STATE_ENGINE.evaluateLiveState({
    plan,
    events: scenarios[0].events,
    elapsed: 300,
  }),
  context: { elapsed: 300 },
});

print(`explainLiveState count: ${allReasons.length}`);
process.exit(failed);
