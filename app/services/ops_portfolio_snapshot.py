"""運営ダッシュボード週次スナップショット保存基盤（Phase 2）。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app import models


def save_portfolio_weekly_snapshots(
    db: Session,
    rows: Iterable[dict],
    *,
    generated_at: Optional[datetime] = None,
) -> int:
    """会社ごとの週次観測記録を保存する（レポート生成・画面表示は別途）。"""
    ts = generated_at or datetime.utcnow()
    saved: List[models.OpsPortfolioWeeklySnapshot] = []
    for row in rows:
        cid = str(row.get("company_id") or "").strip()
        if not cid:
            continue
        saved.append(
            models.OpsPortfolioWeeklySnapshot(
                company_id=cid,
                blue_count=int(row.get("blue_count") or 0),
                blue_rate=float(row.get("blue_rate") or 0.0),
                danger_score=int(row.get("danger_score") or 0),
                prev_day_incomplete_count=int(row.get("prev_day_incomplete_count") or 0),
                after_cutoff_count=int(row.get("after_cutoff_count") or 0),
                generated_at=ts,
            )
        )
    if not saved:
        return 0
    db.add_all(saved)
    db.commit()
    return len(saved)
