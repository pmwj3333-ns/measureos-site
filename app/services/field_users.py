"""班長マスタ（field_users）と入力名の突き合わせ。"""

import unicodedata


def _norm_token(s: str) -> str:
    """全角英数・互換文字の揺れを吸収（班長マスタと user_id の一致率向上）。"""
    return unicodedata.normalize("NFKC", (s or "").strip())


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
