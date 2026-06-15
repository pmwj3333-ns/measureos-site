"""
会社の package_code（A〜D）に応じた条文フェーズと、派生フラグ（フェーズ2・赤系）。

表向きは Package のみ。条文×フェーズの詳細は get_enabled_phases の辞書で保持。
DB に legacy の D が残っていても、UI 表示は C として扱う。
"""
from __future__ import annotations

from typing import Dict, List

from app import models

PACKAGE_LABELS: Dict[str, str] = {
    "A": "現場可観測基盤",
    "B": "可観測運用制御",
    "C": "構造分析・経営最適化",
}

PACKAGE_TAGLINES: Dict[str, str] = {
    "A": "現場を観測する",
    "B": "観測可能なまま現場を安定化する",
    "C": "現場構造を理解・分析・最適化する",
}

PACKAGE_DESCRIPTIONS: Dict[str, str] = {
    "A": "現場を止めずに、何が起きているかを観測可能にする。",
    "B": "観測可能性を壊さずに、現場運用を安定化する。",
    "C": "観測ログから、構造改善・分析・AI支援へ接続する。",
}

PACKAGE_BULLETS: Dict[str, List[str]] = {
    "A": ["異常を隠さない", "まず残す", "現場の流れを観測する"],
    "B": ["崩れを放置しない", "例外を正式な流れとして扱う", "負荷と遅れを可視化する"],
    "C": ["属人化分析", "ボトルネック分析", "緊急依存分析", "AI分析基盤"],
}

PACKAGE_TARGETS: Dict[str, str] = {
    "A": "第1条A / 第3条A / 第5条A / 第7条A",
    "B": "第1〜7条 Bフェーズ",
    "C": "第1〜7条 Cフェーズ",
}


def package_display_code(package_code: str) -> str:
    """UI 用。legacy D は C として表示。"""
    pc = (package_code or "A").strip().upper()
    if pc == "D":
        return "C"
    if pc in PACKAGE_LABELS:
        return pc
    return "A"


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
    return PACKAGE_LABELS.get(package_display_code(package_code), PACKAGE_LABELS["A"])


def package_tagline(package_code: str) -> str:
    return PACKAGE_TAGLINES.get(package_display_code(package_code), PACKAGE_TAGLINES["A"])


def package_description(package_code: str) -> str:
    return PACKAGE_DESCRIPTIONS.get(
        package_display_code(package_code),
        PACKAGE_DESCRIPTIONS["A"],
    )


def package_bullets(package_code: str) -> List[str]:
    return list(
        PACKAGE_BULLETS.get(package_display_code(package_code), PACKAGE_BULLETS["A"])
    )


def package_targets(package_code: str) -> str:
    return PACKAGE_TARGETS.get(package_display_code(package_code), PACKAGE_TARGETS["A"])
