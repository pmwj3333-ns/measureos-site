"""CSV Header Normalizer（共通別名解決）。"""

from __future__ import annotations

import pytest

from app.services.csv_header_normalizer import (
    export_schema_for_client,
    normalize_header_cell,
    resolve_header_indices,
)
from app.services.shipment_csv import parse_shipment_csv_text
from app.services.stock_csv import parse_stock_csv_text


@pytest.mark.parametrize(
    "headers,field,schema",
    [
        (["商品コード", "商品名", "在庫数"], "product_code", "stock"),
        (["品番", "商品名", "在庫数"], "product_code", "stock"),
        (["code", "name", "stock"], "product_code", "stock"),
        (["商品CD", "品名", "現在庫"], "product_code", "stock"),
        (["product_code", "product_name", "qty"], "label", "stock"),
        (["品番", "名称", "棚卸数"], "label", "stock"),
        (["品番", "商品名", "数量"], "stock_qty", "stock"),
        (["code", "name", "stock_qty"], "stock_qty", "stock"),
        (["商品CD", "名称", "出荷予定数", "納期"], "product_code", "shipment"),
        (["品番", "品名", "予定数", "出荷予定日"], "ship_qty", "shipment"),
        (["code", "name", "quantity", "date"], "ship_qty", "shipment"),
        (["code", "name", "qty", "delivery_date"], "due_date", "shipment"),
        (["code", "name", "qty", "出荷日"], "due_date", "shipment"),
    ],
)
def test_header_aliases_map_to_canonical(headers, field, schema):
    colmap = resolve_header_indices(headers, schema)
    assert colmap is not None
    assert field in colmap


def test_backward_compat_legacy_csv_headers():
    """旧 FIELD_ALIASES 相当のヘッダー（既存テスト・運用CSV）が引き続き取り込めること。"""
    stock_legacy = "product_code,label,stock_qty\nNEW2,新商品C,5\n"
    stock_jp = "商品コード,商品名,在庫数\nA001,商品A,10\n"
    ship_legacy = "product_code,label,ship_qty,due_date\nNEW3,新商品D,3,2026-06-01\n"
    ship_jp = "商品コード,商品名,出荷予定数,納期\nA001,商品A,5,2026-06-01\n"

    rows, err, fatal = parse_stock_csv_text(stock_legacy)
    assert fatal is None and err == 0 and rows[0]["product_code"] == "NEW2"

    rows, err, fatal = parse_stock_csv_text(stock_jp)
    assert fatal is None and err == 0 and rows[0]["stock_qty"] == 10.0

    rows, err, fatal = parse_shipment_csv_text(ship_legacy)
    assert fatal is None and err == 0 and rows[0]["due_date"] == "2026-06-01"

    rows, err, fatal = parse_shipment_csv_text(ship_jp)
    assert fatal is None and err == 0 and rows[0]["ship_qty"] == 5.0


def test_stock_csv_accepts_permuted_column_order():
    cases = [
        "現在庫,品番,品名\n40,B001,切替確認\n",
        "品名,現在庫,品番\n切替確認,40,B001\n",
    ]
    for text in cases:
        rows, err, fatal = parse_stock_csv_text(text)
        assert fatal is None, text
        assert err == 0, text
        assert len(rows) == 1, text
        assert rows[0]["product_code"] == "B001"
        assert rows[0]["label"] == "切替確認"
        assert rows[0]["stock_qty"] == 40.0


def test_shipment_csv_accepts_permuted_column_order():
    text = "出荷日,予定数,名称,商品CD\n2026-06-23,15,商品Y,B002\n"
    rows, err, fatal = parse_shipment_csv_text(text)
    assert fatal is None
    assert err == 0
    assert len(rows) == 1
    assert rows[0]["product_code"] == "B002"
    assert rows[0]["label"] == "商品Y"
    assert rows[0]["ship_qty"] == 15.0
    assert rows[0]["due_date"] == "2026-06-23"


def test_resolve_header_indices_maps_by_name_not_position():
    headers = ["現在庫", "品番", "品名"]
    colmap = resolve_header_indices(headers, "stock")
    assert colmap == {"product_code": 1, "label": 2, "stock_qty": 0}


def test_stock_csv_with_japanese_headers():
    text = "品番,品名,現在庫\nB001,切替確認,40\n"
    rows, err, fatal = parse_stock_csv_text(text)
    assert fatal is None
    assert err == 0
    assert len(rows) == 1
    assert rows[0]["product_code"] == "B001"
    assert rows[0]["label"] == "切替確認"
    assert rows[0]["stock_qty"] == 40.0


def test_shipment_csv_with_japanese_headers():
    text = "商品CD,名称,予定数,出荷日\nB002,商品Y,15,2026-06-23\n"
    rows, err, fatal = parse_shipment_csv_text(text)
    assert fatal is None
    assert err == 0
    assert len(rows) == 1
    assert rows[0]["product_code"] == "B002"
    assert rows[0]["ship_qty"] == 15.0
    assert rows[0]["due_date"] == "2026-06-23"


def test_company_override_extends_aliases():
    headers = ["独自品番", "商品名", "在庫数"]
    colmap = resolve_header_indices(
        headers,
        "stock",
        company_overrides={"product_code": ["独自品番"]},
    )
    assert colmap == {"product_code": 0, "label": 1, "stock_qty": 2}


def test_normalize_header_cell_nfkc():
    assert normalize_header_cell(" 商品ＣＤ ") == "商品cd"


def test_export_schema_for_client(client):
    r = client.get("/v2/csv/import-schemas/stock")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema"] == "stock"
    assert "product_code" in body["aliases"]
    assert "品番" in body["aliases"]["product_code"]

    r404 = client.get("/v2/csv/import-schemas/unknown")
    assert r404.status_code == 404

    exported = export_schema_for_client("shipment")
    assert "出荷予定数" in exported["aliases"]["ship_qty"]
