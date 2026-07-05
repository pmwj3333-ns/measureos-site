window.MO_OBSERVATION_CATEGORIES = [
  {
    label: "攻撃",
    events: ["左侵入", "中央侵入", "右侵入", "クロス", "シュート"],
  },
  {
    label: "守備",
    events: [
      "被左侵入",
      "被中央侵入",
      "被右侵入",
      "被クロス",
      "被シュート",
      "ボール奪取",
      "前線奪取",
    ],
  },
  {
    label: "トランジション",
    events: ["即時奪回成功", "カウンター開始", "カウンター被弾"],
  },
  {
    label: "セットプレー",
    layout: "team-split",
    events: ["CK", "FK", "PK", "決定機"],
  },
];
