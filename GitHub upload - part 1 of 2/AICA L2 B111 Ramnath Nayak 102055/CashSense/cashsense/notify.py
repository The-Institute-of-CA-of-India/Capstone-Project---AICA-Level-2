"""Telegram conversation: approval cards with buttons, the daily summary, commands, and
statement uploads. Only the CA's own chat (TELEGRAM_CHAT_ID) can approve or ask for data."""
from __future__ import annotations

import html
import json
from datetime import datetime

from . import config
from .approvals import decide
from .db.adapter import Database
from .messaging.telegram import TelegramClient, TelegramError
from .money import fmt_amount

ICON = {"journal_entry": "📒", "fuzzy_match": "🔍", "risk_flag": "🚨"}
HELP = ("<b>CashSense</b> (SAMPLE data)\n/status - bank reconciliation and risk summary\n/risks - open risk flags\n"
        "/pending - resend approvals waiting for you\n/help - this message\n"
        "Ask any question by typing it or by sending a 🎙️ voice note, e.g. \"What is my CC utilisation if customers "
        "pay 15 days late?\"\nSend a bank statement (CSV, PDF or photos) to import, categorise and reconcile it.")


def esc(x) -> str:
    return html.escape(str(x or ""))


def approval_card(ap: dict) -> tuple[str, list]:
    p = json.loads(ap["payload"])
    aid = ap["approval_id"]
    if ap["kind"] == "risk_flag":
        f = p["flag"]
        ev = f.get("evidence", {})
        lines = [f"{ICON['risk_flag']} <b>Risk {aid} - {esc(f['severity']).upper()}</b>",
                 esc(f.get("explanation") or ap["title"])]
        if f.get("action"):
            lines.append(f"<b>Action:</b> {esc(f['action'])}")
        if ev.get("account_holder"):
            lines.append(f"<i>Browser check: account holder {esc(ev['account_holder'])}; beneficiary added "
                         f"{esc(ev.get('beneficiary_added_on'))} by {esc(ev.get('beneficiary_added_by'))}</i>")
        return "\n".join(lines), [[("✅ Reviewed", f"a:{aid}:y"), ("🚩 Escalate", f"a:{aid}:n")]]
    lines = [f"{ICON[ap['kind']]} <b>Approval {aid}</b>", esc(ap["title"])]
    for i in p["items"]:
        s = i["suggestion"]
        cur = s.get("currency", "INR")
        amt = s.get("correction_minor", s.get("bank_amount_minor", 0))
        dr, cr = (s.get("bank_ledger"), s.get("counter_ledger")) if amt > 0 else (s.get("counter_ledger"), s.get("bank_ledger"))
        lines.append(f"• Dr {esc(dr)} / Cr {esc(cr)}: <b>{esc(fmt_amount(abs(amt), cur))}</b>")
        if i.get("explanation"):
            lines.append(f"  <i>{esc(i['explanation'][:300])}</i>")
    return "\n".join(lines), [[("✅ Approve", f"a:{aid}:y"), ("❌ Reject", f"a:{aid}:n")]]


def send_pending(db: Database, tg: TelegramClient, resend: bool = False) -> int:
    sent = 0
    for ap in db.query("approvals", {"status": "pending"}, order="approval_id"):
        if ap["channel_message_id"] and not resend:
            continue
        text, buttons = approval_card(ap)
        msg = tg.send_message(text, buttons)
        db.update("approvals", {"approval_id": ap["approval_id"]},
                  {"channel": "telegram", "channel_message_id": str(msg["message_id"])})
        sent += 1
    return sent


def daily_summary(result: dict) -> str:
    lines = [f"<b>CashSense daily run - as at {esc(result['as_of'])}</b> (SAMPLE)"]
    for r in result["reconciliations"]:
        mark = "✅" if r["status"] == "agreed" else "⚠️"
        items = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in r["items"].items()) or "nothing outstanding"
        lines.append(f"{mark} {r['account_id']}: books {esc(r['book'])}, bank {esc(r['bank'])} - {esc(items)}")
    lines.append(f"🚨 Open risk flags: {result['open_risk_flags']} (high: {result['high_risks']})")
    if result["verification_mismatches"]:
        v = result["verification_mismatches"][0]
        lines.append(f"🔎 Browser check: payment account registered to <b>{esc(v['holder'])}</b>, not {esc(v['expected'])}")
    lines.append(f"📝 Approvals waiting for you: {result['pending_approvals']}")
    if result.get("commentary"):
        lines.append("\n" + esc(result["commentary"]))
    return "\n".join(lines)


