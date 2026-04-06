"""
テスト専用の参照時刻（擬似「現在」）。本番では無効のまま運用し、
MEASUREOS_ALLOW_TEST_CLOCK=1 のときのみ HTTP で上書き可能。

営業日算出・過去営業日の再計算など「カレンダー上の現在」に使う。
レコードの created_at / started_at / actual_at は従来どおり実システム時刻。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

_override_naive_utc: Optional[datetime] = None


def reference_utc_now() -> datetime:
    """営業日・再判定の基準時刻。上書きがなければ実 UTC。"""
    if _override_naive_utc is not None:
        return _override_naive_utc
    return datetime.utcnow()


def get_clock_state() -> Dict[str, Any]:
    active = _override_naive_utc is not None
    return {
        "active": active,
        "utc_iso": _override_naive_utc.isoformat() + "Z" if _override_naive_utc else None,
    }


def parse_iso_to_naive_utc(raw: str) -> datetime:
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def set_reference_utc_naive(naive_utc: Optional[datetime]) -> None:
    global _override_naive_utc
    _override_naive_utc = naive_utc
