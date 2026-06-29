"""field_v2: session company 化（Step 3）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
FIELD_V2_HTML = ROOT / "frontend" / "field_v2.html"


def _set_password(client: TestClient, cid: str, password: str) -> None:
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "班長A", "process": "組立"}],
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


@pytest.mark.no_auth
def test_field_v2_redirects_without_session(client: TestClient):
    cases = [
        ("/genba/v2", "/office/v2?return_to=%2Fgenba%2Fv2"),
        ("/field/v2", "/office/v2?return_to=%2Ffield%2Fv2"),
        ("/現場/v2", "/office/v2?return_to=%2F%E7%8F%BE%E5%A0%B4%2Fv2"),
        ("/field", "/office/v2?return_to=%2Ffield"),
        ("/現場", "/office/v2?return_to=%2F%E7%8F%BE%E5%A0%B4"),
    ]
    for path, location in cases:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 307, path
        assert r.headers.get("location") == location, path
        assert "no-store" in r.headers.get("cache-control", "").lower()
        assert r.headers.get("vary") == "Cookie"


def test_field_v2_serves_with_session_company(client: TestClient):
    cid = "field_sess_co"
    _set_password(client, cid, "FieldPass1")
    _login(client, cid, "FieldPass1")

    r = client.get("/genba/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text
    assert "__MO_FIELD_USERS_RAW__" in r.text


def test_field_v2_ignores_url_company_query(client: TestClient):
    cid = "field_url_ignore_co"
    _set_password(client, cid, "FieldPass2")
    _login(client, cid, "FieldPass2")

    r = client.get("/genba/v2?company=other_co&company_id=other_co", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text
    assert "__MO_BOOTSTRAP_COMPANY__=\"other_co\"" not in r.text


def test_field_v2_logout_denies_access(client: TestClient):
    cid = "field_logout_co"
    _set_password(client, cid, "FieldPass3")
    _login(client, cid, "FieldPass3")

    assert client.get("/genba/v2", follow_redirects=False).status_code == 200
    assert client.post("/v2/office/logout").status_code == 200
    assert client.get("/v2/office/session").status_code == 401

    r = client.get("/genba/v2", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/office/v2?return_to=%2Fgenba%2Fv2"


def test_field_v2_injects_leader_list_from_session_company(client: TestClient):
    cid = "field_leaders_co"
    _set_password(client, cid, "FieldPass4")
    client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "田中", "process": "検査"}],
            "company_name": cid,
            "company_password": "FieldPass4",
        },
    )
    _login(client, cid, "FieldPass4")

    r = client.get("/field/v2", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "__MO_FIELD_USERS_RAW__=" in r.text
    assert json.dumps("田中:検査", ensure_ascii=True)[1:-1] in r.text


def _field_html() -> str:
    return FIELD_V2_HTML.read_text(encoding="utf-8")


def test_field_v2_no_company_input_ui():
    html = _field_html()
    assert 'id="companyInput"' not in html
    assert 'id="cfg-company"' not in html
    assert 'id="companyBox"' not in html
    assert "saveCompany" not in html
    assert "field-company-pick" not in html
    assert "班長を選択してください" in html


def test_field_v2_uses_session_bootstrap_not_url_storage():
    html = _field_html()
    assert "fieldSessionCompanyId" in html
    assert "initFieldSessionCompanyFromBootstrap" in html
    assert "redirectToOfficeLogin" in html
    assert "LS_SHARED_COMPANY_ID" not in html
    assert "persistSharedCompanyId" not in html
    assert 'param("company"' not in html
    assert "sessionStorage" not in html
    assert 'localStorage.setItem("company_id"' not in html


def test_field_v2_get_config_uses_session_company():
    html = _field_html()
    fn_start = html.index("function getConfig()")
    fn_end = html.index("function saveCfgToLocal()", fn_start)
    fn = html[fn_start:fn_end]
    assert "const company = fieldSessionCompanyId" in fn
    assert 'param("company"' not in fn
    assert 'param("company_id"' not in fn


def test_field_v2_boot_retries_session_before_office_redirect():
    html = _field_html()
    init = html.split("(function init()")[1].split("})();")[0]
    assert "bootFieldWhenBootstrapMissing" in init
    assert "/v2/office/session" in init
    assert "window.location.reload()" in init
    assert "redirectToOfficeLogin()" in init
    assert "startFieldMainShell()" in html
