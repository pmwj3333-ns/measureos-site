"""company_password 基盤（Step 1）。"""

from __future__ import annotations

from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.company_password import verify_company_password


def _put_leaders(client: TestClient, cid: str, **extra):
    payload = {"leaders": [], "company_name": extra.pop("company_name", cid), **extra}
    return client.put(f"/v2/company/{cid}/leaders", json=payload)


def _master_row(db, cid: str) -> models.CompanyMaster | None:
    return (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == cid)
        .first()
    )


def test_password_hash_saved_on_put(client: TestClient):
    cid = "pwd_hash_co"
    plain = "SecretPass123!"
    r = _put_leaders(client, cid, company_password=plain)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_password"] is True

    db = SessionLocal()
    try:
        row = _master_row(db, cid)
        assert row is not None
        h = row.company_password_hash
        assert h
        assert h.startswith("$2")
        assert verify_company_password(plain, h)
    finally:
        db.close()


def test_plaintext_not_stored_in_db(client: TestClient):
    cid = "pwd_plain_co"
    plain = "NoPlainInDb99"
    r = _put_leaders(client, cid, company_password=plain)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        row = _master_row(db, cid)
        assert row is not None
        h = row.company_password_hash or ""
        assert h != plain
        assert plain not in h
    finally:
        db.close()


def test_password_update_changes_hash(client: TestClient):
    cid = "pwd_update_co"
    r1 = _put_leaders(client, cid, company_password="first-pass")
    assert r1.status_code == 200, r.text

    db = SessionLocal()
    try:
        first_hash = _master_row(db, cid).company_password_hash
    finally:
        db.close()

    r2 = _put_leaders(client, cid, company_password="second-pass")
    assert r2.status_code == 200, r.text

    db = SessionLocal()
    try:
        row = _master_row(db, cid)
        assert row.company_password_hash != first_hash
        assert verify_company_password("second-pass", row.company_password_hash)
        assert not verify_company_password("first-pass", row.company_password_hash)
    finally:
        db.close()


def test_empty_password_keeps_existing_hash(client: TestClient):
    cid = "pwd_keep_co"
    r1 = _put_leaders(
        client,
        cid,
        company_name="保持テスト株式会社",
        company_password="keep-me",
    )
    assert r1.status_code == 200, r.text

    db = SessionLocal()
    try:
        saved_hash = _master_row(db, cid).company_password_hash
    finally:
        db.close()

    r2 = _put_leaders(
        client,
        cid,
        company_name="名称だけ変更",
    )
    assert r2.status_code == 200, r.text
    assert r2.json()["company_name"] == "名称だけ変更"
    assert r2.json()["has_password"] is True

    db = SessionLocal()
    try:
        row = _master_row(db, cid)
        assert row.company_password_hash == saved_hash
        assert verify_company_password("keep-me", row.company_password_hash)
    finally:
        db.close()


def test_get_returns_has_password_not_secret(client: TestClient):
    cid = "pwd_get_co"
    _put_leaders(client, cid, company_password="get-test-pw")

    r = client.get(f"/v2/company/{cid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_password"] is True
    assert "company_password" not in body
    assert "company_password_hash" not in body


def test_put_response_excludes_password_fields(client: TestClient):
    cid = "pwd_resp_co"
    r = _put_leaders(client, cid, company_password="resp-test-pw")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_password"] is True
    assert "company_password" not in body
    assert "company_password_hash" not in body


def test_existing_company_without_password_still_works(client: TestClient):
    cid = "pwd_legacy_co"
    r = _put_leaders(client, cid, company_name="既存互換テスト")
    assert r.status_code == 200, r.text

    g = client.get(f"/v2/company/{cid}")
    assert g.status_code == 200, r.text
    assert g.json()["has_password"] is False

    db = SessionLocal()
    try:
        row = _master_row(db, cid)
        assert row is not None
        assert not row.company_password_hash
    finally:
        db.close()

    w = client.post(
        "/v2/work",
        json={
            "company_id": cid,
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-01",
        },
    )
    assert w.status_code == 200, w.text
