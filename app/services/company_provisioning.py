"""新規会社の company_id / 初期パスワード自動生成。"""

from __future__ import annotations

import re
import secrets
import string
from typing import Optional

from sqlalchemy.orm import Session

from app import models

_LEGAL_SUFFIXES = (
    "株式会社",
    "有限会社",
    "合同会社",
    "(株)",
    "（株）",
    "（有）",
    "(有)",
)

_READING_HINTS = (
    ("テスト", "test"),
    ("山田", "yamada"),
    ("田中", "tanaka"),
    ("佐藤", "sato"),
    ("鈴木", "suzuki"),
    ("高橋", "takahashi"),
)

_ID_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits
_PASSWORD_ALPHABET = string.ascii_uppercase + string.digits


def _strip_legal_suffixes(name: str) -> str:
    s = (name or "").strip()
    for suffix in _LEGAL_SUFFIXES:
        s = s.replace(suffix, "")
    return s.strip()


def slug_base_from_company_name(company_name: str) -> str:
    """会社名から人間が読める slug 基底（latin 抽出 + 既知読み）。"""
    raw = _strip_legal_suffixes(company_name)
    for hint, slug in _READING_HINTS:
        if hint in raw:
            return slug
    parts = re.findall(r"[A-Za-z0-9]+", raw)
    if parts:
        return parts[0].lower()[:16]
    return "co"


def generate_company_id_suffix(length: int = 4) -> str:
    return "".join(secrets.choice(_ID_SUFFIX_ALPHABET) for _ in range(length))


def generate_initial_password(length: int = 8) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def company_id_exists(db: Session, company_id: str) -> bool:
    cid = (company_id or "").strip()
    if not cid:
        return False
    return (
        db.query(models.CompanyMaster.id)
        .filter(models.CompanyMaster.company_id == cid)
        .first()
        is not None
    )


def generate_unique_company_id(
    db: Session,
    company_name: str,
    *,
    max_attempts: int = 32,
) -> str:
    base = slug_base_from_company_name(company_name)
    for _ in range(max_attempts):
        cid = f"{base}-{generate_company_id_suffix(4)}"
        if not company_id_exists(db, cid):
            return cid
    raise RuntimeError("company_id の自動生成に失敗しました")
