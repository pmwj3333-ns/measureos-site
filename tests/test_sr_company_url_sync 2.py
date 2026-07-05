"""sr_v2: company URL 同期（?company=）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"
CTX_JS = ROOT / "frontend" / "static" / "sr_v2_company_context.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sr_v2_has_update_company_query_helper():
    html = _read(SR_V2_HTML)
    assert "function updateCompanyQuery(companyId)" in html
    assert "history.replaceState(null, \"\", href)" in html
    assert "u.searchParams.set(\"company\", c)" in html


def test_sr_v2_load_success_syncs_url():
    html = _read(SR_V2_HTML)
    assert 'id="company-search-input"' in html
    assert "updateCompanyQuery(cid)" in html
    assert "showMsg(true, \"読み込みました\")" in html
    load_idx = html.index("async function load()")
    success_block = html[load_idx : html.index("async function save()", load_idx)]
    assert success_block.index("updateCompanyQuery(cid)") < success_block.index(
        "showMsg(true, \"読み込みました\")"
    )


def test_sr_v2_reset_clears_company_query():
    html = _read(SR_V2_HTML)
    assert "updateCompanyQuery(\"\")" in html
    assert "localStorage.getItem(LS_LAST_COMPANY)" not in html


def test_sr_v2_observe_sync_on_load_success():
    html = _read(SR_V2_HTML)
    assert "syncObserveContextForCompany" in html
    assert "isCompanyDetailMode()" in html
    assert "updateObserveCompanyHeading" in html


def test_sr_v2_init_restores_company_from_url():
    html = _read(SR_V2_HTML)
    assert "readUrlCompanyId" in html
    assert "initCompanyFromUrl()" in html
    assert "updateCompanyQuery(urlCompany)" in html
    init_idx = html.index("function initCompanyFromUrl()")
    init_fn = html[init_idx : html.index("function syncCompanyUrlFromState()", init_idx)]
    assert "load();" in init_fn


def test_company_context_preserves_tab_with_company():
    script = _read(CTX_JS)
    runner = (
        script
        + """
const href = SrV2CompanyContext.buildHrefWithCompany('/sr/v2?tab=observe', 'test1');
const u = new URL(href, 'http://local');
if (u.searchParams.get('company') !== 'test1') {
  throw new Error('expected company=test1 got ' + u.searchParams.get('company'));
}
if (u.searchParams.get('tab') !== 'observe') {
  throw new Error('expected tab=observe got ' + u.searchParams.get('tab'));
}
const cleared = SrV2CompanyContext.buildHrefWithCompany('/sr/v2?tab=observe&company=old', '');
const u2 = new URL(cleared, 'http://local');
if (u2.searchParams.get('company')) {
  throw new Error('company should be removed');
}
if (u2.searchParams.get('tab') !== 'observe') {
  throw new Error('tab should remain');
}
console.log('ok');
"""
    )
    out = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr or out.stdout


def test_company_context_reload_restore():
    script = _read(CTX_JS)
    runner = (
        script
        + """
if (SrV2CompanyContext.readCompanyFromSearch('?company=test1') !== 'test1') {
  throw new Error('reload restore failed');
}
if (SrV2CompanyContext.readCompanyFromSearch('?tab=observe&company=test1') !== 'test1') {
  throw new Error('reload restore with tab failed');
}
console.log('ok');
"""
    )
    out = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr or out.stdout
