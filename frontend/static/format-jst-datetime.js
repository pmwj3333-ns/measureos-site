/**
 * API の ISO 8601 時刻（UTC 想定: Z 付き or naive UTC）を JST で「YYYY/M/D HH:mm:ss」表示に揃える。
 * office_v2 / debug_v2 / field_v2 共通。保存・API は変更しない（表示のみ）。
 */
(function (global) {
  var jstFormatter = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  function parseApiUtc(iso) {
    if (iso == null || String(iso).trim() === "") return null;
    var s = String(iso).trim();
    if (s.endsWith("Z") || s.endsWith("z")) return new Date(s);
    if (/[+-]\d{2}:\d{2}$/.test(s) || /[+-]\d{2}:\d{2}:\d{2}$/.test(s)) return new Date(s);
    return new Date(s + "Z");
  }

  /**
   * @param {string|null|undefined} datetimeStr
   * @returns {string}
   */
  function formatJST(datetimeStr) {
    if (datetimeStr == null || datetimeStr === undefined) return "—";
    var raw = String(datetimeStr).trim();
    if (raw === "") return "—";
    if (raw === "—" || raw === "-") return raw;
    var d = parseApiUtc(raw);
    if (d === null || Number.isNaN(d.getTime())) return "—";
    return jstFormatter.format(d);
  }

  /** ブラウザの現在瞬間を同じ JST 表記で（debug の「最終更新」など） */
  function formatNowJST() {
    return jstFormatter.format(new Date());
  }

  global.parseApiUtc = parseApiUtc;
  global.formatJST = formatJST;
  global.formatNowJST = formatNowJST;
})(typeof window !== "undefined" ? window : globalThis);
