"""予告の draft（未登録）と正式登録（planned_registered_at）の分離。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.conftest import v2_register_planned, v2_start

CO = "planned_reg_test_co"
TASK = "task_pr"
PROC = "proc_pr"
BD = "2026-05-01"
USER = "班長:予告登録テスト"


def _shell(client: TestClient) -> dict:
    r = client.post(
        "/v2/work",
        json={
            "company_id": CO,
            "task_id": TASK,
            "process_id": PROC,
            "user_id": USER,
            "business_date": BD,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_start_without_planned_registration_returns_422(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    r = client.post(f"/v2/work/{uid}/start", json={})
    assert r.status_code == 422, r.text
    assert "予告登録" in r.json()["detail"]


def test_start_with_empty_planned_registration(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    reg = v2_register_planned(client, uid, lines=[])
    assert reg.get("planned_registered_at")
    assert not (reg.get("planned_lines") or [])
    assert not reg.get("planned_at")
    started = v2_start(client, reg["id"])
    assert started.get("started_at")
    assert started.get("planned_registered_at")


def test_start_when_registered_ignores_body_lines(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    reg = v2_register_planned(
        client, uid, lines=[{"label": "正式A", "value": 1}]
    )
    uid2 = reg["id"]
    r2 = client.post(
        f"/v2/work/{uid2}/start",
        json={"lines": [{"label": "改ざん試行", "value": 99}]},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    lines = body.get("planned_lines") or []
    assert len(lines) == 1
    assert lines[0]["label"] == "正式A"
    assert float(lines[0]["value"]) == 1.0


def test_planned_post_sets_registered_at(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    r = client.post(
        f"/v2/work/{uid}/planned",
        json={"lines": [{"label": "商品Z", "value": 3}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("planned_registered_at")
    assert body.get("planned_lines")
    assert body["planned_lines"][0]["label"] == "商品Z"


def test_planned_post_allows_empty_lines(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    r = client.post(f"/v2/work/{uid}/planned", json={"lines": []})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("planned_registered_at")
    assert not (body.get("planned_lines") or [])
    assert body.get("planned_at") is None


def test_planned_post_allows_label_without_quantity(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    r = client.post(
        f"/v2/work/{uid}/planned",
        json={"lines": [{"label": "商品Qのみ"}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("planned_registered_at")
    lines = body.get("planned_lines") or []
    assert len(lines) == 1
    assert lines[0]["label"] == "商品Qのみ"
    assert lines[0].get("value") is None
    assert body.get("planned_value") is None


def test_actual_post_rejects_label_without_quantity(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    r = client.post(
        f"/v2/work/{uid}/actual",
        json={
            "lines": [{"label": "実績は数量必須"}],
            "pattern_a": False,
            "pattern_b": False,
        },
    )
    assert r.status_code == 422, r.text


def test_post_work_resumes_open_row_after_start(client: TestClient):
    """同日キーで着手済み・未報告なら POST /work は新規 INSERT せず同一系の最新行を返す。"""
    w1 = _shell(client)
    uid = w1["id"]
    reg = v2_register_planned(client, uid, lines=[])
    started = v2_start(client, reg["id"])
    assert started.get("started_at")
    tip_id = started["id"]
    w2 = _shell(client)
    assert w2["id"] == tip_id
    assert w2.get("started_at")


def test_post_work_new_shell_after_actual(client: TestClient):
    """実績報告済み（actual_at あり）のあと POST /work は新しい未報告行を作る。"""
    w = _shell(client)
    uid = w["id"]
    reg = v2_register_planned(client, uid, lines=[])
    uid = v2_start(client, reg["id"])["id"]
    done = client.post(
        f"/v2/work/{uid}/actual",
        json={
            "lines": [{"label": "商品R", "value": 1}],
            "pattern_a": False,
            "pattern_b": False,
            "deviation_reason": "統合テスト（7条逸脱許容）",
        },
    )
    assert done.status_code == 200, done.text
    done_body = done.json()
    assert done_body.get("actual_at")
    done_id = done_body["id"]
    w2 = _shell(client)
    assert w2["id"] > done_id
    assert not w2.get("actual_at")


def test_empty_actual_report_classified_as_b_not_a(client: TestClient):
    """予告（空）→ 着手 → 実績内容なしは B* / is_diff_anomaly。"""
    w = _shell(client)
    reg = v2_register_planned(client, w["id"], lines=[])
    started = v2_start(client, reg["id"])
    done = client.post(f"/v2/work/{started['id']}/actual", json={"lines": []})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body.get("actual_at")
    assert not (body.get("actual_lines") or [])
    assert body.get("system_pattern") == "B*"
    assert body.get("is_invalid_flow") is False
    assert body.get("is_diff_anomaly") is True
    assert body.get("status") == "blue"
