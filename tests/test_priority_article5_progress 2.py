"""第5条進捗（article5_progress）: 空実績を進捗集計から除外する。"""

from __future__ import annotations

import json
from datetime import date, datetime, time

from app import models
from app.database import SessionLocal
from app.services.priority_article7_context import (
    _latest_work_units_with_actual_for_priority,
    _latest_work_units_with_actual_per_natural_key,
    _work_unit_has_positive_actual_content,
    article5_progress_for_priority_items,
)

CO = "a5_progress_test_co"
TASK = "task_s500"
PROC = "proc_mfg"
USER = "班長"
BD = date(2026, 5, 19)
NOW = datetime(2026, 5, 19, 10, 0)


def _seed_settings(db) -> None:
    db.add(
        models.CompanySettings(
            company_id=CO,
            unit="個",
            tolerance_value=0,
            day_boundary_time=time(0, 0),
            package_code="A",
            input_mode="manufacturing",
        )
    )


def _seed_priority(db, *, prod_value: float = 20.0) -> models.PriorityItem:
    p = models.PriorityItem(
        company_id=CO,
        product_code="s500",
        label="s-500",
        ship_value=20.0,
        stock_qty=40.0,
        prod_value=prod_value,
        value=20.0,
        status="open",
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(p)
    db.flush()
    return p


def _unit(
    db,
    *,
    actual_value: float | None,
    actual_lines_json: str | None = None,
    actual_at: datetime | None = NOW,
    planned_registered_at: datetime | None = None,
    actual_item_name: str | None = None,
) -> models.WorkUnit:
    if actual_item_name is None and actual_value is not None:
        actual_item_name = "s-500"
    u = models.WorkUnit(
        company_id=CO,
        task_id=TASK,
        process_id=PROC,
        user_id=USER,
        business_date=BD,
        status="normal",
        planned_registered_at=planned_registered_at,
        actual_at=actual_at,
        actual_value=actual_value,
        actual_lines_json=actual_lines_json,
        actual_item_name=actual_item_name,
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(u)
    db.flush()
    return u


def test_work_unit_has_positive_actual_content():
    with_qty = models.WorkUnit(
        company_id=CO,
        task_id=TASK,
        process_id=PROC,
        user_id=USER,
        business_date=BD,
        actual_at=NOW,
        actual_value=5.0,
        actual_item_name="s-500",
    )
    empty = models.WorkUnit(
        company_id=CO,
        task_id=TASK,
        process_id=PROC,
        user_id=USER,
        business_date=BD,
        actual_at=NOW,
        actual_value=None,
        actual_lines_json=None,
    )
    lines = models.WorkUnit(
        company_id=CO,
        task_id=TASK,
        process_id=PROC,
        user_id=USER,
        business_date=BD,
        actual_at=NOW,
        actual_lines_json=json.dumps(
            [{"label": "s-500", "value": 3, "product_code": "s500"}]
        ),
    )
    assert _work_unit_has_positive_actual_content(with_qty, "manufacturing")
    assert not _work_unit_has_positive_actual_content(empty, "manufacturing")
    assert _work_unit_has_positive_actual_content(lines, "manufacturing")


def test_empty_actual_excluded_progress_uses_previous_with_qty():
    """同一 planned_registered_at 内 20→5 訂正 + 空実績 のとき 5 を採用。"""
    db = SessionLocal()
    try:
        _seed_settings(db)
        p = _seed_priority(db, prod_value=20.0)
        preg = datetime(2026, 5, 19, 9, 0)
        u20 = _unit(
            db,
            actual_value=20.0,
            planned_registered_at=preg,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 20, "product_code": "s500"}]
            ),
        )
        u5 = _unit(
            db,
            actual_value=5.0,
            planned_registered_at=preg,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 5, "product_code": "s500"}]
            ),
        )
        u_empty = _unit(
            db,
            actual_value=None,
            planned_registered_at=preg,
            actual_lines_json=None,
        )
        db.commit()

        all_units = db.query(models.WorkUnit).filter_by(company_id=CO).all()
        latest = _latest_work_units_with_actual_per_natural_key(all_units, "manufacturing")
        assert len(latest) == 1
        assert latest[0].id == u5.id

        progress = article5_progress_for_priority_items(CO, [p], db)
        row = progress[int(p.id)]
        assert row.completed_qty == 5.0
        assert row.remaining_qty == 15.0
        assert row.effective_usable_qty == 45.0
        assert row.margin_after_ship_qty == 25.0
        assert u20.id < u5.id < u_empty.id
    finally:
        db.close()


def test_only_empty_actuals_gives_zero_completed():
    db = SessionLocal()
    try:
        _seed_settings(db)
        p = _seed_priority(db, prod_value=20.0)
        _unit(db, actual_value=None, actual_lines_json=None)
        db.commit()

        progress = article5_progress_for_priority_items(CO, [p], db)
        row = progress[int(p.id)]
        assert row.completed_qty == 0.0
        assert row.remaining_qty == 20.0
        assert row.effective_usable_qty == 40.0
        assert row.margin_after_ship_qty == 20.0
    finally:
        db.close()


def test_latest_with_qty_wins_over_older_with_qty_same_key():
    db = SessionLocal()
    try:
        _seed_settings(db)
        p = _seed_priority(db, prod_value=100.0)
        _unit(
            db,
            actual_value=20.0,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 20, "product_code": "s500"}]
            ),
        )
        u_latest = _unit(
            db,
            actual_value=7.0,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 7, "product_code": "s500"}]
            ),
        )
        db.commit()

        progress = article5_progress_for_priority_items(CO, [p], db)
        row = progress[int(p.id)]
        assert row.completed_qty == 7.0
        assert row.remaining_qty == 93.0
        assert row.effective_usable_qty == 47.0
        assert u_latest.id is not None
    finally:
        db.close()


