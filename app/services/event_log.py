"""
イベントログ記録サービス
設計書（measure-os-rules-skeleton.md）の handleEvent / createAnomaly に対応。

各操作で log_event() を呼ぶことで全操作の証跡を work_events に残す。
event_type を増やすだけで新種別に対応できる構造にする。
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app import models


# ─────────────────────────────────────────
# 使用する event_type の定数（後から追加しやすいよう集約）
# ─────────────────────────────────────────
class EventType:
    START_WORK       = "start_work"        # 着手ボタン押下
    RECORD_ACTUAL    = "record_actual"     # 実績一括登録
    RECORD_FORECAST  = "record_forecast"   # 予告一括登録
    CREATE_UNIT      = "create_unit"       # 作業レコード新規作成
    CREATE_TARGET    = "create_target"     # 現場による対象マスタ新規登録
    EDIT_TARGET      = "edit_target"       # 事務による対象マスタ編集
    MERGE_TARGET     = "merge_target"      # 事務による対象マスタ統合
    HIDE_TARGET      = "hide_target"       # 事務による対象マスタ非表示
    APPROVE_ANOMALY  = "approve_anomaly"   # 事務による異常承認


def log_event(
    db: Session,
    event_type: str,
    company_id: str,
    *,
    actor_role: Optional[str] = None,
    actor_id: Optional[str] = None,
    team_or_section: Optional[str] = None,
    target_id: Optional[int] = None,
    related_record_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> models.WorkEvent:
    """
    イベントを work_events に記録する。
    呼び出し側でコミットすること（commitは呼び出し元に委ねる）。
    """
    event = models.WorkEvent(
        event_type=event_type,
        occurred_at=datetime.utcnow(),
        company_id=company_id,
        actor_role=actor_role,
        actor_id=actor_id,
        team_or_section=team_or_section,
        target_id=target_id,
        related_record_id=related_record_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(event)
    return event
