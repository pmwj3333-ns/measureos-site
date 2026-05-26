"""company_master 管理 API（第1段階）。"""

from __future__ import annotations

from starlette.testclient import TestClient


def test_admin_companies_crud_flow(client: TestClient):
    r = client.get("/admin/companies")
    assert r.status_code == 200
    before_ids = {row["company_id"] for row in r.json()}

    cid = "admin_crud_demo_co"
    assert cid not in before_ids

    r = client.post(
        "/admin/companies",
        json={"company_id": f"  {cid}  ", "company_name": "デモ会社"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["company_id"] == cid
    assert body["company_name"] == "デモ会社"
    assert body["is_active"] is True
    row_id = body["id"]

    r = client.get("/admin/companies")
    assert cid in {row["company_id"] for row in r.json()}

    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": "別名"},
    )
    assert r.status_code == 422

    r = client.patch(
        f"/admin/companies/{row_id}",
        json={"is_active": False, "company_name": "デモ株式会社"},
    )
    assert r.status_code == 200
    patched = r.json()
    assert patched["is_active"] is False
    assert patched["company_name"] == "デモ株式会社"

    r = client.get("/admin/companies", params={"active_only": True})
    assert cid not in {row["company_id"] for row in r.json()}

    r = client.get("/admin/companies")
    demo_rows = [row for row in r.json() if row["company_id"] == cid]
    assert len(demo_rows) == 1
    assert demo_rows[0]["is_active"] is False


def test_admin_companies_rejects_empty_ids(client: TestClient):
    r = client.post(
        "/admin/companies",
        json={"company_id": "   ", "company_name": "名前"},
    )
    assert r.status_code == 422

    r = client.post(
        "/admin/companies",
        json={"company_id": "ok_co", "company_name": ""},
    )
    assert r.status_code == 422


def test_admin_companies_patch_not_found(client: TestClient):
    r = client.patch("/admin/companies/99999", json={"is_active": False})
    assert r.status_code == 404
