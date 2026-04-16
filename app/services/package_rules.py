"""
会社の package_code（A〜D）に応じた条文フェーズと、派生フラグ（フェーズ2・赤系）。

表向きは Package のみ。条文×フェーズの詳細は get_enabled_phases の辞書で保持。
"""
from __future__ import annotations

from typing import Dict

from app import models

PACKAGE_LABELS: Dict[str, str] = {
    "A": "\u8a18\u9332\u57fa\u76e4",
    "B": "\u904b\u7528\u53ef\u8996\u5316",
    "C": "\u7d71\u5236\u30fb\u5f37\u5236",
    "D": "\u7d4c\u55b6\u6d3b\u7528",
}


def get_company_package(settings: models.CompanySettings | None) -> str:
    """company_settings の package_code。未設定・不正値は 'A'。"""
    if settings is None:
        return "A"
    raw = getattr(settings, "package_code", None)
    if raw is None or str(raw).strip() == "":
        return "A"
    c = str(raw).strip().upper()
    if c in ("A", "B", "C", "D"):
        return c
    return "A"


def get_enabled_phases(package_code: str) -> Dict[str, int]:
    """条文キー → 有効とみなすフェーズ番号（設計用マップ）。"""
    pc = (package_code or "A").strip().upper()
    if pc == "A":
        return {"article_1": 1, "article_5": 1, "article_7": 1}
    if pc == "B":
        return {
            "article_1": 2,
            "article_2": 2,
            "article_3": 2,
            "article_5": 2,
            "article_7": 1,
        }
    if pc == "C":
        return {
            "article_1": 3,
            "article_2": 2,
            "article_3": 3,
            "article_4": 3,
            "article_5": 3,
            "article_6": 2,
            "article_7": 1,
        }
    if pc == "D":
        return {f"article_{i}": 4 for i in range(1, 8)}
    return get_enabled_phases("A")


def is_phase2_enabled(settings: models.CompanySettings | None) -> bool:
    """
    blue→red・judgement_red_deadline_at等の「フェーズ2」系を有効にするか。
    Package B / C / D で true。A は false（phase2_enabled カラムは参照しない）。
    """
    return get_company_package(settings) in ("B", "C", "D")


def package_label(package_code: str) -> str:
    return PACKAGE_LABELS.get(
        (package_code or "A").strip().upper(),
        PACKAGE_LABELS["A"],
    )
