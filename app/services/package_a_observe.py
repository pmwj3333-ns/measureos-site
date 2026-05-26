"""Package A: 管理者向け現場観測ダッシュボード（読取専用・制御なし）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.routers.work import _get_or_create_settings, _unit_to_out
from app.services.article7_safety_stock import load_safety_stock_by_product_code
from app.services.business_date import calc_business_date

WORK_LIST_LIMIT = 500
ANOMALY_LIMIT = 40


def _natural_key(row: dict) -> Tuple[Any, ...]:
    return (
        row.get("company_id"),
        row.get("task_id"),
        row.get("process_id"),
        row.get("user_id"),
        row.get("business_date"),
    )


def _leader_label(user_id: str) -> str:
    s = (user_id or "").strip()
    for i, ch in enumerate(s):
        if ch in (":", "："):
            name = s[:i].strip()
            return name or s
    return s


def _parse_iso_dt(raw: object) -> Optional[datetime]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _row_observed_at(row: dict) -> Optional[datetime]:
    for key in (
        "actual_at",
        "started_at",
        "planned_registered_at",
        "created_at",
        "anomaly_started_at",
    ):
        dt = _parse_iso_dt(row.get(key))
        if dt is not None:
            return dt
    return None


def _format_observed_time(row: dict) -> str:
    dt = _row_observed_at(row)
    if dt is None:
        return "—"
    # JST 表示（UTC naive は JST とみなさずそのまま HH:mm）
    return dt.strftime("%H:%M")


def passes_observe_anomaly_display(r: dict) -> bool:
    """office_v2 passesOfficeAnomalyDisplay と同等。"""
    st = (r.get("status") or "").lower()
    if st not in ("blue", "red"):
        return False
    if st == "red":
        return True
    if r.get("is_unregistered_user") is True:
        return True
    if r.get("is_article7_deviation") is True or r.get("is_deviation") is True:
        return True
    if r.get("is_diff_anomaly") is True:
        return True
    if r.get("is_invalid_flow") is True:
        return True
    if r.get("is_missing") is True:
        return True
    if str(r.get("system_pattern") or "").strip():
        return True
    return False


def row_planned_unstarted(r: dict) -> bool:
    if not r.get("planned_registered_at"):
        return False
    if r.get("started_at"):
        return False
    if (r.get("status") or "").lower() == "closed":
        return False
    return True


def row_prev_day_incomplete(r: dict, current_biz: date) -> bool:
    bd_raw = r.get("business_date")
    if not bd_raw:
        return False
    try:
        bd = date.fromisoformat(str(bd_raw))
    except ValueError:
        return False
    if bd >= current_biz:
        return False
    if (r.get("status") or "").lower() == "closed":
        return False
    if r.get("is_missing") is True:
        return True
    if r.get("started_at") and not r.get("actual_at"):
        return True
    if r.get("planned_registered_at") and not r.get("actual_at"):
        return True
    return False


def row_exception_input(r: dict) -> bool:
    if r.get("is_deviation") is True or r.get("is_article7_deviation") is True:
        return True
    if r.get("is_unregistered_user") is True:
        return True
    if r.get("is_invalid_flow") is True:
        return True
    return False


def _latest_rows_by_natural_key(rows: List[dict]) -> List[dict]:
    by_nk: Dict[Tuple[Any, ...], dict] = {}
    for r in sorted(rows, key=lambda x: int(x.get("id") or 0)):
        by_nk[_natural_key(r)] = r
    return list(by_nk.values())


def _classify_anomaly_kind(r: dict, current_biz: date) -> str:
    if r.get("is_unregistered_user") is True:
        return "未登録ユーザー"
    if r.get("is_deviation") is True or r.get("is_article7_deviation") is True:
        return "例外入力"
    if r.get("is_diff_anomaly") is True:
        return "数値乖離"
    if r.get("is_invalid_flow") is True:
        return "順序不備"
    if row_planned_unstarted(r):
        return "未着手予告"
    if row_prev_day_incomplete(r, current_biz):
        return "前営業日未完了"
    if r.get("is_missing") is True:
        return "未入力"
    st = (r.get("status") or "").lower()
    if st == "red":
        return "要注意"
    if st == "blue":
        return "要注意（青）"
    return "観測"


def _anomaly_content(r: dict) -> str:
    parts: List[str] = []
    sp = str(r.get("system_pattern") or "").strip()
    if sp:
        parts.append(sp)
    dr = str(r.get("deviation_reason") or "").strip()
    if dr:
        parts.append(dr)
    if r.get("is_diff_anomaly") is True:
        pv = r.get("planned_value")
        av = r.get("actual_value")
        if pv is not None or av is not None:
            parts.append(f"予告 {pv} / 実績 {av}")
    if row_planned_unstarted(r):
        parts.append("予告登録済み・着手前")
    if not parts:
        bd = r.get("business_date") or ""
        parts.append(f"業務日 {bd}")
    return " / ".join(parts[:3])


def _collect_anomaly_rows(latest: List[dict], current_biz: date) -> List[dict]:
    out: List[dict] = []
    seen_nk: set = set()
    for r in latest:
        st = (r.get("status") or "").lower()
        is_attn = st in ("blue", "red") and passes_observe_anomaly_display(r)
        is_planned = row_planned_unstarted(r)
        is_prev = row_prev_day_incomplete(r, current_biz)
        if not (is_attn or is_planned or is_prev):
            continue
        nk = _natural_key(r)
        if nk in seen_nk:
            continue
        seen_nk.add(nk)
        out.append(
            {
                "observed_at": (_row_observed_at(r) or datetime.min).isoformat(),
                "time_label": _format_observed_time(r),
                "leader": _leader_label(str(r.get("user_id") or "")),
                "process_id": str(r.get("process_id") or "—"),
                "kind": _classify_anomaly_kind(r, current_biz),
                "content": _anomaly_content(r),
                "business_date": str(r.get("business_date") or ""),
            }
        )
    out.sort(key=lambda x: x.get("observed_at") or "", reverse=True)
    return out[:ANOMALY_LIMIT]


def _priority_concentration_label(items: List[models.PriorityItem]) -> str:
    if not items:
        return "該当なし"
    total = sum(float(getattr(i, "prod_value", 0) or 0) for i in items)
    if total <= 0:
        return "需要なし"
    sorted_items = sorted(
        items, key=lambda x: float(getattr(x, "prod_value", 0) or 0), reverse=True
    )
    top3 = sum(float(getattr(x, "prod_value", 0) or 0) for x in sorted_items[:3])
    pct = round(100.0 * top3 / total)
    if pct >= 60:
        return f"上位3件で需要の{pct}%"
    return "分散"


def build_package_a_dashboard(company_id: str, db: Session) -> dict:
    cid = (company_id or "").strip()
    settings = _get_or_create_settings(cid, db)
    current_biz = calc_business_date(datetime.utcnow(), settings, db)

    sort_key = func.coalesce(models.WorkUnit.updated_at, models.WorkUnit.created_at)
    units = (
        db.query(models.WorkUnit)
        .filter(models.WorkUnit.company_id == cid)
        .order_by(sort_key.desc().nulls_last(), models.WorkUnit.id.desc())
        .limit(WORK_LIST_LIMIT)
        .all()
    )
    raw_rows = [_unit_to_out(u, settings, db, None, office_chain_hint="") for u in units]
    latest = _latest_rows_by_natural_key(raw_rows)

    blue_count = sum(
        1
        for r in latest
        if (r.get("status") or "").lower() == "blue" and passes_observe_anomaly_display(r)
    )
    planned_unstarted_count = sum(1 for r in latest if row_planned_unstarted(r))
    diff_anomaly_count = sum(1 for r in latest if r.get("is_diff_anomaly") is True)
    exception_count = sum(1 for r in latest if row_exception_input(r))
    prev_incomplete_count = sum(
        1 for r in latest if row_prev_day_incomplete(r, current_biz)
    )

    open_priority = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .filter(models.PriorityItem.status == "open")
        .all()
    )
    after_cutoff_count = sum(
        1 for p in open_priority if bool(getattr(p, "is_after_cutoff", False))
    )
    shortage_count = sum(
        1 for p in open_priority if float(getattr(p, "prod_value", 0) or 0) > 0
    )

    safety_map = load_safety_stock_by_product_code(db, cid)
    safety_unset_codes: set = set()
    for p in open_priority:
        pc = (p.product_code or "").strip()
        if not pc:
            continue
        info = safety_map.get(pc)
        if info is None or info.is_unset:
            safety_unset_codes.add(pc)

    process_stats: Dict[str, dict] = {}
    for r in latest:
        proc = str(r.get("process_id") or "").strip() or "（未設定）"
        bucket = process_stats.setdefault(
            proc,
            {"process_id": proc, "total": 0, "blue_count": 0, "incomplete_count": 0},
        )
        bucket["total"] += 1
        if (r.get("status") or "").lower() == "blue" and passes_observe_anomaly_display(r):
            bucket["blue_count"] += 1
        if r.get("is_missing") is True or row_prev_day_incomplete(r, current_biz):
            bucket["incomplete_count"] += 1

    process_rows = []
    for proc in sorted(process_stats.keys()):
        b = process_stats[proc]
        total = b["total"]
        blue_n = b["blue_count"]
        rate = round(100.0 * blue_n / total, 1) if total else 0.0
        process_rows.append(
            {
                "process_id": b["process_id"],
                "blue_count": blue_n,
                "blue_rate": rate,
                "after_cutoff_count": 0,
                "incomplete_count": b["incomplete_count"],
                "total_count": total,
            }
        )

    return {
        "company_id": cid,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "current_business_date": str(current_biz),
        "summary": {
            "blue_count": blue_count,
            "after_cutoff_count": after_cutoff_count,
            "prev_day_incomplete_count": prev_incomplete_count,
            "planned_unstarted_count": planned_unstarted_count,
            "diff_anomaly_count": diff_anomaly_count,
            "exception_input_count": exception_count,
        },
        "recent_anomalies": _collect_anomaly_rows(latest, current_biz),
        "process_observation": process_rows,
        "priority_status": {
            "shortage_count": shortage_count,
            "after_cutoff_count": after_cutoff_count,
            "safety_unset_count": len(safety_unset_codes),
            "concentration_label": _priority_concentration_label(open_priority),
            "open_item_count": len(open_priority),
        },
    }
