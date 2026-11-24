"""Command line entry point.

    python -m cashsense.cli phase1              generate Phase 1 data, load the database, build the review workbook
    python -m cashsense.cli phase2              render statements, import March 2026, categorise, measure, workbook
    python -m cashsense.cli import FILE [FILE]  import one statement (CSV, PDF or photo pages) [--replace]
    python -m cashsense.cli categorise --period 2026-03 [--rules-only]
    python -m cashsense.cli gemini-check        list the Gemini models this key can use and run a tiny test
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import config
from .money import fmt_amount


def cmd_phase1(args) -> None:
    from .datagen.phase1 import generate
    from .db import get_database
    from .db.load import load_phase1
    from .erp.mock_erp import MockERP
    from .review.phase1_workbook import build

    out = config.DATA_DIR / "phase1"
    manifest = generate(out)
    print("Generated:", json.dumps(manifest["counts"]))
    db = get_database()
    counts = load_phase1(db, out, actor="cli")
    print("Loaded into", config.db_backend(), ":", json.dumps(counts))
    erp = MockERP(db)
    as_of = config.as_of_date()
    print(f"\nBook balances as at {as_of}:")
    for a in erp.list_bank_accounts():
        bal = fmt_amount(erp.book_balance(a["account_id"], as_of), a["currency"])
        print(f"  {a['account_id']}  {a['name']:<34} {bal:>22}")
    if not args.no_workbook:
        wb = build(out, out / "Phase1_Review_SAMPLE.xlsx")
        print("\nReview workbook:", wb)


def cmd_phase2(args) -> None:
    from .agents.categoriser import categorise
    from .ai.gemini import GeminiClient, GeminiError
    from .datagen.phase2 import generate
    from .db import get_database
    from .db.load import load_phase1
    from .evaluation import compare_lines, load_expected, load_truth, score_categories
    from .ingest.importer import ImportRefused, import_statement, read_statement
    from .review.phase2_workbook import build

    p1, p2 = config.DATA_DIR / "phase1", config.DATA_DIR / "phase2"
    generate(p1, p2)
    db = get_database()
    load_phase1(db, p1, actor="cli")          # clean start from the Phase 1 data
    client = GeminiClient()
    use_ai = client.available and not args.rules_only
    ai_note = "" if client.available else ("No GEMINI_API_KEY in .env: photo statements were not read and the "
                                           "categoriser used rules only. Add the key and run phase2 again.")
    readers = []
    for exp in load_expected(p2):
        paths = [p2 / f for f in exp["files"]]
        row = {"account_id": exp["account_id"], "period": exp["period"], "format": exp["format"], "files": exp["files"]}
        if exp["format"] == "photo" and not use_ai:
            row["status_text"] = "skipped - needs Gemini"
            readers.append(row)
            continue
        try:
            st = read_statement(paths, client)
        except (GeminiError, ImportRefused, ValueError) as exc:
            row["status_text"] = f"failed - {exc}"
            readers.append(row)
            continue
        cmp_ = compare_lines(st, exp)
        if exp["period"] == "2026-03":   # March is imported into the database (replacing the Phase 1 copy)
            res = import_statement(db, st, [str(p.relative_to(config.ROOT)) for p in paths], actor="cli", replace=True)
            row.update(issues=res["issues"], repairs=res["repairs"], model=res["model"], status=res["status"])
        else:
            from .ingest.common import validate

            if exp["format"] != "photo":
                validate(st)
            row.update(issues=st.issues, repairs=st.repairs, model=st.model, status=st.status)
        row.update(cmp_)
        row["status_text"] = f"{row['status']} - {cmp_['exact_lines']}/{cmp_['expected_lines']} lines exact"
        readers.append(row)
        print(f"{exp['account_id']} {exp['period']} {exp['format']:>5}: {row['status_text']}")

    march = [ln for ln in db.query("bank_lines", order="line_id") if ln["txn_date"].startswith("2026-03")]
    out = categorise(db, march, client if use_ai else None, use_ai=use_ai, actor="cli")
    truth = load_truth(p2)
    score = score_categories(out["results"], truth)
    by_id = {ln["line_id"]: ln for ln in march}
    cur = {a["account_id"]: a["currency"] for a in db.query("bank_accounts")}
    cat_lines = [{"line_id": r["line_id"], "date": by_id[r["line_id"]]["txn_date"],
                  "description": by_id[r["line_id"]]["description"],
                  "amount": by_id[r["line_id"]]["amount_minor"] / 100,
                  "currency": cur[by_id[r["line_id"]]["account_id"]],
                  "truth": truth[r["line_id"]]["category"], "truth_party": truth[r["line_id"]]["party_id"],
                  "category": r["category"], "party_id": r["party_id"], "source": r["source"],
                  "review_status": r["review_status"], "flags": r["flags"],
                  "reason": r["reason"] + (" | " + "; ".join(r["flags"]) if r["flags"] else "")}
                 for r in out["results"]]
    print(f"Categorised {out['lines']} March lines: {score['category_correct']} correct, "
          f"{out['ai']} by AI, {out['rules']} by rules, {out['review']} to review"
          + (f" (AI note: {out['ai_error']})" if out["ai_error"] else ""))
    results = {"run_at": config.now_ist().isoformat(timespec="seconds"),
               "ai_engine": f"Gemini ({out['model'] or client.last_model or 'not used'})" if use_ai else "rules only",
               "ai_note": ai_note or (out["ai_error"] or ""), "readers": readers,
               "categories": {"scope": "all accounts, March 2026", "ai": out["ai"], "rules": out["rules"],
                              "review": out["review"], "score": score, "lines": cat_lines}}
    rdir = p2 / "results"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "phase2_results.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    wb = build(rdir / "phase2_results.json", p2 / "Phase2_Review_SAMPLE.xlsx")
    print("Review workbook:", wb)


def cmd_import(args) -> None:
    from .db import get_database
    from .ingest.importer import import_statement, read_statement

    paths = [Path(p) for p in args.files]
    st = read_statement(paths)
    print(json.dumps(import_statement(get_database(), st, [str(p) for p in paths], actor="cli",
                                      replace=args.replace), indent=1))


def cmd_categorise(args) -> None:
    from .agents.categoriser import categorise
    from .ai.gemini import GeminiClient
    from .db import get_database

    db = get_database()
    lines = [ln for ln in db.query("bank_lines", order="line_id") if ln["txn_date"].startswith(args.period)]
    out = categorise(db, lines, None if args.rules_only else GeminiClient(), use_ai=not args.rules_only, actor="cli")
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=1))


def cmd_gemini_check(args) -> None:
    from .ai.gemini import GeminiClient, GeminiError

    c = GeminiClient()
    if not c.available:
        print("GEMINI_API_KEY is not set. Copy .env.example to .env and paste the key after GEMINI_API_KEY=")
        return
    try:
        print("Text models (in order):  ", c.models_for("text")[:6])
        print("Vision models (in order):", c.models_for("vision")[:6])
        ans = c.generate_json("Reply in JSON.", ["Return {\"ok\": true}"],
                              {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}, "required": ["ok"]})
        print("Test call:", ans, "via", c.last_model)
    except GeminiError as exc:
        print("Gemini check failed:", exc)


def cmd_telegram_check(args) -> None:
    from .messaging.telegram import TelegramClient, TelegramError

    t = TelegramClient()
    if not t.available:
        print("TELEGRAM_BOT_TOKEN is not set. Paste the token from @BotFather into .env after TELEGRAM_BOT_TOKEN=")
        return
    try:
        me = t.get_me()
        print(f"Bot OK: @{me['username']} ({me['first_name']})")
        if not t.chat_id:
            chat = t.discover_chat_id()
            if not chat and args.wait:
                import time

                print(f"Waiting up to {args.wait} s for a message to t.me/{me['username']} ...", flush=True)
                end = time.monotonic() + args.wait
                while not chat and time.monotonic() < end:
                    t.get_updates(wait=int(min(25, max(1, end - time.monotonic()))))
                    chat = t.discover_chat_id()
            if not chat:
                print(f"No /start received yet. Open t.me/{me['username']} in Telegram, tap Start, then run again.")
                return
            config.save_setting("TELEGRAM_CHAT_ID", chat)
            t.chat_id = chat
            print("Chat found and saved to .env as TELEGRAM_CHAT_ID")
        t.send_message("<b>CashSense test</b>\nYour bot is connected. Approvals and alerts will arrive here.\n"
                       "<i>SAMPLE data only - fictitious company.</i>")
        print("Test message sent - check Telegram on your phone.")
    except TelegramError as exc:
        print("Telegram check failed:", exc)


def cmd_phase3(args) -> None:
    """Fresh database, Phase 2 imports and AI categorisation, then the daily run (reconcile, risk scan with
    browser verification, Gemini explanations, approvals), measured against the Phase 3 answer key."""
    from .ai.gemini import GeminiClient
    from .datagen.phase3 import generate
    from .db import get_database
    from .db.load import load_phase1
    from .pipeline import dumps, run_daily

    generate(config.DATA_DIR / "phase1", config.DATA_DIR / "phase3")
    db = get_database()
    if not args.keep_db:
        load_phase1(db, config.DATA_DIR / "phase1", actor="cli")
        from .agents.categoriser import categorise

        lines = db.query("bank_lines", order="line_id")
        march = [ln for ln in lines if ln["txn_date"].startswith("2026-03")]
        categorise(db, [ln for ln in lines if not ln["txn_date"].startswith("2026-03")], None, use_ai=False, actor="cli")
        categorise(db, march, GeminiClient(), use_ai=True, actor="cli")
    result = run_daily(db, config.as_of_date(), GeminiClient(), use_browser=not args.no_browser, actor="cli")
    if args.notify:
        from .messaging.telegram import TelegramClient
        from .notify import notify_daily

        result["telegram_messages"] = notify_daily(db, TelegramClient(), result) + 1
    accuracy = phase3_accuracy(db, result)
    result["accuracy"] = accuracy
    out = config.DATA_DIR / "phase3" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase3_daily_run.json").write_text(dumps(result), encoding="utf-8")
    from .review.phase3_workbook import build

    wb = build(db, result, accuracy, config.DATA_DIR / "phase3" / "Phase3_Review_SAMPLE.xlsx")
    print(dumps({k: v for k, v in result.items() if k not in ("commentary", "verification_results")}))
    print("\nCommentary:", result["commentary"] or "(none)")
    print("Review workbook:", wb)


def phase3_accuracy(db, result: dict) -> dict:
    import csv

    key_dir = config.DATA_DIR / "phase3" / "answer_key"
    recon_key = json.loads((key_dir / "expected_recon_items.json").read_text(encoding="utf-8"))
    risk_key = json.loads((key_dir / "expected_risk_flags.json").read_text(encoding="utf-8"))
    with (config.DATA_DIR / "phase1" / "answer_key" / "matches.csv").open(newline="", encoding="utf-8") as fh:
        truth = {(r["entry_id"], r["line_id"]) for r in csv.DictReader(fh)}
    auto = {(lk["entry_id"], lk["line_id"]) for lk in db.query("recon_links") if lk["link_type"] == "auto_exact"}
    items = [i for rid in result["run_ids"] for i in db.query("recon_items", {"run_id": rid})]
    fuzzy = {i["line_id"] for i in items if i["category"] == "amount_mismatch"}
    got = sorted((i["account_id"], i["category"], i["line_id"] or i["entry_id"]) for i in items)
    exp = sorted((a, i["category"], i.get("line_id") or i.get("entry_id")) for a, r in recon_key.items() for i in r["items"])
    flags = db.query("risk_flags")
    flag_keys = {(f["flag_type"], tuple(sorted(json.loads(f["line_ids"]))) or f["bill_no"]) for f in flags}
    exp_flags = {(r["type"], tuple(sorted([r["line_id"]] if r.get("line_id") else
                                          [x["line_id"] for x in r.get("lines", [])])) or r["bill_no"]) for r in risk_key}
    return {"links_made": len(auto), "links_correct": len(auto & truth),
            "links_missed_non_fuzzy": len([t for t in truth - auto if t[1] not in fuzzy]),
            "items_match": got == exp, "items_found": len(got), "items_expected": len(exp),
            "risks_expected": len(exp_flags), "risks_found": len(flag_keys & exp_flags),
            "risk_false_positives": len(flag_keys - exp_flags)}


def check_answer(q: dict, answer: str, fc: dict) -> tuple[bool, str]:
    """Question-bank check: expected facts must appear in the assistant's answer."""
    text = answer.lower().replace("**", "")
    expected = []
    ok = True
    if q.get("expect_all"):
        expected += q["expect_all"]
        ok &= all(x.lower() in text for x in q["expect_all"])
    for k in ("expect_any", "expect_any_2"):
        if q.get(k):
            expected.append(" / ".join(q[k]))
            ok &= any(x.lower() in text for x in q[k])
    if q.get("expect_from_forecast"):
        e = q["expect_from_forecast"]
        val = fc[e["scenario"]]["summary"][e["field"]]
        want = e["format"].format(val)
        expected.append(want)
        ok &= want.lower() in text
    return ok, "; ".join(expected)


