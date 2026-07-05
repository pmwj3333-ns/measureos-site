"""office ログイン return_to（ログイン後の元画面復帰）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.services.return_to import build_office_login_url, safe_return_to_path

ROOT = Path(__file__).resolve().parent.parent
OFFICE_V2_HTML = ROOT / "frontend" / "office_v2.html"
FIELD_V2_HTML = ROOT / "frontend" / "field_v2.html"


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/field/v2", "/field/v2"),
        ("/genba/v2", "/genba/v2"),
        ("/priority/v2", "/priority/v2"),
        ("https://evil.example/", None),
        ("//evil.example/", None),
        ("", None),
        ("/field/v2#frag", "/field/v2"),
    ],
)
def test_safe_return_to_path(raw: str, expected: str | None):
    assert safe_return_to_path(raw) == expected


def test_build_office_login_url():
    assert build_office_login_url("/field/v2") == "/office/v2?return_to=%2Ffield%2Fv2"
    assert build_office_login_url(None) == "/office/v2"
    assert build_office_login_url("https://evil.example/") == "/office/v2"


def test_field_unauthenticated_redirect_includes_return_to(client: TestClient):
    r = client.get("/field/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Ffield%2Fv2"


def test_genba_unauthenticated_redirect_includes_return_to(client: TestClient):
    r = client.get("/genba/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Fgenba%2Fv2"


def test_priority_unauthenticated_redirect_includes_return_to(client: TestClient):
    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Fpriority%2Fv2"


def test_field_login_then_returns_field_html(client: TestClient):
    cid = "return_to_field_co"
    _set_password(client, cid, "ReturnPass1")
    assert client.get("/field/v2", follow_redirects=False).status_code == 307

    _login(client, cid, "ReturnPass1")
    r = client.get("/field/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "__MO_BOOTSTRAP_COMPANY__" in r.text
    assert "班長を選択してください" in r.text


def test_priority_login_then_returns_priority_html(client: TestClient):
    cid = "return_to_priority_co"
    _set_password(client, cid, "ReturnPass2")
    assert client.get("/priority/v2", follow_redirects=False).status_code == 307

    _login(client, cid, "ReturnPass2")
    r = client.get("/priority/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "priority_view" in r.text or "優先" in r.text


def test_office_direct_without_return_to_serves_office_html(client: TestClient):
    r = client.get("/office/v2", follow_redirects=False)
    assert r.status_code == 200
    assert "office_v2" in r.text or "事務" in r.text


def test_office_login_without_return_to_keeps_session(client: TestClient):
    cid = "return_to_office_co"
    _set_password(client, cid, "ReturnPass3")
    _login(client, cid, "ReturnPass3")

    sess = client.get("/v2/office/session")
    assert sess.status_code == 200
    assert sess.json()["company_id"] == cid


def test_office_html_navigates_to_return_to_after_login():
    html = OFFICE_V2_HTML.read_text(encoding="utf-8")
    assert "readSafeReturnToFromUrl" in html
    assert "navigateAfterLoginIfReturnTo" in html
    login_fn = html.split("async function submitOfficeLogin", 1)[1].split(
        "async function logoutOffice", 1
    )[0]
    assert "navigateAfterLoginIfReturnTo()" in login_fn
    boot_fn = html.split("async function bootOffice", 1)[1].split(
        "function persistSharedCompanyFromOffice", 1
    )[0]
    assert "navigateAfterLoginIfReturnTo()" in boot_fn


def test_field_client_redirect_includes_return_to():
    html = FIELD_V2_HTML.read_text(encoding="utf-8")
    fn = html.split("function redirectToOfficeLogin", 1)[1].split("let unitId", 1)[0]
    assert "return_to=" in fn
    assert "encodeURIComponent" in fn


def test_external_return_to_rejected_in_office_js():
    html = OFFICE_V2_HTML.read_text(encoding="utf-8")
    fn = html.split("function readSafeReturnToFromUrl", 1)[1].split(
        "function navigateAfterLoginIfReturnTo", 1
    )[0]
    assert 'raw.startsWith("//")' in fn or "raw.startsWith(\"//\")" in fn
    assert 'includes("://")' in fn
