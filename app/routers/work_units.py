from datetime import datetime, time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import anomaly as anomaly_svc
from app.services.business_date import calc_business_date_with_db, next_business_day
from app.services.event_log import log_event, EventType
from app.services.work_unit_guard import is_closed, raise_if_closed

router = APIRouter(prefix="/作業記録", tags=["作業記録"])


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────

def _recompute_work_status(unit: models.WorkUnit, settings: models.CompanySettings, db: Session) -> None:
    """append-only: work v2 と同様に DB の派生フラグは更新しない。"""
    return


def _get_settings(company_id: str, db: Session) -> models.CompanySettings:
    settings = db.query(models.CompanySettings).filter(
        models.CompanySettings.company_id == company_id
    ).first()
    if not settings:
        # フェーズ1：企業設定がなければデフォルト値で自動作成
        settings = models.CompanySettings(
            company_id=company_id,
            day_boundary_time=time(0, 0),
            work_end_time=time(17, 0),
            judgement_time=time(13, 0),
            tolerance_value=0,
            package_code="A",
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _find_previous_unit(
    company_id: str, task_id: str, process_id: str, user_id: str,
    before_date, db: Session
) -> Optional[models.WorkUnit]:
    """前営業日以前で最新の WorkUnit を返す（forecast_ref_id 用）"""
    return db.query(models.WorkUnit).filter(
        models.WorkUnit.company_id == company_id,
        models.WorkUnit.task_id == task_id,
        models.WorkUnit.process_id == process_id,
        models.WorkUnit.user_id == user_id,
        models.WorkUnit.business_date < before_date,
    ).order_by(models.WorkUnit.business_date.desc()).first()


def _get_or_create_unit(
    company_id: str, task_id: str, process_id: str, user_id: str,
    db: Session, settings: models.CompanySettings
) -> tuple[models.WorkUnit, bool]:
    """
    今日の business_date でレコードを取得、なければ作成する。
    新規作成時は前営業日の WorkUnit を forecast_ref_id に紐づける。
    Returns: (unit, is_new)
    """
    biz_date = calc_business_date_with_db(datetime.utcnow(), settings, db)
    unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.company_id == company_id,
        models.WorkUnit.task_id == task_id,
        models.WorkUnit.process_id == process_id,
        models.WorkUnit.user_id == user_id,
        models.WorkUnit.business_date == biz_date,
    ).first()

    if unit is None:
        prev = _find_previous_unit(company_id, task_id, process_id, user_id, biz_date, db)
        unit = models.WorkUnit(
            company_id=company_id,
            task_id=task_id,
            process_id=process_id,
            user_id=user_id,
            business_date=biz_date,
            created_at=datetime.utcnow(),
            input_source="web",   # 現場UIからは常に "web"（設計書: input_source）
            forecast_ref_id=prev.id if prev else None,
        )
        db.add(unit)
        db.flush()
        return unit, True

    return unit, False


def _build_line(
    work_unit_id: int,
    line_type: str,
    row: schemas.WorkUnitLineIn,
    db: Session,
) -> models.WorkUnitLine:
    """
    WorkUnitLine を構築し、target_selected / quantity_entered フラグを自動セットする。
    input_source は呼び出し元で WorkUnit に設定済みのため、行レベルでは不要。
    """
    category = None
    if row.item_id:
        item = db.get(models.TaskItem, row.item_id)
        category = item.category if item else None

    return models.WorkUnitLine(
        work_unit_id=work_unit_id,
        line_type=line_type,
        item_id=row.item_id,
        item_name_free=row.item_name_free,
        value=row.value,
        category=category,
        target_selected=row.item_id is not None,        # 対象が選ばれているか
        quantity_entered=row.value is not None,          # 数量が入力されているか
    )


