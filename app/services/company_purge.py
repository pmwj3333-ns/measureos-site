"""会社配下データの一括削除（QA 前クリーンアップ等）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from sqlalchemy.orm import Session

from app import models
from app.services.company_validator import normalize_company_id


@dataclass
class CompanyPurgePlan:
    keep_ids: List[str]
    delete_ids: List[str]
    row_counts_by_company: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def keep_count(self) -> int:
        return len(self.keep_ids)

    @property
    def delete_count(self) -> int:
        return len(self.delete_ids)

    def total_rows_to_delete(self) -> Dict[str, int]:
        totals: Dict[str, int] = {}
        for per_company in self.row_counts_by_company.values():
            for key, count in per_company.items():
                totals[key] = totals.get(key, 0) + int(count or 0)
        return totals


def _normalize_keep_ids(keep_ids: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for raw in keep_ids:
        cid = normalize_company_id(raw)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return sorted(out)


def collect_all_company_ids(db: Session) -> Set[str]:
    ids: Set[str] = set()
    for row in db.query(models.CompanyMaster.company_id).all():
        cid = normalize_company_id(row[0])
        if cid:
            ids.add(cid)
    for row in db.query(models.CompanySettings.company_id).all():
        cid = normalize_company_id(row[0])
        if cid:
            ids.add(cid)
    for model in (
        models.WorkUnit,
        models.ProductMaster,
        models.PriorityItem,
        models.StockItem,
        models.ShipmentPlanItem,
        models.MonthlyReport,
        models.WorkingCalendar,
        models.CompanyCalendar,
        models.OpsPortfolioWeeklySnapshot,
    ):
        for row in db.query(model.company_id).distinct().all():
            cid = normalize_company_id(row[0])
            if cid:
                ids.add(cid)
    return ids


def count_company_related_rows(db: Session, company_id: str) -> Dict[str, int]:
    cid = normalize_company_id(company_id)
    if not cid:
        return {}

    unit_ids = [
        r[0]
        for r in db.query(models.WorkUnit.id)
        .filter(models.WorkUnit.company_id == cid)
        .all()
    ]

    counts: Dict[str, int] = {}
    counts["work_unit_status_history"] = (
        db.query(models.WorkUnitStatusHistory)
        .filter(models.WorkUnitStatusHistory.work_unit_id.in_(unit_ids))
        .count()
        if unit_ids
        else 0
    )
    counts["office_closed_work_unit_suppress"] = (
        db.query(models.OfficeClosedWorkUnitSuppress)
        .filter(models.OfficeClosedWorkUnitSuppress.peer_unit_id.in_(unit_ids))
        .count()
        if unit_ids
        else 0
    )
    counts["work_unit"] = (
        db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid).count()
    )
    counts["priority_item"] = (
        db.query(models.PriorityItem).filter(models.PriorityItem.company_id == cid).count()
    )
    counts["stock_item"] = (
        db.query(models.StockItem).filter(models.StockItem.company_id == cid).count()
    )
    counts["shipment_plan_item"] = (
        db.query(models.ShipmentPlanItem)
        .filter(models.ShipmentPlanItem.company_id == cid)
        .count()
    )
    counts["product_master"] = (
        db.query(models.ProductMaster).filter(models.ProductMaster.company_id == cid).count()
    )
    counts["monthly_reports"] = (
        db.query(models.MonthlyReport).filter(models.MonthlyReport.company_id == cid).count()
    )
    counts["working_calendar"] = (
        db.query(models.WorkingCalendar)
        .filter(models.WorkingCalendar.company_id == cid)
        .count()
    )
    counts["company_calendar"] = (
        db.query(models.CompanyCalendar).filter(models.CompanyCalendar.company_id == cid).count()
    )
    counts["ops_portfolio_weekly_snapshot"] = (
        db.query(models.OpsPortfolioWeeklySnapshot)
        .filter(models.OpsPortfolioWeeklySnapshot.company_id == cid)
        .count()
    )
    counts["company_settings"] = (
        db.query(models.CompanySettings).filter(models.CompanySettings.company_id == cid).count()
    )
    counts["company_master"] = (
        db.query(models.CompanyMaster).filter(models.CompanyMaster.company_id == cid).count()
    )
    return counts


def plan_company_purge(db: Session, keep_ids: Iterable[str]) -> CompanyPurgePlan:
    keep = _normalize_keep_ids(keep_ids)
    keep_set = set(keep)
    all_ids = sorted(collect_all_company_ids(db))
    delete_ids = [cid for cid in all_ids if cid not in keep_set]
    row_counts = {cid: count_company_related_rows(db, cid) for cid in delete_ids}
    return CompanyPurgePlan(
        keep_ids=keep,
        delete_ids=delete_ids,
        row_counts_by_company=row_counts,
    )


def delete_company_and_related_data(db: Session, company_id: str) -> Dict[str, int]:
    """1 社分の関連データを ORM delete で削除する（commit は呼び出し元）。"""
    cid = normalize_company_id(company_id)
    if not cid:
        return {}

    unit_ids = [
        r[0]
        for r in db.query(models.WorkUnit.id)
        .filter(models.WorkUnit.company_id == cid)
        .all()
    ]

    deleted: Dict[str, int] = {}

    if unit_ids:
        deleted["work_unit_status_history"] = (
            db.query(models.WorkUnitStatusHistory)
            .filter(models.WorkUnitStatusHistory.work_unit_id.in_(unit_ids))
            .delete(synchronize_session=False)
        )
        deleted["office_closed_work_unit_suppress"] = (
            db.query(models.OfficeClosedWorkUnitSuppress)
            .filter(models.OfficeClosedWorkUnitSuppress.peer_unit_id.in_(unit_ids))
            .delete(synchronize_session=False)
        )
    else:
        deleted["work_unit_status_history"] = 0
        deleted["office_closed_work_unit_suppress"] = 0

    deleted["work_unit"] = (
        db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["priority_item"] = (
        db.query(models.PriorityItem).filter(models.PriorityItem.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["stock_item"] = (
        db.query(models.StockItem).filter(models.StockItem.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["shipment_plan_item"] = (
        db.query(models.ShipmentPlanItem)
        .filter(models.ShipmentPlanItem.company_id == cid)
        .delete(synchronize_session=False)
    )
    deleted["product_master"] = (
        db.query(models.ProductMaster).filter(models.ProductMaster.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["monthly_reports"] = (
        db.query(models.MonthlyReport).filter(models.MonthlyReport.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["working_calendar"] = (
        db.query(models.WorkingCalendar)
        .filter(models.WorkingCalendar.company_id == cid)
        .delete(synchronize_session=False)
    )
    deleted["company_calendar"] = (
        db.query(models.CompanyCalendar).filter(models.CompanyCalendar.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["ops_portfolio_weekly_snapshot"] = (
        db.query(models.OpsPortfolioWeeklySnapshot)
        .filter(models.OpsPortfolioWeeklySnapshot.company_id == cid)
        .delete(synchronize_session=False)
    )
    deleted["company_settings"] = (
        db.query(models.CompanySettings).filter(models.CompanySettings.company_id == cid).delete(
            synchronize_session=False
        )
    )
    deleted["company_master"] = (
        db.query(models.CompanyMaster).filter(models.CompanyMaster.company_id == cid).delete(
            synchronize_session=False
        )
    )
    return deleted


def purge_companies_except(db: Session, keep_ids: Iterable[str]) -> CompanyPurgePlan:
    plan = plan_company_purge(db, keep_ids)
    for cid in plan.delete_ids:
        delete_company_and_related_data(db, cid)
    db.commit()
    return plan


def list_company_master_rows(db: Session) -> List[models.CompanyMaster]:
    return (
        db.query(models.CompanyMaster)
        .order_by(models.CompanyMaster.company_id.asc())
        .all()
    )
