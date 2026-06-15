"""company_master + company_settings による active 会社検索（sr/v2 補助 UI）。"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app import models


def _norm(raw) -> str:
    return (raw or "").strip()


def search_active_companies(db: Session, query: str) -> List[dict]:
    """
    active company のみ。company_id / company_name（master または settings）部分一致。
    返値: [{ company_id, company_name, is_active }]
    """
    needle = _norm(query).lower()
    if not needle:
        return []

    settings_names = {
        _norm(s.company_id): _norm(getattr(s, "company_name", None))
        for s in db.query(models.CompanySettings).all()
        if _norm(s.company_id)
    }

    rows = (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.is_active.is_(True))
        .order_by(models.CompanyMaster.company_id.asc())
        .all()
    )

    out: List[dict] = []
    for row in rows:
        cid = _norm(row.company_id)
        if not cid:
            continue
        master_name = _norm(row.company_name)
        settings_name = settings_names.get(cid, "")
        display_name = settings_name or master_name or cid
        haystacks = {cid.lower(), master_name.lower(), settings_name.lower(), display_name.lower()}
        if not any(needle in h for h in haystacks if h):
            continue
        out.append(
            {
                "company_id": cid,
                "company_name": display_name,
                "is_active": True,
            }
        )
    return out
