"""Phase A: tenant API / HTML session guards."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.conftest import login_office


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


@pytest.mark.no_auth
def test_tenant_html_redirects_without_session(client: TestClient):
    paths = [
        "/field",
        "/field/v2",
        "/priority/v2",
        "/priority/input/v2",
        "/stock/import/v2",
        "/product/master/v2",
    ]
    for path in paths:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 307, path
        assert r.headers.get("location", "").startswith("/office/v2?return_to="), path


@pytest.mark.no_auth
def test_tenant_api_blocks_without_session(client: TestClient):
    cid = "tenant_auth_co"
    _set_password(client, cid, "TenantAuth1!")
    assert client.get(f"/v2/work/list?company_id={cid}").status_code == 401
    assert client.get(f"/v2/priority/items?company_id={cid}").status_code == 401
    assert client.get(f"/v2/company/{cid}").status_code == 401
    assert client.get("/v2/csv/import-schemas/stock").status_code == 401


def test_tenant_api_allows_matching_session(client: TestClient):
    cid = "tenant_auth_ok_co"
    _set_password(client, cid, "TenantAuthOk1!")
    login_office(client, cid, "TenantAuthOk1!")
    assert client.get(f"/v2/work/list?company_id={cid}").status_code == 200
    assert client.get(f"/v2/priority/items?company_id={cid}").status_code == 200
    assert client.get(f"/v2/company/{cid}").status_code == 200
    assert client.get("/v2/csv/import-schemas/stock").status_code == 200


def test_internal_routes_still_open_without_session(client: TestClient):
    assert client.get("/sr/v2", follow_redirects=False).status_code == 200
    assert client.get("/admin/companies").status_code == 200
    assert client.get("/v2/sr/observe-portfolio").status_code == 200