def cmd_phase4(args) -> None:
    from datetime import date as _date

    from .agents.assistant import ask
    from .agents.forecaster import apply_scenario, forecast_all, known_flows, week_of
    from .agents.reconciler import reconcile
    from .ai.gemini import GeminiClient, GeminiError
    from .dashboard import refresh_commentary
    from .datagen.phase4 import generate
    from .db import get_database
    from .pipeline import accounts
    from .powerbi import export
    from .review.phase4_workbook import build

    p4 = config.DATA_DIR / "phase4"
    generate(config.DATA_DIR / "phase1", p4)
    db = get_database()
    as_of = config.as_of_date()
    if not [r for r in db.query("recon_runs") if r["as_of"] == as_of.isoformat()]:
        for a in accounts(db):
            reconcile(db, a, as_of, actor="cli")
    fc = forecast_all(db, as_of)
    key = json.loads((p4 / "answer_key" / "expected_forecast_known_flows.json").read_text(encoding="utf-8"))
    match = total = 0
    for s, exp in key["known_weekly"].items():
        flows = apply_scenario(known_flows(db, as_of), s, as_of)
        got = {w: 0 for w in range(1, 14)}
        for f in flows:
            w = week_of(f.when, as_of)
            if 1 <= w <= 13:
                got[w] += f.amount_paise
        for w in range(1, 14):
            total += 1
            match += got[w] == exp[str(w)]
    client = GeminiClient()
    use_ai = client.available and not args.no_ai
    comm = refresh_commentary(db, as_of, client) if use_ai else {"ai_used": False, "error": "AI not used"}
    qa = {"asked": 0, "passed": 0, "results": []}
    if use_ai:
        qs = json.loads((p4 / "answer_key" / "assistant_questions.json").read_text(encoding="utf-8"))
        for q in qs:
            try:
                res = ask(db, q["q"], client, as_of)
            except GeminiError as exc:
                qa["note"] = f"Gemini busy: {str(exc)[:80]}"
                break
            ok, expected = check_answer(q, res["answer"], fc)
            qa["asked"] += 1
            qa["passed"] += ok
            qa["results"].append({"q": q["q"], "answer": res["answer"], "tools_used": [t["name"] for t in res["tools"]],
                                  "expected": expected, "pass": ok})
            print(f"{'PASS' if ok else 'FAIL'}  {q['q']}\n      -> {res['answer'][:220]}")
    pbi = export(db, as_of, p4 / "powerbi")
    results = {"as_of": as_of.isoformat(), "forecast": fc, "commentary": comm, "assistant": qa,
               "accuracy": {"known_flow_weeks": total, "known_flow_weeks_matching": match}, "powerbi": pbi}
    (p4 / "results").mkdir(parents=True, exist_ok=True)
    (p4 / "results" / "phase4_results.json").write_text(json.dumps(
        {**results, "forecast": {s: {**r, "flows": len(r["flows"])} for s, r in fc.items()}}, indent=1, default=str),
        encoding="utf-8")
    wb = build(results, p4 / "Phase4_Review_SAMPLE.xlsx")
    for s, r in fc.items():
        sm = r["summary"]
        print(f"{s:22} peak week {sm['peak_week']:2}  peak use {sm['peak_utilisation']:.0%}  first 85% alert: "
              f"{sm['first_alert_week'] or 'none'}")
    print(f"Known flows vs answer key: {match}/{total} scenario-weeks identical")
    print(f"Assistant: {qa['passed']}/{qa['asked']} questions passed" + (f" ({qa['note']})" if qa.get("note") else ""))
    print("Commentary:", comm.get("headline") or comm.get("error"), "| unverified amounts:", comm.get("unverified_amounts"))
    print("Power BI export:", pbi)
    print("Review workbook:", wb)


