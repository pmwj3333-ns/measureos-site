"""Package A/B/C 表示ラベル・D 互換・sr_v2 UI 文言。"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.services.package_rules import (
    package_bullets,
    package_description,
    package_display_code,
    package_label,
    package_tagline,
    package_targets,
)

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"
CO = "pkg_label_test_co"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "Package ラベルテスト"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register(client)
    return client


def test_package_labels_abc():
    assert package_label("A") == "現場可観測基盤"
    assert package_label("B") == "可観測運用制御"
    assert package_label("C") == "構造分析・経営最適化"


def test_package_d_display_compat():
    assert package_display_code("D") == "C"
    assert package_label("D") == package_label("C")
    assert package_tagline("D") == package_tagline("C")
    assert package_description("D") == package_description("C")
    assert package_bullets("D") == package_bullets("C")
    assert package_targets("D") == package_targets("C")


def test_package_taglines():
    assert package_tagline("A") == "現場を観測する"
    assert package_tagline("B") == "観測可能なまま現場を安定化する"
    assert package_tagline("C") == "現場構造を理解・分析・最適化する"


def test_sr_v2_html_package_ui_text():
    html = _read(SR_V2_HTML)
    assert "A — 現場可観測基盤" in html
    assert "B — 可観測運用制御" in html
    assert "C — 構造分析・経営最適化" in html
    assert "👉 現場を観測する" in html
    assert "👉 観測可能なまま現場を安定化する" in html
    assert "👉 現場構造を理解・分析・最適化する" in html
    assert "記録基盤" not in html
    assert "統制・強制" not in html
    assert 'value="D"' not in html
    assert "packageSelectValue" in html
    assert "運営ダッシュボード" in html
    assert "Package A 観測（会社詳細）" in html


def test_v2_company_api_package_meta(co_client: TestClient):
    r = co_client.put(
        f"/v2/company/{CO}/leaders",
        json={"leaders": [], "package_code": "D"},
    )
    assert r.status_code == 200, r.text

    r = co_client.get(f"/v2/company/{CO}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["package_code"] == "D"
    assert data["package_display_code"] == "C"
    assert data["package_label"] == "構造分析・経営最適化"
    assert data["package_tagline"] == "現場構造を理解・分析・最適化する"
    assert "AI分析基盤" in data["package_bullets"]


def test_v2_save_package_abc(co_client: TestClient):
    for code in ("A", "B", "C"):
        r = co_client.put(
            f"/v2/company/{CO}/leaders",
            json={"leaders": [], "package_code": code},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["package_code"] == code
        assert body["package_display_code"] == code
        assert body["package_label"] == package_label(code)

    r = co_client.put(
        f"/v2/company/{CO}/leaders",
        json={"leaders": [], "package_code": "D"},
    )
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["package_code"] == "D"
    assert saved["package_display_code"] == "C"


def test_observe_dashboard_unchanged_for_package_a(co_client: TestClient):
    co_client.put(
        f"/v2/company/{CO}/leaders",
        json={"leaders": [], "package_code": "A"},
    )
    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "summary" in data
    assert "recent_anomalies" in data
