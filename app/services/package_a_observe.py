"""Package A: 管理者向け現場観測ダッシュボード（読取専用・制御なし）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.routers.work import _get_or_create_settings, _unit_to_out
from app.services.article7_safety_stock import load_safety_stock_by_product_code
from app.services.production_mode import (
    load_production_mode_maps,
    resolve_production_mode,
)
from app.services.judgement_promote import carryover_implies_status_blue
from app.services.anomaly_classification import aggregate_field_classification
from app.services.audit_head import audit_heads_from_rows

WORK_LIST_LIMIT = 500
ANOMALY_LIMIT = 40

# 運営ダッシュボード（L1）状態閾値 — danger_score
PORTFOLIO_DANGER_SCORE_WATCH_MIN = 1
PORTFOLIO_DANGER_SCORE_DANGER_MIN = 10

# 青率（参考・会社詳細等で利用）
OBSERVE_BLUE_RATE_NORMAL_MAX = 20.0
OBSERVE_BLUE_RATE_WATCH_MAX = 50.0

PORTFOLIO_STATUS_NORMAL = "normal"
PORTFOLIO_STATUS_WATCH = "watch"
PORTFOLIO_STATUS_DANGER = "danger"

PORTFOLIO_STATUS_SORT = {
    PORTFOLIO_STATUS_DANGER: 0,
    PORTFOLIO_STATUS_WATCH: 1,
    PORTFOLIO_STATUS_NORMAL: 2,
}

PORTFOLIO_OBSERVE_TOP_N = 5

# 危険度スコア（Phase 2・将来変更可能）
DANGER_SCORE_WEIGHT_BLUE = 2
DANGER_SCORE_WEIGHT_PREV_DAY = 3
DANGER_SCORE_WEIGHT_AFTER_CUTOFF = 5

# 週報対象フラグ（Phase 2・将来変更可能）
WEEKLY_REPORT_DANGER_SCORE_MIN = 10
WEEKLY_REPORT_BLUE_RATE_MIN = 50.0


def classify_portfolio_status(danger_score: int) -> str:
    """danger_score から運営一覧の状態を判定（正常 / 要観察 / 危険）。"""
    score = int(danger_score or 0)
    if score >= PORTFOLIO_DANGER_SCORE_DANGER_MIN:
        return PORTFOLIO_STATUS_DANGER
    if score >= PORTFOLIO_DANGER_SCORE_WATCH_MIN:
        return PORTFOLIO_STATUS_WATCH
    return PORTFOLIO_STATUS_NORMAL


def portfolio_blue_rate(blue_count: int, observed_unit_count: int) -> float:
    if observed_unit_count <= 0:
        return 0.0
    return round(100.0 * blue_count / observed_unit_count, 1)


def portfolio_danger_score(
    *,
    blue_count: int = 0,
    prev_day_incomplete_count: int = 0,
    after_cutoff_count: int = 0,
) -> int:
    """運営観測の危険度（観測値の重み付き加算・定数は将来変更可能）。"""
    return (
        int(blue_count or 0) * DANGER_SCORE_WEIGHT_BLUE
        + int(prev_day_incomplete_count or 0) * DANGER_SCORE_WEIGHT_PREV_DAY
        + int(after_cutoff_count or 0) * DANGER_SCORE_WEIGHT_AFTER_CUTOFF
    )


def portfolio_weekly_report_target(
    *,
    danger_score: int,
    blue_rate: float,
    prev_day_incomplete_count: int,
) -> bool:
    """週報対象会社の自動抽出（事実ベース・将来ルール変更可能）。"""
    if int(danger_score or 0) >= WEEKLY_REPORT_DANGER_SCORE_MIN:
        return True
    if float(blue_rate or 0) >= WEEKLY_REPORT_BLUE_RATE_MIN:
        return True
    if int(prev_day_incomplete_count or 0) > 0:
        return True
    return False


def observed_unit_count_from_dashboard(dashboard: dict) -> int:
    rows = dashboard.get("process_observation") or []
    return sum(int(r.get("total_count") or 0) for r in rows)


def last_activity_at_for_company(db: Session, company_id: str) -> Optional[str]:
    row = (
        db.query(
            func.max(
                func.coalesce(
                    models.WorkUnit.updated_at,
                    models.WorkUnit.created_at,
                )
            )
        )
        .filter(models.WorkUnit.company_id == company_id)
        .scalar()
    )
    if row is None:
        return None
    if isinstance(row, datetime):
        iso = row.isoformat()
        return iso + "Z" if row.tzinfo is None and not iso.endswith("Z") else iso
    return str(row)


def build_observe_portfolio(db: Session, *, active_only: bool = True) -> dict:
    """全社 Package A サマリー（build_package_a_dashboard を会社ごとに再利用）。"""
    q = db.query(models.CompanyMaster)
    if active_only:
        q = q.filter(models.CompanyMaster.is_active.is_(True))
    masters = q.order_by(
        models.CompanyMaster.company_id.asc(),
        models.CompanyMaster.id.asc(),
    ).all()

    companies: List[dict] = []
    now = datetime.utcnow()
    for m in masters:
        cid = (m.company_id or "").strip()
        if not cid:
            continue
        dashboard = build_package_a_dashboard(cid, db)
        summary = dashboard.get("summary") or {}
        blue_count = int(summary.get("blue_count") or 0)
        prev_day_incomplete_count = int(summary.get("prev_day_incomplete_count") or 0)
        after_cutoff_count = int(summary.get("after_cutoff_count") or 0)
        planned_unstarted_count = int(summary.get("planned_unstarted_count") or 0)
        diff_anomaly_count = int(summary.get("diff_anomaly_count") or 0)
        exception_input_count = int(summary.get("exception_input_count") or 0)
        observed = observed_unit_count_from_dashboard(dashboard)
        blue_rate = portfolio_blue_rate(blue_count, observed)
        danger_score = portfolio_danger_score(
            blue_count=blue_count,
            prev_day_incomplete_count=prev_day_incomplete_count,
            after_cutoff_count=after_cutoff_count,
        )
        status = classify_portfolio_status(danger_score)
        weekly_report_target = portfolio_weekly_report_target(
            danger_score=danger_score,
            blue_rate=blue_rate,
            prev_day_incomplete_count=prev_day_incomplete_count,
        )
        companies.append(
            {
                "company_id": cid,
                "company_name": (m.company_name or cid).strip(),
                "blue_count": blue_count,
                "blue_rate": blue_rate,
                "last_activity_at": last_activity_at_for_company(db, cid),
                "status": status,
                "danger_score": danger_score,
                "weekly_report_target": weekly_report_target,
                "prev_day_incomplete_count": prev_day_incomplete_count,
                "after_cutoff_count": after_cutoff_count,
                "planned_unstarted_count": planned_unstarted_count,
                "diff_anomaly_count": diff_anomaly_count,
                "exception_input_count": exception_input_count,
            }
        )

    observation = _build_portfolio_observation(companies, now)

    public_companies = [
        {
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "blue_count": c["blue_count"],
            "blue_rate": c["blue_rate"],
            "last_activity_at": c["last_activity_at"],
            "status": c["status"],
            "danger_score": c["danger_score"],
            "weekly_report_target": c["weekly_report_target"],
            "prev_day_incomplete_count": c["prev_day_incomplete_count"],
            "after_cutoff_count": c["after_cutoff_count"],
            "planned_unstarted_count": c["planned_unstarted_count"],
            "diff_anomaly_count": c["diff_anomaly_count"],
            "exception_input_count": c["exception_input_count"],
        }
        for c in companies
    ]

    public_companies.sort(
        key=lambda c: (
            -int(c["danger_score"]),
            -float(c["blue_rate"]),
            c["company_id"],
        )
    )

    totals = {
        "company_count": len(public_companies),
        "danger_count": sum(
            1 for c in public_companies if c["status"] == PORTFOLIO_STATUS_DANGER
        ),
        "watch_count": sum(
            1 for c in public_companies if c["status"] == PORTFOLIO_STATUS_WATCH
        ),
        "normal_count": sum(
            1 for c in public_companies if c["status"] == PORTFOLIO_STATUS_NORMAL
        ),
    }

    return {
        "companies": public_companies,
        "totals": totals,
        "observation": observation,
        "generated_at": now.isoformat() + "Z",
    }


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


def _portfolio_stale_days(last_activity_at: Optional[str], now: datetime) -> Optional[int]:
    dt = _parse_iso_dt(last_activity_at)
    if dt is None:
        return None
    return max(0, (now.date() - dt.date()).days)


def _build_portfolio_observation(enriched: List[dict], now: datetime) -> dict:
    """運営観測盤: 既存集計のみ（推論・予測なし）。"""
    n = PORTFOLIO_OBSERVE_TOP_N

    top_danger = sorted(
        enriched,
        key=lambda c: (-int(c.get("danger_score") or 0), c["company_id"]),
    )[:n]

    top_prev = sorted(
        [c for c in enriched if int(c.get("prev_day_incomplete_count") or 0) > 0],
        key=lambda c: (
            -int(c["prev_day_incomplete_count"]),
            c["company_id"],
        ),
    )[:n]

    top_blue = sorted(
        enriched,
        key=lambda c: (-float(c["blue_rate"]), -int(c["blue_count"]), c["company_id"]),
    )[:n]

    top_cutoff = sorted(
        [c for c in enriched if int(c.get("after_cutoff_count") or 0) > 0],
        key=lambda c: (-int(c["after_cutoff_count"]), c["company_id"]),
    )[:n]

    def _stale_sort_key(c: dict) -> Tuple[int, str]:
        days = _portfolio_stale_days(c.get("last_activity_at"), now)
        rank = days if days is not None else -1
        return (-rank, c["company_id"])

    stale = sorted(enriched, key=_stale_sort_key)[:n]

    return {
        "top_danger_score": [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "danger_score": c["danger_score"],
                "blue_count": c["blue_count"],
                "prev_day_incomplete_count": c["prev_day_incomplete_count"],
            }
            for c in top_danger
        ],
        "top_prev_day_incomplete": [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "prev_day_incomplete_count": c["prev_day_incomplete_count"],
            }
            for c in top_prev
        ],
        "top_after_cutoff": [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "after_cutoff_count": c["after_cutoff_count"],
            }
            for c in top_cutoff
        ],
        "top_blue_rate": [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "blue_rate": c["blue_rate"],
                "blue_count": c["blue_count"],
            }
            for c in top_blue
        ],
        "stale_updates": [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "last_activity_at": c.get("last_activity_at"),
                "stale_days": _portfolio_stale_days(c.get("last_activity_at"), now),
            }
            for c in stale
        ],
    }


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


def row_completely_empty_legacy_triplet(r: dict) -> bool:
    """_phase1_completely_empty_legacy_triplet の dict 版（Observe 表示用）。"""
    pv = r.get("planned_value")
    if not r.get("planned_registered_at"):
        pv = None
    av = r.get("actual_value")
    return pv is None and not r.get("started_at") and av is None


from app.services.business_date import calc_business_date


def row_carryover_implies_status_blue(
    r: dict,
    settings: models.CompanySettings,
) -> bool:
    """持ち越し青: actual_at なし・effective_date > business_date・closed 以外。"""
    if r.get("actual_at"):
        return False
    bd_raw = r.get("business_date")
    if not bd_raw:
        return False
    try:
        bd = date.fromisoformat(str(bd_raw))
    except ValueError:
        return False
    return carryover_implies_status_blue(
        actual_at=None,
        business_date=bd,
        status=r.get("status"),
        settings=settings,
    )


def passes_observe_anomaly_display(
    r: dict,
    settings: models.CompanySettings,
) -> bool:
    """office_v2 passesOfficeAnomalyDisplay と同等。"""
    st = (r.get("status") or "").lower()
    if st not in ("blue", "red"):
        return False
    if st == "red":
        return True
    if row_carryover_implies_status_blue(r, settings):
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
        return "結果不備"
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


def _collect_anomaly_rows(
    latest: List[dict],
    current_biz: date,
    settings: models.CompanySettings,
) -> List[dict]:
    out: List[dict] = []
    seen_nk: set = set()
    for r in latest:
        st = (r.get("status") or "").lower()
        is_attn = st in ("blue", "red") and passes_observe_anomaly_display(r, settings)
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
    audit_heads = audit_heads_from_rows(raw_rows)

    blue_count = sum(
        1
        for r in audit_heads
        if (r.get("status") or "").lower() == "blue"
        and passes_observe_anomaly_display(r, settings)
    )
    planned_unstarted_count = sum(1 for r in latest if row_planned_unstarted(r))
    diff_anomaly_count = sum(1 for r in audit_heads if r.get("is_diff_anomaly") is True)
    exception_count = sum(1 for r in audit_heads if row_exception_input(r))
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
    by_code, by_label = load_production_mode_maps(db, cid)
    safety_unset_codes: set = set()
    manufacture_shortage = 0
    purchase_shortage = 0
    for p in open_priority:
        pc = (p.product_code or "").strip()
        if pc:
            info = safety_map.get(pc)
            if info is None or info.is_unset:
                safety_unset_codes.add(pc)
        if float(getattr(p, "prod_value", 0) or 0) > 0:
            mode = resolve_production_mode(
                p.product_code, p.label, by_code, by_label
            )
            if mode == "purchase":
                purchase_shortage += 1
            else:
                manufacture_shortage += 1

    process_stats: Dict[str, dict] = {}
    for r in audit_heads:
        proc = str(r.get("process_id") or "").strip() or "（未設定）"
        bucket = process_stats.setdefault(
            proc,
            {"process_id": proc, "total": 0, "blue_count": 0, "incomplete_count": 0},
        )
        bucket["total"] += 1
        if (r.get("status") or "").lower() == "blue" and passes_observe_anomaly_display(r, settings):
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
        "recent_anomalies": _collect_anomaly_rows(audit_heads, current_biz, settings),
        "process_observation": process_rows,
        "priority_status": {
            "shortage_count": shortage_count,
            "after_cutoff_count": after_cutoff_count,
            "safety_unset_count": len(safety_unset_codes),
            "concentration_label": _priority_concentration_label(open_priority),
            "open_item_count": len(open_priority),
            "manufacture_shortage_count": manufacture_shortage,
            "purchase_shortage_count": purchase_shortage,
        },
        "field_classification_breakdown": aggregate_field_classification(audit_heads),
    }
