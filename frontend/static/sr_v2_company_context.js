/** sr_v2: company_id URL / localStorage 同期（テスト可能な純粋ヘルパー） */
(function (root) {
  const LS_LAST_COMPANY = "sr_v2_last_company";
  const LS_KEYS_TO_CLEAR = [LS_LAST_COMPANY, "company_id", "observe_company_id"];

  function buildHrefWithCompany(baseHref, companyId) {
    const u = new URL(String(baseHref || "/sr/v2"), "http://local");
    const c = String(companyId || "").trim();
    if (c) {
      u.searchParams.set("company", c);
    } else {
      u.searchParams.delete("company");
      u.searchParams.delete("company_id");
    }
    return u.pathname + u.search + u.hash;
  }

  function readCompanyFromSearch(search) {
    const q = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    return (q.get("company") || q.get("company_id") || "").trim();
  }

  function formatCompanySearchLabel(companyId, companyName) {
    const id = String(companyId || "").trim();
    const nm = String(companyName || "").trim();
    if (!id) return "";
    return nm ? id + "｜" + nm : id;
  }

  /** active company のみ。company_id / company_name 部分一致。 */
  function filterActiveCompaniesForSearch(companies, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return [];
    return (companies || [])
      .filter(function (r) {
        return r && r.is_active !== false;
      })
      .map(function (r) {
        return {
          company_id: String(r.company_id || "").trim(),
          company_name: String(r.company_name || "").trim(),
        };
      })
      .filter(function (r) {
        return r.company_id;
      })
      .filter(function (r) {
        const id = r.company_id.toLowerCase();
        const name = r.company_name.toLowerCase();
        return id.indexOf(q) >= 0 || name.indexOf(q) >= 0;
      })
      .sort(function (a, b) {
        return a.company_id.localeCompare(b.company_id, "ja");
      });
  }

  root.SrV2CompanyContext = {
    LS_LAST_COMPANY,
    LS_KEYS_TO_CLEAR,
    buildHrefWithCompany,
    readCompanyFromSearch,
    formatCompanySearchLabel,
    filterActiveCompaniesForSearch,
  };
})(typeof globalThis !== "undefined" ? globalThis : globalThis);
