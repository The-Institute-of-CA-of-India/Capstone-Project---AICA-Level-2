"""End-to-end browser test (needs playwright + chromium):  python tests/browser_test.py SAMPLES_DIR OUT_DIR"""
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
samples, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
files = [str(p) for p in sorted(samples.glob("[01][0-9]_*"))]
env = dict(os.environ, REDACTOR_NO_BROWSER="1", REDACTOR_PORT="8597")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=APP, env=env)
errors = []
try:
    time.sleep(4)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto("http://127.0.0.1:8597", wait_until="networkidle")
        pg.wait_for_selector("text=Prepare documents for AI review")
        pg.fill("#c-pans", "AAKCS1234F")
        pg.fill("#c-dates", "15/04/1980")
        pg.fill("#c-names", "Sample Traders")
        pg.locator("#file-input").set_input_files(files)
        pg.wait_for_selector(f"text=Redact {len(files)} files")
        pg.screenshot(path=str(out / "1_composer.png"))
        pg.click("#btn-settings")
        time.sleep(0.4)
        pg.screenshot(path=str(out / "2_settings.png"))
        pg.click("text=Done")
        pg.click("#btn-start")
        pg.wait_for_selector(".frow", timeout=300000)
        pg.wait_for_selector(".pg img", timeout=60000)
        time.sleep(2)
        pg.screenshot(path=str(out / "3_workspace.png"))

        # open the HDFC statement, original view
        pg.locator(".frow", has_text="08_hdfc").click()
        pg.wait_for_selector(".mark")
        pg.keyboard.press("o")
        time.sleep(1.2)
        pg.screenshot(path=str(out / "4_original_marks.png"))

        # click a mark to leave it visible (IFSC), draw a box over the deposit amount
        n_before = pg.locator(".mark.redacted").count()
        pg.locator(".mark").first.click()
        assert pg.locator(".mark.pending-keep").count() == 1, "toggle failed"
        pg.keyboard.press("d")
        import pymupdf
        doc = pymupdf.open(samples / "08_hdfc_statement.pdf")
        pw, ph = doc[0].rect.width, doc[0].rect.height
        ws = [w for w in doc[0].get_text("words") if w[4] in ("CASH", "SELF")]
        bx = (min(w[0] for w in ws) - 2, min(w[1] for w in ws) - 1, max(w[2] for w in ws) + 2, max(w[3] for w in ws) + 1)
        page_el = pg.locator(".pg").first.bounding_box()
        sx = lambda x: page_el["x"] + x / pw * page_el["width"]
        sy = lambda y: page_el["y"] + y / ph * page_el["height"]
        pg.mouse.move(sx(bx[0]), sy(bx[1])); pg.mouse.down(); pg.mouse.move(sx(bx[2]), sy(bx[3]), steps=6); pg.mouse.up()
        assert pg.locator(".mbox").count() == 1, "draw failed"
        pg.wait_for_selector(".textpop", timeout=10000)
        assert "CASH DEPOSIT BY SELF" in pg.locator(".textpop").inner_text(), pg.locator(".textpop").inner_text()
        pg.screenshot(path=str(out / "5a_textpop.png"))
        pg.locator(".textpop button", has_text="Just this box").click()
        assert pg.locator("#pending").is_visible()
        print("pending:", pg.locator("#pending-text").inner_text())
        pg.screenshot(path=str(out / "5_pending.png"))
        pg.keyboard.press("Control+Enter")
        pg.wait_for_selector("text=Applied to 08_hdfc_statement.pdf", timeout=60000)
        time.sleep(1)
        assert pg.locator(".mbox.saved").count() == 1
        assert pg.locator(".mark.kept").count() >= 1
        pg.keyboard.press("s")
        time.sleep(1.5)
        pg.screenshot(path=str(out / "6_split_after_apply.png"))

        # batch-wide: leave a counterparty visible in all files via the item menu
        pg.locator(".irow", has_text="NAME-1").first.hover()
        pg.locator(".irow", has_text="NAME-1").first.locator(".imenu").click()
        pg.click("text=Redact this text in all files")
        pg.wait_for_selector("text=Redacted in all files", timeout=120000)

        # add tab: words for all files
        pg.click("[data-tab=add]")
        pg.fill("#tab-add textarea", "Interest credit")
        pg.locator("#tab-add .seg button", has_text="All files").click()
        pg.locator("#tab-add button", has_text="Redact").last.click()
        pg.wait_for_selector("text=Redacted in all files", timeout=120000)
        pg.click("[data-tab=details]")
        time.sleep(0.5)
        pg.screenshot(path=str(out / "7_details.png"))

        # draw over a counterparty name on the SBI statement -> every match in this file
        pg.locator(".frow", has_text="01_sbi").click()
        pg.wait_for_selector(".mark")
        pg.keyboard.press("o"); pg.keyboard.press("d")
        time.sleep(0.8)
        doc = pymupdf.open(samples / "01_sbi_statement_digital.pdf")
        pw, ph = doc[0].rect.width, doc[0].rect.height
        w = [w for w in doc[0].get_text("words") if w[4] == "Interest"][0]
        page_el = pg.locator(".pg").first.bounding_box()
        sx = lambda x: page_el["x"] + x / pw * page_el["width"]
        sy = lambda y: page_el["y"] + y / ph * page_el["height"]
        pg.mouse.move(sx(w[0] - 1), sy(w[1] - 1)); pg.mouse.down(); pg.mouse.move(sx(w[2] + 1), sy(w[3] + 1), steps=5); pg.mouse.up()
        pg.wait_for_selector(".textpop", timeout=10000)
        pg.locator(".textpop button", has_text="Every match in this file").click()
        pg.wait_for_selector("text=Applied to 01_sbi_statement_digital.pdf", timeout=60000)
        pg.click("[data-tab=items]")
        time.sleep(0.5)
        pg.screenshot(path=str(out / "7b_sbi_after_terms.png"))

        # office file and downloads
        pg.locator(".frow", has_text="10_statement").click()
        time.sleep(1)
        pg.screenshot(path=str(out / "8_excel.png"))
        pg.click("#btn-download")
        pg.screenshot(path=str(out / "9_download.png"))
        with pg.expect_download() as d:
            pg.locator(".pop button", has_text="Download ZIP").click()
        d.value.save_as(out / "ai.zip")
        pg.click("#btn-records")
        pg.fill("#rec-tool", "Claude (Anthropic)")
        pg.screenshot(path=str(out / "10_records.png"))
        with pg.expect_download() as d2:
            pg.click("text=All records (ZIP)")
        d2.value.save_as(out / "records.zip")
        print("browser test passed; console errors:", errors)
        br.close()
finally:
    srv.terminate()
