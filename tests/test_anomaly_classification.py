"""第5条: 現場 A/B 中分類（anomaly_classification_json）。"""
from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from app.services.anomaly_classification import (
    build_storage_from_request,
    parse_classification_json,
)

CO = "planned_reg_test_co"
TASK = "task_ac"
PROC = "proc_ac"
BD = "2026-05-10"
USER = "班長:中分類テスト"


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


def _actual(client: TestClient, uid: int, payload: dict) -> dict:
    base = {
        "deviation_reason": "中分類テスト（7条逸脱許容）",
    }
    base.update(payload)
    r = client.post(f"/v2/work/{uid}/actual", json=base)
    assert r.status_code == 200, r.text
    return r.json()


def test_build_storage_parent_a_only_empty_subs():
    blob, pa, pb, up = build_storage_from_request(
        {"process": [], "result": []},
        parent_process=True,
        parent_result=False,
    )
    assert pa is True
    assert pb is False
    assert up is None
    assert blob == json.dumps({"process": []}, ensure_ascii=False, separators=(",", ":"))


def test_build_storage_nested_subs():
    blob, pa, pb, up = build_storage_from_request(
        {
            "process": ["handoff_missing", "deferred"],
            "result": ["material_shortage"],
        },
        parent_process=True,
        parent_result=True,
    )
    assert pa is True
    assert pb is True
    assert up == "B"
    parsed = json.loads(blob or "{}")
    assert parsed["process"] == ["handoff_missing", "deferred"]
    assert parsed["result"] == ["material_shortage"]


def test_build_storage_clears_subs_when_parent_off():
    blob, pa, pb, up = build_storage_from_request(
        {
            "process": ["handoff_missing"],
            "result": ["material_shortage"],
        },
        parent_process=False,
        parent_result=False,
    )
    assert blob is None
    assert pa is False
    assert pb is False
    assert up is None


def test_actual_save_parent_a_only_without_subs(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    body = _actual(
        client,
        uid,
        {
            "lines": [{"label": "商品A", "value": 1}],
            "pattern_a": True,
            "pattern_b": False,
            "anomaly_classification": {"process": [], "result": []},
        },
    )
    assert body["pattern_a"] is True
    assert body["pattern_b"] is False
    assert body.get("anomaly_classification") == {"process": []}


def test_actual_save_with_subcategories(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    body = _actual(
        client,
        uid,
        {
            "lines": [{"label": "商品B", "value": 2}],
            "pattern_a": True,
            "pattern_b": True,
            "anomaly_classification": {
                "process": ["handoff_missing", "deferred"],
                "result": ["material_shortage"],
            },
        },
    )
    assert body["pattern_a"] is True
    assert body["pattern_b"] is True
    assert body["user_pattern"] == "B"
    assert body["anomaly_classification"] == {
        "process": ["handoff_missing", "deferred"],
        "result": ["material_shortage"],
    }


def test_actual_save_without_classification_legacy(client: TestClient):
    w = _shell(client)
    uid = w["id"]
    body = _actual(
        client,
        uid,
        {
            "lines": [{"label": "商品C", "value": 3}],
            "pattern_a": False,
            "pattern_b": False,
        },
    )
    assert body["pattern_a"] is False
    assert body["pattern_b"] is False
    assert body.get("anomaly_classification") is None


def test_parse_classification_json_roundtrip():
    raw = '{"process":["deferred"],"result":["work_error"]}'
    parsed = parse_classification_json(raw)
    assert parsed == {"process": ["deferred"], "result": ["work_error"]}


def test_field_v2_html_has_anomaly_subcategories():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "frontend" / "field_v2.html").read_text(
        encoding="utf-8"
    )
    assert 'data-anomaly-code="handoff_missing"' in html
    assert 'data-anomaly-code="material_shortage"' in html
    assert "anomaly-classification.js" in html
    assert "anomaly_classification" in html


def test_office_v2_html_shows_field_classification_detail():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "frontend" / "office_v2.html").read_text(
        encoding="utf-8"
    )
    assert "現場分類" in html
    assert "formatDetailBlock" in html or "MO_ANOMALY_CLASSIFICATION" in html
    assert "anomaly-classification.js" in html
