"""第5条: 現場異常分類（A/B 中分類）— Package A 任意入力。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

PROCESS_REASON_CODES = frozenset(
    {
        "input_forgotten",
        "sequence_skip",
        "deferred",
        "handoff_missing",
        "other",
    }
)

RESULT_REASON_CODES = frozenset(
    {
        "material_shortage",
        "equipment_stop",
        "work_error",
        "estimate_wrong",
        "priority_change",
        "other",
    }
)

PROCESS_REASON_LABELS: Dict[str, str] = {
    "input_forgotten": "入力忘れ",
    "sequence_skip": "順序飛び",
    "deferred": "後回し",
    "handoff_missing": "引継ぎ漏れ",
    "other": "その他",
}

RESULT_REASON_LABELS: Dict[str, str] = {
    "material_shortage": "材料不足",
    "equipment_stop": "設備停止",
    "work_error": "作業ミス",
    "estimate_wrong": "見立て違い",
    "priority_change": "突発優先変更",
    "other": "その他",
}

PROCESS_REASON_ORDER: List[str] = [
    "input_forgotten",
    "sequence_skip",
    "deferred",
    "handoff_missing",
    "other",
]

RESULT_REASON_ORDER: List[str] = [
    "material_shortage",
    "equipment_stop",
    "work_error",
    "estimate_wrong",
    "priority_change",
    "other",
]

FIELD_CLASSIFICATION_NOTE = (
    "※Package Aでは任意入力のため参考値です。"
    "※未入力は異常なしを意味しません。"
)

AUTO_CLASSIFICATION_LABEL = "（自動判定）"
PROCESS_PARENT_LABEL = "A 順序不備"
RESULT_PARENT_LABEL = "B 結果不備"


def _has_timestamp(value: object) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def _has_planned(row: dict) -> bool:
    return bool(row.get("planned_registered_at")) or _has_timestamp(row.get("planned_at"))


def _has_actual(row: dict) -> bool:
    return _has_timestamp(row.get("actual_at"))


def _has_started(row: dict) -> bool:
    return _has_timestamp(row.get("started_at"))


def row_has_empty_actual_content(row: dict) -> bool:
    """actual_at あり・actual_lines / actual_value なし（表示補完用）。"""
    if not _has_actual(row):
        return False
    lines = row.get("actual_lines")
    if isinstance(lines, list) and len(lines) > 0:
        return False
    val = row.get("actual_value")
    if val is not None:
        try:
            float(val)
            return False
        except (TypeError, ValueError):
            pass
    return True


def _system_pattern_segments(row: dict) -> List[str]:
    raw = str(row.get("system_pattern") or "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.replace(";", ",").replace("，", ",").split(",") if s.strip()]


def row_has_field_classification_input(row: dict) -> bool:
    """現場が A/B または中分類を入力済み（表示補完より優先）。"""
    if row.get("pattern_a") is True or row.get("pattern_b") is True:
        return True
    cls = row.get("anomaly_classification")
    if isinstance(cls, dict):
        if cls.get("process") or cls.get("result"):
            return True
    return False


def infer_auto_process_display(row: dict) -> bool:
    """
    現場未入力時に A 順序不備として補完表示する条件（表示のみ）。
    予告なし実績 / 順序不備 / 着手なし実績 / 入力忘れ / 後入力（A*）。
    """
    empty_actual = row_has_empty_actual_content(row)
    if empty_actual and _has_started(row):
        return False
    if row.get("is_invalid_flow") is True:
        if empty_actual and _has_started(row):
            return False
        return True
    if _has_actual(row) and not _has_started(row):
        return True
    if _has_actual(row) and not _has_planned(row):
        if empty_actual and _has_started(row):
            return False
        return True
    if row.get("is_missing") is True:
        return True
    if "A*" in _system_pattern_segments(row):
        if empty_actual and _has_started(row):
            return False
        return True
    return False


def infer_auto_result_display(row: dict) -> bool:
    """現場未入力時に B 結果不備として補完表示（数値乖離・実績内容なし）。"""
    if row.get("is_diff_anomaly") is True:
        return True
    if "B*" in _system_pattern_segments(row):
        return True
    if row_has_empty_actual_content(row) and _has_started(row):
        return True
    return False


def is_article7_only_without_ab(row: dict) -> bool:
    """7条逸脱のみ（A/B 補完対象なし）→ 現場分類は出さない。"""
    art7 = (
        row.get("is_article7_deviation") is True
        or row.get("is_deviation") is True
        or "7条逸脱" in _system_pattern_segments(row)
    )
    if not art7:
        return False
    return not infer_auto_process_display(row) and not infer_auto_result_display(row)


def resolve_field_classification_display(row: dict) -> dict:
    """
    行単位の現場分類表示（DB 変更なし）。
    mode: field | auto | none
    """
    if row_has_field_classification_input(row):
        cls = row.get("anomaly_classification")
        return {
            "mode": "field",
            "section_label": "現場分類",
            "classification": cls if isinstance(cls, dict) else {},
            "pattern_a": row.get("pattern_a") is True,
            "pattern_b": row.get("pattern_b") is True,
            "auto_process": False,
            "auto_result": False,
        }
    if is_article7_only_without_ab(row):
        return {
            "mode": "none",
            "section_label": "",
            "classification": {},
            "pattern_a": False,
            "pattern_b": False,
            "auto_process": False,
            "auto_result": False,
        }
    auto_a = infer_auto_process_display(row)
    auto_b = infer_auto_result_display(row)
    if not auto_a and not auto_b:
        return {
            "mode": "none",
            "section_label": "",
            "classification": {},
            "pattern_a": False,
            "pattern_b": False,
            "auto_process": False,
            "auto_result": False,
        }
    return {
        "mode": "auto",
        "section_label": "現場分類（自動判定）",
        "classification": {},
        "pattern_a": auto_a,
        "pattern_b": auto_b,
        "auto_process": auto_a,
        "auto_result": auto_b,
    }


def _dedupe_codes(codes: Any, allowed: frozenset) -> List[str]:
    if not isinstance(codes, list):
        return []
    out: List[str] = []
    seen: set = set()
    for raw in codes:
        code = str(raw or "").strip()
        if not code or code not in allowed or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def normalize_classification_input(
    raw: Any,
    *,
    parent_process: bool = False,
    parent_result: bool = False,
) -> Dict[str, List[str]]:
    """親 OFF の側は中分類を落とす。親 ON で子未選択は空配列。"""
    src = raw if isinstance(raw, dict) else {}
    process = _dedupe_codes(src.get("process"), PROCESS_REASON_CODES) if parent_process else []
    result = _dedupe_codes(src.get("result"), RESULT_REASON_CODES) if parent_result else []
    return {"process": process, "result": result}


def classification_to_json_blob(classification: Dict[str, List[str]]) -> Optional[str]:
    """DB 保存用。親 ON 側のみキーを含める（空配列可）。"""
    blob: Dict[str, List[str]] = {}
    if classification.get("process") is not None and "process" in classification:
        blob["process"] = list(classification.get("process") or [])
    if classification.get("result") is not None and "result" in classification:
        blob["result"] = list(classification.get("result") or [])
    if not blob:
        return None
    return json.dumps(blob, ensure_ascii=False, separators=(",", ":"))


def parse_classification_json(raw: Optional[str]) -> Optional[Dict[str, List[str]]]:
    if raw is None or not str(raw).strip():
        return None
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    out: Dict[str, List[str]] = {}
    if "process" in data:
        out["process"] = _dedupe_codes(data.get("process"), PROCESS_REASON_CODES)
    if "result" in data:
        out["result"] = _dedupe_codes(data.get("result"), RESULT_REASON_CODES)
    return out or None


def sync_pattern_flags_from_classification(
    *,
    parent_process: bool,
    parent_result: bool,
) -> Tuple[bool, bool, Optional[str]]:
    """pattern_a / pattern_b / user_pattern 同期（親チェック基準）。"""
    pattern_a = bool(parent_process)
    pattern_b = bool(parent_result)
    user_pattern = "B" if pattern_b else None
    return pattern_a, pattern_b, user_pattern


def build_storage_from_request(
    raw_classification: Any,
    *,
    parent_process: Optional[bool],
    parent_result: Optional[bool],
) -> Tuple[Optional[str], bool, bool, Optional[str]]:
    """
    リクエストから DB 保存値と pattern 同期結果を返す。
    parent_* が None のときは JSON の配列長から推定（後方互換）。
    """
    pa = bool(parent_process) if parent_process is not None else False
    pb = bool(parent_result) if parent_result is not None else False

    normalized = normalize_classification_input(
        raw_classification,
        parent_process=pa,
        parent_result=pb,
    )
    if parent_process is None and normalized.get("process"):
        pa = True
    if parent_result is None and normalized.get("result"):
        pb = True

    if not pa and not pb:
        return None, False, False, None

    to_store: Dict[str, List[str]] = {}
    if pa:
        to_store["process"] = normalized.get("process") or []
    if pb:
        to_store["result"] = normalized.get("result") or []

    json_blob = classification_to_json_blob(to_store)
    pattern_a, pattern_b, user_pattern = sync_pattern_flags_from_classification(
        parent_process=pa,
        parent_result=pb,
    )
    return json_blob, pattern_a, pattern_b, user_pattern


def classification_has_display_content(
    classification: Optional[Dict[str, List[str]]],
    *,
    pattern_a: Optional[bool] = None,
    pattern_b: Optional[bool] = None,
) -> bool:
    if pattern_a is True or pattern_b is True:
        return True
    if not classification:
        return False
    return bool(classification.get("process")) or bool(classification.get("result"))


def format_classification_lines(
    classification: Optional[Dict[str, List[str]]],
    *,
    pattern_a: Optional[bool] = None,
    pattern_b: Optional[bool] = None,
) -> List[str]:
    """事務詳細用テキスト行（HTML ではなくプレーン構造）。"""
    lines: List[str] = []
    cls = classification or {}
    show_process = pattern_a is True or bool(cls.get("process"))
    show_result = pattern_b is True or bool(cls.get("result"))

    if show_process:
        lines.append("プロセス不備")
        subs = cls.get("process") or []
        if subs:
            for code in subs:
                lines.append("・" + PROCESS_REASON_LABELS.get(code, code))
        else:
            lines.append("・（中分類未選択）")

    if show_result:
        lines.append("結果不備")
        subs = cls.get("result") or []
        if subs:
            for code in subs:
                lines.append("・" + RESULT_REASON_LABELS.get(code, code))
        else:
            lines.append("・（中分類未選択）")

    return lines


def aggregate_field_classification(rows: List[dict]) -> dict:
    """
    現場分類（参考）の件数集計。
    ① 現場入力の中分類 code をカウント
    ② 未入力時は system 判定から A/B 親分類を自動補完カウント（表示のみ）
    """
    counts_process: Dict[str, int] = {code: 0 for code in PROCESS_REASON_ORDER}
    counts_result: Dict[str, int] = {code: 0 for code in RESULT_REASON_ORDER}
    auto_process_count = 0
    auto_result_count = 0

    for row in rows:
        if row_has_field_classification_input(row):
            cls = row.get("anomaly_classification")
            if not cls or not isinstance(cls, dict):
                continue
            for code in cls.get("process") or []:
                if code in counts_process:
                    counts_process[code] += 1
            for code in cls.get("result") or []:
                if code in counts_result:
                    counts_result[code] += 1
            continue
        if is_article7_only_without_ab(row):
            continue
        if infer_auto_process_display(row):
            auto_process_count += 1
        if infer_auto_result_display(row):
            auto_result_count += 1

    def _breakdown(
        counts: Dict[str, int],
        labels: Dict[str, str],
        order: List[str],
    ) -> List[dict]:
        return [
            {"code": code, "label": labels[code], "count": counts[code]}
            for code in order
            if counts[code] > 0
        ]

    process_rows = _breakdown(counts_process, PROCESS_REASON_LABELS, PROCESS_REASON_ORDER)
    result_rows = _breakdown(counts_result, RESULT_REASON_LABELS, RESULT_REASON_ORDER)
    has_field = bool(process_rows or result_rows)
    has_auto = auto_process_count > 0 or auto_result_count > 0
    if has_field and has_auto:
        display_mode = "mixed"
    elif has_auto:
        display_mode = "auto"
    elif has_field:
        display_mode = "field"
    else:
        display_mode = "empty"

    out: dict = {
        "note": FIELD_CLASSIFICATION_NOTE,
        "display_mode": display_mode,
        "process": process_rows,
        "result": result_rows,
    }
    if auto_process_count > 0:
        out["auto_process"] = {
            "code": "__auto_process__",
            "label": AUTO_CLASSIFICATION_LABEL,
            "count": auto_process_count,
        }
    if auto_result_count > 0:
        out["auto_result"] = {
            "code": "__auto_result__",
            "label": AUTO_CLASSIFICATION_LABEL,
            "count": auto_result_count,
        }
    return out
