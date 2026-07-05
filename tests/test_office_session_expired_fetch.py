"""office_session_expired.js: tenant API 401 を fetch 共通で検知する。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION_EXPIRED_JS = ROOT / "frontend" / "static" / "office_session_expired.js"


def test_office_session_expired_installs_fetch_401_handler():
    js = SESSION_EXPIRED_JS.read_text(encoding="utf-8")
    assert "installFetch401Handler" in js
    assert "global.fetch = function" in js
    assert "res.status === 401" in js
    assert "handleSessionExpired();" in js
    assert "installFetch401Handler();" in js


def test_office_session_expired_does_not_intercept_login_screen_session_check():
    js = SESSION_EXPIRED_JS.read_text(encoding="utf-8")
    assert 'path === "/v2/office/login"' in js
    assert 'path === "/v2/office/logout"' in js
    assert 'path === "/v2/office/session"' in js
    assert 'global.location.pathname === "/office/v2"' in js
