"""第7条再生成時の3条ルール：受注締切超過なら製造スロット日（priority の due_date）を翌々営業日へ。

- ShipmentPlanItem.due_date は物流・出荷納期（変更しない）。
- priority_item.due_date は現場が見る製造スロット日（本モジュールで補正可）。
- 締切時刻は company_settings.order_cutoff_time（未設定なら3条スキップ）。
- ordered_at が無い行はスキップ（出荷納期をそのまま第7条に載せる）。
- 営業日は company_calendar を利用（business_date.next_business_day）。
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.business_date import JST, next_business_day
from app.services.shipment_csv import parse_due_date


def ordered_at_to_jst(dt: Optional[datetime]) -> Optional[datetime]:
    """DB の naive datetime は UTC とみなして JST に変換（shipment 取り込みと整合）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(JST)
    return dt.astimezone(JST)


def second_next_business_day_from_anchor(
    anchor_calendar_date: date, company_id: str, db: Session
) -> date:
    """受注日（JST 暦日）を起点とした翌々営業日（company_calendar 利用）。"""
    d1 = next_business_day(anchor_calendar_date, company_id, db)
    return next_business_day(d1, company_id, db)


def compute_priority_due_article3(
    shipment_due_raw: Optional[str],
    ordered_at: Optional[datetime],
    order_cutoff: Optional[time],
    company_id: str,
    db: Session,
) -> Tuple[str, bool]:
    """
    Returns:
        (priority_item に保存する due_date YYYY-MM-DD 相当, スライドしたか)
    """
    due_norm = parse_due_date(shipment_due_raw)
    if not due_norm:
        s = str(shipment_due_raw or "").strip()
        return (s, False)

    if order_cutoff is None or ordered_at is None:
        return (due_norm, False)

    o_jst = ordered_at_to_jst(ordered_at)
    if o_jst is None:
        return (due_norm, False)

    cutoff_dt = datetime.combine(o_jst.date(), order_cutoff, tzinfo=JST)
    if o_jst < cutoff_dt:
        return (due_norm, False)

    slid = second_next_business_day_from_anchor(o_jst.date(), company_id, db)
    return (slid.isoformat(), True)
