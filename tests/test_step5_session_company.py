"""Step5: stock / shipment / product master の session company 化。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

SESSION_SCREENS = [
    (
        "/stock/import/v2",
        "stock_import_v2.html",
        "stock_sess_co",
        "StockPass1",
        "在庫CSV",
    ),
    (
        "/shipment/import/v2",
        "shipment_import_v2.html",
        "shipment_sess_co",
        "ShipmentPass1",
        "出荷予定CSV",
    ),
    (
        "/product/master/v2",
        "product_master_v2.html",
        "product_master_sess_co",
        "ProductMasterPass1",
        "商品マスタ",
    ),
]


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
    "path,html_name,cid,password,title",
    SESSION_SCREENS,
)
def test_step5_redirects_without_session(
    client: TestClient, path: str, html_name: str, cid: str, password: str, title: str
):
    del html_name, cid, password, title
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == f"/office/v2?return_to={quote(path, safe='')}"
    assert "no-store" in r.headers.get("cache-control", "").lower()
    assert r.headers.get("vary") == "Cookie"


@pytest.mark.parametrize(
    "path,html_name,cid,password,title",
    SESSION_SCREENS,
)
def test_step5_serves_with_session_company(
    client: TestClient, path: str, html_name: str, cid: str, password: str, title: str
):
    del html_name, title
    _set_password(client, cid, password)
    _login(client, cid, password)

    r = client.get(path, follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text


@pytest.mark.parametrize(
    "path,html_name,cid,password,title",
    SESSION_SCREENS,
)
def test_step5_ignores_url_company_query(
    client: TestClient, path: str, html_name: str, cid: str, password: str, title: str
):
    del html_name, title
    _set_password(client, cid, password)
    _login(client, cid, password)

    r = client.get(
        path + "?company=other_co&company_id=other_co",
        follow_redirects=False,
    )
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text
    assert '__MO_BOOTSTRAP_COMPANY__="other_co"' not in r.text


@pytest.mark.parametrize(
    "path,html_name,cid,password,title",
    SESSION_SCREENS,
)
def test_step5_logout_denies_access(
    client: TestClient, path: str, html_name: str, cid: str, password: str, title: str
):
    del html_name, title
    _set_password(client, cid, password)
    _login(client, cid, password)

    assert client.get(path, follow_redirects=False).status_code == 200
    assert client.post("/v2/office/logout").status_code == 200
    assert client.get("/v2/office/session").status_code == 401

    r = client.get(path, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == f"/office/v2?return_to={quote(path, safe='')}"


@pytest.mark.parametrize(
    "path,html_name,cid,password,title",
    SESSION_SCREENS,
)
def test_step5_login_then_returns_screen_html(
    client: TestClient, path: str, html_name: str, cid: str, password: str, title: str
):
    del html_name, title
    _set_password(client, cid, password)
    assert client.get(path, follow_redirects=False).status_code == 307

    _login(client, cid, password)
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 200, r.text
    assert f"__MO_BOOTSTRAP_COMPANY__={json.dumps(cid)}" in r.text


def test_stock_import_v2_no_company_input_ui():
    html = (ROOT / "frontend" / "stock_import_v2.html").read_text(encoding="utf-8")
    assert 'id="company"' not in html
    assert 'for="company"' not in html
    assert "company_id を入力してください" not in html
    assert "sessionCompanyId" in html
    assert "initSessionCompanyFromBootstrap" in html
    assert 'localStorage.setItem("company_id"' not in html


def test_shipment_import_v2_no_company_input_ui():
    html = (ROOT / "frontend" / "shipment_import_v2.html").read_text(encoding="utf-8")
    assert 'id="company"' not in html
    assert 'for="company"' not in html
    assert "company_id を入力してください" not in html
    assert "sessionCompanyId" in html
    assert "initSessionCompanyFromBootstrap" in html
    assert 'localStorage.setItem("company_id"' not in html


def test_product_master_v2_no_company_input_ui():
    html = (ROOT / "frontend" / "product_master_v2.html").read_text(encoding="utf-8")
    assert 'id="company"' not in html
    assert 'id="btn-load"' not in html
    assert 'for="company"' not in html
    assert "company_id を入力してください" not in html
    assert "productMasterSessionCompanyId" in html
    assert "initProductMasterSessionCompanyFromBootstrap" in html
    assert 'params.get("company_id")' not in html
