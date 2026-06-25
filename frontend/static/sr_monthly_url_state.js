/** sr_monthly: target_month URL / localStorage 同期（テスト可能な純粋ヘルパー） */
(function (root) {
  const LS_TARGET_MONTH = "monthly_target_month";
  const MONTH_RE = /^\d{4}-\d{2}$/;

  function isValidTargetMonth(raw) {
    const s = String(raw || "").trim();
    if (!MONTH_RE.test(s)) return "";
    const m = parseInt(s.slice(5, 7), 10);
    if (m < 1 || m > 12) return "";
    return s;
  }

  function defaultTargetMonth(now) {
    const d = now instanceof Date ? now : new Date();
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, "0");
    return y + "-" + mo;
  }

  function readTargetMonthFromSearch(search) {
    const q = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    return isValidTargetMonth(q.get("target_month") || q.get("month") || "");
  }

  function readStoredTargetMonth(storage) {
    try {
      if (!storage) return "";
      return isValidTargetMonth(storage.getItem(LS_TARGET_MONTH));
    } catch (_) {
      return "";
    }
  }

  function resolveTargetMonth(search, storage, now) {
    return (
      readTargetMonthFromSearch(search) ||
      readStoredTargetMonth(storage) ||
      defaultTargetMonth(now)
    );
  }

  function buildHrefWithTargetMonth(baseHref, targetMonth) {
    const u = new URL(String(baseHref || "/sr/monthly"), "http://local");
    const m = isValidTargetMonth(targetMonth);
    if (m) u.searchParams.set("target_month", m);
    else u.searchParams.delete("target_month");
    return u.pathname + u.search + u.hash;
  }

  function buildPageHref(baseHref, companyId, targetMonth) {
    const u = new URL(String(baseHref || "/sr/monthly"), "http://local");
    const c = String(companyId || "").trim();
    if (c) {
      u.searchParams.set("company", c);
      u.searchParams.delete("company_id");
    }
    const m = isValidTargetMonth(targetMonth);
    if (m) u.searchParams.set("target_month", m);
    else u.searchParams.delete("target_month");
    return u.pathname + u.search + u.hash;
  }

  root.MonthlyReportUrlState = {
    LS_TARGET_MONTH,
    isValidTargetMonth,
    defaultTargetMonth,
    readTargetMonthFromSearch,
    readStoredTargetMonth,
    resolveTargetMonth,
    buildHrefWithTargetMonth,
    buildPageHref,
  };
})(typeof globalThis !== "undefined" ? globalThis : globalThis);