def status_text(db: Database) -> str:
    runs = db.query("recon_runs", order="created_at")
    latest = {}
    for r in runs:
        latest[r["account_id"]] = r
    cur = {a["account_id"]: a["currency"] for a in db.query("bank_accounts")}
    lines = ["<b>CashSense status</b> (SAMPLE)"]
    for aid, r in sorted(latest.items()):
        s = json.loads(r["summary"])
        items = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in s["items"].items()) or "nothing outstanding"
        lines.append(f"{'✅' if r['status'] == 'agreed' else '⚠️'} {aid} as at {r['as_of']}: "
                     f"books {esc(fmt_amount(r['book_balance_minor'], cur[aid]))} - {esc(items)}")
    flags = db.query("risk_flags", {"status": "open"})
    lines.append(f"🚨 Open risks: {len(flags)} | 📝 Pending approvals: {len(db.query('approvals', {'status': 'pending'}))}")
    return "\n".join(lines) if latest else "No reconciliation has run yet."


def risks_text(db: Database) -> str:
    flags = db.query("risk_flags", order="flag_id")
    if not flags:
        return "No risk flags."
    return "\n".join(["<b>Risk flags</b>"] + [f"{'🔴' if f['severity'] == 'high' else '🟠' if f['severity'] == 'medium' else '🟡'} "
                                              f"{esc(f['flag_type'].replace('_', ' '))} - {esc(f['status'])}: "
                                              f"{esc((f['explanation'] or '')[:160])}" for f in flags])


def handle_updates(db: Database, tg: TelegramClient, client=None) -> dict:
    """Process new Telegram updates once (called by n8n every few seconds)."""
    offset = int(db.get_state("telegram_offset", "0") or 0)
    try:
        updates = tg.get_updates(offset=offset + 1 if offset else None)
    except TelegramError as exc:   # network blip: nothing was processed, the next poll retries
        return {"updates": 0, "decisions": [], "commands": [], "imports": [], "ignored": 0,
                "error": f"{exc} - will retry on the next poll"}
    out = {"updates": len(updates), "decisions": [], "commands": [], "imports": [], "ignored": 0, "warnings": [],
           "_client": client}
    albums: dict[str, list] = {}
    for upd in updates:
        offset = max(offset, upd["update_id"])
        db.set_state("telegram_offset", str(offset))   # saved per update: a later failure never re-processes it
        try:
            _handle_one(db, tg, upd, out, albums)
        except TelegramError as exc:   # the decision is already recorded; only the chat reply failed
            out["warnings"].append(str(exc))
            db.audit("telegram", "reply_failed", "telegram", str(upd["update_id"]), {"error": str(exc)})
    _process_albums(db, tg, albums, client, out)
    out.pop("_client", None)
    return out


def _handle_one(db: Database, tg: TelegramClient, upd: dict, out: dict, albums: dict) -> None:
    cq = upd.get("callback_query")
    msg = upd.get("message") or {}
    chat_id = str((cq or {}).get("message", {}).get("chat", {}).get("id") or msg.get("chat", {}).get("id") or "")
    if chat_id != str(tg.chat_id):
        out["ignored"] += 1
        db.audit("telegram", "ignored_update_from_unknown_chat", "telegram", "unknown_chat", {})  # no chat IDs stored
        if cq:
            tg.answer_callback(cq["id"], "Not authorised")
        return
    if cq:
        parts = (cq.get("data") or "").split(":")
        if len(parts) == 3 and parts[0] == "a":
            who = cq.get("from", {}).get("first_name", "CA")
            res = decide(db, parts[1], "approve" if parts[2] == "y" else "reject", actor=f"telegram:{who}")
            out["decisions"].append(res)
            tg.answer_callback(cq["id"], res["message"])
            if res["ok"]:
                stamp = config.now_ist().strftime("%d-%b %H:%M")
                old = (cq.get("message") or {}).get("text", "")
                tg.edit_message(cq["message"]["message_id"],
                                f"{esc(old)}\n\n<b>{'✅' if res['status'] == 'approved' else '❌'} "
                                f"{esc(res['message'])}</b> by {esc(who)}, {stamp}")
        return
    text = (msg.get("text") or "").strip().lower()
    n_before = len(out["commands"])
    if text.startswith("/status") or text.startswith("/brs"):
        tg.send_message(status_text(db))
        out["commands"].append("status")
    elif text.startswith("/risks"):
        tg.send_message(risks_text(db))
        out["commands"].append("risks")
    elif text.startswith("/pending"):
        if not send_pending(db, tg, resend=True):
            tg.send_message("No approvals are waiting.")
        out["commands"].append("pending")
    elif msg.get("document") or msg.get("photo"):
        fid = msg["document"]["file_id"] if msg.get("document") else msg["photo"][-1]["file_id"]
        albums.setdefault(msg.get("media_group_id") or str(msg["message_id"]), []).append(
            (fid, (msg.get("document") or {}).get("file_name")))
    elif msg.get("voice") or msg.get("audio"):
        out["questions"] = out.get("questions", []) + [_voice_question(db, tg, msg, out.get("_client"))]
    elif text.startswith("/help") or text.startswith("/start"):
        tg.send_message(HELP)
        out["commands"].append("help")
    elif text:
        out["questions"] = out.get("questions", []) + [_text_question(db, tg, msg["text"], out.get("_client"))]
    if len(out["commands"]) > n_before:
        db.audit("telegram", f"command_{out['commands'][-1]}", "telegram", "ca_chat", {})  # chat ID is private


