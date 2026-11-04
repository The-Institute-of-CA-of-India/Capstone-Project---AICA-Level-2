"""Broker web portal: saved logins and an assisted download session.

How a session works
1. The app opens Microsoft Edge (or Chrome) in a separate window with its own profile, whose
   download folder is Data\\Transaction Data\\Portal Downloads\\<broker>\\Inbox.
2. It fills the user id and password on the broker's login page (it never presses Login).
3. The user types the OTP / CAPTCHA / PIN, logs in, and clicks the downloads needed
   (contract notes, ledger, P&L, holdings) for the period.
4. Every file that lands in the Inbox is sorted: contract notes are imported straight
   away; ledger, P&L, holding and tradebook files are filed in their own folders.

Passwords are stored encrypted with Windows DPAPI (see vault.py).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import vault
from .paths import Layout

SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_logins (broker TEXT PRIMARY KEY, user_id TEXT, secret TEXT, url TEXT, updated_at TEXT);
"""

# Login pages (editable in Settings; brokers change these from time to time)
DEFAULT_URLS = {
    "Zerodha Broking": "https://console.zerodha.com/",
    "IIFL Capital Services": "https://www.indiainfoline.com/",
    "Kotak Securities": "https://www.kotaksecurities.com/",
    "ICICI Securities": "https://secure.icicidirect.com/",
    "HDFC Securities": "https://ntrade.hdfcsec.com/",
    "Angel One": "https://www.angelone.in/login/",
    "Upstox": "https://login.upstox.com/",
    "Groww": "https://groww.in/login",
    "Dhan": "https://login.dhan.co/",
    "5paisa": "https://login.5paisa.com/",
    "Motilal Oswal": "https://invest.motilaloswal.com/",
    "PhillipCapital (India)": "https://www.phillipcapital.in/",
    "Sharekhan": "https://www.sharekhan.com/",
    "Axis Securities": "https://simplehai.axisdirect.in/",
    "SBI Securities": "https://www.sbisecurities.in/",
    "Nuvama Wealth": "https://www.nuvamawealth.com/",
}

KINDS = {   # folder name -> filename keywords
    "Ledger": ("ledger", "fund statement", "account statement", "statement of account"),
    "Profit and Loss": ("p&l", "pnl", "p_l", "profit", "loss", "taxpnl", "tax_pnl", "capital gain", "realised", "realized"),
    "Holdings": ("holding", "demat", "portfolio", "dp statement", "transaction statement"),
    "Tradebook": ("tradebook", "trade book", "trade_book", "tradelist", "trade list"),
}
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))     # never send local calls via a proxy
PARTIAL = (".crdownload", ".tmp", ".part", ".partial", ".download")


def ensure(store):
    store.db.executescript(SCHEMA)


def logins(store) -> list[dict]:
    ensure(store)
    return [dict(r) for r in store.query("SELECT broker, user_id, secret, url FROM portal_logins ORDER BY broker")]


def save_all(store, rows) -> int:
    """rows: (broker, user_id, password_or_None_to_keep, url). Replaces the whole list."""
    ensure(store)
    old = {r["broker"]: r for r in logins(store)}
    now = datetime.now().isoformat(timespec="seconds")
    store.db.execute("DELETE FROM portal_logins")
    n = 0
    for broker, user, pw, url in rows:
        broker = (broker or "").strip()
        if not broker or not (user or "").strip():
            continue
        secret = vault.protect(pw) if pw else (old.get(broker) or {}).get("secret", "")
        store.db.execute("INSERT OR REPLACE INTO portal_logins VALUES (?,?,?,?,?)",
                         (broker, user.strip(), secret, (url or DEFAULT_URLS.get(broker, "")).strip(), now))
        n += 1
    store.db.commit()
    return n


def credentials(store, broker) -> tuple[str, str, str]:
    ensure(store)
    r = store.query("SELECT user_id, secret, url FROM portal_logins WHERE broker=?", (broker,))
    if not r:
        raise ValueError(f"no portal login saved for {broker}")
    return r[0]["user_id"], vault.reveal(r[0]["secret"]), r[0]["url"] or DEFAULT_URLS.get(broker, "")


# --------------------------------------------------------------------------- browser

def find_browser() -> str:
    cands = []
    for base in (os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                 os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        if base:
            cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                      Path(base) / "Google/Chrome/Application/chrome.exe"]
    for c in cands:
        if c.exists():
            return str(c)
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise FileNotFoundError("Microsoft Edge or Google Chrome was not found on this computer")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _prepare_profile(profile: Path, inbox: Path):
    prefs_file = profile / "Default" / "Preferences"
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prefs = {}
    prefs.setdefault("download", {}).update({"default_directory": str(inbox), "prompt_for_download": False,
                                             "directory_upgrade": True})
    prefs.setdefault("savefile", {})["default_directory"] = str(inbox)
    prefs.setdefault("plugins", {})["always_open_pdf_externally"] = True     # PDFs download instead of opening
    prefs.setdefault("profile", {})["exit_type"] = "Normal"
    prefs_file.write_text(json.dumps(prefs), encoding="utf-8")


