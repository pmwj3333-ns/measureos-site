"""出荷予定CSVのパース（第7条ステップ②）。在庫突合・第7条計算は行わない。"""

from __future__ import annotations

import csv
import io
import math
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.services.stock_csv import cleanse_numeric_string, _norm_header_cell

FIELD_ALIASES: Dict[str, List[str]] = {
    "product_code": [
        "product_code",
        "品番",
        "商品コード",
        "code",
        "コード",
    ],
    "label": [
        "label",
        "商品名",
        "ラベル",
        "品名",
        "name",
        "商品",
    ],
    "ship_qty": [
        "ship_qty",
        "出荷予定数",
        "出荷数",
        "出荷数量",
        "ship",
        "qty",
        "数量",
    ],
    "due_date": [
        "due_date",
        "納期",
        "希望納期",
        "出荷予定日",
        "delivery",
        "delivery_date",
        "due",
    ],
    "ordered_at": [
        "ordered_at",
        "受注時刻",
        "受注日時",
        "order_at",
        "ordered",
    ],
}

FIELD_ALIAS_SETS: Dict[str, set] = {
    field: {_norm_header_cell(a) for a in aliases}
    for field, aliases in FIELD_ALIASES.items()
}


def _resolve_header_indices(header_cells: List[str]) -> Optional[Dict[str, int]]:
    out: Dict[str, int] = {}
    for i, cell in enumerate(header_cells):
        n = _norm_header_cell(cell)
        if not n:
            continue
        for field, alias_set in FIELD_ALIAS_SETS.items():
            if field in out:
                continue
            if n in alias_set:
                out[field] = i
                break
    req = ("product_code", "label", "ship_qty", "due_date")
    if not all(f in out for f in req):
        return None
    return out


def parse_due_date(raw: object) -> Optional[str]:
    """YYYY-MM-DD に正規化。失敗時は None。"""
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", str(raw).strip())
    if not s:
        return None
    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    if "T" in s:
        s = s.split("T", 1)[0]
    elif " " in s:
        head = s.split()[0]
        if re.match(r"^\d{4}[-/.]", head):
            s = head
    s = s.replace(".", "-").replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def parse_ordered_at(raw: object) -> Optional[datetime]:
    """ISO8601 風を基本にパース。不可なら None（行はエラーにしないで任意列として扱う仕様）。"""
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", str(raw).strip())
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if re.match(r"^\d{4}-\d{2}-\d{2} \d", s):
        s = s.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_float_required(s: str) -> Optional[float]:
    if not s:
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    if not math.isfinite(x):
        return None
    return x


def parse_shipment_csv_text(text: str) -> Tuple[List[dict], int, Optional[str]]:
    """
    Returns:
      - rows: 有効行
      - error_count: スキップしたデータ行数
      - fatal: ヘッダ不正・空ファイル等
    """
    if not text or not str(text).strip():
        return [], 0, "CSVが空です"

    buf = io.StringIO(text.lstrip("\ufeff"))
    reader = csv.reader(buf)
    rows_iter = list(reader)

    header_idx = None
    header_cells: List[str] = []
    for i, row in enumerate(rows_iter):
        if row and any(str(c).strip() for c in row):
            header_idx = i
            header_cells = row
            break

    if header_idx is None:
        return [], 0, "データ行がありません"

    colmap = _resolve_header_indices(header_cells)
    if colmap is None:
        return [], 0, (
            "1行目に必須列（product_code・label・ship_qty・due_date、または 商品コード・商品名・出荷予定数・納期 等）が見つかりません"
        )

    def get_cell(r: List[str], key: str) -> str:
        j = colmap[key]
        if j >= len(r):
            return ""
        return str(r[j])

    ordered_ix: Optional[int] = colmap.get("ordered_at")

    out_rows: List[dict] = []
    err = 0

    for row in rows_iter[header_idx + 1 :]:
        if not row or not any(str(c).strip() for c in row):
            continue

        pc = get_cell(row, "product_code").strip()
        lb = get_cell(row, "label").strip()
        sq_raw = cleanse_numeric_string(get_cell(row, "ship_qty"))
        due_raw = get_cell(row, "due_date")

        if not pc or not lb:
            err += 1
            continue

        ship_qty = _parse_float_required(sq_raw)
        if ship_qty is None:
            err += 1
            continue

        due_norm = parse_due_date(due_raw)
        if due_norm is None:
            err += 1
            continue

        ordered_at: Optional[datetime] = None
        if ordered_ix is not None and ordered_ix < len(row):
            raw_o = row[ordered_ix]
            if raw_o is not None and str(raw_o).strip():
                ordered_at = parse_ordered_at(raw_o)

        out_rows.append(
            {
                "product_code": pc,
                "label": lb,
                "ship_qty": ship_qty,
                "due_date": due_norm,
                "ordered_at": ordered_at,
            }
        )

    return out_rows, err, None


def dedupe_by_product_code_and_due_date(rows: List[dict]) -> List[dict]:
    """同一 product_code + due_date は後勝ち（キー順は初出順、値は最終行）。"""
    by_key: Dict[Tuple[str, str], dict] = {}
    for r in rows:
        key = (str(r["product_code"]).strip(), str(r["due_date"]).strip())
        by_key[key] = r
    return list(by_key.values())
