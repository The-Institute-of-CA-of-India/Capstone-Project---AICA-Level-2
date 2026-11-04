"""Start Investor Manager: local server plus an app window (Edge / Chrome app mode)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import urllib.request as _ur
_LOCAL = _ur.build_opener(_ur.ProxyHandler({}))     # calls to this computer never go via a proxy
PORT = int(os.environ.get("CNM_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}/"

# pythonw has no console: send output to a log file so errors are never lost
if sys.stdout is None or sys.stderr is None or os.environ.get("CNM_LOGFILE"):
    log_dir = Path(os.environ.get("CNM_DATA", HERE)) / "Temporary Data" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = open(log_dir / "app.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stderr = fh


def port_busy() -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def open_window():
    if os.environ.get("CNM_NO_WINDOW"):
        return
    for _ in range(60):                          # wait for the server (max 15 s)
        try:
            _LOCAL.open(URL, timeout=1)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        profile = Path(local) / "ContractNoteManager" / "window"
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / r"Microsoft\Edge\Application\msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Microsoft\Edge\Application\msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
            Path(local) / r"Google\Chrome\Application\chrome.exe",
        ]
        for exe in candidates:
            if exe.exists():
                subprocess.Popen([str(exe), f"--app={URL}", f"--user-data-dir={profile}", "--start-maximized",
                                  "--no-first-run", "--no-default-browser-check"])
                maximize_window()
                return
    webbrowser.open(URL)


VERSION = os.environ.get("CNM_VERSION", "dev")


def running_version() -> str:
    try:
        with _LOCAL.open(URL + "cnm/version", timeout=2) as r:
            return r.read().decode().strip()
    except Exception:  # noqa: BLE001 - older versions have no version endpoint
        return "unknown"


def stop_running() -> bool:
    """Ask the app that is already running to close, and wait until the port is free."""
    try:
        _LOCAL.open(urllib.request.Request(URL + "cnm/shutdown", data=b"", method="POST"), timeout=3)
    except Exception:  # noqa: BLE001
        pass
    for _ in range(40):
        if not port_busy():
            return True
        time.sleep(0.25)
    return False


# --------------------------------------------------------------------------- windows (Windows only)

TITLE = "Investor Manager"
OLD_TITLES = ("Investor Manager", "Contract Note Manager")     # windows of earlier versions too


def app_windows() -> list:
    """Visible browser app windows showing Investor Manager (or Contract Note Manager, before v1.9)."""
    if not sys.platform.startswith("win"):
        return []
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, title, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if title.value.startswith(OLD_TITLES) and cls.value.startswith("Chrome_WidgetWin"):
                found.append(hwnd)
        return True
    user32.EnumWindows(each, 0)
    return found


def focus_window() -> bool:
    """Bring the existing app window to the front. False if there is none."""
    wins = app_windows()
    if not wins:
        return False
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = wins[0]
    user32.keybd_event(0x12, 0, 0, 0)            # Alt press lets a background process take the foreground
    user32.ShowWindow(hwnd, 3)                   # SW_MAXIMIZE
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    return True


def maximize_window(wait: float = 15.0) -> None:
    """Open the app window maximised (the user can make it smaller as usual)."""
    import ctypes
    end = time.time() + wait
    while time.time() < end:
        wins = app_windows()
        if wins:
            time.sleep(0.3)
            for hwnd in app_windows():
                ctypes.windll.user32.ShowWindow(hwnd, 3)          # SW_MAXIMIZE
            return
        time.sleep(0.25)


def close_windows() -> None:
    import ctypes
    for hwnd in app_windows():
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE


def port_owner_pid() -> int | None:
    """PID of the program listening on our port (Windows netstat)."""
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout
    return parse_netstat(out, PORT)


def parse_netstat(out: str, port: int) -> int | None:
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 5 and p[0].upper() == "TCP" and p[1].endswith(f":{port}") and p[3].upper() == "LISTENING":
            return int(p[4])
    return None


def force_stop_old() -> None:
    """Last resort for very old versions without a shutdown command: end our own Python on that port."""
    if not sys.platform.startswith("win"):
        return
    pid = port_owner_pid()
    if not pid or pid == os.getpid():
        return
    image = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True,
                           text=True, creationflags=0x08000000).stdout.lower()
    if "python" in image:                        # only ever our own app, never another program
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=0x08000000)
        for _ in range(20):
            if not port_busy():
                break
            time.sleep(0.25)


def main():
    if port_busy():
        if running_version() == VERSION:          # same version already running: show its window
            if not focus_window():
                open_window()
            return
        stop_running()                            # a different (or very old) version: replace it
        if port_busy():
            force_stop_old()
        close_windows()                           # old windows would otherwise stay open
        time.sleep(0.5)
        if port_busy():
            open_window()
            return
    threading.Thread(target=open_window, daemon=True).start()
    import cnm_ui  # noqa: F401 - registers the pages
    from nicegui import app, ui
    from starlette.responses import PlainTextResponse

    @app.get("/cnm/version")
    def _version():
        return PlainTextResponse(VERSION)

    @app.post("/cnm/shutdown")
    def _shutdown():
        threading.Timer(0.3, app.shutdown).start()
        return PlainTextResponse("bye")

    ui.run(host="127.0.0.1", port=PORT, title=TITLE, reload=False, show=False,
           favicon=str(HERE / "icon.ico") if (HERE / "icon.ico").exists() else None,
           storage_secret="cnm-local", show_welcome_message=False, uvicorn_logging_level="warning")


if __name__ in {"__main__", "__mp_main__"}:
    main()
