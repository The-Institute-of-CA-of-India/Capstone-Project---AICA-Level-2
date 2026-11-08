"""Scenario tests against a simulated browser. No portal traffic. Run: python tests/test_scenarios.py"""
import base64, ctypes, importlib.util, io, os, shutil, sys, tempfile, threading, time, traceback
from openpyxl import Workbook, load_workbook
from PIL import Image

sys.dont_write_bytecode = True
PROJ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
spec = importlib.util.spec_from_file_location("uv", os.path.join(PROJ, "MSME_CertiFetch.py"))
uv = importlib.util.module_from_spec(spec); spec.loader.exec_module(uv)
app = uv.UdyamVerifierApp()
tk_errors = []
def _tkerr(exc, val, tb):
    tk_errors.append(repr(val)); print("TK-CALLBACK-ERROR", repr(val), flush=True)
app.report_callback_exception = _tkerr
TMP = tempfile.mkdtemp()
results = []; logs = []
orig_log = app.log
app.log = lambda m: (logs.append(m), orig_log(m))
def check(name, ok, info=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name, info if not ok else "", flush=True)

buf = io.BytesIO(); Image.new("RGB", (281, 100), "white").save(buf, "PNG"); PNG = buf.getvalue()
class Fake:
    pdf_error = False
    def quit(self): pass
    def execute_script(self, *a): return None
    def execute_cdp_cmd(self, *a):
        if Fake.pdf_error: raise RuntimeError("simulated print failure")
        return {"data": base64.b64encode(b"%PDF-1.4 sample").decode()}

script = []; cfg = {}; counts = {"reset": 0, "captcha": 0}
def fake_popup():
    if not app.waiting_for_captcha: return
    def act():
        time.sleep(0.05)
        app.captcha_text_var.set("X")
        app.captcha_action = script.pop(0) if script else "submit"
        app.waiting_for_captcha = False
    threading.Thread(target=act, daemon=True).start()

def patch():
    app._setup_chrome = lambda: Fake()
    app._navigate_to_verify_page_via_menu = lambda d: None
    app._enter_udyam_number = lambda d, n: None
    def _capture(d):
        counts["captcha"] += 1
        return PNG
    app._capture_captcha_image = _capture
    app._click_back = lambda d: None
    app._click_verify = lambda d: True
    def _reset(d):
        counts["reset"] += 1
        cfg.get("reset", lambda: None)()
    app._reset_verify_page = _reset
    app._wrong_captcha_shown = lambda d: cfg.get("wrong", lambda: False)()
    app._enter_captcha_in_browser = lambda d, t: cfg.get("captcha_ok", True)
    app._is_result_page = lambda d: cfg.get("result", lambda: True)()
    app._extract_all_data = lambda d: {"name": "SAMPLE", "major_activity": "Trading",
        "classifications": [{"year": "2026-27", "type": "Micro"}]}
    app._popup_window = fake_popup

def run(name, numbers, acts=(), **kw):
    folder = kw.pop("folder", os.path.join(TMP, name)); os.makedirs(folder, exist_ok=True)
    x = os.path.join(TMP, name + ".xlsx")
    wb = Workbook(); ws = wb.active; ws.append(["Udyam Number", "Status"])
    for n in numbers: ws.append([n, None])
    wb.save(x)
    script[:] = list(acts); cfg.clear(); cfg.update(kw); logs.clear(); counts.update(reset=0, captcha=0)
    Fake.pdf_error = kw.get("pdf_error", False)
    app._process_all(x, folder)
    time.sleep(0.3)
    return [r[1] for r in load_workbook(x).active.iter_rows(min_row=2, values_only=True)], folder

def report(folder, f="UDYAM_Report.xlsx"):
    return {r[0]: r for r in load_workbook(os.path.join(folder, f)).active.iter_rows(min_row=2, values_only=True)}

