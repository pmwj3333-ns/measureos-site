"""ログイン後の元画面復帰（return_to）— 内部パスのみ許可。"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote


def safe_return_to_path(raw: Optional[str]) -> Optional[str]:
    """
    許可: / で始まる同一オリジン相対パス。
    禁止: 外部 URL、//host、スキーム付き URL。
    """
    s = (raw or "").strip()
    if not s:
        return None
    if not s.startswith("/"):
        return None
    if s.startswith("//"):
        return None
    if "://" in s:
        return None
    if "\\" in s:
        return None
    if "#" in s:
        s = s.split("#", 1)[0].strip()
    return s or None


def build_office_login_url(return_to: Optional[str]) -> str:
    safe = safe_return_to_path(return_to)
    if not safe:
        return "/office/v2"
    return f"/office/v2?return_to={quote(safe, safe='')}"


def login_redirect_response(return_to: Optional[str], *, headers: dict) -> str:
    """307 redirect 先 URL（テスト・呼び出し側で RedirectResponse に渡す）。"""
    return build_office_login_url(return_to)