def _with_lines(
    unit: models.WorkUnit,
    db: Session,
    already_submitted: bool = False,
) -> schemas.WorkUnitOut:
    """
    WorkUnitOut に actual_lines / planned_lines / prev_planned_lines / anomalies を付けて返す。
    prev_planned_lines は forecast_ref_id が指す前営業日 WorkUnit の planned_lines。
    already_submitted は実績/予告が既に登録済みだった状態で再送信された場合に True。
    """
    out = schemas.WorkUnitOut.model_validate(unit)
    out.actual_lines = []
    out.planned_lines = []
    out.prev_planned_lines = []
    out.anomalies = [schemas.WorkAnomalyOut.model_validate(a) for a in unit.anomalies]
    out.already_submitted = already_submitted

    for line in unit.lines:
        lo = _line_out(line, db)
        if line.line_type == "actual":
            out.actual_lines.append(lo)
        else:
            out.planned_lines.append(lo)

    # 前営業日の予告行（前回予告表示用）
    if unit.forecast_ref_id:
        prev_unit = db.get(models.WorkUnit, unit.forecast_ref_id)
        if prev_unit:
            out.prev_planned_lines = [
                _line_out(l, db) for l in prev_unit.lines if l.line_type == "planned"
            ]

    return out


def _line_out(line: models.WorkUnitLine, db: Session) -> schemas.WorkUnitLineOut:
    item_name = None
    if line.item_id:
        item = db.get(models.TaskItem, line.item_id)
        item_name = item.item_name if item else None
    elif line.item_name_free:
        item_name = line.item_name_free
    return schemas.WorkUnitLineOut(
        id=line.id,
        line_type=line.line_type,
        item_id=line.item_id,
        item_name_free=line.item_name_free,
        value=line.value,
        category=line.category,
        target_selected=line.target_selected,
        quantity_entered=line.quantity_entered,
        item_name=item_name,
    )


# ─────────────────────────────────────────
# エンドポイント
# ─────────────────────────────────────────

@router.post("/レコード作成", response_model=schemas.WorkUnitOut, summary="今日のレコードを取得または作成する")
def get_or_create_unit(body: schemas.UnitIdentifiers, db: Session = Depends(get_db)):
    """
    今日の business_date でレコードを取得します。なければ空のレコードを作成します。
    新規作成時は前営業日 WorkUnit を forecast_ref_id に自動紐づけします。
    """
    settings = _get_settings(body.company_id, db)
    unit, is_new = _get_or_create_unit(
        body.company_id, body.task_id, body.process_id, body.user_id, db, settings
    )
    if not is_new:
        raise_if_closed(unit)
    if is_new:
        log_event(db, EventType.CREATE_UNIT, body.company_id,
                  actor_role="field", actor_id=body.user_id,
                  related_record_id=unit.id,
                  payload={"task_id": body.task_id, "process_id": body.process_id,
                           "forecast_ref_id": unit.forecast_ref_id})
    anomaly_svc.detect_and_update(unit, settings, db)
    _recompute_work_status(unit, settings, db)
    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db)