def cmd_migrate(args) -> None:
    """Copy the local SQLite database to Supabase, verify row counts, and switch .env to Supabase."""
    from .db.adapter import SQLiteDatabase, SupabaseDatabase, TABLES, copy_database

    src = SQLiteDatabase(config.sqlite_path())
    dst = SupabaseDatabase(config.setting("SUPABASE_URL"), config.setting("SUPABASE_KEY"))
    dst.init_schema()
    print("Copying local database to Supabase:")
    counts = copy_database(src, dst)
    dst._cache.clear()
    bad = {t: (counts[t], len(dst.query(t))) for t in TABLES if len(dst.query(t)) != counts[t]}
    if bad:
        raise SystemExit(f"Row counts differ after copy: {bad}")
    config.save_setting("CASHSENSE_DB", "supabase")
    dst.audit("cli", "migrate_to_supabase", "database", "", counts)
    print("All row counts verified. .env now uses CASHSENSE_DB=supabase (set it back to sqlite to work locally).")


def cmd_briefing(args) -> None:
    from . import briefing
    from .db import get_database

    if args.secret:
        briefing.secret()
        print("APPS_SCRIPT_SECRET is in .env - copy its value into the Apps Script property CASHSENSE_SECRET.")
        return
    b = briefing.build(get_database(), config.as_of_date())
    res = briefing.send(b, ping=args.ping, send_email=not args.no_email)
    print(json.dumps(res, indent=1))


