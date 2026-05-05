"""
office_v2「実績（最新のみ）」の商品単位集約・訂正の統合テスト。

ケース①〜④は要件どおり DB に実績を積み、GET /v2/work/list と
tests/office_latest_aggregate.collect_latest_slices で検証する。
一覧の status が normal になるよう、各ケースで予告→着手→実績とする（着手なし実績は blue となり下段から除外される）。
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.office_latest_aggregate import collect_latest_slices, norm_office_ws

CO = "office_v2_agg_test_co"
TASK = "task_office_agg"
PROC = "proc_office_agg"
BD = "2026-04-04"
USER_YON = "田中四:オフィステスト"
USER_SAN = "田中三:オフィステスト"


def _shell(client: TestClient, user_id: str) -> dict:
    r = client.post(
        "/v2/work",
        json={
            "company_id": CO,
            "task_id": TASK,
            "process_id": PROC,
            "user_id": user_id,
            "business_date": BD,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _planned(client: TestClient, unit_id: int, label: str, qty: float) -> dict:
    r = client.post(
        f"/v2/work/{unit_id}/planned",
        json={"lines": [{"label": label, "value": qty}]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _start(client: TestClient, unit_id: int) -> dict:
    r = client.post(f"/v2/work/{unit_id}/start")
    assert r.status_code == 200, r.text
    return r.json()


def _actual(client: TestClient, unit_id: int, label: str, qty: float) -> dict:
    r = client.post(
        f"/v2/work/{unit_id}/actual",
        json={
            "lines": [{"label": label, "value": qty}],
            "pattern_a": False,
            "pattern_b": False,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _planned_start_actual(
    client: TestClient, shell_unit_id: int, label: str, qty: float
) -> dict:
    """append-only のため各 POST の返却 id を繋ぎ、実績一覧が blue にならないよう予告→着手→実績とする。"""
    uid = _planned(client, shell_unit_id, label, qty)["id"]
    uid = _start(client, uid)["id"]
    return _actual(client, uid, label, qty)


@pytest.fixture(autouse=True)
def _seed_article7_labels_for_integration(client: TestClient):
    """実績ラベルを open の第7条に載せ、逸脱・青 status を避ける（下段実績一覧テスト用）。"""
    r = client.post(
        "/v2/priority/create",
        json={
            "company_id": CO,
            "items": [
                {
                    "label": "商品A",
                    "ship_value": 100.0,
                    "prod_value": 50.0,
                    "due_date": "2026-12-31",
                },
                {
                    "label": "商品B",
                    "ship_value": 100.0,
                    "prod_value": 50.0,
                    "due_date": "2026-12-31",
                },
                {
                    "label": "商品C",
                    "ship_value": 100.0,
                    "prod_value": 50.0,
                    "due_date": "2026-12-31",
                },
            ],
        },
    )
    assert r.status_code == 200, r.text


def _list(client: TestClient) -> list:
    r = client.get("/v2/work/list", params={"company_id": CO})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    return data


def test_same_product_latest_overwrites_and_revision_when_qty_changes(
    client: TestClient,
):
    """① 同一商品の上書き（別商品はまだ無い状態で訂正も確認）。"""
    _label = "商品A"
    _qty_a = 10.0
    _qty_b = 20.0
    w1 = _shell(client, USER_YON)
    first = _planned_start_actual(client, w1["id"], _label, _qty_a)

    rows_mid = _list(client)
    slices_mid = collect_latest_slices(rows_mid)
    assert len(slices_mid) == 1
    assert float(slices_mid[0]["office_unit_row"]["actual_lines"][0]["value"]) == _qty_a
    assert slices_mid[0]["office_unit_row"]["id"] == first["id"]
    assert first.get("is_actual_revision") is False

    w2 = _shell(client, USER_YON)
    second = _planned_start_actual(client, w2["id"], _label, _qty_b)

    rows = _list(client)
    slices = collect_latest_slices(rows)
    pk = norm_office_ws(_label)

    assert len(slices) == 1
    assert slices[0]["office_product_key"] == pk
    row = slices[0]["office_unit_row"]
    assert row["id"] == second["id"]
    assert row["actual_lines"] and float(row["actual_lines"][0]["value"]) == _qty_b

    assert second.get("is_actual_revision") is True
    detail = second.get("actual_revision_detail_line") or ""
    assert _label in detail
    assert str(int(_qty_a)) in detail or str(_qty_a) in detail
    assert str(int(_qty_b)) in detail or str(_qty_b) in detail
    assert "訂正" in detail


def test_different_products_remain_separate_rows(client: TestClient):
    """② 別商品は別スライスとして残る（①の続きのデータ状態を再現）。"""
    w1 = _shell(client, USER_YON)
    _planned_start_actual(client, w1["id"], "商品A", 10)

    w2 = _shell(client, USER_YON)
    _planned_start_actual(client, w2["id"], "商品A", 20)

    w3 = _shell(client, USER_YON)
    _planned_start_actual(client, w3["id"], "商品B", 10)

    rows = _list(client)
    slices = collect_latest_slices(rows)
    pks = {s["office_product_key"] for s in slices}
    assert pks == {norm_office_ws("商品A"), norm_office_ws("商品B")}
    assert len(slices) == 2
    actual_rows = [r for r in rows if r.get("actual_at")]
    assert len(actual_rows) >= 3
    assert len(slices) < len(actual_rows)

    by_pk = {s["office_product_key"]: s["office_unit_row"] for s in slices}
    assert float(by_pk[norm_office_ws("商品A")]["actual_lines"][0]["value"]) == 20
    assert float(by_pk[norm_office_ws("商品B")]["actual_lines"][0]["value"]) == 10


def test_same_qty_reregister_no_revision(client: TestClient):
    """③ 同一数量の再登録では訂正にならない。"""
    w1 = _shell(client, USER_SAN)
    _planned_start_actual(client, w1["id"], "商品C", 20)

    w2 = _shell(client, USER_SAN)
    second = _planned_start_actual(client, w2["id"], "商品C", 20)

    rows = _list(client)
    slices = collect_latest_slices(rows)
    assert len(slices) == 1
    assert slices[0]["office_product_key"] == norm_office_ws("商品C")

    assert second.get("is_actual_revision") is False
    assert not (second.get("actual_revision_detail_line") or "").strip()


def test_same_product_reappears_after_other_product_only_a_revised(client: TestClient):
    """④ A→B→A の順。一覧は A20 と B10 の2行、訂正は商品Aのみ・B は無変更。"""
    w1 = _shell(client, USER_YON)
    _planned_start_actual(client, w1["id"], "商品A", 10)

    w2 = _shell(client, USER_YON)
    _planned_start_actual(client, w2["id"], "商品B", 10)

    w3 = _shell(client, USER_YON)
    third = _planned_start_actual(client, w3["id"], "商品A", 20)

    rows = _list(client)
    by_id = {r["id"]: r for r in rows}
    slices = collect_latest_slices(rows)

    assert len(slices) == 2
    pk_a = norm_office_ws("商品A")
    pk_b = norm_office_ws("商品B")
    by_pk = {s["office_product_key"]: s for s in slices}

    row_a = by_pk[pk_a]["office_unit_row"]
    row_b = by_pk[pk_b]["office_unit_row"]

    assert row_a["id"] == third["id"]
    assert float(row_a["actual_lines"][0]["value"]) == 20
    assert float(row_b["actual_lines"][0]["value"]) == 10

    assert third.get("is_actual_revision") is True
    detail = third.get("actual_revision_detail_line") or ""
    assert "商品A" in detail and "10" in detail and "20" in detail and "訂正" in detail
    assert "商品B" not in detail

    b_full = by_id[row_b["id"]]
    assert not b_full.get("is_actual_revision")
    assert not (b_full.get("actual_revision_detail_line") or "").strip()


def test_collect_latest_slices_excludes_blue_and_red_status():
    """実績一覧候補から status blue/red を除外（要注意専用・集約ロジックは維持）。"""
    base = {
        "company_id": "c",
        "task_id": "t",
        "process_id": "p",
        "user_id": "u",
        "business_date": "2026-04-04",
        "actual_at": "2026-04-04T12:00:00",
        "actual_lines": [{"label": "商品X", "value": 1}],
    }
    rows = [
        {**base, "id": 1, "status": "blue"},
        {
            **base,
            "id": 2,
            "status": "normal",
            "actual_lines": [{"label": "商品X", "value": 5}],
        },
        {**base, "id": 3, "status": "red", "actual_lines": [{"label": "商品Y", "value": 9}]},
        {
            **base,
            "id": 4,
            "status": "closed",
            "actual_lines": [{"label": "商品Z", "value": 3}],
        },
    ]
    slices = collect_latest_slices(rows)
    pks = {s["office_product_key"] for s in slices}
    assert norm_office_ws("商品X") in pks
    assert norm_office_ws("商品Z") in pks
    assert norm_office_ws("商品Y") not in pks
    by_pk = {s["office_product_key"]: s["office_unit_row"]["id"] for s in slices}
    assert by_pk[norm_office_ws("商品X")] == 2
    assert by_pk[norm_office_ws("商品Z")] == 4
