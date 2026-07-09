window.MO_ATTACK_CONTROLLER_BINDINGS = (() => {
  const GAMEPAD = {
    LEFT: 14,
    UP: 12,
    RIGHT: 15,
    DOWN: 13,
    B: 1,
    A: 0,
    X: 2,
    L1: 4,
    R1: 5,
    L2: 6,
    R2: 7,
  };

  const ARROW_KEY_TO_EVENT = {
    ArrowLeft: "shot",
    ArrowUp: "right",
    ArrowRight: "center",
    ArrowDown: "left",
  };

  const KEYBOARD_TO_EVENT = {
    u: "possession",
    o: "long",
    b: "bigChance",
    l: "lost",
    h: "corner_kick",
    x: "free_kick",
    p: "penalty_kick",
  };

  const GAMEPAD_TO_EVENT = {
    [GAMEPAD.LEFT]: "shot",
    [GAMEPAD.UP]: "right",
    [GAMEPAD.RIGHT]: "center",
    [GAMEPAD.DOWN]: "left",
    [GAMEPAD.B]: "bigChance",
    [GAMEPAD.L1]: "lost",
    [GAMEPAD.R1]: "possession",
    [GAMEPAD.L2]: "long",
    [GAMEPAD.A]: "corner_kick",
    [GAMEPAD.X]: "free_kick",
    [GAMEPAD.R2]: "penalty_kick",
  };

  const EVENT_CONTROL_HINTS = {
    shot: "←",
    right: "↑",
    center: "→",
    left: "↓",
    lost: "L",
    bigChance: "B",
    possession: "R1",
    long: "L2",
    corner_kick: "A",
    free_kick: "X",
    penalty_kick: "R2",
  };

  const GUIDE_ROWS = [
    {
      group: "十字キー",
      items: [
        { control: "←", eventCode: "shot", label: "シュート" },
        { control: "↑", eventCode: "right", label: "右" },
        { control: "→", eventCode: "center", label: "中央" },
        { control: "↓", eventCode: "left", label: "左" },
      ],
    },
    {
      group: "Build Up",
      items: [
        { control: "R1", eventCode: "possession", label: "保持前進" },
        { control: "L2", eventCode: "long", label: "ロング前進" },
      ],
    },
    {
      group: "Finish",
      items: [
        { control: "L", eventCode: "lost", label: "ロスト" },
        { control: "B", eventCode: "bigChance", label: "決定機" },
      ],
    },
    {
      group: "Set Piece",
      items: [
        { control: "A", eventCode: "corner_kick", label: "コーナーキック" },
        { control: "X", eventCode: "free_kick", label: "フリーキック" },
        { control: "R2", eventCode: "penalty_kick", label: "PK" },
      ],
    },
  ];

  const EVENT_LABELS = {
    left: "左",
    center: "中央",
    right: "右",
    possession: "保持前進",
    long: "ロング前進",
    shot: "シュート",
    bigChance: "決定機",
    lost: "ロスト",
    corner_kick: "コーナーキック",
    free_kick: "フリーキック",
    penalty_kick: "PK",
  };

  const SET_PIECE_CODES = new Set(["corner_kick", "free_kick", "penalty_kick"]);

  function isSetPieceEventCode(eventCode) {
    return SET_PIECE_CODES.has(eventCode);
  }

  function getControlHintForEvent(eventCode) {
    return EVENT_CONTROL_HINTS[eventCode] || "";
  }

  return {
    GAMEPAD,
    ARROW_KEY_TO_EVENT,
    KEYBOARD_TO_EVENT,
    GAMEPAD_TO_EVENT,
    EVENT_CONTROL_HINTS,
    GUIDE_ROWS,
    EVENT_LABELS,
    SET_PIECE_CODES,
    isSetPieceEventCode,
    getControlHintForEvent,
  };
})();
