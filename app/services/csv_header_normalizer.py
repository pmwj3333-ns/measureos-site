"""CSV 取込共通: ヘッダー行を canonical key に正規化する Header Normalizer。

会社ごとの列名マッピング（将来）を差し込めるよう、
DEFAULT_FIELD_ALIASES + IMPORT_SCHEMAS + optional company_overrides で構成する。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# canonical field → よく使われるヘッダー別名（正規化前の表記）
DEFAULT_FIELD_ALIASES: Dict[str, List[str]] = {
    "product_code": [
        "product_code",
        "商品コード",
        "品番",
        "コード",
        "code",
        "商品cd",
        "商品CD",
    ],
    "label": [
        "label",
        "商品名",
        "品名",
        "名称",
        "name",
        "product_name",
        "ラベル",
        "商品",
    ],
    "stock_qty": [
        "stock_qty",
        "在庫数",
        "現在庫",
        "数量",
        "棚卸数",
        "qty",
        "stock",
        "在庫",
        "在庫数量",
    ],
    "safety_stock": [
        "safety_stock",
        "安全在庫",
        "安全在庫数",
        "安全在庫数量",
        "min",
    ],
    "ship_qty": [
        "ship_qty",
        "出荷予定数",
        "出荷数",
        "予定数",
        "数量",
        "qty",
        "quantity",
        "出荷数量",
        "ship",
    ],
    "due_date": [
        "due_date",
        "納期",
        "出荷予定日",
        "出荷日",
        "delivery_date",
        "date",
        "希望納期",
        "delivery",
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

# 取込種別ごとの必須・任意列（canonical key）
IMPORT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "stock": {
        "label": "在庫CSV",
        "required": ("product_code", "label", "stock_qty"),
        "optional": ("safety_stock",),
    },
    "shipment": {
        "label": "出荷予定CSV",
        "required": ("product_code", "label", "ship_qty", "due_date"),
        "optional": ("ordered_at",),
    },
    "product_master": {
        "label": "商品マスタCSV",
        "required": ("label",),
        "optional": ("product_code", "safety_stock"),
    },
}


def normalize_header_cell(raw: object) -> str:
    """ヘッダー1セルを比較用に正規化（NFKC・小文字・空白除去）。"""
    t = unicodedata.normalize("NFKC", str(raw or "").strip()).lower()
    t = re.sub(r"[\s\u3000]+", "", t)
    return t


def schema_field_order(schema: str) -> Tuple[str, ...]:
    """スキーマ内フィールドの優先順（必須→任意）。"""
    cfg = IMPORT_SCHEMAS.get(schema)
    if cfg is None:
        raise KeyError(f"unknown csv import schema: {schema!r}")
    return tuple(cfg["required"]) + tuple(cfg.get("optional") or ())


def get_effective_aliases(
    schema: str,
    company_overrides: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[str]]:
    """
    スキーマ対象フィールドの別名一覧（canonical → 表示別名）。
    company_overrides は将来 DB から渡す拡張用（既存別名の後に追加）。
    """
    fields = schema_field_order(schema)
    out: Dict[str, List[str]] = {}
    for field in fields:
        merged: List[str] = list(DEFAULT_FIELD_ALIASES.get(field, []))
        if company_overrides and field in company_overrides:
            for alias in company_overrides[field]:
                s = str(alias or "").strip()
                if s and s not in merged:
                    merged.append(s)
        out[field] = merged
    return out


def build_alias_sets(
    schema: str,
    company_overrides: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, set]:
    """正規化済み別名 set（field → normalized aliases）。"""
    aliases = get_effective_aliases(schema, company_overrides)
    return {
        field: {normalize_header_cell(a) for a in names if str(a).strip()}
        for field, names in aliases.items()
    }


def resolve_header_indices(
    header_cells: Sequence[str],
    schema: str,
    company_overrides: Optional[Mapping[str, Sequence[str]]] = None,
) -> Optional[Dict[str, int]]:
    """
    ヘッダー行を canonical key → 列 index に解決する。
    必須列が揃わない場合は None。
    """
    if schema not in IMPORT_SCHEMAS:
        raise KeyError(f"unknown csv import schema: {schema!r}")

    alias_sets = build_alias_sets(schema, company_overrides)
    field_order = schema_field_order(schema)
    out: Dict[str, int] = {}

    for i, cell in enumerate(header_cells):
        n = normalize_header_cell(cell)
        if not n:
            continue
        for field in field_order:
            if field in out:
                continue
            if n in alias_sets.get(field, set()):
                out[field] = i
                break

    required = IMPORT_SCHEMAS[schema]["required"]
    if not all(f in out for f in required):
        return None
    return out


def missing_required_fields(
    header_cells: Sequence[str],
    schema: str,
    company_overrides: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[str]:
    """解決できなかった必須 canonical key の一覧。"""
    colmap = resolve_header_indices(header_cells, schema, company_overrides) or {}
    required = IMPORT_SCHEMAS[schema]["required"]
    return [f for f in required if f not in colmap]


def format_missing_header_error(schema: str) -> str:
    """パーサ fatal 用の日本語メッセージ。"""
    cfg = IMPORT_SCHEMAS[schema]
    label = cfg.get("label") or schema
    req = cfg["required"]
    examples: Dict[str, str] = {
        "product_code": "商品コード・品番",
        "label": "商品名・品名",
        "stock_qty": "在庫数・現在庫",
        "ship_qty": "出荷予定数・出荷数",
        "due_date": "納期・出荷予定日",
    }
    parts = [examples.get(f, f) for f in req]
    return (
        f"1行目に{label}の必須列（{' / '.join(parts)} 等）が見つかりません。"
        f" 内部キー: {', '.join(req)}"
    )


def export_schema_for_client(
    schema: str,
    company_overrides: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    """フロントエンド・将来の会社別マッピング UI 向け JSON。"""
    if schema not in IMPORT_SCHEMAS:
        raise KeyError(f"unknown csv import schema: {schema!r}")
    cfg = IMPORT_SCHEMAS[schema]
    return {
        "schema": schema,
        "label": cfg.get("label") or schema,
        "required": list(cfg["required"]),
        "optional": list(cfg.get("optional") or ()),
        "aliases": get_effective_aliases(schema, company_overrides),
    }
