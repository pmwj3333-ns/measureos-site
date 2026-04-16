/**
 * Article 7 phase 1: due date (YYYY-MM-DD) -> display-only priority tier.
 * Uses local calendar days until due (no business-day logic).
 */
(function (global) {
  "use strict";

  function utcMidnightFromYmd(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "").trim());
    if (!m) return null;
    var y = Number(m[1]);
    var mo = Number(m[2]);
    var d = Number(m[3]);
    if (!y || !mo || !d) return null;
    return Date.UTC(y, mo - 1, d);
  }

  function utcMidnightToday(ref) {
    var x = ref instanceof Date ? ref : new Date(ref);
    return Date.UTC(x.getFullYear(), x.getMonth(), x.getDate());
  }

  /**
   * @param {string} dueDateIso YYYY-MM-DD
   * @param {Date} [refDate]
   * @returns {{ tier: string, emoji: string, label: string, daysUntil: number }|null}
   */
  function priorityTierFromDueDate(dueDateIso, refDate) {
    var due = utcMidnightFromYmd(dueDateIso);
    var day0 = utcMidnightToday(refDate || new Date());
    if (due === null) return null;
    var daysUntil = Math.round((due - day0) / 86400000);
    var tier;
    var emoji;
    var label;
    if (daysUntil < 0 || daysUntil <= 1) {
      tier = "high";
      emoji = "\uD83D\uDD34";
      label = "\u9AD8";
    } else if (daysUntil <= 3) {
      tier = "mid";
      emoji = "\uD83D\uDFE1";
      label = "\u4E2D";
    } else {
      tier = "low";
      emoji = "\uD83D\uDD35";
      label = "\u4F4E";
    }
    return { tier: tier, emoji: emoji, label: label, daysUntil: daysUntil };
  }

  global.priorityTierFromDueDate = priorityTierFromDueDate;
})(
  typeof globalThis !== "undefined"
    ? globalThis
    : typeof window !== "undefined"
      ? window
      : this
);
