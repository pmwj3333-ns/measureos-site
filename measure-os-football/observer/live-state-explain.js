(function () {
  const FLOW_SEPARATOR = " → ";

  const ATTACK_DIRECTION_EVENTS = ["左侵入", "中央侵入", "右侵入"];
  const ATTACK_FLOW_TAIL = ["クロス", "シュート"];

  const DEFENSE_DIRECTION_EVENTS = ["被左侵入", "被中央侵入", "被右侵入"];
  const DEFENSE_FLOW_TAIL = ["被クロス", "被シュート"];
  const DEFENSE_RECOVERY_EVENTS = [
    { eventName: "前線奪取", label: "高奪取" },
    { eventName: "ボール奪取", label: "奪取" },
  ];

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function hasAnyCount(counts) {
    if (!counts || typeof counts !== "object") return false;
    return Object.values(counts).some((value) => Number(value) > 0);
  }

  function joinFlowParts(parts, limit = 3) {
    const filtered = parts.filter(Boolean);
    if (filtered.length === 0) return "--";
    return filtered.slice(0, limit).join(FLOW_SEPARATOR);
  }

  function pickDominantEventName(counts, eventNames) {
    let bestEvent = null;
    let bestCount = 0;

    eventNames.forEach((eventName) => {
      const count = Number(counts[eventName]) || 0;
      if (count > bestCount) {
        bestCount = count;
        bestEvent = eventName;
      }
    });

    return bestCount > 0 ? bestEvent : null;
  }

  function appendExistingEvents(parts, counts, eventNames) {
    eventNames.forEach((eventName) => {
      if ((Number(counts[eventName]) || 0) > 0) {
        parts.push(eventName);
      }
    });
    return parts;
  }

  function summarizeAttackFlow(counts) {
    const parts = [];
    const direction = pickDominantEventName(counts, ATTACK_DIRECTION_EVENTS);
    if (direction) parts.push(direction);
    appendExistingEvents(parts, counts, ATTACK_FLOW_TAIL);
    return joinFlowParts(parts);
  }

  function summarizeDefenseFlow(counts) {
    const parts = [];
    const direction = pickDominantEventName(counts, DEFENSE_DIRECTION_EVENTS);
    if (direction) parts.push(direction);
    appendExistingEvents(parts, counts, DEFENSE_FLOW_TAIL);

    if (parts.length > 0) {
      return joinFlowParts(parts);
    }

    const recoveryParts = [];
    DEFENSE_RECOVERY_EVENTS.forEach(({ eventName, label }) => {
      if ((Number(counts[eventName]) || 0) > 0) {
        recoveryParts.push(label);
      }
    });

    return joinFlowParts(recoveryParts);
  }

  function summarizeBuildUpFlow(counts) {
    const advance = {
      left: Number(counts.左侵入) || 0,
      central: Number(counts.中央侵入) || 0,
      right: Number(counts.右侵入) || 0,
    };
    const conceded = {
      left: Number(counts.被左侵入) || 0,
      central: Number(counts.被中央侵入) || 0,
      right: Number(counts.被右侵入) || 0,
    };
    const totalAdvance = advance.left + advance.central + advance.right;
    const totalConceded = conceded.left + conceded.central + conceded.right;
    const quickRecovery = Number(counts.即時奪回成功) || 0;
    const counterConceded = Number(counts.カウンター被弾) || 0;

    let holdPart = null;
    let outcomePart = null;

    if (counterConceded > 0 && counterConceded >= totalAdvance) {
      holdPart = "後方保持";
      outcomePart = "停滞";
      return joinFlowParts([holdPart, outcomePart]);
    }

    if (totalAdvance > 0 && totalConceded > totalAdvance) {
      holdPart = "後方保持";
      outcomePart = "展開";
      return joinFlowParts([holdPart, outcomePart]);
    }

    if (totalAdvance > 0) {
      if (advance.left >= advance.central && advance.left >= advance.right) {
        holdPart = "左保持";
      } else if (advance.right >= advance.left && advance.right >= advance.central) {
        holdPart = "右保持";
      } else {
        holdPart = "中央保持";
      }
    } else if (totalConceded > 0) {
      holdPart = "後方保持";
      outcomePart = "停滞";
      return joinFlowParts([holdPart, outcomePart]);
    } else if (quickRecovery > 0) {
      holdPart = "奪回後";
      outcomePart = "前進";
      return joinFlowParts([holdPart, outcomePart]);
    }

    if (holdPart === "中央保持" && totalAdvance > totalConceded) {
      outcomePart = totalConceded === 0 && advance.central >= advance.left && advance.central >= advance.right
        ? "ロング"
        : "前進";
    } else if (totalAdvance > totalConceded) {
      outcomePart = "前進";
    } else if (holdPart === "右保持" && totalAdvance <= totalConceded + 1) {
      outcomePart = "保持";
    } else if (totalAdvance > 0) {
      outcomePart = totalConceded >= totalAdvance ? "保持" : "前進";
    }

    return joinFlowParts([holdPart, outcomePart]);
  }

  function summarizeTransitionFlow(counts, ruleId) {
    const recovery = Number(counts.即時奪回成功) || 0;
    const counterStarted = Number(counts.カウンター開始) || 0;
    const counterConceded = Number(counts.カウンター被弾) || 0;
    const forward = (Number(counts.左侵入) || 0)
      + (Number(counts.中央侵入) || 0)
      + (Number(counts.右侵入) || 0);
    const shot = Number(counts.シュート) || 0;
    const centralConceded = Number(counts.被中央侵入) || 0;
    const shotConceded = Number(counts.被シュート) || 0;
    const ballWon = Number(counts.ボール奪取) || 0;

    if (counterConceded >= 1) {
      return "被カウンター注意";
    }

    switch (ruleId) {
      case "rule008":
        if (recovery >= 2 && recovery > counterStarted) return "即奪回優勢";
        if (recovery >= 1 && recovery >= counterStarted) return "即奪回優勢";
        if (counterStarted >= 2) return "カウンター多発";
        if (counterStarted >= 1) return "カウンター多発";
        return "切り替えは落ち着いている";

      case "rule009":
        if (shotConceded >= 1) return joinFlowParts(["中央突破", "被シュート"]);
        if (centralConceded >= 2) return "中央突破を許している";
        if (ballWon >= 1 && centralConceded <= 1) return "守備ブロックを整備";
        if (centralConceded >= 1) return "中央突破を許している";
        return "守備再構築が機能";

      case "rule010":
        if (counterStarted >= 1 && (forward >= 1 || shot >= 1)) return "縦に速い攻撃";
        if (counterStarted >= 1) return "カウンター多発";
        if (forward >= 1 || shot >= 1) return "縦に速い攻撃";
        if (recovery >= 1) return "奪回後の縦攻撃";
        return "縦攻撃が滞っている";

      case "rule011":
        if (recovery >= 1 && counterConceded === 0) return "ボール保持継続";
        if (counterStarted >= 1) return "カウンター多発";
        return "保持で試合を落ち着け";

      default:
        if (recovery > counterStarted && recovery > 0) return "即奪回優勢";
        if (counterStarted > recovery && counterStarted > 0) return "カウンター多発";
        if (forward >= 1 || shot >= 1) return "縦に速い攻撃";
        return "--";
    }
  }

  function summarizeByCategory(categoryKey, ruleId, counts) {
    switch (categoryKey) {
      case "attack":
        return summarizeAttackFlow(counts);
      case "defense":
        return summarizeDefenseFlow(counts);
      case "buildUp":
        return summarizeBuildUpFlow(counts);
      case "transition":
        return summarizeTransitionFlow(counts, ruleId);
      default:
        return "--";
    }
  }

  function pickPrimaryLiveStateItem(items) {
    if (!Array.isArray(items) || items.length === 0) return null;

    const withReason = items.find(
      (item) => item?.reasonEventCounts && hasAnyCount(item.reasonEventCounts),
    );
    if (withReason) return withReason;

    const ruleSourced = items.find((item) => item?.source === "rule");
    if (ruleSourced) return ruleSourced;

    return items[0];
  }

  function buildLiveStateExplainLine(liveState, context = {}, helpers = {}) {
    if (!liveState) return "--";

    const categoryKey = liveState.planCategoryKey || null;
    const ruleId = liveState.ruleId || null;
    let counts = liveState.reasonEventCounts;

    if (!hasAnyCount(counts) && typeof helpers.getReasonEvents === "function") {
      const elapsed = Number(context.elapsed) || 0;
      const windowStart = Math.max(0, elapsed - 5 * 60);
      const reasonEvents = helpers.getReasonEvents(ruleId, context.events || []).filter((event) => {
        const eventSeconds = parseMatchTime(event.time);
        return eventSeconds >= windowStart && eventSeconds <= elapsed;
      });
      if (reasonEvents.length > 0) {
        counts = {};
        reasonEvents.forEach((event) => {
          counts[event.eventName] = (counts[event.eventName] || 0) + 1;
        });
      }
    }

    if (!hasAnyCount(counts)) {
      return "--";
    }

    return summarizeByCategory(categoryKey, ruleId, counts);
  }

  window.MO_LIVE_STATE_EXPLAIN = {
    buildLiveStateExplainLine,
    pickPrimaryLiveStateItem,
    summarizeAttackFlow,
    summarizeDefenseFlow,
    summarizeBuildUpFlow,
    summarizeTransitionFlow,
  };
})();
