"""WorkUnit の状態ガード（ルータ横断）。"""
from fastapi import HTTPException

from app import models


def raise_if_closed(unit: models.WorkUnit) -> None:
    """
    完了（closed）後は現場・事務ともにレコードを変更できない。
    status を normal / blue / red に戻す操作は不可。
    """
    st = (unit.status or "").strip().lower()
    if st == "closed":
        raise HTTPException(
            status_code=409,
            detail="この作業記録は完了済みのため変更できません",
        )


def is_closed(unit: models.WorkUnit) -> bool:
    return (unit.status or "").strip().lower() == "closed"
