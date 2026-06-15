"""product_master 蓄積型商品辞書（CSV 非同期・非破壊 ensure）。"""

from __future__ import annotations

import io
from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.product_master import ensure_product_master_entries

CO = "pm_dict_test_co"


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "商品辞書テスト"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register(client)
    return client


def _seed_legacy_product(db) -> models.ProductMaster:
    row = models.ProductMaster(
        company_id=CO,
        label="旧商品A",
        product_code="OLD1",
        is_active=True,
        safety_stock_value=12,
        production_mode="purchase",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_ensure_adds_only_missing_entries():
    db = SessionLocal()
    try:
        legacy = _seed_legacy_product(db)
        created = ensure_product_master_entries(
            CO,
            [
                {"product_code": "OLD1", "label": "旧商品A"},
                {"product_code": "NEW1", "label": "新商品B"},
            ],
            db,
        )
        db.commit()
        assert created == 1
        rows = (
            db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == CO)
            .order_by(models.ProductMaster.id.asc())
            .all()
        )
        assert len(rows) == 2
        old = next(r for r in rows if r.id == legacy.id)
        assert old.safety_stock_value == 12
        assert old.production_mode == "purchase"
        assert old.label == "旧商品A"
    finally:
        db.close()


def test_stock_import_does_not_remove_legacy_product(co_client: TestClient):
    db = SessionLocal()
    try:
        _seed_legacy_product(db)
    finally:
        db.close()

    csv_body = "product_code,label,stock_qty\nNEW2,新商品C,5\n"
    r = co_client.post(
        "/v2/stock/import",
        data={"company_id": CO},
        files={"file": ("stock.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        labels = [
            (row.label or "")
            for row in db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == CO)
            .all()
        ]
        assert "旧商品A" in labels
        assert "新商品C" in labels
        legacy = (
            db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == CO)
            .filter(models.ProductMaster.product_code == "OLD1")
            .first()
        )
        assert legacy is not None
        assert legacy.safety_stock_value == 12
        assert legacy.production_mode == "purchase"
    finally:
        db.close()


def test_shipment_import_adds_new_product_without_touching_existing(co_client: TestClient):
    db = SessionLocal()
    try:
        _seed_legacy_product(db)
    finally:
        db.close()

    csv_body = "product_code,label,ship_qty,due_date\nNEW3,新商品D,3,2026-06-01\n"
    r = co_client.post(
        "/v2/shipment/import",
        data={"company_id": CO},
        files={"file": ("ship.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        codes = {
            (row.product_code or "")
            for row in db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == CO)
            .all()
        }
        assert "OLD1" in codes
        assert "NEW3" in codes
    finally:
        db.close()


def test_ensure_by_label_skips_existing_without_code_update():
    db = SessionLocal()
    try:
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="ラベルOnly",
                product_code=None,
                safety_stock_value=7,
                production_mode="manufacture",
            )
        )
        db.commit()
        created = ensure_product_master_entries(
            CO,
            [{"product_code": "X9", "label": "ラベルOnly"}],
            db,
        )
        db.commit()
        assert created == 0
        row = (
            db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == CO)
            .filter(models.ProductMaster.label == "ラベルOnly")
            .first()
        )
        assert row is not None
        assert row.product_code is None
        assert row.safety_stock_value == 7
    finally:
        db.close()