def _text_question(db: Database, tg: TelegramClient, question: str, client) -> dict:
    from .agents.assistant import ask

    if client is None or not client.available:
        tg.send_message("The assistant needs Gemini, which is not configured. " + HELP)
        return {"question": question, "answer": None}
    try:
        res = ask(db, question, client)
    except Exception as exc:  # Gemini busy etc.
        tg.send_message(f"⚠️ The assistant is busy right now ({esc(str(exc)[:120])}). Try again in a minute.")
        return {"question": question, "error": str(exc)}
    tools = ", ".join(sorted({t["name"].replace("get_", "") for t in res["tools"]}))
    tg.send_message(f"{esc(res['answer'])}\n<i>Sources: {esc(tools) or 'none'}</i>")
    return {"question": question, "answer": res["answer"], "tools": res["tools"]}


def _voice_question(db: Database, tg: TelegramClient, msg: dict, client) -> dict:
    from .voice import answer_voice_note

    if client is None or not client.available:
        tg.send_message("Voice questions need Gemini, which is not configured.")
        return {"voice": True, "answer": None}
    media = msg.get("voice") or msg.get("audio")
    audio, name = tg.download_file(media["file_id"])
    try:
        res = answer_voice_note(db, client, audio, media.get("mime_type") or "audio/ogg")
    except Exception as exc:
        tg.send_message(f"⚠️ Could not answer the voice note ({esc(str(exc)[:120])}). Try again or type the question.")
        return {"voice": True, "error": str(exc)}
    tools = ", ".join(sorted({t["name"].replace("get_", "") for t in res.get("tools", [])}))
    tg.send_message(f"🎙️ <i>You asked:</i> {esc(res['transcript'])}\n\n{esc(res['answer'])}\n<i>Sources: {esc(tools) or 'none'}</i>")
    if res.get("voice"):
        tg.send_voice(res["voice"], caption=f"Spoken answer ({res['voice_engine']})")
    return {"voice": True, "transcript": res["transcript"], "answer": res["answer"],
            "engine": res.get("voice_engine")}


def _process_albums(db: Database, tg: TelegramClient, albums: dict, client, out: dict) -> None:
    from .pipeline import INBOX, intake

    for group, files in albums.items():
        folder = INBOX / "telegram"      # not the folder n8n watches, so uploads are not imported twice
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for n, (fid, name) in enumerate(files, 1):
            data, tg_name = tg.download_file(fid)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            p = folder / f"tg_{stamp}_{n}_{(name or tg_name).replace(' ', '_')}"
            p.write_bytes(data)
            paths.append(p)
        tg.send_message(f"📥 Received {len(paths)} file(s). Reading and checking the statement...")
        try:
            res = intake(db, paths, client, actor="telegram")
            imp = res["import"]
            tg.send_message(f"✅ {esc(imp['account_id'])} {esc(imp['period'])}: {imp['lines']} lines, statement "
                            f"<b>{esc(imp['status'])}</b>{' (' + str(len(imp['repairs'])) + ' balance-proven corrections)' if imp['repairs'] else ''}; "
                            f"categorised {res['categorised']['lines']} ({res['categorised']['review']} to review); "
                            f"reconciliation {esc(res['reconciliation']['status'])}.")
            out["imports"].append(res)
        except Exception as exc:  # report any reading/import problem back to the user
            tg.send_message(f"⚠️ Could not import: {esc(exc)}")
            out["imports"].append({"error": str(exc)})


def notify_daily(db: Database, tg: TelegramClient, result: dict) -> int:
    """Summary message, then one card per pending approval. Returns the number of approval cards sent."""
    tg.send_message(daily_summary(result))
    return send_pending(db, tg)


def notify_escalation(db: Database, tg: TelegramClient) -> int:
    high = [f for f in db.query("risk_flags", {"status": "open"}) if f["severity"] == "high"]
    if not high:
        return 0
    tg.send_message("🔴 <b>URGENT - high-risk payments need your attention</b>\n" +
                    "\n".join(f"• {esc(f['explanation'][:220])}" for f in high))
    return len(high)


__all__ = ["approval_card", "send_pending", "handle_updates", "notify_daily", "notify_escalation", "TelegramError"]
