"""field_users 工程表示名の解決。"""

from __future__ import annotations

from app.services.field_users import (
    build_process_id_display_map,
    is_internal_process_id,
    resolve_process_display_name,
)


def test_is_internal_process_id():
    assert is_internal_process_id("proc_01")
    assert is_internal_process_id("a")
    assert not is_internal_process_id("組立")
    assert not is_internal_process_id("工程1")


def test_resolve_process_display_from_leader_master():
    field = "A:工程1,B:工程2,C:工程3,D:工程4"
    rows = [
        {"process_id": "a", "user_id": "A"},
        {"process_id": "b", "user_id": "B"},
        {"process_id": "proc_01", "user_id": "C:工程3"},
    ]
    pid_map = build_process_id_display_map(rows, field)
    assert resolve_process_display_name(
        process_id="a",
        user_id="A",
        field_users_raw=field,
        process_id_label_map=pid_map,
    ) == "工程1"
    assert resolve_process_display_name(
        process_id="proc_01",
        user_id="C:工程3",
        field_users_raw=field,
        process_id_label_map=pid_map,
    ) == "工程3"
    assert resolve_process_display_name(
        process_id="proc_99",
        user_id="unknown",
        field_users_raw=field,
        process_id_label_map=pid_map,
    ) == "（未設定）"


def test_build_process_id_display_map_from_user_suffix():
    field = ""
    rows = [{"process_id": "proc_01", "user_id": "班長:工程1"}]
    pid_map = build_process_id_display_map(rows, field)
    assert pid_map["proc_01"] == "工程1"
