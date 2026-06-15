"""company_master パスワード hash（平文は DB に保存しない）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models


def hash_company_password(plain_password: str) -> str:
    raw = str(plain_password or "")
    if not raw.strip():
        raise ValueError("password must not be empty")
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_company_password(plain_password: str, password_hash: Optional[str]) -> bool:
    if not password_hash or not str(password_hash).strip():
        return False
    try:
        return bcrypt.checkpw(
            str(plain_password or "").encode("utf-8"),
            str(password_hash).encode("utf-8"),
        )
    except ValueError:
        return False


def company_has_password(master: models.CompanyMaster | None) -> bool:
    if master is None:
        return False
    h = getattr(master, "company_password_hash", None)
    return bool(h and str(h).strip())


def set_company_password_hash(db: Session, company_id: str, plain_password: str) -> None:
    row = (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == company_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="company_master not found")
    row.company_password_hash = hash_company_password(plain_password)
    row.updated_at = datetime.utcnow()


def get_company_master(db: Session, company_id: str) -> models.CompanyMaster | None:
    return (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == company_id)
        .first()
    )
