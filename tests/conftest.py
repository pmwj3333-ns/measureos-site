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

models.Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_db_tables():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
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
