"""同一 natural key 内の実績履歴から「訂正」を検知する（Package A・第5条）。"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models


def natural_key_tuple(unit: models.WorkUnit) -> Tuple[str, str, str, str, str]:
    return (
        unit.company_id,
        unit.task_id,
        unit.process_id,
        unit.user_id,
        str(unit.business_date),
    )


def _norm_ws(s: Any) -> str:
    return "".join(str(s or "").split())


def revision_product_key_from_line(line: Dict[str, Any]) -> str:
    """訂正判定用 product_key（product_code があればそれ、なければラベル正規化）。"""
    pc = str(line.get("product_code") or "").strip()
    if pc:
        return pc
    lab = (
        str(line.get("label") or "").strip()
        or str(line.get("item_name") or "").strip()
    )
    return _norm_ws(lab) or "__none__"


def display_label_for_revision_key(pk: str, line_hint: Dict[str, Any]) -> str:
    lab = (
        str(line_hint.get("label") or "").strip()
        or str(line_hint.get("item_name") or "").strip()
    )
    if lab:
        return lab
    if pk and pk != "__none__":
        return pk
    return ""


def _parse_actual_lines(unit: models.WorkUnit) -> List[Dict[str, Any]]:
    raw = getattr(unit, "actual_lines_json", None)
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def revision_normalized_actual_qty_map(
    unit: models.WorkUnit,
) -> Tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    """訂正用・キーは revision_product_key と同一規則。"""
    qty: Dict[str, float] = {}
    hints: Dict[str, Dict[str, Any]] = {}
    lines = _parse_actual_lines(unit)
    if lines:
        for line in lines:
            if not isinstance(line, dict):
                continue
            try:
                v = line.get("value")
                if v is None:
                    continue
                fv = float(v)
            except (TypeError, ValueError):
                continue
            pk = revision_product_key_from_line(line)
            qty[pk] = qty.get(pk, 0.0) + fv
            if pk not in hints:
                hints[pk] = line
        return qty, hints

    av = getattr(unit, "actual_value", None)
    if av is None:
        return qty, hints
    try:
        fv = float(av)
    except (TypeError, ValueError):
        return qty, hints

    name = (
        str(getattr(unit, "actual_item_name", None) or "").strip()
        or str(getattr(unit, "actual_work_label", None) or "").strip()
        or str(getattr(unit, "actual_work_type", None) or "").strip()
    )
    pk = _norm_ws(name) or "__none__"
    qty[pk] = qty.get(pk, 0.0) + fv
    if pk not in hints:
        hints[pk] = {"label": name or None}
    return qty, hints


def unit_has_meaningful_actual(unit: models.WorkUnit) -> bool:
    if getattr(unit, "actual_at", None) is None:
        return False
    q, _ = revision_normalized_actual_qty_map(unit)
    return bool(q)


def _fmt_qty(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return str(v)


def _finite_qty(q: Optional[float]) -> Optional[float]:
    if q is None:
        return None
    try:
        x = float(q)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def _build_revision_detail_payload(snaps: List[models.WorkUnit]) -> Optional[Dict[str, Any]]:
    """
    商品単位で訂正を判定する。
    natural key は company/task/process/user/business_date に加え、比較対象は各 product_key ごとの履歴。
    同一 product_key が複数スナップショットに載ったとき、その末尾2件の数量だけを比較する。
    ・別商品の追加／削除だけでは訂正にならない（当該キーの履歴が1件のみになるため）
    ・最新 WorkUnit に当該商品が載っていない数量変化は表示しない（古い訂正を最新行に引きずらない）
    """
    if len(snaps) < 2:
        return None
    latest_id = snaps[-1].id

    chains: Dict[str, List[Tuple[int, float]]] = {}
    hints: Dict[str, Dict[str, Any]] = {}

    for u in snaps:
        m, h = revision_normalized_actual_qty_map(u)
        for pk, qv in m.items():
            fq = _finite_qty(qv)
            if fq is None:
                continue
            chains.setdefault(pk, []).append((u.id, fq))
            if pk in h:
                hints[pk] = h[pk]

    lines: List[str] = []
    for pk in sorted(chains.keys()):
        ch = chains[pk]
        if len(ch) < 2:
            continue
        _, q_prev = ch[-2]
        id_curr, q_curr = ch[-1]
        if id_curr != latest_id:
            continue
        if abs(q_prev - q_curr) < 1e-9:
            continue
        label = display_label_for_revision_key(pk, hints.get(pk, {})).strip()
        if not label:
            continue
        lines.append(f"{label}：{_fmt_qty(q_prev)} → {_fmt_qty(q_curr)}（訂正）")

    if not lines:
        return None

    return {
        "is_actual_revision": True,
        "actual_revision_detail_line": "\n".join(lines),
        "actual_revision_notice_strong": True,
    }


def fetch_units_same_natural(db: Session, unit: models.WorkUnit) -> List[models.WorkUnit]:
    return (
        db.query(models.WorkUnit)
        .filter(
            models.WorkUnit.company_id == unit.company_id,
            models.WorkUnit.task_id == unit.task_id,
            models.WorkUnit.process_id == unit.process_id,
            models.WorkUnit.user_id == unit.user_id,
            models.WorkUnit.business_date == unit.business_date,
        )
        .order_by(models.WorkUnit.id.asc())
        .all()
    )


def compute_actual_revision_meta_for_unit(db: Session, unit: models.WorkUnit) -> Dict[str, Any]:
    """save_actual 直後など・単一行に対する訂正メタ（この行が最新実績スナップショットのときのみ埋まる）。"""
    empty = {
        "is_actual_revision": False,
        "actual_revision_detail_line": None,
        "actual_revision_notice_strong": False,
    }
    if not unit_has_meaningful_actual(unit):
        return empty

    siblings = fetch_units_same_natural(db, unit)
    snaps = [u for u in siblings if unit_has_meaningful_actual(u)]
    if len(snaps) < 2 or snaps[-1].id != unit.id:
        return empty

    payload = _build_revision_detail_payload(snaps)
    return payload if payload else empty


def enrich_units_actual_revision_meta(
    units: List[models.WorkUnit],
    db: Session,
) -> Dict[int, Dict[str, Any]]:
    """一覧用・各行 id に付与する flat dict。"""
    base_empty = {
        "is_actual_revision": False,
        "actual_revision_detail_line": None,
        "actual_revision_notice_strong": False,
    }

    nk_fetch: Dict[Tuple[str, str, str, str, str], List[models.WorkUnit]] = {}
    unique_nks = {natural_key_tuple(u) for u in units}

    for nk in unique_nks:
        cid, tid, pid, uid, bd = nk
        q = (
            db.query(models.WorkUnit)
            .filter(
                models.WorkUnit.company_id == cid,
                models.WorkUnit.task_id == tid,
                models.WorkUnit.process_id == pid,
                models.WorkUnit.user_id == uid,
                models.WorkUnit.business_date == bd,
            )
            .order_by(models.WorkUnit.id.asc())
        )
        nk_fetch[nk] = q.all()

    out: Dict[int, Dict[str, Any]] = {}
    for u in units:
        out[u.id] = dict(base_empty)

    for nk, sibs in nk_fetch.items():
        snaps = [x for x in sibs if unit_has_meaningful_actual(x)]
        if len(snaps) < 2:
            continue
        payload = _build_revision_detail_payload(snaps)
        if not payload:
            continue

        latest = snaps[-1]
        out[latest.id] = payload

    return out
