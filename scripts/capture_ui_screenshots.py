"""Capture UI screenshots for the paper's System section (fig6a-c).

Requires the app running locally (streamlit run src/app/app.py --server.port 8620).
Run: python scripts/capture_ui_screenshots.py
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "papers/figures"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8620"

SPEC = ("Over-ear wireless headphones, 50mm titanium drivers, hybrid ANC with "
        "transparency mode, 40-hour battery, Bluetooth 5.3 multipoint, aluminum "
        "frame, memory foam cushions, foldable, USB-C fast charge, IPX4, "
        "2-year warranty with free replacement")


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        # boot streamlit once so the tornado routes are injected
        page.goto(BASE, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(6_000)

        page.goto(f"{BASE}/app-premium", wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(2_000)

        # fill the simulator
        page.fill("input[placeholder*='SoundWave']", "AeroPods Pro X")
        price = page.locator("input[type='number']").first
        price.fill("79.99")
        page.fill("textarea", SPEC)

        # spec critique (mock off -> real LLM; falls back per provider pool)
        page.click("button:has-text('Review my spec')")
        page.wait_for_timeout(25_000)
        page.screenshot(path=OUT / "fig6b_spec_coach.png", full_page=False)
        print("captured fig6b_spec_coach.png")

        # prediction
        page.click("button:has-text('Predict success')")
        page.wait_for_timeout(30_000)
        page.screenshot(path=OUT / "fig6a_prediction.png", full_page=False)
        print("captured fig6a_prediction.png")

        # analyzer tab (honest benchmark table incl. FAIL row)
        page.click("button:has-text('Analyzer')")
        page.wait_for_timeout(2_500)
        page.screenshot(path=OUT / "fig6c_analyzer.png", full_page=False)
        print("captured fig6c_analyzer.png")

        browser.close()


if __name__ == "__main__":
    main()
