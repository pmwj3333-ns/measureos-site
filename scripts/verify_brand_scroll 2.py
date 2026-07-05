#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
OUT = Path(__file__).resolve().parent.parent / "website" / "verify-output"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL, wait_until="networkidle")

    # Hero viewport (initial)
    page.screenshot(path=str(OUT / "viewport-hero.png"))

    # Scroll through page to trigger Intersection Observer
    page.evaluate(
        """async () => {
          const delay = ms => new Promise(r => setTimeout(r, ms));
          const h = document.documentElement.scrollHeight;
          for (let y = 0; y <= h; y += 400) {
            window.scrollTo(0, y);
            await delay(120);
          }
          window.scrollTo(0, 0);
          await delay(300);
        }"""
    )

    dom = page.evaluate(
        """() => {
          const hidden = [...document.querySelectorAll('.reveal')].filter(el => {
            const s = getComputedStyle(el);
            return s.opacity === '0' || s.visibility === 'hidden';
          });
          return {
            reveal_total: document.querySelectorAll('.reveal').length,
            reveal_still_hidden: hidden.length,
            hidden_samples: hidden.slice(0, 5).map(el => el.id || el.className),
          };
        }"""
    )

    page.screenshot(path=str(OUT / "viewport-after-scroll-top.png"), full_page=True)

    browser.close()

(OUT / "scroll-report.json").write_text(json.dumps(dom, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dom, ensure_ascii=False, indent=2))
