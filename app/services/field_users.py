"""班長マスタ（field_users）と入力名の突き合わせ。"""


def parse_master_names(field_users_raw: str) -> list[str]:
    """カンマ区切り。各要素は「名前」または「名前:工程」形式。照合は名前部分のみ。"""
    if not field_users_raw or not field_users_raw.strip():
        return []
    out: list[str] = []
    for part in field_users_raw.split(","):
        part = part.strip()
        if not part:
            continue
        name = part.split(":", 1)[0].strip()
        if name:
            out.append(name)
    return out


def classify_leader(user_id: str, field_users_raw: str) -> tuple[bool, str]:
    """
    Returns:
        (is_unregistered_user, user_source)
        user_source: "master" | "manual"
    """
    uid = (user_id or "").strip()
    names = parse_master_names(field_users_raw or "")
    if not names:
        return True, "manual"
    if uid in names:
        return False, "master"
    return True, "manual"
