"""
PDF Redactor PRO - desktop entry point (used by the installed program).

    python app_main.py              open in its own app window (falls back to the default browser)
    python app_main.py --browser    open in the default browser instead
    python app_main.py --selftest   check the installation and exit (used by the build)

The interface is served by a local server inside this process (127.0.0.1 only). The app window is
Microsoft Edge (or Google Chrome) in "app" mode with its own private profile: no address bar or tabs,
and no extra component to install, because Edge is part of Windows 10 and 11. The program stops by
itself when its window is closed.

Everything that happens is written to app.log in the settings folder (%APPDATA%\\PDF Redactor PRO),
including crashes, and any start-up failure is shown in a message box: it never fails silently.
"""

from __future__ import annotations

import faulthandler
import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

LOG = None


def _setup_logging() -> None:
    """One log file for everything: prints, uncaught errors and hard crashes (faulthandler)."""
    global LOG
    from redact.model import VERSION
    from redact.paths import FROZEN, data_dir
    log_path = data_dir() / "app.log"
    try:
        if log_path.exists() and log_path.stat().st_size > 2_000_000:
            log_path.replace(log_path.with_name("app.old.log"))
    except OSError:
        pass
    LOG = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = LOG
    if sys.stderr is None:
        sys.stderr = LOG
    faulthandler.enable(file=LOG, all_threads=True)
    logging.basicConfig(stream=LOG, level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log(f"--- start v{VERSION} frozen={FROZEN} python={sys.version.split()[0]} args={sys.argv[1:]}")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    for stream in {LOG, sys.stdout} - {None}:
        try:
            print(line, file=stream, flush=True)
        except Exception:
            pass


def error_box(text: str) -> None:
    """A visible message, so a failure is never silent."""
    from redact.model import APP_NAME
    log("ERROR shown to user: " + text.replace("\n", " | "))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10 | 0x10000)   # error icon, foreground
            return
        except Exception:
            pass
    print(text, file=sys.stderr)


# ---------------------------------------------------------------- app window (Edge / Chrome app mode)
def find_app_browser() -> str | None:
    """Edge first (always present on Windows 10/11), then Chrome / Chromium. REDACTOR_BROWSER overrides."""
    env = os.environ.get("REDACTOR_BROWSER")
    if env:
        return env if Path(env).exists() else None
    cands: list[str] = []
    if sys.platform == "win32":
        try:
            import winreg
            for exe in ("msedge.exe", "chrome.exe"):
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                            cands.append(winreg.QueryValue(k, None))
                    except OSError:
                        pass
        except Exception:
            pass
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                          os.path.join(base, r"Google\Chrome\Application\chrome.exe")]
    elif sys.platform == "darwin":
        cands += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    else:
        cands += [shutil.which(n) or "" for n in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser")]
    for c in cands:
        c = (c or "").strip('"')
        if c and Path(c).is_file():
            return c
    return None


def _window_size() -> tuple[int, int]:
    w, h = 1440, 900
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            w, h = min(w, u.GetSystemMetrics(0) - 40), min(h, u.GetSystemMetrics(1) - 80)
        except Exception:
            pass
    return max(w, 1000), max(h, 640)


def open_app_window(url: str) -> subprocess.Popen | None:
    from redact.paths import cache_dir
    exe = find_app_browser()
    if not exe:
        log("no Edge/Chrome found for the app window")
        return None
    w, h = _window_size()
    args = [exe, f"--app={url}", f"--user-data-dir={cache_dir() / 'window'}", f"--window-size={w},{h}",
            "--no-first-run", "--no-default-browser-check", "--disable-sync", "--hide-crash-restore-bubble",
            "--disable-features=Translate,msEdgeSidebarV2,msImplicitSignin"]
    args += os.environ.get("REDACTOR_BROWSER_ARGS", "").split()      # testing / troubleshooting only
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"app window started with {exe} (pid {proc.pid})")
        return proc
    except Exception as exc:
        log(f"could not start {exe}: {exc!r}")
        return None


# ---------------------------------------------------------------- single instance
def _instance_file() -> Path:
    from redact.paths import data_dir
    return data_dir() / "instance.json"


def _running_instance() -> str | None:
    """URL of an already running copy of the program, if any."""
    import urllib.request
    from redact.model import APP_NAME
    try:
        info = json.loads(_instance_file().read_text(encoding="utf-8"))
        url = info["url"]
        with urllib.request.urlopen(url + "/api/meta", timeout=2) as r:
            if json.loads(r.read().decode("utf-8")).get("app") == APP_NAME:
                return url
    except Exception:
        pass
    return None


