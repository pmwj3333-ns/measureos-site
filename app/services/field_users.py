"""班長マスタ（field_users）と入力名の突き合わせ。"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Dict, List, Tuple

_INTERNAL_PROCESS_ID = re.compile(r"^proc_\d+$", re.IGNORECASE)


def _norm_token(s: str) -> str:
    """全角英数・互換文字の揺れを吸収（班長マスタと user_id の一致率向上）。"""
    return unicodedata.normalize("NFKC", (s or "").strip())


def parse_field_user_entries(field_users_raw: str) -> List[Tuple[str, str]]:
    """field_users を (班長名, 工程表示名) のリストに分解。"""
    if not field_users_raw or not str(field_users_raw).strip():
        return []
    out: List[Tuple[str, str]] = []
    for part in str(field_users_raw).split(","):
        part = _norm_token(part)
        if not part:
            continue
        if ":" in part or "：" in part:
            sep = "：" if "：" in part and ":" not in part else ":"
            name, proc = part.split(sep, 1)
            name = _norm_token(name)
            proc = _norm_token(proc)
        else:
            name = _norm_token(part)
            proc = ""
        if name:
            out.append((name, proc))
    return out


def leader_name_from_user_id(user_id: str) -> str:
    """user_id の班長名部分（: より前）。"""
    s = _norm_token(user_id)
    for i, ch in enumerate(s):
        if ch in (":", "："):
            name = s[:i].strip()
            return name or s
    return s


def process_suffix_from_user_id(user_id: str) -> str:
    """user_id の工程部分（: より後）。無ければ空。"""
    s = _norm_token(user_id)
    for i, ch in enumerate(s):
        if ch in (":", "："):
            return s[i + 1 :].strip()
    return ""


def is_internal_process_id(process_id: str) -> bool:
    """社労士・経営者向け画面に出さない内部 process_id。"""
    pid = _norm_token(process_id)
    if not pid:
        return False
    if _INTERNAL_PROCESS_ID.match(pid):
        return True
    if len(pid) == 1 and pid.isascii() and pid.isalpha():
        return True
    return False


def build_process_id_display_map(
    rows: List[dict],
    field_users_raw: str,
) -> Dict[str, str]:
    """process_id → 表示工程名（班長マスタと user_id から推定）。"""
    leader_process = {
        name: proc for name, proc in parse_field_user_entries(field_users_raw) if proc
    }
    counts: Dict[str, Counter] = {}
    for r in rows or []:
        pid = _norm_token(str(r.get("process_id") or ""))
        if not pid:
            continue
        uid = str(r.get("user_id") or "")
        label = ""
        leader = leader_name_from_user_id(uid)
        if leader in leader_process:
            label = leader_process[leader]
        if not label:
            label = process_suffix_from_user_id(uid)
        if not label:
            continue
        counts.setdefault(pid, Counter())[label] += 1
    return {pid: counter.most_common(1)[0][0] for pid, counter in counts.items() if counter}


def resolve_process_display_name(
    *,
    process_id: str,
    user_id: str,
    field_users_raw: str,
    process_id_label_map: Dict[str, str] | None = None,
) -> str:
    """work_unit 行から社労士向け工程表示名を返す（内部 process_id は出さない）。"""
    pid = _norm_token(process_id)
    uid = str(user_id or "")
    leader = leader_name_from_user_id(uid)
    for name, proc in parse_field_user_entries(field_users_raw):
        if proc and name == leader:
            return proc
    suffix = process_suffix_from_user_id(uid)
    if suffix:
        return suffix
    if pid and process_id_label_map and pid in process_id_label_map:
        return process_id_label_map[pid]
    if pid and not is_internal_process_id(pid):
        return pid
    return "（未設定）"


def parse_master_names(field_users_raw: str) -> list[str]:
    """カンマ区切り。各要素は「名前」または「名前:工程」形式。照合は名前部分のみ。"""
    if not field_users_raw or not field_users_raw.strip():
        return []
    out: list[str] = []
    for part in field_users_raw.split(","):
        part = _norm_token(part)
        if not part:
            continue
        name = _norm_token(part.split(":", 1)[0])
        if name:
            out.append(name)
    return out


def classify_leader(user_id: str, field_users_raw: str) -> tuple[bool, str]:
    """
    Returns:
        (is_unregistered_user, user_source)
        user_source: "master" | "manual"
    """
    uid = _norm_token(user_id)
    names = parse_master_names(field_users_raw or "")
    # 班長マスタ未設定（空）の場合は全員「登録済み」扱いとし、A*/B* を付けられるようにする
    if not names:
        return False, "master"
    if uid in names:
        return False, "master"
    return True, "manual"
