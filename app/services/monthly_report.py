"""社労士向け月報: 対象月の work_unit / priority_item から自動集計。"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app import models
from app.routers.work import _get_or_create_settings, _unit_to_out
from app.services.company_validator import validate_company_id
from app.services.field_users import (
    build_process_id_display_map,
    leader_name_from_user_id,
    resolve_process_display_name,
)
from app.services.business_date import effective_calendar_date_jst
from app.services.judgement_promote import reference_now_jst
from app.services.package_a_observe import (
    _natural_key,
)
from app.services.anomaly_classification import aggregate_field_classification
from app.services.audit_head import (
    audit_episode_heads_from_rows,
    audit_heads_from_rows,
    group_rows_by_natural_key,
    is_audit_episode_confirmed,
)


def parse_target_month(raw: str) -> Tuple[str, date, date]:
    """YYYY-MM → (正規化文字列, 月初, 月末)。"""
    s = (raw or "").strip()
    if len(s) != 7 or s[4] != "-":
        raise ValueError("target_month は YYYY-MM 形式で指定してください")
    year = int(s[:4])
    month = int(s[5:7])
    if month < 1 or month > 12:
        raise ValueError("target_month の月が不正です")
    last_day = calendar.monthrange(year, month)[1]
    return s, date(year, month, 1), date(year, month, last_day)


def previous_target_month(target_month: str) -> str:
    y, m = map(int, target_month.split("-"))
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


def target_month_label(target_month: str) -> str:
    y, m = map(int, target_month.split("-"))
    return f"{y}年{m}月"


def _month_dt_range(month_start: date, month_end: date) -> Tuple[datetime, datetime]:
    start = datetime.combine(month_start, time.min)
    end = datetime.combine(month_end, time(23, 59, 59))
    return start, end


def _row_incomplete(r: dict) -> bool:
    """対象月終了時点で actual_at なし = 未完了。"""
    return not bool(r.get("actual_at"))


def _row_started_without_planned(r: dict) -> bool:
    return bool(r.get("started_at")) and not r.get("planned_registered_at")


def _row_completed(r: dict) -> bool:
    """actual_at あり = 完了（status は判定に使わない）。"""
    return bool(r.get("actual_at"))


# ── 異常発生内訳（anomaly_breakdown）────────────────────────────────────
#
# 各異常を独立集計（1 作業が複数区分に該当しうる）。
# status=closed でも件数は減らさない（発生した事実）。
#
ANOMALY_BREAKDOWN_SPECS: Tuple[Tuple[str, str], ...] = (
    ("carryover", "持ち越し"),
    ("invalid_flow", "順序不備"),
    ("diff_anomaly", "結果不備"),
    ("deviation", "第7条例外"),
    ("unregistered_user", "未登録ユーザー"),
)

ANOMALY_BREAKDOWN_NOTE = (
    "各区分は独立集計です。"
    "同一作業が複数項目に計上される場合があります。"
    "確認済み（closed）になっても、ここの件数は減りません。"
)

AUDIT_BREAKDOWN_SPECS: Tuple[Tuple[str, str], ...] = (
    ("blue", "未確認"),
    ("closed", "確認済み"),
    ("red", "期限超過"),
)

AUDIT_BREAKDOWN_NOTE = (
    "監査対応状況は、異常が発生した作業に対する事務確認の進捗を表します。"
    "確認済みは異常解消ではなく、事務確認完了を意味します。"
)


def _parse_row_business_date(r: dict) -> Optional[date]:
    raw = r.get("business_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _row_carryover_occurrence(r: dict, settings: models.CompanySettings) -> bool:
    """発生事実: actual_at なし・effective_date > business_date（status 無視）。"""
    if r.get("actual_at"):
        return False
    bd = _parse_row_business_date(r)
    if bd is None:
        return False
    effective = effective_calendar_date_jst(
        reference_now_jst(), settings.day_boundary_time
    )
    return effective > bd


def _row_has_anomaly_occurrence(r: dict, settings: models.CompanySettings) -> bool:
    return (
        _row_carryover_occurrence(r, settings)
        or r.get("is_invalid_flow") is True
        or r.get("is_diff_anomaly") is True
        or r.get("is_deviation") is True
        or r.get("is_article7_deviation") is True
        or r.get("is_unregistered_user") is True
    )


def _after_cutoff_order_count(
    db: Session,
    company_id: str,
    month_start: date,
    month_end: date,
) -> int:
    """対象月に作成され is_after_cutoff の priority_item（第3条・締切後受注）。"""
    start_dt, end_dt = _month_dt_range(month_start, month_end)
    return (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == company_id)
        .filter(models.PriorityItem.is_after_cutoff.is_(True))
        .filter(models.PriorityItem.created_at >= start_dt)
        .filter(models.PriorityItem.created_at <= end_dt)
        .count()
    )


def _count_anomaly_breakdown(
    rows: List[dict],
    settings: models.CompanySettings,
) -> List[dict]:
    totals = {key: 0 for key, _ in ANOMALY_BREAKDOWN_SPECS}
    for r in rows:
        if _row_carryover_occurrence(r, settings):
            totals["carryover"] += 1
        if r.get("is_invalid_flow") is True:
            totals["invalid_flow"] += 1
        if r.get("is_diff_anomaly") is True:
            totals["diff_anomaly"] += 1
        if r.get("is_deviation") is True or r.get("is_article7_deviation") is True:
            totals["deviation"] += 1
        if r.get("is_unregistered_user") is True:
            totals["unregistered_user"] += 1
    return [{"key": key, "label": label, "count": totals[key]} for key, label in ANOMALY_BREAKDOWN_SPECS]


def _audit_response_rate(confirmed_count: int, audit_target_count: int) -> float:
    if audit_target_count <= 0:
        return 0.0
    return round(confirmed_count * 100.0 / audit_target_count, 1)


def _count_audit_breakdown(
    raw_rows: List[dict],
    settings: models.CompanySettings,
    suppressed_peer_ids: Set[int],
) -> dict:
    """
    監査対応状況（Audit Head / 異常エピソードベース）。
    merge 行ではなく actual_at 単位のエピソード代表 + close / suppress 判定。
    """
    grouped = group_rows_by_natural_key(raw_rows)
    has_occ = lambda r: _row_has_anomaly_occurrence(r, settings)
    episodes = audit_episode_heads_from_rows(raw_rows, has_anomaly_occurrence=has_occ)
    totals = {key: 0 for key, _ in AUDIT_BREAKDOWN_SPECS}
    for head in episodes:
        versions = grouped.get(
            (
                head.get("company_id"),
                head.get("task_id"),
                head.get("process_id"),
                head.get("user_id"),
                head.get("business_date"),
            ),
            [],
        )
        if is_audit_episode_confirmed(head, versions, suppressed_peer_ids):
            totals["closed"] += 1
            continue
        st = (head.get("status") or "normal").strip().lower()
        if st == "red":
            totals["red"] += 1
        else:
            totals["blue"] += 1
    confirmed = totals["closed"]
    target = len(episodes)
    return {
        "audit_target_count": target,
        "audit_response_rate": _audit_response_rate(confirmed, target),
        "audit_breakdown": [
            {"key": key, "label": label, "count": totals[key]}
            for key, label in AUDIT_BREAKDOWN_SPECS
        ],
        "audit_breakdown_note": AUDIT_BREAKDOWN_NOTE,
    }


def _load_suppressed_peer_ids(db: Session, raw_rows: List[dict]) -> Set[int]:
    ids = {int(r.get("id") or 0) for r in raw_rows if r.get("id") is not None}
    if not ids:
        return set()
    rows = (
        db.query(models.OfficeClosedWorkUnitSuppress.peer_unit_id)
        .filter(models.OfficeClosedWorkUnitSuppress.peer_unit_id.in_(ids))
        .all()
    )
    return {int(r[0]) for r in rows}


def _count_rows(
    rows: List[dict],
    field_users_raw: str = "",
    *,
    settings: models.CompanySettings,
) -> dict:
    pid_map = build_process_id_display_map(rows, field_users_raw)
    by_process: Dict[str, int] = {}
    by_leader: Dict[str, int] = {}
    for r in rows:
        proc = resolve_process_display_name(
            process_id=str(r.get("process_id") or ""),
            user_id=str(r.get("user_id") or ""),
            field_users_raw=field_users_raw,
            process_id_label_map=pid_map,
        )
        leader = leader_name_from_user_id(str(r.get("user_id") or "")) or "（未設定）"
        by_process[proc] = by_process.get(proc, 0) + 1
        by_leader[leader] = by_leader.get(leader, 0) + 1

    def _sorted_rows(d: Dict[str, int]) -> List[dict]:
        return [
            {"label": k, "count": v}
            for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0]))
        ]

    breakdown = _count_anomaly_breakdown(rows, settings)
    anomaly_count = sum(item["count"] for item in breakdown)

    return {
        "total_work_count": len(rows),
        "completed_count": sum(1 for r in rows if _row_completed(r)),
        "planned_registered_count": sum(1 for r in rows if r.get("planned_registered_at")),
        "actual_registered_count": sum(1 for r in rows if r.get("actual_at")),
        "started_without_planned_count": sum(
            1 for r in rows if _row_started_without_planned(r)
        ),
        "incomplete_count": sum(1 for r in rows if _row_incomplete(r)),
        "anomaly_count": anomaly_count,
        "anomaly_breakdown": breakdown,
        "anomaly_breakdown_note": ANOMALY_BREAKDOWN_NOTE,
        "by_process": _sorted_rows(by_process),
        "by_leader": _sorted_rows(by_leader),
    }


def _priority_counts(
    db: Session,
    company_id: str,
    month_start: date,
    month_end: date,
) -> Tuple[int, int]:
    start_dt, end_dt = _month_dt_range(month_start, month_end)
    items = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == company_id)
        .all()
    )
    article7 = 0
    after_cutoff = 0
    for item in items:
        created = getattr(item, "created_at", None)
        in_month = created is not None and start_dt <= created <= end_dt
        if in_month:
            article7 += 1
            if bool(getattr(item, "is_after_cutoff", False)):
                after_cutoff += 1
        elif bool(getattr(item, "is_after_cutoff", False)) and (
            getattr(item, "status", "") or ""
        ).lower() == "open":
            due = (getattr(item, "due_date", None) or "").strip()
            if due.startswith(month_start.strftime("%Y-%m")):
                after_cutoff += 1
    return article7, after_cutoff


def _merge_month_versions(raw_rows: List[dict]) -> List[dict]:
    """同一 natural key の月内全バージョンをマージ（最新行 + 累積フラグ）。"""
    grouped: Dict[Tuple, List[dict]] = {}
    for r in raw_rows:
        grouped.setdefault(_natural_key(r), []).append(r)
    merged: List[dict] = []
    for versions in grouped.values():
        latest = max(versions, key=lambda x: int(x.get("id") or 0))
        row = dict(latest)
        if any(v.get("planned_registered_at") for v in versions):
            row["planned_registered_at"] = next(
                v.get("planned_registered_at")
                for v in versions
                if v.get("planned_registered_at")
            )
        if any(v.get("actual_at") for v in versions):
            row["actual_at"] = next(
                v.get("actual_at") for v in versions if v.get("actual_at")
            )
        if any(_row_started_without_planned(v) for v in versions):
            row["started_at"] = row.get("started_at") or next(
                (v.get("started_at") for v in versions if v.get("started_at")),
                None,
            )
            if not row.get("planned_registered_at"):
                row["planned_registered_at"] = None
        for flag in (
            "is_diff_anomaly",
            "is_invalid_flow",
            "is_missing",
            "is_deviation",
            "is_article7_deviation",
            "is_unregistered_user",
        ):
            if any(v.get(flag) is True for v in versions):
                row[flag] = True
        merged.append(row)
    return merged


def _load_month_raw_rows(
    db: Session,
    company_id: str,
    month_start: date,
    month_end: date,
) -> List[dict]:
    settings = _get_or_create_settings(company_id, db)
    units = (
        db.query(models.WorkUnit)
        .filter(models.WorkUnit.company_id == company_id)
        .filter(models.WorkUnit.business_date >= month_start)
        .filter(models.WorkUnit.business_date <= month_end)
        .order_by(models.WorkUnit.id.asc())
        .all()
    )
    return [_unit_to_out(u, settings, db, None, office_chain_hint="") for u in units]


def _load_month_work_rows(
    db: Session,
    company_id: str,
    month_start: date,
    month_end: date,
) -> List[dict]:
    return _merge_month_versions(
        _load_month_raw_rows(db, company_id, month_start, month_end)
    )


def compute_monthly_metrics(
    db: Session,
    company_id: str,
    target_month: str,
) -> dict:
    _, month_start, month_end = parse_target_month(target_month)
    settings = _get_or_create_settings(company_id, db)
    raw_rows = _load_month_raw_rows(db, company_id, month_start, month_end)
    suppressed_peer_ids = _load_suppressed_peer_ids(db, raw_rows)
    rows = _merge_month_versions(raw_rows)
    metrics = _count_rows(
        rows,
        settings.field_users or "",
        settings=settings,
    )
    audit = _count_audit_breakdown(raw_rows, settings, suppressed_peer_ids)
    metrics["audit_target_count"] = audit["audit_target_count"]
    metrics["audit_response_rate"] = audit["audit_response_rate"]
    metrics["audit_breakdown"] = audit["audit_breakdown"]
    metrics["audit_breakdown_note"] = audit["audit_breakdown_note"]
    metrics["field_classification_breakdown"] = aggregate_field_classification(
        audit_heads_from_rows(raw_rows)
    )
    article7, after_cutoff = _priority_counts(db, company_id, month_start, month_end)
    metrics["article7_count"] = article7
    metrics["after_cutoff_count"] = after_cutoff
    return metrics


def generate_monthly_summary(
    metrics: dict,
    *,
    target_month_label: str = "",
) -> str:
    parts: List[str] = []
    label = target_month_label or "今月"
    parts.append(f"{label}は総作業数{metrics.get('total_work_count', 0)}件。")

    completed = int(metrics.get("completed_count") or 0)
    incomplete = int(metrics.get("incomplete_count") or 0)
    parts.append(f"実績入力済み{completed}件、実績未入力{incomplete}件。")

    by_process = metrics.get("by_process") or []
    if by_process:
        top = by_process[0]
        if int(top.get("count") or 0) > 0:
            parts.append(f"作業件数は{top.get('label')}が最多（{top.get('count')}件）。")

    anomaly_parts: List[str] = []
    for row in metrics.get("anomaly_breakdown") or []:
        count = int(row.get("count") or 0)
        if count > 0:
            anomaly_parts.append(f"{row.get('label')}{count}件")
    if anomaly_parts:
        parts.append("、".join(anomaly_parts) + "が発生。")

    audit_target = int(metrics.get("audit_target_count") or 0)
    if audit_target > 0:
        audit_map = {
            r.get("key"): int(r.get("count") or 0)
            for r in metrics.get("audit_breakdown") or []
        }
        blue_n = audit_map.get("blue", 0)
        closed_n = audit_map.get("closed", 0)
        rate = float(metrics.get("audit_response_rate") or 0.0)
        parts.append(
            f"異常発生作業{audit_target}件のうち、"
            f"確認済み{closed_n}件（{rate:g}%）、"
            f"未確認{blue_n}件"
            f"（異常解消ではなく確認完了）。"
        )

    return "".join(parts)


def _company_display_name(db: Session, company_id: str) -> str:
    settings = (
        db.query(models.CompanySettings)
        .filter(models.CompanySettings.company_id == company_id)
        .first()
    )
    if settings and (settings.company_name or "").strip():
        return (settings.company_name or "").strip()
    master = (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == company_id)
        .first()
    )
    if master and (master.company_name or "").strip():
        return (master.company_name or "").strip()
    return company_id


def build_monthly_report_aggregate(
    db: Session,
    company_id: str,
    target_month: str,
) -> dict:
    cid = validate_company_id(db, company_id)
    norm_month, _, _ = parse_target_month(target_month)
    metrics = compute_monthly_metrics(db, cid, norm_month)
    prev_month = previous_target_month(norm_month)
    try:
        previous_metrics = compute_monthly_metrics(db, cid, prev_month)
    except ValueError:
        previous_metrics = None

    month_label = target_month_label(norm_month)
    generated_summary = generate_monthly_summary(
        metrics,
        target_month_label=month_label,
    )

    saved = (
        db.query(models.MonthlyReport)
        .filter(models.MonthlyReport.company_id == cid)
        .filter(models.MonthlyReport.target_month == norm_month)
        .order_by(models.MonthlyReport.id.desc())
        .first()
    )

    return {
        "company_id": cid,
        "company_name": _company_display_name(db, cid),
        "target_month": norm_month,
        "target_month_label": month_label,
        "metrics": metrics,
        "previous_metrics": previous_metrics,
        "generated_summary": generated_summary,
        "consultant_comment": (saved.consultant_comment or "") if saved else "",
        "saved_report_id": saved.id if saved else None,
        "saved_at": saved.created_at.isoformat() + "Z"
        if saved and saved.created_at
        else None,
    }


def save_monthly_report(
    db: Session,
    *,
    company_id: str,
    target_month: str,
    generated_summary: str,
    consultant_comment: str,
) -> models.MonthlyReport:
    cid = validate_company_id(db, company_id)
    norm_month, _, _ = parse_target_month(target_month)
    now = datetime.utcnow()
    row = (
        db.query(models.MonthlyReport)
        .filter(models.MonthlyReport.company_id == cid)
        .filter(models.MonthlyReport.target_month == norm_month)
        .first()
    )
    if row is None:
        row = models.MonthlyReport(
            company_id=cid,
            target_month=norm_month,
            generated_summary=(generated_summary or "").strip(),
            consultant_comment=(consultant_comment or "").strip(),
            created_at=now,
        )
        db.add(row)
    else:
        row.generated_summary = (generated_summary or "").strip()
        row.consultant_comment = (consultant_comment or "").strip()
        row.created_at = now
    db.commit()
    db.refresh(row)
    return row