@router.post("/次営業日開始", response_model=schemas.WorkUnitOut, summary="次の営業日を開始する（着手含む）")
def start_next_business_day(body: schemas.NextDayStartCreate, db: Session = Depends(get_db)):
    """
    完了画面から次の営業日を開始する。

    1. current_business_date の翌営業日を company_calendar に基づいて算出する。
    2. その business_date の work_unit を取得または作成する。
    3. 着手（started_at）を記録する（未着手の場合のみ）。
    4. 更新された work_unit を返す。
    """
    from datetime import date as date_type
    settings = _get_settings(body.company_id, db)

    # 完了済み業務日の翌営業日を算出
    try:
        current_date = date_type.fromisoformat(body.current_business_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="current_business_date の形式が不正です（YYYY-MM-DD）")

    next_biz_date = next_business_day(current_date, body.company_id, db)

    # 翌営業日の unit を取得または作成
    unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.company_id == body.company_id,
        models.WorkUnit.task_id == body.task_id,
        models.WorkUnit.process_id == body.process_id,
        models.WorkUnit.user_id == body.user_id,
        models.WorkUnit.business_date == next_biz_date,
    ).first()

    if unit is None:
        prev = _find_previous_unit(body.company_id, body.task_id, body.process_id,
                                   body.user_id, next_biz_date, db)
        unit = models.WorkUnit(
            company_id=body.company_id,
            task_id=body.task_id,
            process_id=body.process_id,
            user_id=body.user_id,
            business_date=next_biz_date,
            created_at=datetime.utcnow(),
            input_source="web",
            forecast_ref_id=prev.id if prev else None,
        )
        db.add(unit)
        db.flush()
        log_event(db, EventType.CREATE_UNIT, body.company_id,
                  actor_role="field", actor_id=body.user_id,
                  related_record_id=unit.id,
                  payload={"task_id": body.task_id, "process_id": body.process_id,
                           "forecast_ref_id": unit.forecast_ref_id,
                           "next_business_date": str(next_biz_date)})
    else:
        raise_if_closed(unit)

    # 着手記録（重複しない）
    if unit.started_at is None:
        unit.started_at = datetime.utcnow()
        log_event(db, EventType.START_WORK, unit.company_id,
                  actor_role="field", actor_id=unit.user_id,
                  related_record_id=unit.id,
                  payload={"started_at": unit.started_at.isoformat()})

    anomaly_svc.detect_and_update(unit, settings, db)
    _recompute_work_status(unit, settings, db)
    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db)


@router.post("/{unit_id}/着手", response_model=schemas.WorkUnitOut, summary="着手を記録する")
def create_started(unit_id: int, body: schemas.StartedCreate, db: Session = Depends(get_db)):
    """
    作業の開始を記録します。フェーズ1：すでに着手済みでも上書きせずそのまま返す。
    """
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    raise_if_closed(unit)
    settings = _get_settings(unit.company_id, db)

    if unit.started_at is None:
        unit.started_at = body.started_at or datetime.utcnow()
        log_event(db, EventType.START_WORK, unit.company_id,
                  actor_role="field", actor_id=unit.user_id,
                  related_record_id=unit_id,
                  payload={"started_at": unit.started_at.isoformat()})

    anomaly_svc.detect_and_update(unit, settings, db)
    _recompute_work_status(unit, settings, db)
    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db)


@router.post("/{unit_id}/実績一括", response_model=schemas.WorkUnitOut, summary="実績を複数行まとめて登録する")
def create_actual_bulk(unit_id: int, body: schemas.ActualBulkCreate, db: Session = Depends(get_db)):
    """
    実績行を一括で登録します。既存の実績行は置き換えられます。
    input_source は自動で "web" が設定されます（現場UIからの入力）。
    """
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    raise_if_closed(unit)
    settings = _get_settings(unit.company_id, db)

    # 再送信検出（フェーズ1：ブロックしないが記録する）
    was_already_submitted = unit.actual_at is not None

    # 既存の実績行を削除して上書き（冪等処理）
    for line in list(unit.lines):
        if line.line_type == "actual":
            db.delete(line)
    db.flush()

    total = 0.0
    for row in body.lines:
        if row.value is not None:
            total += row.value
        db.add(_build_line(unit_id, "actual", row, db))

    unit.actual_value = total if body.lines else None
    unit.actual_at = datetime.utcnow()
    unit.anomaly_type_a = body.anomaly_type_a or False
    unit.anomaly_type_b = body.anomaly_type_b or False

    db.flush()
    anomaly_svc.detect_and_update(unit, settings, db)
    _recompute_work_status(unit, settings, db)

    log_event(db, EventType.RECORD_ACTUAL, unit.company_id,
              actor_role="field", actor_id=unit.user_id,
              related_record_id=unit_id,
              payload={
                  "total": unit.actual_value,
                  "line_count": len(body.lines),
                  "is_invalid_flow": unit.is_invalid_flow,
                  "resubmit": was_already_submitted,  # 再送信ログ
              })

    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db, already_submitted=was_already_submitted)


