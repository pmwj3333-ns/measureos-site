"""
フェーズ2（赤・judgement 期限・信用度）機能の ON/OFF。

フェーズ1運用時は company_settings.phase2_enabled=False とし、
blue→red 昇格と judgement_red_deadline_at の返却を止める。
"""
from __future__ import annotations

from app import models


def is_phase2_enabled(settings: models.CompanySettings) -> bool:
    return bool(getattr(settings, "phase2_enabled", False))
