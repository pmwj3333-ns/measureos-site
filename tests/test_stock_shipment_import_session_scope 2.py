"""stock / shipment CSV import: session company_id 一致を強制。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

CO_A = "stock_ship_scope_a"
CO_B = "stock_ship_scope_b"
PASS = "StockShipScope1"

STOCK_CSV = "product_code,label,stock_qty\nA001,商品A,10\n"
SHIP_CSV = "product_code,label,ship_qty,due_date\nA001,商品A,5,2026-06-01\n"


def _register(client: TestClient, cid: str) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": cid},
    )
    assert r.status_code == 200, r.text


def _set_password(client: TestClient, cid: str) -> None:
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "班長", "process": ""}],
            "company_name": cid,
            "company_password": PASS,
        },
    )
    assert r.status_code == 200, r.text


def _login(client: TestClient, cid: str) -> None:
    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": PASS},
    )
    assert r.status_code == 200, r.text


def _stock_files():
    return {"file": ("stock.csv", io.BytesIO(STOCK_CSV.encode("utf-8")), "text/csv")}


def _ship_files():
    return {"file": ("ship.csv", io.BytesIO(SHIP_CSV.encode("utf-8")), "text/csv")}


@pytest.mark.parametrize(
    "path,files,data_key",
    [
        ("/v2/stock/import", _stock_files, "company_id"),
        ("/v2/shipment/import", _ship_files, "company_id"),
    ],
)
def test_import_requires_session(client: TestClient, path: str, files, data_key: str):
    _register(client, CO_A)
    r = client.post(path, data={data_key: CO_A}, files=files())
    assert r.status_code == 401


@pytest.mark.parametrize(
    "path,files",
    [
        ("/v2/stock/import", _stock_files),
        ("/v2/shipment/import", _ship_files),
    ],
)
def test_import_rejects_other_company(client: TestClient, path: str, files):
    _register(client, CO_A)
    _register(client, CO_B)
    _set_password(client, CO_A)
    _set_password(client, CO_B)
    _login(client, CO_A)
    r = client.post(path, data={"company_id": CO_B}, files=files())
    assert r.status_code == 403
    assert r.json()["detail"] == "company_id does not match session"


@pytest.mark.parametrize(
    "path,files",
    [
        ("/v2/stock/import", _stock_files),
        ("/v2/shipment/import", _ship_files),
    ],
)
def test_import_allows_matching_session(client: TestClient, path: str, files):
    _register(client, CO_A)
    _set_password(client, CO_A)
    _login(client, CO_A)
    r = client.post(path, data={"company_id": CO_A}, files=files())
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_stock_import_html_has_session_sync_helpers():
    html = (ROOT / "frontend" / "stock_import_v2.html").read_text(encoding="utf-8")
    assert "ensureSessionCompanyForWrite" in html
    assert "pageBootstrapCompanyId" in html
    assert "resolveSessionCompanyId" in html


def test_shipment_import_html_has_session_sync_helpers():
    html = (ROOT / "frontend" / "shipment_import_v2.html").read_text(encoding="utf-8")
    assert "ensureSessionCompanyForWrite" in html
    assert "pageBootstrapCompanyId" in html
    assert "resolveSessionCompanyId" in html