@router.post("/{unit_id}/予告一括", response_model=schemas.WorkUnitOut, summary="予告を複数行まとめて登録する")
def create_planned_bulk(unit_id: int, body: schemas.PlannedBulkCreate, db: Session = Depends(get_db)):
    """予告行を一括で登録します。既存の予告行は置き換えられます。"""
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    raise_if_closed(unit)
    settings = _get_settings(unit.company_id, db)

    # 再送信検出
    was_already_submitted = unit.planned_at is not None

    for line in list(unit.lines):
        if line.line_type == "planned":
            db.delete(line)
    db.flush()

    total = 0.0
    for row in body.lines:
        if row.value is not None:
            total += row.value
        db.add(_build_line(unit_id, "planned", row, db))

    unit.planned_value = total if body.lines else None
    unit.planned_at = datetime.utcnow()

    db.flush()
    anomaly_svc.detect_and_update(unit, settings, db)
    _recompute_work_status(unit, settings, db)

    log_event(db, EventType.RECORD_FORECAST, unit.company_id,
              actor_role="field", actor_id=unit.user_id,
              related_record_id=unit_id,
              payload={
                  "total": unit.planned_value,
                  "line_count": len(body.lines),
                  "resubmit": was_already_submitted,
              })

    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db, already_submitted=was_already_submitted)


@router.post("/{unit_id}/承認", response_model=schemas.WorkUnitOut, summary="事務が承認して完了にする")
def approve(unit_id: int, body: schemas.ApprovalCreate, db: Session = Depends(get_db)):
    """事務担当者が内容を確認し、異常を承認して完了（closed）にします。"""
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_settings(unit.company_id, db)
    if is_closed(unit):
        db.refresh(unit)
        return _with_lines(unit, db)
    if unit.status == "normal":
        raise HTTPException(status_code=400, detail="異常がないため承認は不要です")

    from app.routers.work import _apply_minimal_judgement

    _apply_minimal_judgement(unit, settings, db=db, force_status="closed")
    if body.memo:
        unit.memo = body.memo

    # 関連する open 異常を resolved に更新
    for anomaly in unit.anomalies:
        if anomaly.status == "open":
            anomaly.status = "resolved"
            anomaly.resolved_at = datetime.utcnow()

    log_event(db, EventType.APPROVE_ANOMALY, unit.company_id,
              actor_role="office",
              related_record_id=unit_id,
              payload={"memo": body.memo})

    db.commit()
    db.refresh(unit)
    return _with_lines(unit, db)


@router.get("/一覧", response_model=List[schemas.WorkUnitOut], summary="作業記録の一覧を取得する（開発検証用）")
def list_units(
    company_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """company_id に紐づく作業記録を新しい順で返します（開発検証用）。"""
    units = (
        db.query(models.WorkUnit)
        .filter(models.WorkUnit.company_id == company_id)
        .order_by(models.WorkUnit.business_date.desc(), models.WorkUnit.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_with_lines(u, db) for u in units]


@router.get("/異常一覧", response_model=List[schemas.WorkUnitOut], summary="異常中の作業一覧を取得する")
def list_anomalies(company_id: str, db: Session = Depends(get_db)):
    """現在「青（異常あり）」になっている作業の一覧を返します。"""
    units = db.query(models.WorkUnit).filter(
        models.WorkUnit.company_id == company_id,
        models.WorkUnit.status == "blue",
    ).order_by(models.WorkUnit.business_date).all()
    return [_with_lines(u, db) for u in units]


@router.get("/{unit_id}", response_model=schemas.WorkUnitOut, summary="作業記録の詳細を取得する")
def get_work_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    return _with_lines(unit, db)
