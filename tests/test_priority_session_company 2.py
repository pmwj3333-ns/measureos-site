"""priority_v2: session company 化（Step 4）。"""

from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
PRIORITY_VIEW_HTML = ROOT / "frontend" / "priority_view.html"


def _set_password(client: TestClient, cid: str, password: str) -> None:
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "班長A", "process": ""}],
            "company_name": cid,
            "company_password": password,
        },
    )
    assert r.status_code == 200, r.text


def _login(client: TestClient, cid: str, password: str) -> None:
    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": password},
    )
    assert r.status_code == 200, r.text


def test_priority_v2_redirects_without_session(client: TestClient):
    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Fpriority%2Fv2"
    assert "no-store" in r.headers.get("cache-control", "").lower()
    assert r.headers.get("vary") == "Cookie"


def test_priority_v2_serves_with_session_company(client: TestClient):
    cid = "priority_sess_co"
    _set_password(client, cid, "PriorityPass1")
    _login(client, cid, "PriorityPass1")

    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text
    assert "優先度監視盤" in r.text


def test_priority_v2_ignores_url_company_query(client: TestClient):
    cid = "priority_url_ignore_co"
    _set_password(client, cid, "PriorityPass2")
    _login(client, cid, "PriorityPass2")

    r = client.get(
        "/priority/v2?company=other_co&company_id=other_co",
        follow_redirects=False,
    )
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text
    assert '__MO_BOOTSTRAP_COMPANY__="other_co"' not in r.text


def test_priority_v2_logout_denies_access(client: TestClient):
    cid = "priority_logout_co"
    _set_password(client, cid, "PriorityPass3")
    _login(client, cid, "PriorityPass3")

    assert client.get("/priority/v2", follow_redirects=False).status_code == 200
    assert client.post("/v2/office/logout").status_code == 200
    assert client.get("/v2/office/session").status_code == 401

    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Fpriority%2Fv2"


def test_priority_login_then_returns_priority_html(client: TestClient):
    cid = "priority_return_co"
    _set_password(client, cid, "PriorityPass4")
    assert client.get("/priority/v2", follow_redirects=False).status_code == 307

    _login(client, cid, "PriorityPass4")
    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text


def _priority_html() -> str:
    return PRIORITY_VIEW_HTML.read_text(encoding="utf-8")


def test_priority_v2_no_company_input_ui():
    html = _priority_html()
    assert 'id="company"' not in html
    assert 'id="btn-load"' not in html
    assert 'for="company"' not in html
    assert "company_id を入力してください" not in html


def test_priority_v2_uses_session_bootstrap_not_url_storage():
    html = _priority_html()
    assert "prioritySessionCompanyId" in html
    assert "initPrioritySessionCompanyFromBootstrap" in html
    assert "redirectToOfficeLogin" in html
    assert "localStorage.setItem(\"company_id\"" not in html
    assert "history.replaceState" not in html
    assert "searchParams.set(\"company\"" not in html
    assert 'param("company"' not in html
    assert 'param("company_id"' not in html


def test_priority_v2_boot_retries_session_before_office_redirect():
    html = _priority_html()
    boot = html.split("if (!prioritySessionCompanyId) {", 1)[1].split("} else {", 1)[0]
    assert "bootPriorityWhenBootstrapMissing" in boot
    assert "/v2/office/session" in boot
    assert "window.location.reload()" in boot
    assert "redirectToOfficeLogin()" in boot
    else_part = html.split("} else {", 1)[1].split("})();")[0]
    assert "void load()" in else_part
