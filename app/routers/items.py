from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.event_log import log_event, EventType

router = APIRouter(prefix="/対象", tags=["対象マスター"])


@router.post("/登録", response_model=schemas.TaskItemOut, summary="【現場】商品・作業を新規登録する")
def create_item(body: schemas.TaskItemCreate, db: Session = Depends(get_db)):
    """
    現場が新規作成した商品・作業をマスターに保存します。
    現場は追加のみ可能です（編集・削除は事務が行います）。
    """
    item = models.TaskItem(
        company_id=body.company_id,
        item_code=body.item_code,
        item_name=body.item_name,
        category=body.category or "generic",
    )
    db.add(item)
    db.flush()

    log_event(db, EventType.CREATE_TARGET, body.company_id,
              actor_role="field",
              target_id=item.id,
              payload={"item_name": item.item_name, "category": item.category})

    db.commit()
    db.refresh(item)
    return item


@router.get("/一覧", response_model=List[schemas.TaskItemOut], summary="商品・作業リストを取得する")
def list_items(company_id: str, db: Session = Depends(get_db)):
    """企業の有効な商品・作業リストを返します。"""
    return db.query(models.TaskItem).filter(
        models.TaskItem.company_id == company_id,
        models.TaskItem.is_active == True,
    ).order_by(models.TaskItem.item_code, models.TaskItem.item_name).all()


@router.put("/{item_id}/編集", response_model=schemas.TaskItemOut, summary="【事務】商品名・品番・区分を修正する")
def edit_item(item_id: int, body: schemas.ItemEditBody, db: Session = Depends(get_db)):
    """事務が商品名・品番・対象区分を修正します。"""
    item = db.get(models.TaskItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    before = {"item_name": item.item_name, "item_code": item.item_code, "category": item.category}
    if body.item_name is not None:
        item.item_name = body.item_name
    if body.item_code is not None:
        item.item_code = body.item_code
    if body.category is not None:
        item.category = body.category

    log_event(db, EventType.EDIT_TARGET, item.company_id,
              actor_role="office",
              target_id=item_id,
              payload={"before": before,
                       "after": {"item_name": item.item_name,
                                 "item_code": item.item_code,
                                 "category": item.category}})

    db.commit()
    db.refresh(item)
    return item


@router.post("/統合", summary="【事務】重複商品を統合する")
def merge_items(body: schemas.ItemMergeBody, db: Session = Depends(get_db)):
    """重複・表記ゆれのある商品を統合します。"""
    keep = db.get(models.TaskItem, body.keep_id)
    if not keep:
        raise HTTPException(status_code=404, detail="残す商品が見つかりません")
    if body.keep_id in body.merge_ids:
        raise HTTPException(status_code=400, detail="同じ商品は統合できません")

    merged_names = []
    for remove_id in body.merge_ids:
        remove = db.get(models.TaskItem, remove_id)
        if not remove:
            continue
        merged_names.append(remove.item_name)
        db.query(models.WorkUnit).filter(
            models.WorkUnit.item_id == remove_id
        ).update({"item_id": body.keep_id})
        db.query(models.WorkUnitLine).filter(
            models.WorkUnitLine.item_id == remove_id
        ).update({"item_id": body.keep_id})
        remove.is_active = False

    log_event(db, EventType.MERGE_TARGET, keep.company_id,
              actor_role="office",
              target_id=body.keep_id,
              payload={"keep_id": body.keep_id,
                       "merge_ids": body.merge_ids,
                       "merged_names": merged_names})

    db.commit()
    return {"結果": "統合しました", "残したID": body.keep_id, "統合した商品名": merged_names}


@router.delete("/{item_id}", summary="【事務】商品を無効化する")
def deactivate_item(item_id: int, db: Session = Depends(get_db)):
    """商品を非表示にします（データは残ります）。"""
    item = db.get(models.TaskItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    log_event(db, EventType.HIDE_TARGET, item.company_id,
              actor_role="office",
              target_id=item_id,
              payload={"item_name": item.item_name})

    item.is_active = False
    db.commit()
    return {"結果": "無効化しました", "商品名": item.item_name}