class Session:
    """One assisted login + download session for a broker."""

    def __init__(self, store, data_dir: Path, broker: str):
        self.broker = broker
        self.user, self.password, self.url = credentials(store, broker)
        if not self.url:
            raise ValueError(f"no portal address saved for {broker}")
        safe = re.sub(r"[^\w .()-]", "_", broker).strip()
        self.root = Layout(data_dir).portal / safe
        self.inbox = self.root / "Inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.profile = Layout(data_dir).browser / safe
        self.port = _free_port()
        self.proc = None
        self.seen: set[str] = {p.name for p in self.inbox.iterdir()}
        self.filled = False
        self.seen_alive = False
        self.started = time.time()

    def open(self):
        exe = find_browser()
        _prepare_profile(self.profile, self.inbox)
        args = [exe, f"--remote-debugging-port={self.port}", "--remote-allow-origins=*",
                f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
                "--new-window", self.url]
        flags = 0x08000000 if sys.platform.startswith("win") else 0
        self.proc = subprocess.Popen(args, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ---- filling the login form (Chrome DevTools protocol, local only)
    def _pages(self):
        with _LOCAL.open(f"http://127.0.0.1:{self.port}/json", timeout=3) as r:
            return [p for p in json.loads(r.read()) if p.get("type") == "page"]

    def _eval(self, ws_url: str, expr: str):
        from websockets.sync.client import connect
        with connect(ws_url, open_timeout=5, max_size=2 ** 22) as ws:
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": expr, "returnByValue": True}}))
            deadline = time.time() + 5
            while time.time() < deadline:
                msg = json.loads(ws.recv(timeout=5))
                if msg.get("id") == 1:
                    return ((msg.get("result") or {}).get("result") or {}).get("value")
        return None

    def try_fill(self) -> str:
        """Fill user id / password fields that are visible and empty. Returns what was done."""
        js = FILL_JS % (json.dumps(self.user), json.dumps(self.password))
        done = []
        try:
            pages = self._pages()
        except Exception:   # noqa: BLE001 - the browser is still starting or was closed
            return ""
        for p in pages:
            if p.get("webSocketDebuggerUrl") and p.get("url", "").startswith("http"):
                try:
                    v = self._eval(p["webSocketDebuggerUrl"], js)
                except Exception:   # noqa: BLE001 - the page may be navigating
                    continue
                if v:
                    done.append(v)
        if any("password" in d for d in done):
            self.filled = True
        return ", ".join(done)

    def alive(self) -> bool:
        """False only when the window was open and is now closed (or never opened within 90 seconds)."""
        try:
            self._pages()
            self.seen_alive = True
            return True
        except Exception:   # noqa: BLE001
            return not self.seen_alive and time.time() - self.started < 90

    # ---- downloads
    def new_files(self) -> list[Path]:
        out = []
        for p in sorted(self.inbox.iterdir(), key=lambda x: x.stat().st_mtime):
            if p.name in self.seen or p.is_dir() or p.suffix.lower() in PARTIAL or p.name.startswith("."):
                continue
            try:
                s1 = p.stat().st_size
                time.sleep(0.4)
                if s1 == 0 or p.stat().st_size != s1:
                    continue            # still being written
            except OSError:
                continue
            self.seen.add(p.name)
            out.append(p)
        return out

    def file_away(self, p: Path, kind: str) -> Path:
        dest_dir = self.root / kind
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / p.name
        if dest.exists():
            dest = dest_dir / f"{p.stem}_{datetime.now():%Y%m%d_%H%M%S}{p.suffix}"
        shutil.move(str(p), dest)
        return dest


def classify(name: str) -> str:
    """Contract note / Ledger / Profit and Loss / Holdings / Tradebook / Other, from the file name."""
    n = name.lower().replace("-", " ")
    if re.search(r"contract|\bcn\b|cnote|c_note|ecn|confirmation", n):
        return "Contract note"
    for kind, words in KINDS.items():
        if any(w in n for w in words):
            return kind
    if Path(n).suffix in (".pdf", ".zip", ".htm", ".html"):
        return "Contract note"      # most broker PDFs without a hint are contract notes; import will verify
    return "Other"


FILL_JS = r"""
(function(user, pass){
  function vis(e){ var r=e.getBoundingClientRect(); var s=getComputedStyle(e);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none' && !e.disabled && !e.readOnly; }
  function put(e, v){ if(!e || e.value) return false;
    var proto = Object.getPrototypeOf(e); var d = Object.getOwnPropertyDescriptor(proto, 'value');
    e.focus(); if(d && d.set){ d.set.call(e, v); } else { e.value = v; }
    e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true}));
    e.blur(); return true; }
  var ins = Array.prototype.slice.call(document.querySelectorAll('input')).filter(vis);
  var pw = ins.filter(function(e){ return e.type==='password'; });
  var txt = ins.filter(function(e){ return ['text','email','tel','number',''].indexOf(e.type)>=0; });
  var re = /(user|login|client|email|mobile|phone|id|pan|ucc)/i;
  var bad = /(otp|captcha|pin|totp|code|search|amount|price)/i;
  function label(e){ return [e.name, e.id, e.placeholder, e.getAttribute('aria-label'), e.autocomplete].join(' '); }
  var u = txt.filter(function(e){ return re.test(label(e)) && !bad.test(label(e)); })[0];
  if(!u && pw.length){ var before = txt.filter(function(e){ return !bad.test(label(e)) &&
      (e.compareDocumentPosition(pw[0]) & Node.DOCUMENT_POSITION_FOLLOWING); }); u = before[before.length-1]; }
  var done = [];
  if(u && put(u, user)) done.push('user id');
  if(pw.length && !bad.test(label(pw[0])) && put(pw[0], pass)) done.push('password');
  return done.join(' and ');
})(%s, %s)
"""
