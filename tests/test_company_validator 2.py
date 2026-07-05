"""company_id 入口統制（company_master）。"""

from __future__ import annotations

from starlette.testclient import TestClient


def _register(client: TestClient, cid: str, name: str | None = None) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": name or cid},
    )
    assert r.status_code == 200, r.text


def test_post_work_rejects_unregistered_company(client: TestClient):
    r = client.post(
        "/v2/work",
        json={
            "company_id": "not_in_master_xyz",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-01",
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "company_id is not registered"


def test_post_work_rejects_inactive_company(client: TestClient):
    _register(client, "inactive_co", "無効会社")
    row = client.get("/admin/companies").json()
    rid = next(x["id"] for x in row if x["company_id"] == "inactive_co")
    r = client.patch(f"/admin/companies/{rid}", json={"is_active": False})
    assert r.status_code == 200

    r = client.post(
        "/v2/work",
        json={
            "company_id": "inactive_co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-01",
        },
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "company is inactive"


def test_post_work_allows_registered_active_company(client: TestClient):
    _register(client, "active_gate_co", "有効会社")
    r = client.post(
        "/v2/work",
        json={
            "company_id": "active_gate_co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-01",
        },
    )
    assert r.status_code == 200, r.text


def test_stock_csv_import_validates_company(client: TestClient):
    files = {"file": ("stock.csv", "product_code,label,stock_qty\nA,商品,1\n", "text/csv")}
    r = client.post(
        "/v2/stock/import",
        data={"company_id": "unknown_csv_co"},
        files=files,
    )
    assert r.status_code == 401


def test_v2_put_leaders_auto_registers_company_master(client: TestClient):
    cid = "sr_v2_auto_reg_co"
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "班長A", "process": "組立"}],
            "company_name": "自動登録テスト株式会社",
            "package_code": "A",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == cid
    assert body["company_name"] == "自動登録テスト株式会社"
    assert body["saved_count"] == 1

    rows = client.get("/admin/companies").json()
    master = next(x for x in rows if x["company_id"] == cid)
    assert master["company_name"] == "自動登録テスト株式会社"
    assert master["is_active"] is True


def test_v2_put_leaders_rejects_inactive_company(client: TestClient):
    cid = "sr_v2_inactive_save_co"
    _register(client, cid, "無効保存テスト")
    rid = next(x["id"] for x in client.get("/admin/companies").json() if x["company_id"] == cid)
    r = client.patch(f"/admin/companies/{rid}", json={"is_active": False})
    assert r.status_code == 200

    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={"leaders": [], "company_name": "無効保存テスト"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "company is inactive"
