#!/usr/bin/env python3
"""Capture real app screenshots for brand site V chapter evidence."""
from __future__ import annotations

import json
import sys
from datetime import datetime, time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.priority_rebuild import rebuild_priority_items_for_company  # noqa: E402

BASE = "http://127.0.0.1:8000"
OUT = ROOT / "website" / "assets" / "img"
COMPANY_ID = "brand_evidence_co"
PASSWORD = "BrandEvidence1"


def _setup_company(client: httpx.Client) -> None:
    r = client.put(
        f"{BASE}/v2/company/{COMPANY_ID}/leaders",
        json={
            "leaders": [{"name": "班長A", "process": "組立"}],
            "company_name": "Brand Evidence Co",
            "company_password": PASSWORD,
        },
    )
    r.raise_for_status()


def _login(client: httpx.Client) -> None:
    r = client.post(
        f"{BASE}/v2/office/login",
        json={"company_id": COMPANY_ID, "password": PASSWORD},
    )
    r.raise_for_status()


def _cookies_for_playwright(client: httpx.Client) -> list[dict]:
    jar = client.cookies.jar
    cookies = []
    for cookie in jar:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": "127.0.0.1",
                "path": cookie.path or "/",
            }
        )
    return cookies


def _seed_evidence_data() -> dict:
    """Priority / Observe 用データと Field 予告画面用 work unit を DB に投入。"""
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        cid = COMPANY_ID

        db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid).delete(
            synchronize_session=False
        )
        db.query(models.PriorityItem).filter(models.PriorityItem.company_id == cid).delete(
            synchronize_session=False
        )
        db.commit()

        settings = db.query(models.CompanySettings).filter_by(company_id=cid).first()
        if not settings:
            db.add(
                models.CompanySettings(
                    company_id=cid,
                    unit="個",
                    tolerance_value=0,
                    day_boundary_time=time(0, 0),
                    package_code="A",
                    input_mode="manufacturing",
                )
            )

        products = [
            ("410C", "410C", 20.0),
            ("520A", "520A", 15.0),
            ("630B", "630B", 10.0),
        ]
        for code, label, safety in products:
            row = (
                db.query(models.ProductMaster)
                .filter_by(company_id=cid, product_code=code)
                .first()
            )
            if not row:
                row = (
                    db.query(models.ProductMaster)
                    .filter_by(company_id=cid, label=label)
                    .first()
                )
            if row:
                row.product_code = code
                row.label = label
                row.is_active = True
                row.safety_stock_value = safety
                row.updated_at = now
            else:
                db.add(
                    models.ProductMaster(
                        company_id=cid,
                        product_code=code,
                        label=label,
                        is_active=True,
                        safety_stock_value=safety,
                        created_at=now,
                        updated_at=now,
                    )
                )

        db.query(models.StockItem).filter(models.StockItem.company_id == cid).delete(
            synchronize_session=False
        )
        for code, label, qty in [
            ("410C", "410C", 30.0),
            ("520A", "520A", 25.0),
            ("630B", "630B", 40.0),
        ]:
            db.add(
                models.StockItem(
                    company_id=cid,
                    product_code=code,
                    label=label,
                    stock_qty=qty,
                    created_at=now,
                )
            )

        db.query(models.ShipmentPlanItem).filter(
            models.ShipmentPlanItem.company_id == cid
        ).delete(synchronize_session=False)
        for code, label, ship, due in [
            ("410C", "410C", 80.0, "2099-06-01"),
            ("520A", "520A", 70.0, "2099-06-02"),
            ("630B", "630B", 90.0, "2099-06-03"),
        ]:
            db.add(
                models.ShipmentPlanItem(
                    company_id=cid,
                    product_code=code,
                    label=label,
                    ship_qty=ship,
                    due_date=due,
                    created_at=now,
                )
            )

        db.commit()
        rebuild_priority_items_for_company(cid, db)
        db.commit()

        # 観測ダッシュボード: 未着手予告・第7条警告を出す（Field 用 work unit と natural key を分離）
        observe_shell = models.WorkUnit(
            company_id=cid,
            task_id="410C",
            process_id="組立",
            user_id="班長A",
            business_date=now.date(),
            status="normal",
            planned_lines_json=json.dumps(
                [{"label": "410C", "value": 10}], ensure_ascii=False
            ),
            planned_registered_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(observe_shell)

        db.query(models.PriorityItem).filter(
            models.PriorityItem.company_id == cid,
            models.PriorityItem.product_code == "630B",
        ).update({"is_after_cutoff": True}, synchronize_session=False)

        unset_row = (
            db.query(models.ProductMaster)
            .filter_by(company_id=cid, product_code="630B")
            .first()
        )
        if unset_row:
            unset_row.safety_stock_value = None

        db.commit()

        return {
            "id": None,
            "company_id": cid,
            "task_id": "520A",
            "process_id": "組立",
            "user_id": "班長A",
            "planned_lines": [
                {"label": "410C", "value": 10},
                {"label": "520A", "value": 8},
            ],
        }
    finally:
        db.close()


def _seed_field_planned_work(client: httpx.Client, template: dict) -> dict:
    """Field 予告画面用 work unit（観測集計と natural key が重ならない task）。"""
    r = client.post(
        "/v2/work",
        json={
            "company_id": template["company_id"],
            "task_id": template["task_id"],
            "process_id": template["process_id"],
            "user_id": template["user_id"],
        },
    )
    r.raise_for_status()
    body = r.json()
    return {
        **body,
        "planned_lines": template["planned_lines"],
    }


def _capture_field_screenshot(page, work_data: dict, dest: Path) -> None:
    """現場盤：予告画面（第7条一覧 + 予告入力）。"""
    resp = page.goto(f"{BASE}/field/v2", wait_until="networkidle", timeout=30000)
    if not resp or resp.status != 200:
        raise RuntimeError(f"field/v2 status={getattr(resp, 'status', None)}")

    page.wait_for_function("typeof showPlannedScreen === 'function'", timeout=15000)
    page.evaluate(
        """async (data) => {
          document.getElementById('overlay').classList.add('hidden');
          const hu = document.getElementById('header-user');
          if (hu) hu.textContent = '班長A';
          unitId = data.id;
          lastWorkData = data;
          await showPlannedScreen(data);
          await refreshArticle7Panels();
        }""",
        work_data,
    )
    page.wait_for_selector("#screen-planned.active", timeout=10000)
    page.wait_for_selector("#article7-board-planned .a7-card-wrap", timeout=15000)
    page.wait_for_selector("#planned-rows-mfg .multi-row-line", timeout=10000)
    page.wait_for_timeout(800)
    clip = page.evaluate(
        """() => {
          const header = document.querySelector('header');
          const intro = document.querySelector('#screen-planned .field-intro-panel');
          const card = document.querySelector('#screen-planned .field-planned-card');
          if (!header || !card) return null;
          const top = header.getBoundingClientRect().top;
          const bottom = card.getBoundingClientRect().bottom + 16;
          return {
            x: 0,
            y: Math.max(0, top),
            width: document.documentElement.clientWidth,
            height: bottom - top,
          };
        }"""
    )
    if clip:
        page.screenshot(path=str(dest), full_page=False, clip=clip)
    else:
        page.screenshot(path=str(dest), full_page=False)


def _capture_priority_screenshot(page, dest: Path) -> None:
    url = f"{BASE}/priority/v2"
    resp = page.goto(url, wait_until="networkidle", timeout=30000)
    if not resp or resp.status != 200:
        raise RuntimeError(f"priority/v2 status={getattr(resp, 'status', None)}")
    page.wait_for_selector(".prio-row", timeout=15000)
    page.wait_for_timeout(600)
    clip = page.evaluate(
        """() => {
          const panelHead = document.querySelector('.wrap .panel .panel-head');
          const rows = document.querySelectorAll('.prio-row');
          if (!panelHead || !rows.length) return null;
          const top = panelHead.getBoundingClientRect().top - 4;
          const last = rows[rows.length - 1];
          return {
            x: 0,
            y: Math.max(0, top),
            width: document.documentElement.clientWidth,
            height: last.getBoundingClientRect().bottom + 20,
          };
        }"""
    )
    if clip:
        page.screenshot(path=str(dest), full_page=False, clip=clip)
    else:
        page.screenshot(path=str(dest), full_page=False)


def _capture_observe_screenshot(page, dest: Path) -> None:
    url = f"{BASE}/sr/v2?tab=observe&company={COMPANY_ID}"
    resp = page.goto(url, wait_until="networkidle", timeout=30000)
    if not resp or resp.status != 200:
        raise RuntimeError(f"sr/v2 observe status={getattr(resp, 'status', None)}")
    page.wait_for_selector("#observe-summary .observe-stat", timeout=15000)
    page.wait_for_function(
        """() => {
          const vals = [...document.querySelectorAll('#observe-summary .observe-stat-value')];
          return vals.some(el => el.textContent.trim() !== '0');
        }""",
        timeout=15000,
    )
    page.wait_for_timeout(800)
    page.evaluate(
        """() => {
          const fc = document.querySelector('#observe-field-classification-heading')
            ?.closest('.observe-section');
          if (fc) fc.style.display = 'none';
          const panel = document.getElementById('panel-observe');
          if (!panel) return;
          panel.querySelector('.observe-back-link')?.style.setProperty('display', 'none');
          panel.querySelector('.observe-detail-head')?.style.setProperty('display', 'none');
          panel.querySelector('.observe-bar')?.style.setProperty('display', 'none');
        }"""
    )
    page.wait_for_selector("#observe-process tr", timeout=15000)
    clip = page.evaluate(
        """() => {
          const panel = document.getElementById('panel-observe');
          const sections = panel ? panel.querySelectorAll('.observe-section') : [];
          const processSection = sections[3];
          const msg = document.getElementById('observe-msg');
          const kpiSection = sections[0];
          if (!processSection) return null;
          const topEl =
            msg && msg.textContent.trim() ? msg : kpiSection;
          if (!topEl) return null;
          const top = topEl.getBoundingClientRect().top - 8;
          const tbody = processSection.querySelector('tbody');
          const firstRow = tbody && tbody.querySelector('tr');
          const thead = processSection.querySelector('thead');
          const bottom = firstRow
            ? firstRow.getBoundingClientRect().bottom + 20
            : thead
              ? thead.getBoundingClientRect().bottom + 16
              : processSection.getBoundingClientRect().bottom + 12;
          return {
            x: 0,
            y: Math.max(0, top),
            width: document.documentElement.clientWidth,
            height: bottom - top,
          };
        }"""
    )
    if clip:
        page.screenshot(path=str(dest), full_page=False, clip=clip)
    else:
        page.screenshot(path=str(dest), full_page=False)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as client:
        health = client.get("/")
        if health.status_code != 200:
            print(f"Server not ready: GET / -> {health.status_code}", file=sys.stderr)
            return 1

        _setup_company(client)
        _login(client)
        field_template = _seed_evidence_data()
        field_work = _seed_field_planned_work(client, field_template)
        cookies = _cookies_for_playwright(client)

    targets = [
        ("field.png", "field_planned"),
        ("priority.png", "priority"),
        ("observe.png", "observe"),
    ]

    report: dict = {"captures": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()

        for filename, kind in targets:
            dest = OUT / filename
            try:
                if kind == "field_planned":
                    _capture_field_screenshot(page, field_work, dest)
                    capture_url = f"{BASE}/field/v2#planned"
                elif kind == "priority":
                    _capture_priority_screenshot(page, dest)
                    capture_url = f"{BASE}/priority/v2"
                else:
                    _capture_observe_screenshot(page, dest)
                    capture_url = f"{BASE}/sr/v2?tab=observe&company={COMPANY_ID}"
                size = dest.stat().st_size
                report["captures"].append(
                    {
                        "file": filename,
                        "url": capture_url,
                        "bytes": size,
                        "ok": size > 20000,
                    }
                )
                print(f"OK {filename} ({size} bytes)")
            except Exception as exc:
                report["captures"].append(
                    {"file": filename, "kind": kind, "error": str(exc), "ok": False}
                )
                print(f"FAIL {filename}: {exc}", file=sys.stderr)

        browser.close()

    report_path = OUT / "capture-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = [c for c in report["captures"] if not c.get("ok")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
