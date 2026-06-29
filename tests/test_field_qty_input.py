"""field_v2: 第5条数量欄の IME 安全な入力処理。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELD_V2_HTML = ROOT / "frontend" / "field_v2.html"


def _extract_fn(html: str, start: str, end: str) -> str:
    i = html.index(start)
    j = html.index(end, i + len(start))
    return html[i:j]


def test_field_v2_qty_binding_is_composition_aware():
    html = FIELD_V2_HTML.read_text(encoding="utf-8")
    assert "function bindQtyInputEvents" in html
    assert "function isQtyInputComposing" in html
    assert "function normalizeQtyInputInPlace" in html
    bind = _extract_fn(html, "function bindQtyInputEvents", "function isLogistics")
    assert "compositionstart" in bind
    assert "compositionend" in bind
    assert "finalizeQtyInputAfterComposition" in bind
    assert "normalizeQtyInputIfFullwidthPresent" in bind
    assert "addEventListener(\"blur\"" in bind
    assert "function finalizeQtyInputAfterComposition" in html
    assert "requestAnimationFrame" in html
    assert "normalizeNumberInput(qtyIn.value)" not in bind
    assert "qtyIn.value = v" not in bind


def test_sync_deviation_reason_panel_does_not_normalize_dom_on_read():
    html = FIELD_V2_HTML.read_text(encoding="utf-8")
    fn = _extract_fn(html, "function syncDeviationReasonPanel", "function article7BoardTier")
    assert "normalizeQtyInputsInHost(actualRowsHost())" not in fn


def test_submit_paths_force_normalize_qty_inputs():
    html = FIELD_V2_HTML.read_text(encoding="utf-8")
    assert re.search(
        r"function scanProductBlockLinesForSubmit[\s\S]*?"
        r"normalizeQtyInputsInHost\(host, \{ force: true \}\)",
        html,
    )
    assert re.search(
        r"function scanHostLinesForSubmit[\s\S]*?"
        r"normalizeQtyInputsInHost\(host, \{ force: true \}\)",
        html,
    )


def test_normalize_number_input_fullwidth():
    """Python mirror of normalizeNumberInput for regression."""
    import unicodedata

    def normalize_number_input(value):
        if value is None or value == "":
            return value
        out = []
        for ch in str(value):
            if "\uff10" <= ch <= "\uff19":
                out.append(chr(ord(ch) - 0xFEE0))
            else:
                out.append(ch)
        return "".join(out)

    assert normalize_number_input("１２３") == "123"
    assert normalize_number_input("110") == "110"
    assert normalize_number_input("") == ""
    assert normalize_number_input("12.5") == "12.5"
    assert len(normalize_number_input("１２")) == len("12")
