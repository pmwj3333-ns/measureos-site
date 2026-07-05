"""会社検索（company_id / company_name）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.company_search import search_active_companies

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"
CTX_JS = ROOT / "frontend" / "static" / "sr_v2_company_context.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sr_v2_company_search_ui_uses_search_api():
    html = _read(SR_V2_HTML)
    assert "既存会社を検索（ID・会社名）" in html
    assert "/admin/companies/search?q=" in html
    assert "fetchCompanySearchHits" in html


def test_sr_v2_search_select_still_loads_company():
    html = _read(SR_V2_HTML)
    assert "selectCompanyFromSearch" in html
    assert "await load()" in html
    assert "updateCompanyQuery(cid)" in html


def test_filter_active_companies_by_name_and_id_js_helper():
    script = _read(CTX_JS)
    runner = (
        script
        + """
const rows = [
  { company_id: 'test1', company_name: '株式会社サンプル1', is_active: true },
  { company_id: 'test2', company_name: '株式会社サンプル', is_active: true },
  { company_id: 'old_co', company_name: '旧会社', is_active: false },
];
const byName = SrV2CompanyContext.filterActiveCompaniesForSearch(rows, 'サンプル');
if (byName.length !== 2) throw new Error('expected 2 name hits got ' + byName.length);
const byId = SrV2CompanyContext.filterActiveCompaniesForSearch(rows, 'test');
if (byId.length !== 2) throw new Error('expected 2 id hits got ' + byId.length);
console.log('ok');
"""
    )
    out = subprocess.run(
        ["node", "-e", runner],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr or out.stdout


def test_search_active_companies_by_settings_name():
    db = SessionLocal()
    try:
        db.add(
            models.CompanyMaster(
                company_id="search_test2",
                company_name="search_test2",
                is_active=True,
            )
        )
        db.merge(
            models.CompanySettings(
                company_id="search_test2",
                company_name="株式会社サンプル",
            )
        )
        db.commit()
        hits = search_active_companies(db, "株式会社サンプル")
    finally:
        db.close()

    assert any(h["company_id"] == "search_test2" for h in hits)
    match = next(h for h in hits if h["company_id"] == "search_test2")
    assert match["company_name"] == "株式会社サンプル"


def test_search_api_by_name_and_id(client: TestClient):
    db = SessionLocal()
    try:
        db.add(
            models.CompanyMaster(
                company_id="search_test8",
                company_name="株式会社テスト8",
                is_active=True,
            )
        )
        db.add(
            models.CompanyMaster(
                company_id="search_inactive_x",
                company_name="株式会社テスト無効",
                is_active=False,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/admin/companies/search", params={"q": "株式会社"})
    assert r.status_code == 200, r.text
    ids = {x["company_id"] for x in r.json()}
    assert "search_test8" in ids
    assert "search_inactive_x" not in ids

    r2 = client.get("/admin/companies/search", params={"q": "test8"})
    assert r2.status_code == 200
    assert any(x["company_id"] == "search_test8" for x in r2.json())

    r3 = client.get("/admin/companies/search", params={"q": "存在しない語"})
    assert r3.status_code == 200
    assert r3.json() == []


def test_search_api_empty_query(client: TestClient):
    r = client.get("/admin/companies/search", params={"q": "  "})
    assert r.status_code == 200
    assert r.json() == []
