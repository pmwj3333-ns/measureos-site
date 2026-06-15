"""Audit Head: 監査・観測用の代表行選定（Editing Head = id 最大とは別）。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def natural_key(row: dict) -> Tuple[Any, ...]:
    return (
        row.get("company_id"),
        row.get("task_id"),
        row.get("process_id"),
        row.get("user_id"),
        row.get("business_date"),
    )


def _has_timestamp(value: object) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def is_completely_empty_shell(row: dict) -> bool:
    """planned_at / started_at / actual_at がすべて null の完全空シェル。"""
    return (
        not _has_timestamp(row.get("planned_at"))
        and not _has_timestamp(row.get("started_at"))
        and not _has_timestamp(row.get("actual_at"))
    )


def is_successor_shell(row: dict, versions: List[dict]) -> bool:
    """
    実績報告後の次サイクル空シェル（574 の後の 575 型）。
    完全空シェルかつ、同一 NK に actual_at ありの先行 revision がある。
    """
    if not is_completely_empty_shell(row):
        return False
    rid = int(row.get("id") or 0)
    for v in versions:
        if int(v.get("id") or 0) >= rid:
            continue
        if _has_timestamp(v.get("actual_at")):
            return True
    return False


def is_audit_candidate(row: dict, versions: List[dict]) -> bool:
    """監査候補行。完全空シェル・Successor Shell は対象外。"""
    if is_completely_empty_shell(row):
        return False
    if is_successor_shell(row, versions):
        return False
    return True


def select_audit_head_for_nk(versions: List[dict]) -> Optional[dict]:
    """同一 NK 内で id 降順に走査し、最初の監査候補行を返す。"""
    if not versions:
        return None
    for row in sorted(versions, key=lambda r: int(r.get("id") or 0), reverse=True):
        if is_audit_candidate(row, versions):
            return row
    return None


def audit_heads_from_rows(rows: List[dict]) -> List[dict]:
    """全行から NK ごとに Audit Head を 1 行ずつ選定。"""
    grouped: Dict[Tuple[Any, ...], List[dict]] = defaultdict(list)
    for row in rows or []:
        if not row:
            continue
        grouped[natural_key(row)].append(row)
    out: List[dict] = []
    for versions in grouped.values():
        head = select_audit_head_for_nk(versions)
        if head is not None:
            out.append(head)
    return out


def group_rows_by_natural_key(rows: List[dict]) -> Dict[Tuple[Any, ...], List[dict]]:
    grouped: Dict[Tuple[Any, ...], List[dict]] = defaultdict(list)
    for row in rows or []:
        if not row:
            continue
        grouped[natural_key(row)].append(row)
    return grouped


def audit_episode_heads_from_rows(
    rows: List[dict],
    *,
    has_anomaly_occurrence: Callable[[dict], bool],
) -> List[dict]:
    """
    月報監査 KPI 用: NK 内の異常エピソード代表行（actual_at 単位）。
    Successor Shell / 完全空シェルは除外。close スナップショット（576 型）は
    同一 actual_at の最小 id（574 型）に集約する。
    """
    grouped = group_rows_by_natural_key(rows)
    episodes: List[dict] = []
    for versions in grouped.values():
        candidates: List[dict] = []
        for row in versions:
            if not is_audit_candidate(row, versions):
                continue
            if not has_anomaly_occurrence(row):
                continue
            if not _has_timestamp(row.get("actual_at")):
                continue
            candidates.append(row)
        by_actual: Dict[str, dict] = {}
        for row in candidates:
            actual_key = str(row.get("actual_at"))
            rid = int(row.get("id") or 0)
            prev = by_actual.get(actual_key)
            if prev is None or rid < int(prev.get("id") or 0):
                by_actual[actual_key] = row
        episodes.extend(by_actual.values())
    episodes.sort(key=lambda r: int(r.get("id") or 0))
    return episodes


def is_audit_episode_confirmed(
    head: dict,
    versions: List[dict],
    suppressed_peer_ids: Set[int],
) -> bool:
    """
    異常エピソードが事務確認済みか。
    POST /work/{id}/close による closed スナップショット、または suppress 登録。
    """
    hid = int(head.get("id") or 0)
    if (head.get("status") or "").strip().lower() == "closed":
        return True
    if hid in suppressed_peer_ids:
        return True
    head_actual = head.get("actual_at")
    if not _has_timestamp(head_actual):
        return False
    head_actual_s = str(head_actual)
    for row in versions:
        rid = int(row.get("id") or 0)
        if rid <= hid:
            continue
        if (row.get("status") or "").strip().lower() != "closed":
            continue
        if _has_timestamp(row.get("actual_at")) and str(row.get("actual_at")) == head_actual_s:
            return True
    return False
