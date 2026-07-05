"""sr_v2: company_id 空時の URL / localStorage / UI 初期化。"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"
CTX_JS = ROOT / "frontend" / "static" / "sr_v2_company_context.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sr_v2_does_not_restore_company_from_localstorage_on_load():
    html = _read(SR_V2_HTML)
    assert "fromUrl || fromStore" not in html
    assert "localStorage.getItem(LS_LAST_COMPANY)" not in html
    assert "resetCompanyContext" in html
    assert "clearStoredCompanyKeys" in html
    assert "clearObserveDashboard" in html


def test_sr_v2_includes_company_context_script():
    html = _read(SR_V2_HTML)
    assert "/static/sr_v2_company_context.js" in html


def test_company_context_js_build_href_without_company():
    script = _read(CTX_JS)
    runner = (
        script
        + """
const href = SrV2CompanyContext.buildHrefWithCompany('/sr/v2?company=test7&tab=observe', '');
if (href !== '/sr/v2?tab=observe') {
  throw new Error('expected /sr/v2?tab=observe got ' + href);
}
const withCo = SrV2CompanyContext.buildHrefWithCompany('/sr/v2', 'test7');
if (withCo !== '/sr/v2?company=test7') {
  throw new Error('expected /sr/v2?company=test7 got ' + withCo);
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


def test_company_context_js_read_company_from_search():
    script = _read(CTX_JS)
    runner = (
        script
        + """
if (SrV2CompanyContext.readCompanyFromSearch('?company=test7') !== 'test7') {
  throw new Error('read company failed');
}
if (SrV2CompanyContext.readCompanyFromSearch('') !== '') {
  throw new Error('empty search should yield empty company');
}
if (SrV2CompanyContext.readCompanyFromSearch('?tab=observe') !== '') {
  throw new Error('no company param should yield empty');
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


def test_company_context_js_storage_keys_to_clear():
    script = _read(CTX_JS)
    runner = (
        script
        + """
const keys = SrV2CompanyContext.LS_KEYS_TO_CLEAR;
if (!keys.includes('sr_v2_last_company')) throw new Error('missing sr_v2_last_company');
if (!keys.includes('company_id')) throw new Error('missing company_id');
if (!keys.includes('observe_company_id')) throw new Error('missing observe_company_id');
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


def test_sr_v2_observe_empty_state_message():
    html = _read(SR_V2_HTML)
    assert "company が指定されていません" in html


def test_sr_v2_company_input_clears_on_empty():
    html = _read(SR_V2_HTML)
    assert 'if (!cid) resetCompanyContext();' in html
    assert 'updateCompanyQuery("")' in html


def test_sr_v2_syncs_company_url_on_input_tab_and_save():
    html = _read(SR_V2_HTML)
    assert "readUrlCompanyId" in html
    assert "initCompanyFromUrl" in html
    assert "bootSrV2" in html
    assert "pageshow" in html
    assert "localStorage.setItem(LS_LAST_COMPANY" not in html


def test_sr_v2_url_empty_resets_without_input_fallback():
    html = _read(SR_V2_HTML)
    init_idx = html.index("function initCompanyFromUrl()")
    init_fn = html[init_idx : html.index("function resetSettingsFormToEmpty()", init_idx)]
    assert "if (!urlCompany)" in init_fn
    assert "resetCompanyContext();" in init_fn
    assert "return;" in init_fn
    assert "getActiveCompanyId()" not in init_fn.split("resetCompanyContext")[0]


def test_sr_v2_switch_tab_does_not_promote_input_without_url():
    html = _read(SR_V2_HTML)
    switch_idx = html.index("function switchTab(panelId)")
    switch_fn = html[switch_idx : html.index("async function enterCompanyDetailMode", switch_idx)]
    assert "replaceMainShellUrl" in switch_fn
    assert "loadOpsPortfolio" in switch_fn
    assert "loadObserveDashboard" not in switch_fn
    assert "syncCompanyUrlFromState()" not in switch_fn


def test_sr_v2_reset_clears_observe_dashboard_state():
    html = _read(SR_V2_HTML)
    reset_idx = html.index("function resetCompanyContext()")
    reset_fn = html[reset_idx : html.index("function escapeHtml", reset_idx)]
    assert "clearObserveDashboard()" in reset_fn
    assert 'updateCompanyQuery("")' in reset_fn


def test_sr_v2_url_company_restores_on_init():
    html = _read(SR_V2_HTML)
    assert "initCompanyFromUrl()" in html
    assert "updateCompanyQuery(urlCompany)" in html
    assert "load();" in html


def test_company_context_js_build_href_preserves_tab_with_company():
    script = _read(CTX_JS)
    runner = (
        script
        + """
const href = SrV2CompanyContext.buildHrefWithCompany('/sr/v2?tab=observe', 'test8');
const u = new URL(href, 'http://local');
if (u.searchParams.get('company') !== 'test8') {
  throw new Error('expected company=test8 got ' + u.searchParams.get('company'));
}
if (u.searchParams.get('tab') !== 'observe') {
  throw new Error('expected tab=observe got ' + u.searchParams.get('tab'));
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
