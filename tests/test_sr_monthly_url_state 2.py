"""sr_monthly: target_month URL / localStorage 同期。"""

from __future__ import annotations

import re
import subprocess
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
SR_MONTHLY_HTML = ROOT / "frontend" / "sr_monthly.html"
URL_STATE_JS = ROOT / "frontend" / "static" / "sr_monthly_url_state.js"

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _is_valid_target_month(raw: str) -> str:
    s = (raw or "").strip()
    if not MONTH_RE.fullmatch(s):
        return ""
    month = int(s[5:7])
    if month < 1 or month > 12:
        return ""
    return s


def _read_target_month_from_search(search: str) -> str:
    q = parse_qs((search or "").lstrip("?"), keep_blank_values=False)
    for key in ("target_month", "month"):
        vals = q.get(key) or []
        if vals:
            valid = _is_valid_target_month(vals[0])
            if valid:
                return valid
    return ""


def _resolve_target_month(search: str, stored: str, default: str) -> str:
    return (
        _read_target_month_from_search(search)
        or _is_valid_target_month(stored)
        or _is_valid_target_month(default)
    )


def _build_page_href(base_href: str, company_id: str, target_month: str) -> str:
    u = urlparse(base_href or "/sr/monthly")
    q = parse_qs(u.query, keep_blank_values=False)
    c = (company_id or "").strip()
    if c:
        q["company"] = [c]
        q.pop("company_id", None)
    m = _is_valid_target_month(target_month)
    if m:
        q["target_month"] = [m]
    else:
        q.pop("target_month", None)
    query = "&".join(f"{k}={v[0]}" for k, v in sorted(q.items()))
    return u.path + (f"?{query}" if query else "")


def test_sr_monthly_page_includes_url_state_helpers():
    html = _read(SR_MONTHLY_HTML)
    assert "/static/sr_monthly_url_state.js" in html
    assert "resolveInitialTargetMonth" in html
    assert "setTargetMonth" in html
    assert "updatePageQuery" in html
    assert "history.replaceState" in html
    assert 'addEventListener("change"' in html
    assert "resolveInitialTargetMonth()" in html
    assert '$("target-month").value = defaultMonth()' not in html


def test_sr_monthly_init_does_not_force_current_month():
    html = _read(SR_MONTHLY_HTML)
    tail = html[html.index('addEventListener("change"') :]
    assert 'value = defaultMonth()' not in tail
    assert "bootMonthlyPage()" in tail
    assert "syncUrl: false" in tail


def test_sr_monthly_init_order_restores_company_before_target_month():
    html = _read(SR_MONTHLY_HTML)
    boot = html[html.index("function bootMonthlyPage()") : html.index("bootMonthlyPage();") + len("bootMonthlyPage();")]
    assert boot.index("readUrlCompanyId()") < boot.index("setCompanyId")
    assert boot.index("setCompanyId") < boot.index("setTargetMonth")
    assert boot.index("setTargetMonth") < boot.index("aggregate()")


def test_build_page_href_preserves_company_when_company_id_empty():
    href = _build_page_href(
        "/sr/monthly?company=test7&target_month=2026-05",
        "",
        "2026-05",
    )
    q = parse_qs(urlparse(href).query)
    assert q.get("company") == ["test7"]
    assert q.get("target_month") == ["2026-05"]


def test_monthly_url_state_priority_url_over_storage():
    resolved = _resolve_target_month(
        "?company=test7&target_month=2026-05",
        "2026-04",
        "2026-06",
    )
    assert resolved == "2026-05"


def test_monthly_url_state_falls_back_to_storage():
    resolved = _resolve_target_month(
        "?company=test7",
        "2026-04",
        "2026-06",
    )
    assert resolved == "2026-04"


def test_monthly_url_state_reload_preserves_target_month():
    href = _build_page_href(
        "/sr/monthly?company=test7&target_month=2026-05",
        "test7",
        "2026-05",
    )
    q = parse_qs(urlparse(href).query)
    assert q.get("company") == ["test7"]
    assert q.get("target_month") == ["2026-05"]
    assert _read_target_month_from_search("?company=test7&target_month=2026-05") == "2026-05"


def test_monthly_url_state_js_exports_match_python_helpers():
    script = _read(URL_STATE_JS)
    assert "monthly_target_month" in script
    assert "resolveTargetMonth" in script
    assert "buildPageHref" in script


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_monthly_url_state_js_runtime_matches_python():
    script = _read(URL_STATE_JS)
    runner = (
        script
        + """
const store = {
  _v: { monthly_target_month: "2026-04" },
  getItem(k) { return this._v[k] || null; },
};
const urlResolved = MonthlyReportUrlState.resolveTargetMonth(
  "?company=test7&target_month=2026-05",
  store,
  new Date("2026-06-15T12:00:00Z"),
);
if (urlResolved !== "2026-05") throw new Error("url priority failed");
const storageResolved = MonthlyReportUrlState.resolveTargetMonth(
  "?company=test7",
  store,
  new Date("2026-06-15T12:00:00Z"),
);
if (storageResolved !== "2026-04") throw new Error("storage fallback failed");
const preserved = MonthlyReportUrlState.buildPageHref(
  "/sr/monthly?company=test7&target_month=2026-05",
  "",
  "2026-05",
);
const u = new URL(preserved, "http://local");
if (u.searchParams.get("company") !== "test7") {
  throw new Error("company should be preserved when companyId empty");
}
console.log("ok");
"""
    )
    out = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr or out.stdout