def cmd_reviewer_setup(args) -> None:
    """One-time setup on a fresh copy (e.g. the ICAI upload): unpack the sample data, create a safe .env,
    build a local SQLite database and run the reconciliation and risk checks (no AI or accounts needed)."""
    import shutil
    import zipfile

    from .datagen.phase1 import FY_END

    root = config.ROOT
    if not (root / "data" / "phase1" / "statement_index.csv").exists():
        zp = root / "data.zip"
        if not zp.exists():
            raise SystemExit("Sample data not found: data.zip is missing")
        print("Unpacking sample data (data.zip)...")
        with zipfile.ZipFile(zp) as z:
            z.extractall(root)
    env = root / ".env"
    if not env.exists():
        shutil.copy(root / ".env.example", env)
        print("Created .env from .env.example (local database; no keys - AI, Telegram and email are switched off)")
    os.environ.setdefault("CASHSENSE_DB", "sqlite")
    if config.db_backend() != "sqlite":
        raise SystemExit(".env uses Supabase - reviewer setup builds a local database; set CASHSENSE_DB=sqlite")
    from .agents.categoriser import categorise
    from .db import get_database
    from .db.load import load_phase1
    from .pipeline import run_daily

    db = get_database()
    print("Building the local database from the sample data...")
    load_phase1(db, root / "data" / "phase1", actor="reviewer_setup")
    categorise(db, db.query("bank_lines", order="line_id"), None, use_ai=False, actor="reviewer_setup")
    print("Running reconciliation, risk checks and approvals (rules only)...")
    try:
        result = run_daily(db, FY_END, None, use_browser=True, actor="reviewer_setup")
    except Exception:  # browser agent not available on this machine
        result = run_daily(db, FY_END, None, use_browser=False, actor="reviewer_setup")
    for r in result["reconciliations"]:
        print(f"  {r['account_id']}: {r['status']} - {r['items'] or 'nothing outstanding'}")
    print(f"  risk flags: {result['risk_flags']} ({result['high_risks']} high); approvals proposed: {result['new_approvals']}"
          + (f"; note: {result['browser_note']}" if result["browser_note"] else ""))
    from .api import _secret

    _secret("DASHBOARD_PASSWORD")
    _secret("SESSION_SECRET")
    print("\nSetup complete. Start CashSense with Start_CashSense.cmd and sign in to the dashboard with")
    print("DASHBOARD_PASSWORD from the .env file (open it with Notepad).")


