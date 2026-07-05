#!/usr/bin/env python3
"""Browser verification for brand site at http://localhost:8000/"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
OUT_DIR = Path(__file__).resolve().parent.parent / "website" / "verify-output"
TARGETS = ["/", "/brand/css/tokens.css", "/brand/js/main.js"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = OUT_DIR / "browser-screenshot.png"
    report_path = OUT_DIR / "browser-report.json"

    report: dict = {
        "url": URL,
        "network": {},
        "console_errors": [],
        "console_warnings": [],
        "dom": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def on_console(msg):
            entry = {"type": msg.type, "text": msg.text}
            if msg.type == "error":
                report["console_errors"].append(entry)
            elif msg.type == "warning":
                report["console_warnings"].append(entry)

        page.on("console", on_console)

        responses: dict[str, dict] = {}

        def on_response(response):
            path = response.url.replace("http://localhost:8000", "").split("?")[0] or "/"
            if path in TARGETS:
                responses[path] = {
                    "status": response.status,
                    "content_type": response.headers.get("content-type", ""),
                }

        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screenshot_path), full_page=True)

        report["network"] = {t: responses.get(t, {"status": None, "content_type": ""}) for t in TARGETS}

        dom = page.evaluate(
            """() => {
              const h1 = document.querySelector('#opening-title');
              const h1Style = h1 ? getComputedStyle(h1) : null;
              const reveals = [...document.querySelectorAll('.reveal')];
              const visibleReveals = reveals.filter(el => el.classList.contains('is-visible'));
              return {
                title: document.title,
                h1_text: h1 ? h1.innerText : null,
                h1_opacity: h1Style ? h1Style.opacity : null,
                h1_visible: h1 ? h1.offsetHeight > 0 && h1Style.opacity !== '0' : false,
                reveal_total: reveals.length,
                reveal_visible_count: visibleReveals.length,
                body_text_length: document.body.innerText.trim().length,
                html_received: document.documentElement.outerHTML.length > 500,
              };
            }"""
        )
        report["dom"] = dom

        browser.close()

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("SCREENSHOT:", screenshot_path)
    print("REPORT:", report_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    ok_network = all(report["network"].get(t, {}).get("status") == 200 for t in TARGETS)
    ok_visible = report["dom"].get("h1_visible") is True
    ok_no_errors = len(report["console_errors"]) == 0

    if ok_network and ok_visible and ok_no_errors:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
