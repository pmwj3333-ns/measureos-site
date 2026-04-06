"""フェーズ1 v2 専用 API（sr_v2 / field_v2 / debug_v2 のみから利用。旧 /settings 非依存）"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

router = APIRouter(prefix="/v2", tags=["v2-設定"])


def _norm_input_mode(raw) -> str:
    if not raw:
        return "manufacturing"
    x = str(raw).strip().lower()
    return "logistics" if x == "logistics" else "manufacturing"


class V2LeaderRow(BaseModel):
    name: str = ""
    process: str = ""


class V2LeadersPut(BaseModel):
    leaders: List[V2LeaderRow] = Field(default_factory=list)


@router.get("/companies", summary="登録済み company_id 一覧（v2）")
def v2_list_companies(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CompanySettings.company_id)
        .order_by(models.CompanySettings.company_id)
        .all()
    )
    return [{"company_id": r[0]} for r in rows]


@router.get("/company/{company_id}", summary="現場 v2 用・会社スナップショット")
def v2_get_company(company_id: str, db: Session = Depends(get_db)):
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if not s:
        return {
            "company_id": company_id,
            "field_users": "",
            "input_mode": "manufacturing",
            "unit": "個",
        }
    return {
        "company_id": s.company_id,
        "field_users": (s.field_users or "").strip(),
        "input_mode": _norm_input_mode(getattr(s, "input_mode", None)),
        "unit": s.unit or "個",
    }


@router.put("/company/{company_id}/leaders", summary="班長マスタを保存（v2・社労士 v2 専用）")
def v2_put_leaders(company_id: str, body: V2LeadersPut, db: Session = Depends(get_db)):
    parts: List[str] = []
    for e in body.leaders:
        n = (e.name or "").strip()
        if not n:
            continue
        p = (e.process or "").strip()
        parts.append(f"{n}:{p}" if p else n)
    raw = ",".join(parts)
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if s is None:
        s = models.CompanySettings(company_id=company_id)
        db.add(s)
    s.field_users = raw
    db.commit()
    db.refresh(s)
    return {
        "company_id": company_id,
        "field_users": (s.field_users or "").strip(),
        "saved_count": len(parts),
    }
