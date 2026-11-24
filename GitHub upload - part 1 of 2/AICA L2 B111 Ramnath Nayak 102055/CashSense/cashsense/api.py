"""CashSense local API - the tools n8n orchestrates.

Runs on 127.0.0.1 only. Every endpoint except /api/health needs the header
X-CashSense-Key: <CASHSENSE_API_KEY from .env> (generated on first start).

    python -m cashsense.cli serve
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel

from . import config
from .db import get_database

app = FastAPI(title="CashSense local API (SAMPLE data)", version="0.3.0")
_lock = threading.Lock()   # one run at a time (SQLite, Telegram offset)


def api_key() -> str:
    key = config.setting("CASHSENSE_API_KEY")
    if not key:
        key = secrets.token_urlsafe(24)
        config.save_setting("CASHSENSE_API_KEY", key)
    return key


def require_key(x_cashsense_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_cashsense_key, api_key()):
        raise HTTPException(status_code=401, detail="Missing or wrong X-CashSense-Key")


class RunRequest(BaseModel):
    as_of: str | None = None
    browser: bool = True
    notify: bool = True


class ImportRequest(BaseModel):
    file: str
    notify: bool = True


class AskRequest(BaseModel):
    question: str


class SpeakRequest(BaseModel):
    text: str


def _as_of(req: RunRequest | None) -> date:
    return date.fromisoformat(req.as_of) if req and req.as_of else config.as_of_date()


def _clients():
    from .ai.gemini import GeminiClient
    from .messaging.telegram import TelegramClient

    return GeminiClient(), TelegramClient()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "cashsense", "as_of": config.as_of_date().isoformat(),
            "time_ist": config.now_ist().isoformat(timespec="seconds")}


@app.post("/api/telegram/poll", dependencies=[Depends(require_key)])
def telegram_poll() -> dict:
    from .notify import handle_updates

    ai, tg = _clients()
    if not tg.available or not tg.chat_id:
        raise HTTPException(503, "Telegram not configured - run: python -m cashsense.cli telegram-check")
    with _lock:
        return handle_updates(get_database(), tg, ai)


@app.post("/api/run/daily", dependencies=[Depends(require_key)])
def run_daily(req: RunRequest | None = None) -> dict:
    from .notify import notify_daily
    from .pipeline import run_daily as daily

    ai, tg = _clients()
    with _lock:
        db = get_database()
        result = daily(db, _as_of(req), ai, use_browser=req.browser if req else True, actor="n8n_daily")
        if (req is None or req.notify) and tg.available and tg.chat_id:
            result["telegram_messages"] = notify_daily(db, tg, result) + 1
        if config.setting("APPS_SCRIPT_URL"):
            from . import briefing

            result["apps_script"] = briefing.send(briefing.build(db, _as_of(req)))
    return {k: v for k, v in result.items() if k != "verification_results"}


@app.post("/api/notify/escalation", dependencies=[Depends(require_key)])
def escalation() -> dict:
    from .notify import notify_escalation

    _, tg = _clients()
    with _lock:
        return {"high_risk_alerts": notify_escalation(get_database(), tg) if tg.available and tg.chat_id else 0}


@app.post("/api/import-file", dependencies=[Depends(require_key)])
def import_file(req: ImportRequest) -> dict:
    from .pipeline import intake, safe_inbox_path

    try:
        path = safe_inbox_path(req.file)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if not path.exists():
        raise HTTPException(404, "File not found in data/inbox")
    ai, tg = _clients()
    with _lock:
        try:
            res = intake(get_database(), [path], ai, actor="n8n_folder_watch")
        except Exception as exc:
            if req.notify and tg.available and tg.chat_id:
                tg.send_message(f"⚠️ Could not import {path.name}: {exc}")
            raise HTTPException(422, str(exc)) from None
    if req.notify and tg.available and tg.chat_id:
        imp = res["import"]
        tg.send_message(f"📂 Imported {path.name}: {imp['account_id']} {imp['period']}, {imp['lines']} lines, "
                        f"{imp['status']}; reconciliation {res['reconciliation']['status']}.")
    return res


@app.post("/api/inbox/scan", dependencies=[Depends(require_key)])
def inbox_scan() -> dict:
    """Import statements dropped into data/inbox/drop. A multi-page photo statement can be dropped as a
    folder of images. Processed items move to drop/processed, failures to drop/failed."""
    import shutil

    from .pipeline import INBOX, intake

    drop = INBOX / "drop"
    drop.mkdir(parents=True, exist_ok=True)
    out = {"imported": [], "failed": []}
    ai, tg = _clients()
    notify = tg.available and tg.chat_id
    for item in sorted(p for p in drop.iterdir() if p.name not in ("processed", "failed")):
        paths = sorted(item.glob("*")) if item.is_dir() else [item]
        with _lock:
            try:
                res = intake(get_database(), paths, ai, actor="n8n_drop_folder")
                dest = drop / "processed"
                imp = res["import"]
                out["imported"].append({"file": item.name, **imp})
                if notify:
                    tg.send_message(f"📂 Imported {item.name}: {imp['account_id']} {imp['period']}, {imp['lines']} lines, "
                                    f"{imp['status']}; reconciliation {res['reconciliation']['status']}.")
            except Exception as exc:
                dest = drop / "failed"
                out["failed"].append({"file": item.name, "error": str(exc)})
                if notify:
                    tg.send_message(f"⚠️ Could not import {item.name}: {exc}")
        dest.mkdir(exist_ok=True)
        stamp = config.now_ist().strftime("%Y%m%d_%H%M%S")
        shutil.move(str(item), str(dest / f"{stamp}_{item.name}"))
    return out


class ToolArgs(BaseModel):
    args: dict = {}


@app.post("/api/tool/{name}", dependencies=[Depends(require_key)])
def run_tool(name: str, req: ToolArgs | None = None) -> dict:
    """Read-only data tools (the same ones the assistant uses) - for the Claude plugin's MCP server."""
    from .agents.assistant import TOOLS, Tools

    if name not in {t["name"] for t in TOOLS}:
        raise HTTPException(404, f"Unknown tool {name}")
    with _lock:
        return Tools(get_database()).run(name, (req.args if req else {}) or {})