def test_article5_progress_with_safety_stock_margin():
    """在庫40 + 作成5 - 出荷20 - 基準在庫40 = 出荷後余裕 -15。"""
    db = SessionLocal()
    try:
        _seed_settings(db)
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="s500",
                label="s-500",
                is_active=True,
                safety_stock_value=40,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        p = _seed_priority(db, prod_value=20.0)
        _unit(
            db,
            actual_value=5.0,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 5, "product_code": "s500"}]
            ),
        )
        db.commit()

        row = article5_progress_for_priority_items(CO, [p], db)[int(p.id)]
        assert row.completed_qty == 5.0
        assert row.remaining_qty == 15.0
        assert row.effective_usable_qty == 45.0
        assert row.margin_after_ship_qty == -15.0
    finally:
        db.close()


def test_priority_items_api_article5_progress_fields(client):
    db = SessionLocal()
    try:
        _seed_settings(db)
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="s500",
                label="s-500",
                is_active=True,
                safety_stock_value=40,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        p = _seed_priority(db, prod_value=20.0)
        _unit(
            db,
            actual_value=5.0,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 5, "product_code": "s500"}]
            ),
        )
        db.commit()
    finally:
        db.close()

    r = client.get(
        "/v2/priority/items",
        params={"company_id": CO, "article5_progress": "true"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["prod_value"] == 20.0
    assert it["stock_qty"] == 40.0
    assert it["article5_completed_qty"] == 5.0
    assert it["article5_remaining_qty"] == 15.0
    assert it["article5_effective_usable_qty"] == 45.0
    assert it["article5_margin_after_ship_qty"] == -15.0


def test_multi_product_same_natural_key_both_counted():
    """同日・同班長で s-500 と 商品D の実績が共存しても、商品ごとに最新行を採用する。"""
    db = SessionLocal()
    try:
        _seed_settings(db)
        p_s500 = _seed_priority(db, prod_value=20.0)
        p_d = models.PriorityItem(
            company_id=CO,
            product_code="D001",
            label="商品D",
            ship_value=30.0,
            stock_qty=0.0,
            prod_value=30.0,
            value=30.0,
            status="open",
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(p_d)
        db.flush()
        _unit(
            db,
            actual_value=10.0,
            actual_lines_json=json.dumps(
                [{"label": "商品D", "value": 10, "product_code": "D001"}]
            ),
        )
        u_s500 = _unit(
            db,
            actual_value=5.0,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 5, "product_code": "s500"}]
            ),
        )
        db.commit()

        all_units = db.query(models.WorkUnit).filter_by(company_id=CO).all()
        latest_d = _latest_work_units_with_actual_for_priority(all_units, p_d, "manufacturing")
        latest_s = _latest_work_units_with_actual_for_priority(all_units, p_s500, "manufacturing")
        assert len(latest_d) == 1
        assert len(latest_s) == 1
        assert latest_d[0].id != latest_s[0].id
        assert latest_s[0].id == u_s500.id

        progress = article5_progress_for_priority_items(CO, [p_s500, p_d], db)
        assert progress[int(p_s500.id)].completed_qty == 5.0
        assert progress[int(p_s500.id)].remaining_qty == 15.0
        assert progress[int(p_d.id)].completed_qty == 10.0
        assert progress[int(p_d.id)].remaining_qty == 20.0
    finally:
        db.close()


def test_additive_planned_sessions_sum_completed():
    """予告20→実績20 + 予告10→実績10 → completed=30, remaining=0。"""
    db = SessionLocal()
    try:
        _seed_settings(db)
        p = models.PriorityItem(
            company_id=CO,
            product_code="D001",
            label="商品D",
            ship_value=30.0,
            stock_qty=0.0,
            prod_value=30.0,
            value=30.0,
            status="open",
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(p)
        db.flush()
        _unit(
            db,
            actual_value=20.0,
            planned_registered_at=datetime(2026, 5, 19, 10, 0),
            actual_item_name="商品D",
            actual_lines_json=json.dumps(
                [{"label": "商品D", "value": 20, "product_code": "D001"}]
            ),
        )
        _unit(
            db,
            actual_value=10.0,
            planned_registered_at=datetime(2026, 5, 19, 11, 0),
            actual_item_name="商品D",
            actual_lines_json=json.dumps(
                [{"label": "商品D", "value": 10, "product_code": "D001"}]
            ),
        )
        db.commit()

        row = article5_progress_for_priority_items(CO, [p], db)[int(p.id)]
        assert row.completed_qty == 30.0
        assert row.remaining_qty == 0.0
    finally:
        db.close()


def test_correction_within_same_planned_session():
    db = SessionLocal()
    try:
        _seed_settings(db)
        p = _seed_priority(db, prod_value=20.0)
        preg = datetime(2026, 5, 19, 12, 0)
        _unit(
            db,
            actual_value=20.0,
            planned_registered_at=preg,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 20, "product_code": "s500"}]
            ),
        )
        _unit(
            db,
            actual_value=5.0,
            planned_registered_at=preg,
            actual_lines_json=json.dumps(
                [{"label": "s-500", "value": 5, "product_code": "s500"}]
            ),
        )
        db.commit()

        row = article5_progress_for_priority_items(CO, [p], db)[int(p.id)]
        assert row.completed_qty == 5.0
        assert row.remaining_qty == 15.0
    finally:
        db.close()
