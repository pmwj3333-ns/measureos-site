"""field_v2: logout 時の班長 localStorage クリア。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICE_V2_HTML = ROOT / "frontend" / "office_v2.html"
FIELD_V2_HTML = ROOT / "frontend" / "field_v2.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_fn(html: str, start: str, end: str) -> str:
    i = html.index(start)
    j = html.index(end, i)
    return html[i:j]


def test_office_logout_clears_field_leader_local_storage():
    html = _read(OFFICE_V2_HTML)
    fn = _extract_fn(html, "async function logoutOffice", "async function bootOffice")
    assert "clearFieldLeaderStorageForCompany(cid)" in fn
    assert "field_v2_last_user:" in html
    assert "field_v2_last_leader_proc:" in html
    clear_fn = _extract_fn(
        html,
        "function clearFieldLeaderStorageForCompany",
        "function resetLoginForm",
    )
    assert "localStorage.removeItem(fieldLeaderStorageKeyUser(cid))" in clear_fn
    assert "localStorage.removeItem(fieldLeaderStorageKeyProc(cid))" in clear_fn


def test_office_logout_captures_company_before_session_clear():
    html = _read(OFFICE_V2_HTML)
    fn = _extract_fn(html, "async function logoutOffice", "async function bootOffice")
    logout_idx = fn.index("await fetch(\"/v2/office/logout\"")
    clear_idx = fn.index("clearFieldLeaderStorageForCompany(cid)")
    reset_idx = fn.index("resetOfficeCompanyContext()")
    assert fn.index("let cid = sessionCompanyId") < logout_idx
    assert clear_idx > logout_idx
    assert reset_idx > clear_idx


def test_office_logout_does_not_clear_other_company_leader_keys():
    html = _read(OFFICE_V2_HTML)
    fn = _extract_fn(
        html,
        "function clearFieldLeaderStorageForCompany",
        "function resetLoginForm",
    )
    assert "localStorage.clear" not in fn
    assert "for (" not in fn
    assert "Object.keys" not in fn


def test_field_reload_still_restores_leader_from_local_storage():
    """F5 / 同一ログイン中: hasSavedSession による班長復元は維持。"""
    html = _read(FIELD_V2_HTML)
    fn = _extract_fn(html, "function startFieldMainShell", "</script>")
    assert "readSavedUserNameForCompany(companyAfterLoad)" in fn
    assert "hasSavedSession" in fn
    assert "void bootstrapWork()" in fn
    else_part = fn.split("} else {", 1)[1]
    assert 'ov.classList.remove("hidden")' in else_part


def test_field_leader_storage_keys_match_office_logout_clear():
    office = _read(OFFICE_V2_HTML)
    field = _read(FIELD_V2_HTML)
    assert 'return "field_v2_last_user:"' in office or '"field_v2_last_user:" +' in office
    assert 'return "field_v2_last_user:"' in field
    assert 'return "field_v2_last_leader_proc:"' in field


def test_field_after_logout_requires_leader_overlay_when_no_saved_user():
    """savedLeader 空 → オーバーレイ表示（logout 後想定）。"""
    html = _read(FIELD_V2_HTML)
    fn = _extract_fn(html, "function startFieldMainShell", "</script>")
    assert "const hasSavedSession = Boolean(companyAfterLoad && savedLeader)" in fn
