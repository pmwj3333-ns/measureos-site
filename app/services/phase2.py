"""互換レイヤ: フェーズ2可否は package_code 由来（package_rules.is_phase2_enabled）。"""
from app.services.package_rules import is_phase2_enabled  # noqa: F401

__all__ = ["is_phase2_enabled"]