def scenarios():
    try:
        patch()
        st, f = run("happy", ["U1", "U2"])
        check("normal run marks Done and writes PDFs", st == ["Done", "Done"] and len([x for x in os.listdir(f) if x.endswith(".pdf")]) == 2, st)
        check("final panel says Complete", app.captcha_status.cget("text") == "Complete.", app.captcha_status.cget("text"))
        check("captcha image cleared at end", app.captcha_photo is None and "No captcha" in app.captcha_image_label.cget("text"))
        check("tiles show totals", app.tile_values["saved"].cget("text") == "2" and app.progress_bar.get() == 1.0)

        st, _ = run("refresh", ["U1"], ["refresh"] * 6)
        check("6 refreshes do not use up attempts", st == ["Done"], st)

        st, f = run("pdffail", ["U1"], pdf_error=True)
        check("PDF failure is Failed, not Done", st == ["Failed"], st)
        check("failed tile counts PDF failure", app.tile_values["failed"].cget("text") == "1")

        st, _ = run("wrong", ["U1"], result=lambda: False)
        check("3 wrong captchas end as Failed", st == ["Failed"], st)

        st, _ = run("nofield", ["U1", "U2"], captcha_ok=False)
        check("attempts exhausted still gets a status", st == ["Failed", "Failed"], st)

        st, _ = run("skip", ["U1", "U2"], ["skip"])
        check("Skip then continue", st == ["Skipped", "Done"], st)

        f = os.path.join(TMP, "merge")
        run("merge", ["U1", "U2"], folder=f)
        run("merge2", ["U3", "U1"], folder=f)
        check("report keeps earlier rows, no duplicates", sorted(report(f)) == ["U1", "U2", "U3"], report(f))

        f = os.path.join(TMP, "lock"); os.makedirs(f)
        import openpyxl.workbook.workbook as W
        orig = W.Workbook.save; calls = {"n": 0}
        def flaky(self, p):
            if str(p).endswith("UDYAM_Report.xlsx"): raise PermissionError(p)
            return orig(self, p)
        W.Workbook.save = flaky
        run("lock", ["U1"], folder=f)
        W.Workbook.save = orig
        names = [x for x in os.listdir(f) if x.startswith("UDYAM_Report_")]
        check("open report saves a new copy", len(names) == 1, os.listdir(f))

        n = {"c": 0}
        def boom():
            raise RuntimeError("simulated portal timeout")
        def res():
            n["c"] += 1
            return n["c"] == 1
        st, f = run("crash", ["U1", "U2"], result=res, reset=boom)
        check("portal failure only costs that number", st == ["Done", "Failed"] and "U1" in report(f), st)
        check("panel still honest after portal failure", app.captcha_status.cget("text") == "Complete.", app.captcha_status.cget("text"))

        seq = iter([False, True])
        w = iter([True])
        st, _ = run("typo", ["U1"], result=lambda: next(seq), wrong=lambda: next(w, False))
        check("wrong captcha: no reload, new captcha shown", st == ["Done"] and counts["reset"] == 0 and counts["captcha"] == 2, (st, counts))

        st, _ = run("retries", ["U1"], result=lambda: False)
        check("each retry reloads exactly once", st == ["Failed"] and counts["reset"] == 2, (st, counts))

        st, _ = run("f5fail", ["U1"], ["refresh"], reset=boom)
        check("failed refresh cannot crash or loop", st == ["Failed"], st)

        app._setup_chrome = lambda: (_ for _ in ()).throw(RuntimeError("line one\nStacktrace: junk"))
        st, _ = run("fatal", ["U1"])
        patch()
        check("real crash is reported, not Complete", "Stopped by an error" in app.captcha_status.cget("text"), app.captcha_status.cget("text"))
        check("error log stays short", any(m == "ERROR: line one" for m in logs), logs[-3:])

        class W:
            def execute_script(self, *a): return True
        saved = app._is_result_page, app._wrong_captcha_shown
        del app._wrong_captcha_shown
        app._is_result_page = lambda d: False
        t0 = time.time(); app._wait_for_verify_outcome(W(), timeout=15); took = time.time() - t0
        app._is_result_page, app._wrong_captcha_shown = saved
        check("wrong captcha detected without the 15s wait", took < 3, took)

        # Template round-trip through the tool's own reader
        t = os.path.join(TMP, "template.xlsx")
        app._write_template(t)
        wb = load_workbook(t)
        check("template first sheet is the input", wb.active.title == "Udyam Numbers" and wb.sheetnames[1] == "Instructions")
        check("template headers exact", wb.active["A1"].value == "Udyam Number" and wb.active["B1"].value == "Status")
        wb.active["A2"] = "U9"; wb.save(t)
        cfg.clear(); script.clear(); Fake.pdf_error = False
        f = os.path.join(TMP, "tpl"); os.makedirs(f)
        app._process_all(t, f); time.sleep(0.3)
        wb = load_workbook(t)
        check("filled template runs, stays valid", wb.active["B2"].value == "Done" and wb.active.max_row >= 2 and wb.sheetnames == ["Udyam Numbers", "Instructions"], wb.active["B2"].value)
    except Exception:
        traceback.print_exc(); results.append(False)
    check("no errors inside the GUI", not tk_errors, tk_errors[:3])
    print(f"TOTAL {sum(results)}/{len(results)} passed", flush=True)
    shutil.rmtree(TMP, ignore_errors=True)
    app.after(0, app.destroy)

threading.Thread(target=scenarios, daemon=True).start()
app.mainloop()
sys.exit(0 if all(results) else 1)
