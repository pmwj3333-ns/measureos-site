"""office_v2 会社ログイン・session。"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
OFFICE_V2_HTML = ROOT / "frontend" / "office_v2.html"

LOGIN_FAIL = "会社IDまたはパスワードが正しくありません"


def _set_password(client: TestClient, cid: str, password: str, name: str | None = None) -> None:
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [],
            "company_name": name or cid,
            "company_password": password,
        },
    )
    assert r.status_code == 200, r.text


def _register(client: TestClient, cid: str, name: str | None = None) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": name or cid},
    )
    assert r.status_code == 200, r.text


def test_office_login_success(client: TestClient):
    cid = "office_login_ok_co"
    _set_password(client, cid, "OfficePass1!", "ログイン成功テスト")

    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": "OfficePass1!"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == cid
    assert body["company_name"] == "ログイン成功テスト"
    assert body["authenticated"] is True
    assert "password" not in body


def test_office_login_wrong_password(client: TestClient):
    cid = "office_login_bad_pw_co"
    _set_password(client, cid, "correct-pass")

    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": "wrong-pass"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == LOGIN_FAIL


def test_office_login_unknown_company(client: TestClient):
    r = client.post(
        "/v2/office/login",
        json={"company_id": "no_such_office_co_xyz", "password": "any"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == LOGIN_FAIL


def test_office_login_no_password_configured(client: TestClient):
    cid = "office_login_no_pw_co"
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={"leaders": [], "company_name": cid},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": "try-any"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == LOGIN_FAIL


def test_office_login_inactive_company_same_message(client: TestClient):
    cid = "office_login_inactive_co"
    _register(client, cid, "無効ログイン")
    _set_password(client, cid, "inactive-pass")
    rid = next(x["id"] for x in client.get("/admin/companies").json() if x["company_id"] == cid)
    assert client.patch(f"/admin/companies/{rid}", json={"is_active": False}).status_code == 200

    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": "inactive-pass"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == LOGIN_FAIL


def test_office_session_after_login(client: TestClient):
    cid = "office_session_co"
    _set_password(client, cid, "SessionPass9")

    login = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": "SessionPass9"},
    )
    assert login.status_code == 200, login.text

    sess = client.get("/v2/office/session")
    assert sess.status_code == 200, sess.text
    body = sess.json()
    assert body["company_id"] == cid
    assert body["authenticated"] is True
    assert "password" not in body
    assert "company_password" not in body
    assert "company_password_hash" not in body


def test_office_logout_clears_session(client: TestClient):
    cid = "office_logout_co"
    _set_password(client, cid, "LogoutPass8")

    assert (
        client.post(
            "/v2/office/login",
            json={"company_id": cid, "password": "LogoutPass8"},
        ).status_code
        == 200
    )
    assert client.get("/v2/office/session").status_code == 200

    out = client.post("/v2/office/logout")
    assert out.status_code == 200
    assert out.json()["ok"] is True

    assert client.get("/v2/office/session").status_code == 401


def test_office_session_does_not_store_password(client: TestClient):
    cid = "office_no_pw_in_sess_co"
    plain = "PlainMustNotPersist"
    _set_password(client, cid, plain)

    client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": plain},
    )

    sess = client.get("/v2/office/session")
    assert sess.status_code == 200
    text = sess.text
    assert plain not in text
    assert "company_password_hash" not in text


def test_office_v2_html_has_login_ui():
    html = OFFICE_V2_HTML.read_text(encoding="utf-8")
    assert 'id="office-login-screen"' in html
    assert 'id="login-company-id"' in html
    assert 'id="login-company-password"' in html
    assert 'id="btn-office-login"' in html
    assert "MEASURE OS ログイン" in html
    login_block = html.split('id="office-login-screen"')[1].split("</form>")[0]
    assert "ログインID" in login_block
    assert "パスワード" in login_block
    assert "ログインIDまたはパスワードが正しくありません" in login_block
    assert "会社ID" not in login_block
    assert "会社パスワード" not in login_block
    assert "MEASURE OS 事務画面" not in login_block
    assert 'id="btn-office-logout"' in html
    assert "ログアウト" in html
    assert "会社変更" not in html
    assert "bootOffice()" in html
    assert "replaceState" not in html


def _office_html() -> str:
    return OFFICE_V2_HTML.read_text(encoding="utf-8")


def _extract_fn(html: str, start: str, end: str) -> str:
    i = html.index(start)
    j = html.index(end, i)
    return html[i:j]


def test_office_logout_resets_company_context():
    html = _office_html()
    logout_fn = _extract_fn(html, "async function logoutOffice", "async function bootOffice")
    assert "resetOfficeCompanyContext()" in logout_fn


def test_office_reset_context_clears_session_form_and_storage():
    html = _office_html()
    fn = _extract_fn(html, "function resetOfficeCompanyContext", "async function fetchOfficeSession")
    assert 'sessionCompanyId = ""' in fn
    assert 'companyEl.value = ""' in fn
    assert "clearOfficeCompanyStorage()" in fn
    assert "resetLoginForm()" in fn


def test_office_reset_login_form_clears_company_id_and_password():
    html = _office_html()
    fn = _extract_fn(html, "function resetLoginForm", "function resetOfficeCompanyContext")
    assert "login-company-id" in fn
    assert "login-company-password" in fn
    assert fn.count('value = ""') >= 2


def test_office_clear_storage_removes_local_and_session():
    html = _office_html()
    fn = _extract_fn(html, "function clearOfficeCompanyStorage", "function resetLoginForm")
    assert "localStorage.removeItem" in fn
    assert "sessionStorage.removeItem" in fn
    assert "LS_SHARED_COMPANY_ID" in fn


def test_office_boot_without_session_resets_login_state():
    html = _office_html()
    fn = _extract_fn(html, "async function bootOffice", "function persistSharedCompanyFromOffice")
    assert "fetchOfficeSession()" in fn
    assert "resetOfficeCompanyContext()" in fn
    assert "showLoginScreen()" in fn


def test_office_login_form_autocomplete_disabled():
    html = _office_html()
    form_block = html.split('id="office-login-form"')[1].split("</form>")[0]
    assert 'autocomplete="off"' in form_block
    id_block = html.split('id="login-company-id"')[1][:320]
    pw_block = html.split('id="login-company-password"')[1][:320]
    assert 'autocomplete="off"' in id_block
    assert 'autocomplete="off"' in pw_block
    assert 'autocomplete="organization"' not in html
    assert 'autocomplete="current-password"' not in html


def test_office_login_success_clears_login_form():
    html = _office_html()
    fn = _extract_fn(html, "async function submitOfficeLogin", "async function logoutOffice")
    success_part = fn.split("if (!res.ok)")[1].split("await applySessionToOffice")[0]
    assert "resetLoginForm()" in success_part
    assert "handleLoginFailure()" not in success_part.split("resetLoginForm()")[1]


def test_office_login_failure_clears_password_only():
    html = _office_html()
    fn = _extract_fn(html, "function handleLoginFailure", "function resetOfficeCompanyContext")
    assert "showLoginError(true)" in fn
    assert "clearLoginPassword()" in fn
    assert "login-company-id" not in fn


def test_office_login_failure_keeps_company_id():
    html = _office_html()
    submit_fn = _extract_fn(html, "async function submitOfficeLogin", "async function logoutOffice")
    fail_block = submit_fn.split("if (!res.ok)")[1].split("resetLoginForm()")[0]
    assert "handleLoginFailure()" in fail_block
    assert 'login-company-id").value = ""' not in fail_block
    assert "resetLoginForm()" not in fail_block


def test_office_clear_login_password_only_clears_password_field():
    html = _office_html()
    fn = _extract_fn(html, "function clearLoginPassword", "function handleLoginFailure")
    assert "login-company-password" in fn
    assert 'value = ""' in fn
    assert "login-company-id" not in fn


def test_office_reload_without_session_starts_empty():
    """bootOffice: session なし → storage/フォーム初期化（stale state 防止）。"""
    html = _office_html()
    boot = _extract_fn(html, "async function bootOffice", "function persistSharedCompanyFromOffice")
    assert "if (sess && sess.company_id)" in boot
    else_part = boot.split("} else {", 1)[1]
    assert "resetOfficeCompanyContext()" in else_part
    assert "localStorage.getItem" not in boot
    assert "sessionStorage.getItem" not in boot


def test_existing_company_password_tests_still_compatible(client: TestClient):
    """Step1 パスワード基盤: GET /v2/company/{id} は session 必須。"""
    cid = "office_compat_co"
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={"leaders": [], "company_name": cid, "company_password": "CompatPass1!"},
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/v2/company/{cid}").status_code == 401
    from tests.conftest import login_office

    login_office(client, cid, "CompatPass1!")
    assert client.get(f"/v2/company/{cid}").json()["has_password"] is True
