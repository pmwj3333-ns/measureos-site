"""v2 新規会社作成（company_id / 初期パスワード自動生成）。"""

from __future__ import annotations

from starlette.testclient import TestClient

from app.database import SessionLocal
from app import models
from app.services.company_password import verify_company_password


def test_v2_create_company_auto_generates_id_and_password(client: TestClient):
    r = client.post(
        "/v2/companies",
        json={"company_name": "株式会社テスト", "package_code": "A"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["company_id"]
    assert cid.startswith("test-")
    assert len(body["initial_password"]) == 8
    assert body["company_name"] == "株式会社テスト"
    assert body["package_code"] == "A"
    assert body["has_password"] is True
    assert "company_password_hash" not in body

    db = SessionLocal()
    try:
        master = (
            db.query(models.CompanyMaster)
            .filter(models.CompanyMaster.company_id == cid)
            .first()
        )
        assert master is not None
        assert master.company_name == "株式会社テスト"
        assert verify_company_password(body["initial_password"], master.company_password_hash)
        settings = db.query(models.CompanySettings).filter_by(company_id=cid).first()
        assert settings is not None
        assert settings.package_code == "A"
    finally:
        db.close()


def test_v2_create_company_requires_company_name(client: TestClient):
    r = client.post("/v2/companies", json={"company_name": "  ", "package_code": "A"})
    assert r.status_code == 422


def test_v2_password_reissue(client: TestClient):
    created = client.post(
        "/v2/companies",
        json={"company_name": "再発行テスト", "package_code": "B"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["company_id"]
    old_pwd = created.json()["initial_password"]

    r = client.post(f"/v2/company/{cid}/password/reissue")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == cid
    assert len(body["initial_password"]) == 8
    assert body["initial_password"] != old_pwd

    db = SessionLocal()
    try:
        master = db.query(models.CompanyMaster).filter_by(company_id=cid).first()
        assert verify_company_password(body["initial_password"], master.company_password_hash)
        assert not verify_company_password(old_pwd, master.company_password_hash)
    finally:
        db.close()


def test_v2_create_company_does_not_mutate_existing_company(client: TestClient):
    """POST /v2/companies は常に新規 company_id を発行し、既存会社名を上書きしない。"""
    existing_id = "overwrite_guard_test9"
    setup = client.put(
        f"/v2/company/{existing_id}/leaders",
        json={"leaders": [], "company_name": "旧株式会社"},
    )
    assert setup.status_code == 200, setup.text

    created = client.post(
        "/v2/companies",
        json={"company_name": "株式会社嵐", "package_code": "A"},
    )
    assert created.status_code == 200, created.text
    new_id = created.json()["company_id"]
    assert new_id != existing_id

    old = client.get(f"/v2/company/{existing_id}").json()
    assert old["company_name"] == "旧株式会社"

    new = client.get(f"/v2/company/{new_id}").json()
    assert new["company_name"] == "株式会社嵐"

    listed = client.get("/v2/companies").json()
    ids = {row["company_id"] for row in listed}
    assert existing_id in ids
    assert new_id in ids


def test_v2_create_company_then_save_leaders_and_working_days(client: TestClient):
    created = client.post(
        "/v2/companies",
        json={"company_name": "フロー確認", "package_code": "A"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["company_id"]

    leaders = client.put(
        f"/v2/company/{cid}/leaders",
        json={"leaders": [{"name": "班長A", "process": "組立"}]},
    )
    assert leaders.status_code == 200, leaders.text

    wd = client.patch(
        "/v2/company-settings/working-days",
        json={
            "company_id": cid,
            "default_working_weekdays": [1, 2, 3, 4, 5],
            "exceptions": [],
        },
    )
    assert wd.status_code == 200, wd.text
