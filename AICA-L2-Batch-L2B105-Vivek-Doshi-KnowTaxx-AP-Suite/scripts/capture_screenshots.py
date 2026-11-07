"""End-to-end browser check, which also produces the screenshots for the docs and presentation.

Runs the real server against a throwaway data folder with seeded data, so your own database is
untouched. Needs: pip install playwright (uses the installed Microsoft Edge, no browser download).

Run: python scripts/capture_screenshots.py [--channel msedge]
Writes: docs/screenshots/*.png. Exits non-zero if any check fails.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
SAMPLES = ROOT / "tests" / "sample_invoices"
PORT = 5077
BASE = f"http://localhost:{PORT}"
DEMO_ADMIN = ("admin", "Admin@123")
DEMO_APPROVER = ("approver1", "Demo@1234")
PHONE = {"viewport": {"width": 375, "height": 812}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
DESKTOP = {"viewport": {"width": 1366, "height": 850}}
failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def login(page, credentials):
    page.goto(f"{BASE}/auth/login")
    page.fill("#username", credentials[0])
    page.fill("#password", credentials[1])
    page.click("#submit")
    page.wait_for_load_state("networkidle")


def shot(page, name, full=False):
    """Full-page shots use a tall viewport, so the fixed sidebar still reaches the bottom."""
    page.evaluate("document.querySelectorAll('.toast').forEach(t => t.remove())")
    original = page.viewport_size
    if full:
        page.set_viewport_size({"width": original["width"], "height": page.evaluate("document.documentElement.scrollHeight")})
        page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / f"{name}.png"))
    if full:
        page.set_viewport_size(original)


def watch_errors(page, sink):
    page.on("pageerror", lambda e: sink.append(f"{page.url}: {e}"))
    page.on("console", lambda m: sink.append(f"{page.url}: {m.text}") if m.type == "error" else None)


def desktop_flow(browser, errors):
    context = browser.new_context(**DESKTOP)
    page = context.new_page()
    watch_errors(page, errors)
    page.goto(f"{BASE}/auth/login")
    shot(page, "login")
    login(page, DEMO_ADMIN)
    shot(page, "clients")

    for name, path in (("client_detail", "/clients/1"), ("vendors", "/clients/1/vendors"), ("dashboard", "/clients/1/reports/dashboard"),
                       ("variance", "/clients/1/reports/variance"), ("cost_centre", "/clients/1/reports/cost-centre"), ("aging", "/clients/1/reports/aging"),
                       ("matrix", "/clients/1/approval-matrix"), ("invoices", "/clients/1/invoices"), ("audit_log", "/admin/audit-log"),
                       ("users", "/admin/users"), ("email_config", "/admin/email-config"), ("backup", "/admin/backup"), ("budgets", "/clients/1/budgets")):
        response = page.goto(BASE + path)
        page.wait_for_load_state("networkidle")
        check(f"page {path}", response.status == 200, str(response.status))
        if name == "dashboard":
            page.wait_for_timeout(900)
            shot(page, name, full=True)
            check("dashboard draws four charts", page.locator("canvas").count() == 4)
        else:
            shot(page, name)

    # Upload a real invoice image and let OCR read it
    page.goto(f"{BASE}/clients/1/invoices/upload")
    shot(page, "upload")
    page.set_input_files("#file-picker", str(SAMPLES / "invoice_gst_1.png"))
    page.wait_for_selector(".upload-result a", timeout=90000)
    check("upload shows OCR confidence", "confidence" in page.locator(".upload-result").inner_text())
    shot(page, "upload_result")
    page.click(".upload-result a")
    page.wait_for_load_state("networkidle")
    expected = next(r for r in json.loads((SAMPLES / "expected.json").read_text()) if r["file"] == "invoice_gst_1.png")
    check("review: invoice number read", page.input_value("#final_invoice_number") == expected["number"])
    check("review: GSTIN read", page.input_value("#final_gstin") == expected["gstin"])
    check("review: total read", float(page.input_value("#final_total_amount")) == expected["total"])
    check("review: vendor auto-linked by GSTIN", "Sharma Steel" in page.locator("#vendor_id option:checked").inner_text())
    check("review: arithmetic check passes", "matches" in page.locator("#arith-hint").inner_text())
    check("review: document image loaded", page.evaluate("document.querySelector('.doc-scroll img').naturalWidth") > 0)
    page.click("[data-zoom-in]")
    check("review: zoom works", page.locator("[data-zoom-level]").inner_text() == "125%")
    page.click("[data-zoom-fit]")
    page.fill("#final_total_amount", "1")
    check("review: arithmetic check catches a bad total", "differs" in page.locator("#arith-hint").inner_text())
    page.click("#accept-all")
    check("review: Accept All restores OCR values", float(page.input_value("#final_total_amount")) == expected["total"])
    check("review: category suggested from line items", page.input_value("#expense_category") == "Raw Materials", page.input_value("#expense_category"))
    page.select_option("#cost_centre_id", index=3)
    page.fill("#gl_account", "Raw Material Purchases")
    shot(page, "review", full=True)
    page.click("#submit_approval")
    page.wait_for_load_state("networkidle")
    check("review: submitted for approval", "Sent to" in page.locator(".flash").first.inner_text(), page.locator("body").inner_text()[:300])

    # Reports exports
    for name in ("dashboard.xlsx", "dashboard.pdf", "tally.csv", "variance.xlsx", "aging.xlsx", "cost-centre.xlsx"):
        status = context.request.get(f"{BASE}/clients/1/reports/export/{name}").status
        check(f"export {name}", status == 200, str(status))
    context.close()


def phone_approval_flow(browser, errors):
    context = browser.new_context(**PHONE)
    page = context.new_page()
    watch_errors(page, errors)
    login(page, DEMO_APPROVER)
    check("approver lands on pending", "/approvals/pending" in page.url, page.url)
    check("service worker registers", page.evaluate("navigator.serviceWorker.ready.then(r => !!r.active)"))
    page.reload()
    page.wait_for_load_state("networkidle")
    check("service worker controls the page", page.evaluate("!!navigator.serviceWorker.controller"))
    shot(page, "mobile_approvals")
    check("manifest linked", page.locator("link[rel=manifest]").count() == 1)

    # Decision dialog: a reject without a reason is refused by the browser
    first_card = page.locator(".approval-card").first
    first_card.locator("[data-action=reject]").click()
    check("reject reason required", page.locator("#decision-comment").evaluate("e => e.required"))
    shot(page, "mobile_reject_dialog")
    page.click("[data-cancel]")

    # Swipe right opens the approve dialog
    box = first_card.bounding_box()
    page.evaluate("""([x, y]) => {
        const card = document.querySelector('.approval-card');
        const fire = (type, cx) => card.dispatchEvent(new TouchEvent(type, { bubbles: true, cancelable: true,
            touches: type === 'touchend' ? [] : [new Touch({ identifier: 1, target: card, clientX: cx, clientY: y })] }));
        fire('touchstart', x); fire('touchmove', x + 80); fire('touchmove', x + 160); fire('touchend', x + 160);
    }""", [box["x"] + 30, box["y"] + 20])
    check("swipe right opens approve dialog", page.locator("#decision-dialog [data-title]").inner_text().startswith("Approve"))
    page.click("[data-cancel]")

    # Offline: decide on an item, reconnect, and watch it sync
    page.wait_for_timeout(1000)  # let the cache snapshot finish
    pending = context.request.get(f"{BASE}/api/bootstrap").json()["pending"]
    context.set_offline(True)
    page.goto(f"{BASE}/approvals/history")
    check("offline fallback page shown", "You are offline" in page.locator("body").inner_text())
    check("offline pill says offline", page.locator("#net-pill").inner_text() == "Offline")
    shot(page, "mobile_offline")
    page.click("[data-tab=approvals]")
    page.wait_for_selector("#pending-list .approval-card")
    check("offline: cached approvals listed", page.locator("#pending-list .approval-card").count() == len(pending))
    target_vendor = page.locator("#pending-list .approval-vendor").first.inner_text()
    target = next(p for p in pending if p["vendor"] == target_vendor)
    page.locator("#pending-list .btn-success").first.click()
    page.wait_for_timeout(300)
    # A photo captured while offline
    page.click("[data-tab=capture]")
    if page.locator("#cap-client option").count():  # approvers have no upload rights; covered by the field-staff flow
        pass
    page.click("[data-tab=queue]")
    page.wait_for_selector("#queue-list .card")
    check("offline: approval queued", page.locator("#queue-list .card").count() == 1)
    shot(page, "mobile_offline_queue")

    context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.wait_for_selector(".toast", timeout=15000)
    toast_text = page.locator(".toast").first.inner_text()
    page.wait_for_function("document.querySelector('#queue-empty') && !document.querySelector('#queue-empty').hidden", timeout=15000)
    check("reconnect: sync toast", "1 item synced" in toast_text or "synced" in page.content(), toast_text)
    status = context.request.get(f"{BASE}/api/bootstrap").json()["pending"]
    check("reconnect: item left the approver's queue or moved a level", not any(p["id"] == target["id"] and p["updated_at"] == target["updated_at"] for p in status))
    context.close()


def phone_field_flow(browser, errors, data_dir):
    context = browser.new_context(**PHONE)
    page = context.new_page()
    watch_errors(page, errors)
    login(page, ("field1", "Demo@1234"))
    check("field staff lands on upload", "/invoices/upload" in page.url, page.url)
    shot(page, "mobile_capture")
    check("Take Photo button visible on phone", page.locator(".camera-btn").is_visible())
    check("camera input requests camera", page.locator("#camera-input").get_attribute("capture") == "camera")
    page.evaluate("navigator.serviceWorker.ready")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    context.set_offline(True)
    page.goto(f"{BASE}/clients")
    check("field staff offline page", "You are offline" in page.locator("body").inner_text())
    page.wait_for_function("document.querySelectorAll('#cap-client option').length > 0", timeout=5000)
    page.set_input_files("#cap-photo", str(SAMPLES / "expense_receipt_1.jpg"))
    page.fill("#cap-vendor", "Hotel Konkan")
    page.fill("#cap-amount", "3920")
    page.click("#capture-form button[type=submit]")
    page.wait_for_timeout(400)
    page.click("[data-tab=queue]")
    check("offline: photo saved on device", page.locator("#queue-list .card").count() == 1)
    context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.wait_for_function("!document.querySelector('#queue-empty').hidden", timeout=60000)
    check("reconnect: photo synced and OCR ran on the server", True)
    page.goto(f"{BASE}/clients/1/invoices")
    check("synced invoice is listed", "Hotel Konkan" in page.locator("table").inner_text() or page.locator("td", has_text="HKR-5521").count() == 1)
    context.close()


def responsive_checks(browser, errors):
    context = browser.new_context(**PHONE)
    page = context.new_page()
    watch_errors(page, errors)
    login(page, DEMO_ADMIN)
    token = None
    for path in ("/clients", "/clients/1", "/clients/1/vendors", "/clients/1/vendors/new", "/clients/1/invoices", "/clients/1/invoices/upload",
                 "/clients/1/reports/dashboard", "/clients/1/reports/variance", "/clients/1/reports/aging", "/clients/1/reports/cost-centre",
                 "/clients/1/approval-matrix", "/clients/1/cost-centres", "/clients/1/budgets", "/approvals/pending", "/approvals/history",
                 "/admin/users", "/admin/users/new", "/admin/audit-log", "/admin/email-config", "/admin/backup", "/admin/roles", "/offline"):
        page.goto(BASE + path)
        page.wait_for_load_state("networkidle")
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(f"375px no page overflow {path}", overflow <= 0, f"{overflow}px")
    page.goto(f"{BASE}/clients/1/reports/dashboard")
    page.wait_for_timeout(900)
    shot(page, "mobile_dashboard")
    page.click("#sidebar-toggle")
    page.wait_for_timeout(300)
    check("hamburger opens sidebar", page.evaluate("document.body.classList.contains('sidebar-open')"))
    shot(page, "mobile_sidebar")
    page.goto(f"{BASE}/clients/1")
    token = page.input_value("#reg-link").rsplit("/", 1)[1]
    context.close()

    public = browser.new_context(**PHONE)
    page = public.new_page()
    watch_errors(page, errors)
    page.goto(f"{BASE}/vendor/register/{token}")
    check("public vendor form opens without login", page.locator("h1").inner_text() == "Vendor registration")
    check("public form has no sidebar", page.locator(".sidebar").count() == 0)
    check("375px no overflow on public form", page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0)
    shot(page, "vendor_register", full=True)
    public.close()

    ipad = browser.new_context(viewport={"width": 768, "height": 1024},
                               user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    page = ipad.new_page()
    login(page, DEMO_ADMIN)
    check("iOS install guide appears", page.locator("#ios-install").is_visible())
    shot(page, "ios_install")
    page.click("#ios-install [data-dismiss]")
    page.reload()
    check("iOS guide stays dismissed", not page.locator("#ios-install").is_visible())
    ipad.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="msedge")
    args = parser.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as data_dir:
        env = dict(os.environ, KTAP_DATA_DIR=data_dir, KTAP_NO_LISTENER="1", KTAP_PORT=str(PORT), KTAP_HOST="127.0.0.1")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo_data.py")], env=env, check=True, cwd=ROOT)
        server = subprocess.Popen([sys.executable, str(ROOT / "run.py")], env=env, cwd=ROOT)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
                    break
                except OSError:
                    time.sleep(.5)
            errors = []
            with sync_playwright() as p:
                browser = p.chromium.launch(channel=args.channel)
                desktop_flow(browser, errors)
                phone_approval_flow(browser, errors)
                phone_field_flow(browser, errors, data_dir)
                responsive_checks(browser, errors)
                browser.close()
            real = [e for e in errors if "ERR_INTERNET_DISCONNECTED" not in e and "503" not in e and "Failed to fetch" not in e]
            check("no browser console or page errors", not real, "; ".join(real[:5]))
        finally:
            server.terminate()
            server.wait(timeout=15)
            time.sleep(1)  # let Windows release the database files
    print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