def _selftest() -> int:
    """Checks the bundled parts; prints a report; exit code 0 = good."""
    ok = True
    report = []
    try:
        from redact import pdf as P
        from redact.model import APP_NAME, VERSION
        report.append(f"{APP_NAME} v{VERSION}")
        st = P.self_test()
        report.append(f"PDF redaction keeps layout: {st}")
        ok &= st
        td = P.find_tessdata()
        report.append(f"OCR language data: {td or 'NOT FOUND'} {P.ocr_languages()}")
        ok &= td is not None
        import cv2
        report.append(f"Face model present: {os.path.exists(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')}")
        import docx  # noqa: F401 - template files must be bundled
        import reportlab  # noqa: F401
        from redact import batch, certificate, office, outputs  # noqa: F401
        import server  # noqa: F401
        report.append(f"Interface files: {server.STATIC_DIR.exists() and (server.STATIC_DIR / 'index.html').exists()}")
        ok &= (server.STATIC_DIR / "index.html").exists()
        # Office files and the certificate: these load bundled templates/fonts at run time
        import io

        import docx as _docx
        import openpyxl
        d1 = _docx.Document()
        d1.sections[0].header.paragraphs[0].text = "x"     # needs the header template
        d1.add_paragraph("PAN AAKCS1234F")
        b1 = io.BytesIO()
        d1.save(b1)
        wb = openpyxl.Workbook()
        wb.active["A1"] = "PAN AAKCS1234F"
        b2 = io.BytesIO()
        wb.save(b2)
        from redact import batch as _B
        from redact import detect as _D
        from redact import outputs as _O
        from redact.model import Options as _Opt
        bt = _B.run_batch([("t.docx", b1.getvalue()), ("t.xlsx", b2.getvalue())], _Opt(rules=set(_D.DEFAULT_RULES)))
        office_ok = all(r.status == "ok" and r.residual == 0 for r in bt.results)
        report.append(f"Word and Excel redaction: {office_ok}")
        ok &= office_ok
        cert = _O.certificate_pdf(bt, {})
        report.append(f"Certificate generated: {cert[:4] == b'%PDF'}")
        ok &= cert[:4] == b"%PDF"
        report.append(f"App window browser: {find_app_browser() or 'none found (will use the default browser)'}")
        # OCR one rendered line end to end
        if td:
            import pymupdf
            d = pymupdf.open()
            pg = d.new_page(width=300, height=80)
            pg.insert_text((20, 45), "PAN AAKCS1234F", fontsize=20)
            img = pymupdf.open()
            ip = img.new_page(width=300, height=80)
            ip.insert_image(ip.rect, stream=pg.get_pixmap(dpi=200).tobytes("png"))
            tp = ip.get_textpage_ocr(language="eng", dpi=200, full=True, tessdata=td)
            txt = ip.get_text(textpage=tp)
            report.append(f"OCR reads a test line: {'AAKCS1234F' in txt.replace(' ', '')}")
            ok &= "AAKCS1234F" in txt.replace(" ", "")
    except Exception as exc:          # report, never crash the build
        report.append(f"ERROR: {exc!r}")
        ok = False
    report.append("SELFTEST " + ("PASSED" if ok else "FAILED"))
    print("\n".join(report))
    out = os.environ.get("REDACTOR_SELFTEST_OUT")
    if out:                                   # a windowed .exe cannot print to the build console
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(report) + "\n")
    return 0 if ok else 1


def main() -> int:
    multiprocessing.freeze_support()          # must run first in a frozen program
    _setup_logging()
    if "--selftest" in sys.argv:
        return _selftest()
    try:
        return run()
    except SystemExit:
        raise
    except BaseException:
        log("FATAL\n" + traceback.format_exc())
        from redact.paths import data_dir
        error_box("PDF Redactor PRO could not start.\n\n" + traceback.format_exc(limit=3)
                  + f"\n\nDetails are in:\n{data_dir() / 'app.log'}")
        return 1


def run() -> int:
    import socket
    import threading
    import webbrowser

    import uvicorn

    from redact.model import APP_NAME

    want_window = "--browser" not in sys.argv and not os.environ.get("REDACTOR_NO_WINDOW")
    no_open = bool(os.environ.get("REDACTOR_NO_OPEN"))            # tests: start the server only

    existing = _running_instance()
    if existing:                               # already running: just bring up another window
        log(f"already running at {existing}; opening a window")
        if not (want_window and open_app_window(existing)):
            webbrowser.open(existing)
        return 0

    import server
    port = server._free_port(int(os.environ.get("REDACTOR_PORT", 8501)))
    url = f"http://127.0.0.1:{port}"
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    t = threading.Thread(target=srv.run, daemon=True, name="server")
    t.start()
    for _ in range(400):                       # wait until the server answers (up to 20 s)
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        if not t.is_alive():
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"the local server did not start on port {port}")
    if not t.is_alive():
        raise RuntimeError(f"the local server stopped while starting (port {port}); see the log")
    log(f"server ready at {url}")
    try:
        _instance_file().write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass

    proc = open_app_window(url) if (want_window and not no_open) else None
    os.environ["REDACTOR_MODE"] = "window" if proc else "browser"
    if not proc and not no_open:
        webbrowser.open(url)
        log("opened in the default browser")

    try:
        _watch(server, t, proc, url, no_open)
    finally:
        srv.should_exit = True
        try:
            if json.loads(_instance_file().read_text(encoding="utf-8")).get("pid") == os.getpid():
                _instance_file().unlink()
        except Exception:
            pass
        log("stopped")
    return 0


def _watch(server, thread, proc, url, no_open) -> None:
    """Keep running while a window is open. Stops when the app window closes, or (browser fallback)
    when no tab has checked in for a long time; Settings > Quit also stops it."""
    import webbrowser
    started = time.time()
    proc_end = None
    while thread.is_alive():
        time.sleep(1)
        now = time.time()
        last = server.LAST_PING[0]
        if proc is not None:
            if proc.poll() is None:
                continue                       # app window open
            if proc_end is None:
                proc_end = now
                log(f"app window process ended (code {proc.returncode})")
                if now - started < 8 and last == 0:
                    # the browser handed the window to another process or failed: give it a moment
                    log("window process ended at once; waiting for the page to check in")
            # the window may live on in another browser process: follow the page's check-ins instead
            if last == 0 and now - proc_end > 20:
                log("no window checked in; opening the default browser instead")
                os.environ["REDACTOR_MODE"] = "browser"
                webbrowser.open(url)
                proc = None
                started = now
                continue
            if last and now - max(last, proc_end) > 12:
                return
        else:
            if no_open and last == 0:
                continue
            limit = 30 * 60                    # browser tabs may be throttled or put to sleep
            if last and now - last > limit:
                log("no browser tab checked in for 30 minutes; stopping")
                return
            if not last and now - started > limit:
                return


if __name__ == "__main__":
    sys.exit(main())
