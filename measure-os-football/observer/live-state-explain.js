(function () {
  const EXPLAIN_EVENT_LABELS = {
    左侵入: "左",
    中央侵入: "中央",
    右侵入: "右",
    クロス: "クロス",
    シュート: "シュート",
    被左侵入: "左",
    被中央侵入: "中央",
    被右侵入: "右",
    被クロス: "クロス",
    被シュート: "シュート",
    ボール奪取: "奪取",
    前線奪取: "高奪取",
    即時奪回成功: "即奪回",
    カウンター開始: "カウンター",
    カウンター被弾: "被カウンター",
  };

  const TRANSITION_EXPLAIN_SEQUENCE = {
    rule008: ["即時奪回成功", "カウンター開始", "カウンター被弾"],
    rule009: ["被中央侵入", "被シュート", "カウンター被弾", "ボール奪取", "被左侵入", "被右侵入"],
    rule010: ["カウンター開始", "即時奪回成功", "左侵入", "中央侵入", "右侵入", "シュート", "カウンター被弾"],
    rule011: ["即時奪回成功", "カウンター開始", "左侵入", "中央侵入", "右侵入", "シュート", "カウンター被弾"],
  };

  function parseMatchTime(timeValue) {
    const [minutes, seconds] = String(timeValue || "").split(":").map(Number);
    if (Number.isNaN(minutes) || Number.isNaN(seconds)) return 0;
    return Math.max(0, minutes * 60 + seconds);
  }

  function hasAnyCount(counts) {
    if (!counts || typeof counts !== "object") return false;
    return Object.values(counts).some((value) => Number(value) > 0);
  }

  function labelForEvent(eventName) {
    return EXPLAIN_EVENT_LABELS[eventName] || eventName;
  }

  function pickDominantDirection(counts, candidates) {
    let bestLabel = null;
    let bestCount = 0;

    candidates.forEach(({ eventName, label }) => {
      const count = Number(counts[eventName]) || 0;
      if (count > bestCount) {
        bestCount = count;
        bestLabel = label;
      }
    });

    return bestLabel;
  }

  function joinParts(parts, limit = 3) {
    const filtered = parts.filter(Boolean);
    if (filtered.length === 0) return "--";
    return filtered.slice(0, limit).join(" > ");
  }

  function summarizeAttackFlow(counts) {
    const direction = pickDominantDirection(counts, [
      { eventName: "左侵入", label: "左" },
      { eventName: "中央侵入", label: "中央" },
      { eventName: "右侵入", label: "右" },
    ]);

    const parts = [];
    if (direction) parts.push(direction);
    if ((counts.クロス || 0) > 0) parts.push("クロス");
    if ((counts.シュート || 0) > 0) parts.push("シュート");
    if (parts.length === 0 && (counts.カウンター被弾 || 0) > 0) parts.push("被カウンター");

    return joinParts(parts);
  }

  function summarizeDefenseFlow(counts) {
    const direction = pickDominantDirection(counts, [
      { eventName: "被左侵入", label: "左" },
      { eventName: "被中央侵入", label: "中央" },
      { eventName: "被右侵入", label: "右" },
    ]);

    const parts = [];
    if (direction) parts.push(direction);
    if ((counts.被クロス || 0) > 0) parts.push("クロス");
    if ((counts.被シュート || 0) > 0) parts.push("シュート");

    if (parts.length === 0) {
      if ((counts.前線奪取 || 0) > 0) parts.push("高奪取");
      if ((counts.ボール奪取 || 0) > 0) parts.push("奪取");
      return joinParts(parts);
    }

    if ((counts.前線奪取 || 0) > 0 && parts.length < 3) parts.push("高奪取");
    else if ((counts.ボール奪取 || 0) > 0 && parts.length < 3) parts.push("奪取");

    return joinParts(parts);
  }

  function summarizeBuildUpFlow(counts, planOption) {
    const left = (counts.左侵入 || 0) + (counts.被左侵入 || 0);
    const right = (counts.右侵入 || 0) + (counts.被右侵入 || 0);
    const central = (counts.中央侵入 || 0) + (counts.被中央侵入 || 0);
    const parts = [];

    const dominant = Math.max(left, right, central);
    if (dominant > 0) {
      if (left >= right && left >= central) parts.push("左");
      else if (right >= left && right >= central) parts.push("右");
      else parts.push("中央");
    }

    if (planOption) parts.push(planOption);
    if ((counts.即時奪回成功 || 0) > 0 && parts.length < 3) parts.push("即奪回");

    return joinParts(parts) !== "--" ? joinParts(parts) : (planOption || "--");
  }

  function summarizeTransitionFlow(counts, planOption, ruleId) {
    const sequence = TRANSITION_EXPLAIN_SEQUENCE[ruleId] || [
      "前線奪取",
      "即時奪回成功",
      "カウンター開始",
      "カウンター被弾",
    ];
    const parts = [];

    sequence.forEach((eventName) => {
      if ((counts[eventName] || 0) > 0) {
        parts.push(labelForEvent(eventName));
      }
    });

    if (parts.length === 0) return planOption || "--";
    return joinParts(parts);
  }

  function summarizeByCategory(categoryKey, ruleId, counts, planOption) {
    switch (categoryKey) {
      case "attack":
        return summarizeAttackFlow(counts);
      case "defense":
        return summarizeDefenseFlow(counts);
      case "buildUp":
        return summarizeBuildUpFlow(counts, planOption);
      case "transition":
        return summarizeTransitionFlow(counts, planOption, ruleId);
      default:
        return planOption || "--";
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

    const planOption = liveState.planOption || null;
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
      return planOption || "--";
    }

    return summarizeByCategory(categoryKey, ruleId, counts, planOption);
  }

  window.MO_LIVE_STATE_EXPLAIN = {
    buildLiveStateExplainLine,
    pickPrimaryLiveStateItem,
  };
})();
