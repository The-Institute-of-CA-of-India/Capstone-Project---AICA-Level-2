"""Export docs/CashSense_Explainer.html to PDF (A4, light theme) with headless Microsoft Edge.

    python scripts/export_explainer.py [--preview DIR]   (--preview also saves desktop / phone screenshots)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "CashSense_Explainer.html"
PDF = ROOT / "docs" / "CashSense_Explainer.pdf"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    args = ap.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        if args.preview:
            out = Path(args.preview)
            out.mkdir(parents=True, exist_ok=True)
            for name, size, scheme in (("desktop", (1100, 900), "light"), ("phone", (390, 844), "light"),
                                       ("desktop_dark", (1100, 900), "dark")):
                page = browser.new_page(viewport={"width": size[0], "height": size[1]}, color_scheme=scheme)
                page.goto(HTML.as_uri())
                page.screenshot(path=str(out / f"explainer_{name}.png"), full_page=True)
                page.close()
        page = browser.new_page(color_scheme="light")
        page.goto(HTML.as_uri())
        page.emulate_media(media="print")
        page.pdf(path=str(PDF), format="A4", print_background=True,
                 margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
        browser.close()
    print("PDF:", PDF)


if __name__ == "__main__":
    main()