@app.post("/api/ask", dependencies=[Depends(require_key)])
def api_ask(req: AskRequest) -> dict:
    return dash_ask(req)


@app.get("/api/approvals", dependencies=[Depends(require_key)])
def approvals(status: str = "pending") -> list[dict]:
    return get_database().query("approvals", {"status": status}, order="approval_id")


@app.get("/api/risks", dependencies=[Depends(require_key)])
def risks() -> list[dict]:
    return get_database().query("risk_flags", order="flag_id")


# ----------------------------------------------------------------------------- mobile dashboard
SESSION_HOURS = 12
_failures: list[float] = []
WEB = Path(__file__).with_name("web")
LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CashSense sign in</title>
<style>body{{font:16px system-ui,Segoe UI,sans-serif;background:#0f3d5e;color:#fff;display:flex;min-height:100vh;
align-items:center;justify-content:center;margin:0}}form{{background:#fff;color:#18212b;padding:24px;border-radius:12px;
width:min(340px,90vw)}}input,button{{width:100%;font-size:16px;padding:10px;margin-top:10px;border-radius:8px;
border:1px solid #ccd}}button{{background:#0f3d5e;color:#fff;border:0}}.e{{color:#c62828}}</style></head>
<body><form method="post" action="/login"><h2>CashSense</h2><div>SAMPLE data - dashboard sign in</div>
<input type="password" name="password" placeholder="Dashboard password" autofocus required>
<button>Sign in</button><div class="e">{error}</div></form></body></html>"""


def _secret(name: str) -> str:
    value = config.setting(name)
    if not value:
        value = secrets.token_urlsafe(18 if name == "DASHBOARD_PASSWORD" else 32)
        config.save_setting(name, value)
    return value


def _sign(ts: str) -> str:
    return hmac.new(_secret("SESSION_SECRET").encode(), f"dash:{ts}".encode(), hashlib.sha256).hexdigest()


def session_ok(request: Request) -> bool:
    token = request.cookies.get("cs_session", "")
    ts, _, sig = token.partition(".")
    return bool(ts.isdigit() and hmac.compare_digest(sig, _sign(ts)) and time.time() - int(ts) < SESSION_HOURS * 3600)


def require_session(request: Request) -> None:
    if not session_ok(request):
        raise HTTPException(status_code=401, detail="Please sign in")


@app.get("/login", response_class=HTMLResponse)
def login_form() -> str:
    return LOGIN_PAGE.format(error="")


@app.post("/login")
async def login(request: Request):
    now = time.time()
    _failures[:] = [t for t in _failures if now - t < 600]
    if len(_failures) >= 10:
        return HTMLResponse(LOGIN_PAGE.format(error="Too many attempts - wait 10 minutes."), status_code=429)
    form = parse_qs((await request.body()).decode())
    if not secrets.compare_digest(form.get("password", [""])[0], _secret("DASHBOARD_PASSWORD")):
        _failures.append(now)
        get_database().audit("dashboard", "login_failed", "dashboard", request.client.host if request.client else "", {})
        return HTMLResponse(LOGIN_PAGE.format(error="Wrong password."), status_code=401)
    ts = str(int(now))
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("cs_session", f"{ts}.{_sign(ts)}", httponly=True, samesite="strict", max_age=SESSION_HOURS * 3600,
                    secure=request.url.scheme == "https")
    get_database().audit("dashboard", "login", "dashboard", "", {})
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("cs_session")
    return resp


@app.get("/", include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not session_ok(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse((WEB / "dashboard.html").read_text(encoding="utf-8"))


@app.get("/api/dash/data", dependencies=[Depends(require_session)])
def dash_data() -> dict:
    from .dashboard import dashboard_data

    with _lock:
        return dashboard_data(get_database(), config.as_of_date())


@app.post("/api/dash/ask", dependencies=[Depends(require_session)])
def dash_ask(req: AskRequest) -> dict:
    from .ai.gemini import GeminiError
    from .agents.assistant import ask

    ai, _ = _clients()
    if not ai.available:
        raise HTTPException(503, "Gemini is not configured")
    try:
        with _lock:
            return ask(get_database(), req.question, ai)
    except GeminiError as exc:
        raise HTTPException(503, f"Assistant busy: {exc}") from None


@app.post("/api/dash/speak", dependencies=[Depends(require_session)])
def dash_speak(req: SpeakRequest) -> Response:
    from .voice import _plain, speak

    ai, _ = _clients()
    ogg, engine = speak(_plain(req.text[:800]), ai)
    return Response(ogg, media_type="audio/ogg", headers={"X-Voice-Engine": engine})


@app.post("/api/dash/commentary", dependencies=[Depends(require_session)])
def dash_commentary() -> dict:
    from .dashboard import refresh_commentary

    ai, _ = _clients()
    with _lock:
        return refresh_commentary(get_database(), config.as_of_date(), ai)
