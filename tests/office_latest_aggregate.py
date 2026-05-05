"""
事務 office_v2「実績（最新のみ）」の商品単位集約ロジックの参照実装。
frontend/office_v2.html の collectLatestActualRows（実績一覧は normal/closed のみ）
と同一アルゴリズムであることを保つこと（変更時は両方更新）。
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote


def _encode_uri_component_like_js(s: str) -> str:
    """ブラウザ encodeURIComponent と同等（office_v2 の officeLatestKey 生成と揃える）。"""
    return quote(s, safe="-_.!~*'()")


def norm_office_ws(s: Any) -> str:
    return re.sub(r"\s+", "", str(s or ""), flags=re.UNICODE)


def raw_line_label_for_display(L: Optional[dict]) -> str:
    if not L or not isinstance(L, dict):
        return ""

    def pick(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, list):
            return "".join("" if x is None else str(x) for x in raw)
        return str(raw)

    a = pick(L.get("label"))
    if a != "":
        return a
    return pick(L.get("item_name"))


def resolve_lines_array_for_display(row: dict, kind: str) -> List[dict]:
    key = "planned_lines" if kind == "planned" else "actual_lines"
    arr = row.get(key)
    if not isinstance(arr, list) or not arr:
        raw_key = "planned_lines_json" if kind == "planned" else "actual_lines_json"
        raw = row.get(raw_key)
        if raw is not None and str(raw).strip():
            try:
                data = json.loads(str(raw))
                if isinstance(data, list):
                    arr = data
            except (json.JSONDecodeError, TypeError):
                arr = []
    return arr if isinstance(arr, list) else []


def legacy_raw_actual_label(row: dict) -> str:

    def pick(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, list):
            return "".join("" if x is None else str(x) for x in raw)
        return str(raw)

    for f in ("actual_item_name", "actual_work_label", "actual_work_type"):
        s = pick(row.get(f))
        if s != "":
            return s
    return ""


def office_product_key_from_line(L: dict) -> str:
    if not L or not isinstance(L, dict):
        return "__none__"
    pc = str(L.get("product_code") or "").strip()
    if pc:
        return pc
    lab = raw_line_label_for_display(L)
    return norm_office_ws(lab) or "__none__"


def natural_key(r: dict) -> str:
    return "\x1e".join(
        [
            str(r.get("company_id") or ""),
            str(r.get("task_id") or ""),
            str(r.get("process_id") or ""),
            str(r.get("user_id") or ""),
            str(r.get("business_date") or ""),
        ]
    )


def _finite_qty(v: Any) -> bool:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x)


def has_actual_row(r: dict) -> bool:
    if not r.get("actual_at") or str(r.get("actual_at") or "").strip() == "":
        return False
    arr = resolve_lines_array_for_display(r, "actual")
    if arr:
        return any(
            L
            and L.get("value") is not None
            and _finite_qty(L.get("value"))
            for L in arr
        )
    av = r.get("actual_value")
    return av is not None and _finite_qty(av)


def row_eligible_for_latest_actual_section(r: dict) -> bool:
    """実績「最新のみ」候補。青・赤は上段要注意のみ。"""
    if not has_actual_row(r):
        return False
    st = str(r.get("status") or "").strip().lower()
    return st in ("normal", "closed")


def actual_product_keys_for_row(r: dict) -> Set[str]:
    keys: Set[str] = set()
    arr = resolve_lines_array_for_display(r, "actual")
    for L in arr:
        if not L or not isinstance(L, dict):
            continue
        if L.get("value") is None or not _finite_qty(L.get("value")):
            continue
        keys.add(office_product_key_from_line(L))
    if not keys:
        av = r.get("actual_value")
        name = legacy_raw_actual_label(r)
        if name and av is not None and _finite_qty(av):
            keys.add(norm_office_ws(name) or "__none__")
    return keys


def collect_latest_slices(source_rows: Optional[List[dict]]) -> List[dict]:
    """
    office_v2 と同様に list の各行 dict を入力し、表示スライスを返す。
    各要素: office_latest_key, office_unit_row（API 行そのもの）, office_product_key
    blue/red の行は含めない。
    """
    by_composite: Dict[str, Dict[str, Any]] = {}
    candidates = [
        r for r in (source_rows or []) if r and row_eligible_for_latest_actual_section(r)
    ]
    candidates.sort(key=lambda x: int(x.get("id") or 0))
    for r in candidates:
        nk = natural_key(r)
        for pk in actual_product_keys_for_row(r):
            ck = nk + "\x1e" + pk
            prev = by_composite.get(ck)
            if not prev or int(r.get("id") or 0) > int(prev["row"].get("id") or 0):
                by_composite[ck] = {"row": r, "product_key": pk}
    slices = list(by_composite.values())
    slices.sort(
        key=lambda v: (
            str(v["row"].get("business_date") or ""),
            int(v["row"].get("id") or 0),
        ),
        reverse=True,
    )
    out = []
    for v in slices:
        uid = int(v["row"].get("id") or 0)
        pk = v["product_key"]
        key = str(uid) + "\x1f" + _encode_uri_component_like_js(pk)
        out.append(
            {
                "office_latest_key": key,
                "office_unit_row": v["row"],
                "office_product_key": pk,
            }
        )
    return out
