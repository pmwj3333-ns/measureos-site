"""sr_v2: UI 構成（読み込み一本化）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"


def _read() -> str:
    return SR_V2_HTML.read_text(encoding="utf-8")


def test_sr_v2_no_duplicate_reload_buttons():
    html = _read()
    assert "btn-reload-working-days" not in html
    assert 'id="btn-load"' not in html
    assert html.count("再読込") == 0


def test_sr_v2_company_create_ui():
    html = _read()
    assert 'id="btn-create-company"' in html
    assert "新規会社を作成" in html
    assert 'id="btn-start-new-company"' in html
    assert "別の新規会社を作成" in html
    assert 'id="btn-reissue-password"' in html
    assert 'id="btn-copy-login"' in html
    assert "ログイン情報をコピー" in html
    assert 'id="company-id-display"' in html
    assert 'id="company_password"' not in html
    assert 'id="btn-company-load"' not in html
    assert "ログインID" in html
    assert "会社ID" not in html


def test_sr_v2_create_company_blocks_edit_mode():
    html = _read()
    fn = html.split("async function createCompany")[1].split("async function reissueCompanyPassword")[0]
    assert "isEditingExistingCompany()" in fn
    assert "companyLoadSeq" in fn
    assert 'api("POST", "/v2/companies"' in fn
    assert "PUT" not in fn


def test_sr_v2_load_sets_edit_lock_before_ui_mode():
    html = _read()
    load_fn = html.split("async function load()")[1].split("async function save()")[0]
    assert load_fn.index("lastFetchedCompanyId = cid") < load_fn.index("setCompanyIdState(cid)")


def test_sr_v2_company_ui_mode_uses_edit_lock():
    html = _read()
    assert "function isEditingExistingCompany()" in html
    assert "hasPendingCompanyLoad()" in html
    mode_fn = html.split("function updateCompanyUiMode()")[1].split("function setCompanyIdState")[0]
    assert "showExistingCompanyActions" in mode_fn
    assert 'newActions.hidden = showExistingCompanyActions' in mode_fn
    assert 'existingNew.hidden = !showExistingCompanyActions' in mode_fn


def test_sr_v2_prepare_new_company_creation():
    html = _read()
    assert "function prepareNewCompanyCreation()" in html
    assert "resetCompanyContext()" in html.split("function prepareNewCompanyCreation")[1].split("async function createCompany")[0]
    assert "companyLoadSeq" in html


def test_sr_v2_load_ignores_stale_fetch():
    html = _read()
    load_fn = html.split("async function load()")[1].split("async function save()")[0]
    assert "companyLoadSeq" in load_fn
    assert "seq !== companyLoadSeq" in load_fn


def test_sr_v2_company_load_via_search_not_manual_id():
    html = _read()
    assert 'id="company-search-input"' in html
    assert "selectCompanyFromSearch" in html


def test_sr_v2_load_refreshes_full_company_context():
    html = _read()
    load_idx = html.index("async function load()")
    save_idx = html.index("async function save()", load_idx)
    load_fn = html[load_idx:save_idx]
    assert "loadWorkingCalendar()" in load_fn
    assert "renderFromFieldUsers" in load_fn
    assert "updateCompanyQuery(cid)" in load_fn
    assert "syncObserveContextForCompany(cid)" in load_fn


def test_sr_v2_save_buttons_retained():
    html = _read()
    assert 'id="btn-save"' in html
    assert 'id="btn-save-working-days"' in html
    assert "保存する" in html
    assert "営業日設定を保存" in html
