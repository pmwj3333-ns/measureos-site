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

  const DIRECTION_PAD = {
    up: { control: "↑", eventCode: "right", label: "右" },
    down: { control: "↓", eventCode: "left", label: "左" },
    left: { control: "←", eventCode: "center", label: "中央" },
    right: { control: "→", eventCode: "shot", label: "シュート" },
  };

  const SHOULDER_LEFT = [
    { control: "L", eventCode: "lost", label: "ロスト" },
    { control: "L2", eventCode: "bigChance", label: "決定機" },
  ];

  const SHOULDER_RIGHT = [
    { control: "Y", eventCode: "long", label: "ロング前進" },
    { control: "B", eventCode: "possession", label: "保持前進" },
  ];

  const SET_PIECE = [
    { control: "A", eventCode: "corner_kick", label: "コーナーキック" },
    { control: "X", eventCode: "free_kick", label: "フリーキック" },
    { control: "R2", eventCode: "penalty_kick", label: "PK" },
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

  function renderShoulderList(items) {
    return items.map((item) => `
      <li class="controller-guide-shoulder-item">
        <span class="controller-guide-control">${item.control}</span>
        <span class="controller-guide-arrow" aria-hidden="true">→</span>
        <span class="controller-guide-label">${item.label}</span>
      </li>
    `).join("");
  }

  function renderGuideMarkup() {
    const pad = DIRECTION_PAD;
    return `
      <div class="controller-guide-layout">
        <section class="controller-guide-body" aria-label="コントローラー（横持ち）">
          <div class="controller-guide-shoulder controller-guide-shoulder--left">
            <h3 class="controller-guide-shoulder-title">左側</h3>
            <ul class="controller-guide-shoulder-list">${renderShoulderList(SHOULDER_LEFT)}</ul>
          </div>

          <div class="controller-guide-center">
            <div class="controller-guide-dpad" aria-label="十字キー">
              <div class="controller-guide-dpad-cell controller-guide-dpad-cell--up">
                <span class="controller-guide-control">${pad.up.control}</span>
                <span class="controller-guide-label">${pad.up.label}</span>
              </div>
              <div class="controller-guide-dpad-cell controller-guide-dpad-cell--left">
                <span class="controller-guide-control">${pad.left.control}</span>
                <span class="controller-guide-label">${pad.left.label}</span>
              </div>
              <div class="controller-guide-dpad-cell controller-guide-dpad-cell--right">
                <span class="controller-guide-control">${pad.right.control}</span>
                <span class="controller-guide-label">${pad.right.label}</span>
              </div>
              <div class="controller-guide-dpad-cell controller-guide-dpad-cell--down">
                <span class="controller-guide-control">${pad.down.control}</span>
                <span class="controller-guide-label">${pad.down.label}</span>
              </div>
            </div>
          </div>

          <div class="controller-guide-shoulder controller-guide-shoulder--right">
            <h3 class="controller-guide-shoulder-title">右側</h3>
            <ul class="controller-guide-shoulder-list">${renderShoulderList(SHOULDER_RIGHT)}</ul>
          </div>
        </section>

        <section class="controller-guide-set-piece" aria-label="セットプレー">
          <h3 class="controller-guide-group-title">Set Piece</h3>
          <ul class="controller-guide-set-piece-list">
            ${SET_PIECE.map((item) => `
              <li class="controller-guide-set-piece-item">
                <span class="controller-guide-control">${item.control}</span>
                <span class="controller-guide-arrow" aria-hidden="true">→</span>
                <span class="controller-guide-label">${item.label}</span>
              </li>
            `).join("")}
          </ul>
        </section>
      </div>
    `;
  }

  return {
    GAMEPAD,
    ARROW_KEY_TO_EVENT,
    KEYBOARD_TO_EVENT,
    GAMEPAD_TO_EVENT,
    EVENT_CONTROL_HINTS,
    DIRECTION_PAD,
    SHOULDER_LEFT,
    SHOULDER_RIGHT,
    SET_PIECE,
    EVENT_LABELS,
    SET_PIECE_CODES,
    isSetPieceEventCode,
    getControlHintForEvent,
    renderGuideMarkup,
  };
})();
