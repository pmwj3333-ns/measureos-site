"""
pytest 用: まず MEASUREOS_SQLITE_URL を設定してから app を import する。
"""

from __future__ import annotations

import os
import tempfile

import pytest

_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["MEASUREOS_SQLITE_URL"] = str(_TEST_DB_PATH)

from starlette.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.company_validator import (  # noqa: E402
    backfill_company_master_from_legacy,
    seed_known_test_companies,
)

models.Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_db_tables():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        backfill_company_master_from_legacy(db)
        seed_known_test_companies(db)
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def login_office(client: TestClient, cid: str, password: str) -> None:
    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": password},
    )
    assert r.status_code == 200, r.text


def ensure_tenant_login(
    client: TestClient,
    cid: str,
    password: str = "TestPass1!",
    *,
    leaders: list | None = None,
) -> None:
    """会社パスワードを設定して session ログインする（tenant API テスト用）。"""
    leader_rows = leaders if leaders is not None else [{"name": "班長", "process": ""}]
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": leader_rows,
            "company_name": cid,
            "company_password": password,
        },
    )
    assert r.status_code == 200, r.text
    login_office(client, cid, password)


@pytest.fixture(autouse=True)
def _auto_tenant_login_from_module(request, client):
    """モジュール定数 CO がある integration テスト向けの既定ログイン。"""
    if request.node.get_closest_marker("no_auth"):
        return
    mod = request.module
    cid = getattr(mod, "CO", None)
    if not cid or not isinstance(cid, str) or not cid.strip():
        return
    password = getattr(mod, "LOGIN_PW", None) or getattr(mod, "PASSWORD", None) or "TestPass1!"
    leaders = None
    user = getattr(mod, "USER", None)
    if isinstance(user, str) and user.strip():
        leaders = [{"name": user.strip(), "process": (getattr(mod, "PROC", None) or "")}]
    ensure_tenant_login(client, cid.strip(), str(password), leaders=leaders)


def v2_register_planned(
    client: TestClient,
    unit_id: int,
    *,
    lines: list | None = None,
) -> dict:
    """予告フェーズ通過（着手前必須）。lines=[] で内容未定登録。"""
    payload_lines: list = [{"label": "テスト商品", "value": 1}] if lines is None else lines
    r = client.post(f"/v2/work/{unit_id}/planned", json={"lines": payload_lines})
    assert r.status_code == 200, r.text
    return r.json()


def v2_start(client: TestClient, unit_id: int) -> dict:
    r = client.post(f"/v2/work/{unit_id}/start", json={})
    assert r.status_code == 200, r.text
    return r.json()
