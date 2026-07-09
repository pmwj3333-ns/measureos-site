window.MO_ATTACK_CONTROLLER_BINDINGS = (() => {
  const GAMEPAD = {
    A: 0,
    B: 1,
    X: 2,
    Y: 3,
    L1: 4,
    R1: 5,
    L2: 6,
    R2: 7,
    UP: 12,
    DOWN: 13,
    LEFT: 14,
    RIGHT: 15,
  };

  const ARROW_KEY_TO_EVENT = {
    ArrowUp: "right",
    ArrowDown: "left",
    ArrowLeft: "center",
    ArrowRight: "shot",
  };

  const KEYBOARD_TO_EVENT = {
    y: "long",
    b: "possession",
    l: "lost",
    k: "bigChance",
    h: "corner_kick",
    x: "free_kick",
    p: "penalty_kick",
  };

  const GAMEPAD_TO_EVENT = {
    [GAMEPAD.UP]: "right",
    [GAMEPAD.DOWN]: "left",
    [GAMEPAD.LEFT]: "center",
    [GAMEPAD.RIGHT]: "shot",
    [GAMEPAD.L1]: "lost",
    [GAMEPAD.L2]: "bigChance",
    [GAMEPAD.Y]: "long",
    [GAMEPAD.B]: "possession",
    [GAMEPAD.A]: "corner_kick",
    [GAMEPAD.X]: "free_kick",
    [GAMEPAD.R2]: "penalty_kick",
  };

  const EVENT_CONTROL_HINTS = {
    right: "↑",
    left: "↓",
    center: "←",
    shot: "→",
    lost: "L",
    bigChance: "L2",
    long: "Y",
    possession: "B",
    corner_kick: "A",
    free_kick: "X",
    penalty_kick: "R2",
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
    SET_PIECE_CODES,
    isSetPieceEventCode,
    getControlHintForEvent,
  };
})();
