/**
 * Article 7 (office/OS): due date (YYYY-MM-DD) -> display-only priority tier.
 * today は new Date() からローカル暦で時刻を捨てた「日付のみ」（日本なら JST の暦日）。
 * 納期も YYYY-MM-DD を同じくローカル暦の日付として解釈し、暦日同士の差を diff にする（UTC ミッドナイト比較は使わない）。
 *   diff <= 1  → HIGH   (red)
 *   diff <= 3  → MEDIUM (yellow)
 *   else       → LOW    (blue)
 * Overdue rows have diff < 0, so they count as HIGH. Not machine/assignee sequencing.
 * diff は除算後に Math.floor（優先度は安全側／DST・環境差でブレにくくする）。
 */
(function (global) {
  "use strict";

  /** @returns {Date|null} その暦日のローカル 00:00（時刻は比較に使わない） */
  function localDateFromYmdString(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "").trim());
    if (!m) return null;
    var y = Number(m[1]);
    var mo = Number(m[2]);
    var d = Number(m[3]);
    if (!y || !mo || !d) return null;
    return new Date(y, mo - 1, d);
  }

  /** ref の日付だけを使い、ローカル暦でその日の 00:00 の Date を返す */
  function localCalendarStart(ref) {
    var x = ref instanceof Date ? ref : new Date(ref);
    return new Date(x.getFullYear(), x.getMonth(), x.getDate());
  }

  /**
   * @param {string} dueDateIso YYYY-MM-DD
   * @param {Date} [refDate]
   * @returns {{ tier: string, emoji: string, label: string, daysUntil: number }|null}
   */
  function priorityTierFromDueDate(dueDateIso, refDate) {
    var dueDay = localDateFromYmdString(dueDateIso);
    if (dueDay === null) return null;
    var todayDay = localCalendarStart(refDate || new Date());
    var diff = Math.floor((dueDay.getTime() - todayDay.getTime()) / 86400000);
    var tier;
    var emoji;
    var label;
    if (diff <= 1) {
      tier = "high";
      emoji = "\uD83D\uDD34";
      label = "\u9AD8";
    } else if (diff <= 3) {
      tier = "mid";
      emoji = "\uD83D\uDFE1";
      label = "\u4E2D";
    } else {
      tier = "low";
      emoji = "\uD83D\uDD35";
      label = "\u4F4E";
    }
    return { tier: tier, emoji: emoji, label: label, daysUntil: diff };
  }

  global.priorityTierFromDueDate = priorityTierFromDueDate;
})(
  typeof globalThis !== "undefined"
    ? globalThis
    : typeof window !== "undefined"
      ? window
      : this
);
