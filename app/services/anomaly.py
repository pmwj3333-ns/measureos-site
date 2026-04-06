"""
異常検知サービス（フェーズ1）
設計書（measure-os-article-5-spec.md）準拠：
  - 未入力（is_missing）
  - 順序不備（is_invalid_flow）
  - 数値乖離（is_diff_anomaly）

WorkUnit のサマリフラグのうち is_invalid_flow / is_diff_anomaly を更新しつつ、
WorkAnomaly テーブルに個別の異常種別を記録する。
is_missing は app.services.missing_boundary でのみ更新（入力時は変更しない）。
フェーズ1：検知のみ、ブロックなし。work_unit.status は変更しない。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app import models


# ─────────────────────────────────────────
# 異常種別の定数（後から追加しやすいよう集約）
# ─────────────────────────────────────────
class AnomalyType:
    TARGET_MISSING   = "target_missing"    # 対象未選択の行がある
    QUANTITY_MISSING = "quantity_missing"  # 数量未入力の行がある
    FORECAST_MISSING = "forecast_missing"  # 予告なしで実績
    FORECAST_DIFF    = "forecast_diff"     # 予告との数値乖離
    START_MISSING    = "start_missing"     # 着手なしで実績


def detect_and_update(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
) -> None:
    """
    フェーズ1の異常検知。
    1. WorkUnit のサマリフラグを更新する
    2. WorkAnomaly に個別記録を残す（重複は UNIQUE 制約でスキップ）
    status / system_pattern は work ルータの _apply_minimal_judgement のみが担当。
    """
    now = datetime.utcnow()
    detected_types: list[str] = []

    # ── 1. is_missing は missing_boundary のみ。ここでは WorkAnomaly 用に種別だけ積む
    if unit.planned_value is None and unit.actual_value is not None:
        detected_types.append(AnomalyType.FORECAST_MISSING)
    if unit.started_at is None and unit.actual_value is not None:
        detected_types.append(AnomalyType.START_MISSING)

    # ── 2. 順序不備チェック（設計書: is_invalid_flow）────────────
    # 着手なしで実績が入っている状態
    unit.is_invalid_flow = (
        unit.actual_value is not None and unit.started_at is None
    )
    if unit.is_invalid_flow and AnomalyType.START_MISSING not in detected_types:
        detected_types.append(AnomalyType.START_MISSING)

    # ── 3. 行レベルの未選択・未入力チェック ──────────────────────
    line_rel = getattr(unit, "lines", None) or []
    actual_lines = [l for l in line_rel if getattr(l, "line_type", None) == "actual"]
    has_target_missing = any(not l.target_selected for l in actual_lines) if actual_lines else False
    has_qty_missing    = any(not l.quantity_entered for l in actual_lines) if actual_lines else False
    if has_target_missing:
        detected_types.append(AnomalyType.TARGET_MISSING)
    if has_qty_missing:
        detected_types.append(AnomalyType.QUANTITY_MISSING)

    # ── 4. 数値乖離チェック（設計書: is_diff_anomaly）────────────
    # 判定式: |actual - planned| > tolerance_value（絶対値・対称判定）
    # UI 表示は「±{tolerance_value}」として社労士・現場に提示する。
    #
    # 将来拡張メモ（フェーズ2以降で検討）:
    #   - tolerance_positive: 過剰側（actual > planned）の許容幅を個別設定
    #   - tolerance_negative: 不足側（actual < planned）の許容幅を個別設定
    #   現時点では対称（±同値）のみ使用。
    if unit.planned_value is not None and unit.actual_value is not None:
        unit.diff_value = unit.actual_value - unit.planned_value
        unit.is_diff_anomaly = abs(unit.diff_value) > settings.tolerance_value
    else:
        unit.diff_value = None
        unit.is_diff_anomaly = False
    if unit.is_diff_anomaly:
        detected_types.append(AnomalyType.FORECAST_DIFF)

    # ── 5. WorkAnomaly に個別記録（重複は UNIQUE 制約で無視）────────
    for atype in detected_types:
        _upsert_anomaly(db, unit.id, atype, now)


def _upsert_anomaly(
    db: Session,
    work_unit_id: int,
    anomaly_type: str,
    detected_at: datetime,
) -> None:
    """
    同一 (work_unit_id, anomaly_type) の異常が未登録なら INSERT する。
    UNIQUE 制約違反（= 既に存在）は静かにスキップする。
    """
    existing = db.query(models.WorkAnomaly).filter(
        models.WorkAnomaly.work_unit_id == work_unit_id,
        models.WorkAnomaly.anomaly_type == anomaly_type,
    ).first()
    if existing:
        return
    anomaly = models.WorkAnomaly(
        work_unit_id=work_unit_id,
        anomaly_type=anomaly_type,
        detected_at=detected_at,
        status="open",
    )
    db.add(anomaly)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
