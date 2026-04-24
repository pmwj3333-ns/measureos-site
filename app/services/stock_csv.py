"""在庫CSVのパース（第7条ステップ①）。計算ロジックは持たない。"""

from __future__ import annotations

import csv
import io
import math
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

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
    "stock_qty": [
        "stock_qty",
        "在庫数",
        "在庫数量",
        "stock",
        "qty",
        "数量",
        "在庫",
    ],
    "safety_stock": [
        "safety_stock",
        "安全在庫",
        "安全在庫数",
        "安全在庫数量",
        "min",
    ],
}

FIELD_ALIAS_SETS: Dict[str, set] = {}


def _norm_header_cell(s: str) -> str:
    t = unicodedata.normalize("NFKC", str(s).strip()).lower()
    t = re.sub(r"[\s\u3000]+", "", t)
    return t


def _build_alias_sets() -> None:
    global FIELD_ALIAS_SETS
    if FIELD_ALIAS_SETS:
        return
    FIELD_ALIAS_SETS = {
        field: {_norm_header_cell(a) for a in aliases}
        for field, aliases in FIELD_ALIASES.items()
    }


_build_alias_sets()


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
    req = ("product_code", "label", "stock_qty")
    if not all(f in out for f in req):
        return None
    return out


def cleanse_numeric_string(raw: object) -> str:
    """カンマ・全角数字・前後空白を除去し、float 解釈可能なASCII数字列に寄せる。"""
    t = unicodedata.normalize("NFKC", str(raw or "")).strip()
    t = t.replace(",", "").replace("，", "")
    t = re.sub(r"\s+", "", t)
    return t


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


def parse_stock_csv_text(text: str) -> Tuple[List[dict], int, Optional[str]]:
    """
    Returns:
      - rows: 有効行（product_code, label, stock_qty, safety_stock は省略可）
      - error_count: スキップしたデータ行数
      - fatal: ヘッダ不正・空ファイル等（このとき rows は空）
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
            "1行目に必須列（product_code・label・stock_qty、または 商品コード・商品名・在庫数 等）が見つかりません"
        )

    def get_cell(r: List[str], key: str) -> str:
        j = colmap[key]
        if j >= len(r):
            return ""
        return str(r[j])

    safety_ix: Optional[int] = colmap.get("safety_stock")

    out_rows: List[dict] = []
    err = 0

    for row in rows_iter[header_idx + 1 :]:
        if not row or not any(str(c).strip() for c in row):
            continue

        pc = get_cell(row, "product_code").strip()
        lb = get_cell(row, "label").strip()
        sq_raw = cleanse_numeric_string(get_cell(row, "stock_qty"))

        if not pc or not lb:
            err += 1
            continue

        stock_qty = _parse_float_required(sq_raw)
        if stock_qty is None:
            err += 1
            continue

        safety_stock: Optional[float] = None
        if safety_ix is not None and safety_ix < len(row):
            raw_ss = str(row[safety_ix])
            if not raw_ss.strip():
                safety_stock = None
            else:
                ss_clean = cleanse_numeric_string(raw_ss)
                safety_stock = _parse_float_required(ss_clean)
                if safety_stock is None:
                    err += 1
                    continue

        out_rows.append(
            {
                "product_code": pc,
                "label": lb,
                "stock_qty": stock_qty,
                "safety_stock": safety_stock,
            }
        )

    return out_rows, err, None


def dedupe_by_product_code(rows: List[dict]) -> List[dict]:
    """同一 product_code は後勝ち（全置換インポート向け）。"""
    by_code: Dict[str, dict] = {}
    for r in rows:
        by_code[str(r["product_code"]).strip()] = r
    return list(by_code.values())
