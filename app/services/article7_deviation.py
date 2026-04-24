"""第5条実績と第7条（open の priority_item）の逸脱判定（Package A）。

逸脱: open の第7条に存在しない「商品」で実績入力した場合のみ（数量・順序は対象外）。

突合（誤結合防止）:
  1. 実績行と第7条行の product_code が両方非空かつ一致 → 非逸脱
  2. 実績行も第7条行も product_code が空のときだけ label 一致 → 非逸脱
  3. 片方だけ product_code がある場合は label では一致させない
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app import models


def _strip(s) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _open_article7_rows(company_id: str, db: Session) -> List[models.PriorityItem]:
    cid = _strip(company_id)
    if not cid:
        return []
    return (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .filter(models.PriorityItem.status == "open")
        .order_by(models.PriorityItem.id.asc())
        .all()
    )


def _actual_line_matched_by_article7(line: dict, open_rows: List[models.PriorityItem]) -> bool:
    ln_pc = _strip(line.get("product_code"))
    ln_lb = _strip(line.get("label"))
    if not ln_pc and not ln_lb:
        return True
    for p in open_rows:
        p_pc = _strip(getattr(p, "product_code", None))
        p_lb = _strip(getattr(p, "label", None))
        if ln_pc and p_pc and ln_pc == p_pc:
            return True
        if (not ln_pc) and (not p_pc) and ln_lb and p_lb and ln_lb == p_lb:
            return True
    return False


def is_actual_deviation_from_article7(
    company_id: str,
    actual_lines: List[dict],
    db: Session,
) -> bool:
    """
    実績の各行を第7条（open）と突合。1行でもルール上「該当なし」なら True。
    実績が空なら False。
    """
    if not actual_lines:
        return False
    open_rows = _open_article7_rows(company_id, db)
    for line in actual_lines:
        ln_pc = _strip(line.get("product_code"))
        ln_lb = _strip(line.get("label"))
        if not ln_pc and not ln_lb:
            continue
        if not _actual_line_matched_by_article7(line, open_rows):
            return True
    return False