def cmd_serve(args) -> None:
    import uvicorn

    from .api import api_key

    api_key()  # make sure a key exists in .env before n8n needs it
    print(f"CashSense API on http://127.0.0.1:{args.port} (key in .env as CASHSENSE_API_KEY)")
    uvicorn.run("cashsense.api:app", host="127.0.0.1", port=args.port, log_level="info")


def main() -> None:
    p = argparse.ArgumentParser(prog="cashsense")
    sub = p.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("phase1", help="Generate and load Phase 1 sample data")
    p1.add_argument("--no-workbook", action="store_true")
    p1.set_defaults(func=cmd_phase1)
    p2 = sub.add_parser("phase2", help="Run the Phase 2 demo and measurement")
    p2.add_argument("--rules-only", action="store_true")
    p2.set_defaults(func=cmd_phase2)
    pi = sub.add_parser("import", help="Import a statement file (CSV, PDF, or photo pages)")
    pi.add_argument("files", nargs="+")
    pi.add_argument("--replace", action="store_true")
    pi.set_defaults(func=cmd_import)
    pc = sub.add_parser("categorise", help="Categorise imported lines for a period")
    pc.add_argument("--period", required=True)
    pc.add_argument("--rules-only", action="store_true")
    pc.set_defaults(func=cmd_categorise)
    pg = sub.add_parser("gemini-check", help="Check the Gemini key and models")
    pg.set_defaults(func=cmd_gemini_check)
    pt = sub.add_parser("telegram-check", help="Check the Telegram bot, save the chat ID, send a test message")
    pt.add_argument("--wait", type=int, default=0, help="seconds to wait for /start")
    pt.set_defaults(func=cmd_telegram_check)
    p3 = sub.add_parser("phase3", help="Run the Phase 3 daily run (reconcile, risks, approvals) on fresh data")
    p3.add_argument("--keep-db", action="store_true", help="do not reload the database first")
    p3.add_argument("--no-browser", action="store_true")
    p3.add_argument("--notify", action="store_true", help="send the summary and approvals to Telegram")
    p3.set_defaults(func=cmd_phase3)
    p4 = sub.add_parser("phase4", help="Forecast, commentary, assistant question bank, Power BI export, workbook")
    p4.add_argument("--no-ai", action="store_true")
    p4.set_defaults(func=cmd_phase4)
    pb = sub.add_parser("briefing", help="Send the daily briefing to the Google Apps Script web app")
    pb.add_argument("--ping", action="store_true", help="only check the connection and the secret")
    pb.add_argument("--no-email", action="store_true")
    pb.add_argument("--secret", action="store_true", help="create APPS_SCRIPT_SECRET in .env")
    pb.set_defaults(func=cmd_briefing)
    pr = sub.add_parser("reviewer-setup", help="One-time setup on a fresh copy: sample data + local database")
    pr.set_defaults(func=cmd_reviewer_setup)
    pm = sub.add_parser("migrate-to-supabase", help="Copy the local database to Supabase and switch .env")
    pm.set_defaults(func=cmd_migrate)
    ps = sub.add_parser("serve", help="Start the local API for n8n (127.0.0.1 only)")
    ps.add_argument("--port", type=int, default=8765)
    ps.set_defaults(func=cmd_serve)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
