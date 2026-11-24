"""Phase 3 acceptance tests: Reconciler, approvals, Risk Sentinel, browser verification,
Gemini guard-rails, Telegram handling and the local API. Offline (stand-ins for Gemini and
Telegram); the browser test runs when Playwright + Microsoft Edge are available.

Run:  python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest import mock

from cashsense.agents.categoriser import categorise
from cashsense.agents.explainer import explain
from cashsense.agents.reconciler import reconcile
from cashsense.agents.risk import scan
from cashsense.approvals import decide, propose
from cashsense.datagen.phase1 import generate as gen1
from cashsense.datagen.phase3 import generate as gen3
from cashsense.db.adapter import SQLiteDatabase
from cashsense.db.load import load_phase1
from cashsense.money import to_paise

ROOT = Path(__file__).resolve().parent.parent
P1, P3 = ROOT / "data" / "phase1", ROOT / "data" / "phase3"
AS_OF = date(2026, 3, 31)
ACCOUNTS = ("CA01", "CC01", "CL01", "EF01")


def payload_lines(text: str) -> str:
    return text.split("\n", 1)[1]


def key_items(rec: dict) -> list:
    return sorted((i["category"], i.get("line_id") or i.get("entry_id")) for i in rec["items"])


class FakeTg:
    available = True

    def __init__(self, chat_id="111", updates=None):
        self.chat_id, self._updates = chat_id, list(updates or [])
        self.sent, self.edits, self.answers, self.n = [], [], [], 100

    def get_updates(self, offset=None, wait=0):
        out, self._updates = self._updates, []
        return out

    def send_message(self, text, buttons=None, chat_id=None):
        self.n += 1
        self.sent.append((text, buttons))
        return {"message_id": self.n}

    def answer_callback(self, cid, text=""):
        self.answers.append(text)

    def edit_message(self, mid, text, chat_id=None):
        self.edits.append((mid, text))


class FakeAI:
    available, last_model = True, "fake-gemini"

    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def generate_json(self, system, parts, schema, **kw):
        self.calls += 1
        return self.fn(json.loads(parts[0].split("\n", 1)[1]))


class Phase3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (P1 / "manifest.json").exists():
            gen1(P1)
        if not (P3 / "manifest.json").exists():
            gen3(P1, P3)
        cls.key = json.loads((P3 / "answer_key" / "expected_recon_items.json").read_text(encoding="utf-8"))
        cls.risk_key = json.loads((P3 / "answer_key" / "expected_risk_flags.json").read_text(encoding="utf-8"))
        cls.after = json.loads((P3 / "answer_key" / "expected_after_approval.json").read_text(encoding="utf-8"))
        with (P1 / "answer_key" / "matches.csv").open(newline="", encoding="utf-8") as fh:
            cls.truth = {(r["entry_id"], r["line_id"]) for r in csv.DictReader(fh)}
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dbpath = Path(cls.tmp.name) / "p3.db"
        cls.db = SQLiteDatabase(cls.dbpath)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.tmp.cleanup()

    def setUp(self):
        load_phase1(self.db, P1, actor="test")
        categorise(self.db, self.db.query("bank_lines", order="line_id"), None, use_ai=False, actor="test")

    def run_all(self):
        return [reconcile(self.db, a, AS_OF, actor="test") for a in ACCOUNTS]

    # ---- Reconciler ------------------------------------------------------------------
    def test_reconciliation_matches_answer_key(self):
        for r in self.run_all():
            self.assertEqual(r["status"], "agreed", r["account_id"])
            self.assertEqual(key_items({"items": r["items"]}), key_items(self.key[r["account_id"]]), r["account_id"])
            links = {(lk["entry_id"], lk["line_id"]) for lk in r["new_links"]}
            truth = {t for t in self.truth if t[1].startswith(r["account_id"])}
            self.assertTrue(links <= truth, "every automatic match must be a true match")
            missed = truth - links
            self.assertTrue(all(any(i["category"] == "amount_mismatch" and i["line_id"] == m[1] for i in r["items"])
                                for m in missed), f"only the fuzzy pair may stay unmatched: {missed}")

    def test_second_run_is_incremental(self):
        self.run_all()
        again = self.run_all()
        self.assertEqual(sum(r["summary"]["auto_matched_now"] for r in again), 0)
        for r in again:
            self.assertEqual(key_items({"items": r["items"]}), key_items(self.key[r["account_id"]]))

    # ---- approvals ---------------------------------------------------------------------
    def test_approve_all_leaves_only_timing_items(self):
        recon, risk = self.run_all(), scan(self.db, AS_OF)
        created = propose(self.db, recon, risk)
        kinds = Counter(c["kind"] for c in created)
        self.assertEqual(kinds, {"journal_entry": 9, "fuzzy_match": 1, "risk_flag": 8})
        self.assertEqual(propose(self.db, recon, risk), [], "proposals are idempotent")
        books_before = len(self.db.query("book_entries"))
        for c in created:
            self.assertTrue(decide(self.db, c["approval_id"], "approve", "test-ca")["ok"])
        posted = self.db.query("book_entries")[books_before:]
        self.assertEqual(len(posted), 13)       # 12 bank lines in the 9 journal approvals + 1 correction
        self.assertTrue(all(e["mode"] == "APPROVED-JV" for e in posted))
        for r in self.run_all():
            self.assertEqual(r["status"], "agreed")
            self.assertTrue(r["summary"]["timing_only"], r["account_id"])
            self.assertEqual(sorted(i.get("entry_id") for i in r["items"]),
                             sorted(i["entry_id"] for i in self.after[r["account_id"]]))
        self.assertEqual({f["status"] for f in self.db.query("risk_flags")}, {"reviewed"})
        actions = Counter(a["action"] for a in self.db.query("audit_log"))
        self.assertEqual(actions["approve_journal_entry"], 9)

    def test_fuzzy_correction_amount(self):
        recon = self.run_all()
        created = propose(self.db, recon, None)
        fz = next(c for c in created if c["kind"] == "fuzzy_match")
        res = decide(self.db, fz["approval_id"], "approve", "test-ca")
        corr = self.db.query("book_entries", {"entry_id": res["posted_entries"][0]})[0]
        self.assertEqual(corr["amount_minor"], to_paise("900.00"))   # books 1,85,400 -> bank 1,84,500

    def test_reject_posts_nothing_and_decisions_are_final(self):
        recon = self.run_all()
        created = propose(self.db, recon, None)
        j = next(c for c in created if c["kind"] == "journal_entry")
        n = len(self.db.query("book_entries"))
        self.assertEqual(decide(self.db, j["approval_id"], "reject", "test-ca")["status"], "rejected")
        self.assertEqual(len(self.db.query("book_entries")), n)
        self.assertFalse(decide(self.db, j["approval_id"], "approve", "test-ca")["ok"], "cannot flip a decision")
        self.assertFalse(decide(self.db, "AP9999", "approve", "x")["ok"])
        self.assertFalse(decide(self.db, created[1]["approval_id"], "maybe", "x")["ok"])
        again = propose(self.db, self.run_all(), None)
        self.assertIn(j["ref_id"], {a["ref_id"] for a in again}, "rejected items come back for review")

    # ---- Risk Sentinel -------------------------------------------------------------------
    def test_risk_scan_matches_answer_key(self):
        out = scan(self.db, AS_OF)
        got = sorted((f["flag_type"], tuple(sorted(f["line_ids"])) or f["bill_no"]) for f in out["flags"])
        exp = []
        for r in self.risk_key:
            lines = tuple(sorted([r["line_id"]] if r.get("line_id") else [x["line_id"] for x in r.get("lines", [])]))
            exp.append((r["type"], lines or r["bill_no"]))
        self.assertEqual(got, sorted(exp))
        sev = {f["flag_type"]: f["severity"] for f in out["flags"]}
        self.assertEqual(sev["vendor_bank_details_changed"], "high")
        self.assertEqual(sev["weekend_payment_to_unknown_payee"], "high")
        r01 = next(f for f in out["flags"] if f["flag_type"] == "vendor_bank_details_changed")
        self.assertEqual(r01["evidence"]["beneficiary_added_by"], "ops.user2")

    def test_risk_scan_does_not_depend_on_ai_label(self):
        """Regression: a Gemini run once labelled the Sunday IMPS to an unknown payee 'unidentified'
        instead of 'supplier_payment'; the risk must still be raised."""
        self.db.update("bank_lines", {"line_id": "CA01-202603-0036"}, {"category": "unidentified", "party_id": None})
        types = {f["flag_type"] for f in scan(self.db, AS_OF)["flags"]}
        self.assertIn("weekend_payment_to_unknown_payee", types)
        self.assertEqual(len(scan(self.db, AS_OF)["flags"]), 8)

    def test_ai_label_variation_does_not_change_controls(self):
        """Regression: Gemini runs labelled the unknown 'M S Raj Traders' credit a customer receipt and the
        unknown Sunday IMPS 'unidentified'. The rule category is kept on disagreement, so the reconciliation
        and risk results stay identical to the answer key."""
        march = [ln for ln in self.db.query("bank_lines", order="line_id") if ln["txn_date"].startswith("2026-03")]

        def answer(payload):
            from cashsense.categories import truth_category  # noqa: F401
            out = []
            for ln in json.loads(payload_lines(payload)):
                cat = "customer_receipt" if "RAJ TRADERS" in ln["description"] else \
                    "unidentified" if "QUICKFIX" in ln["description"] else None
                out.append({"line_id": ln["line_id"], "category": cat or "SKIP", "party_id": None,
                            "confidence": 0.95, "reason": "test"})
            return {"results": [o for o in out if o["category"] != "SKIP"]}

        class AI(FakeAI):
            def generate_json(self, system, parts, schema, **kw):
                return answer(parts[1])

        categorise(self.db, march, AI(None), use_ai=True, actor="test")
        raj = self.db.query("bank_lines", {"line_id": "CL01-202603-0022"})[0]
        self.assertEqual(raj["category"], "unidentified")
        self.assertEqual(raj["review_status"], "review")
        recon = self.run_all()
        for r in recon:
            self.assertEqual(key_items({"items": r["items"]}), key_items(self.key[r["account_id"]]))
        self.assertEqual(len(scan(self.db, AS_OF)["flags"]), 8)

    def test_rescan_keeps_decisions(self):
        out = scan(self.db, AS_OF)
        self.db.update("risk_flags", {"flag_id": out["flags"][0]["flag_id"]}, {"status": "reviewed"})
        again = scan(self.db, AS_OF)
        self.assertEqual(again["flags"][0]["status"], "reviewed")
        self.assertEqual(again["flags"][1]["status"], "open")

    # ---- Gemini guard-rails ---------------------------------------------------------------
    def test_explainer_guardrails(self):
        recon, risk = self.run_all(), scan(self.db, AS_OF)

        def answer(payload):
            items = [{"item_id": i["item_id"], "explanation": "Explained.", "proposed_debit": i["template_debit"],
                      "proposed_credit": i["template_credit"]} for i in payload["items"]]
            charge = next(x for x, i in zip(items, payload["items"]) if i["category"] == "bank_charges_not_booked")
            charge["proposed_debit"] = "Miscellaneous Expenses"
            items.append({"item_id": "FAKE-ID", "explanation": "x", "proposed_debit": "a", "proposed_credit": "b"})
            flags = []
            for f in payload["flags"]:
                sev = "low" if f["suggested_severity"] == "high" else "high" if f["type"] == "duplicate_payment" else f["suggested_severity"]
                flags.append({"flag_id": f["flag_id"], "severity": sev, "explanation": "Why.", "action": "Do this."})
            return {"items": items, "flags": flags, "commentary": "All good."}

        report = explain(self.db, recon, risk, FakeAI(answer))
        self.assertTrue(report["ai_used"])
        self.assertEqual(len(report["ledger_disagreements"]), 1)
        sev = {f["flag_type"]: f["severity"] for f in risk["flags"]}
        self.assertEqual(sev["vendor_bank_details_changed"], "high", "AI cannot lower severity")
        self.assertEqual(sev["duplicate_payment"], "high", "AI may raise severity")
        self.assertEqual(len(report["severity_raised"]), 1)
        stored = self.db.query("recon_items", {"run_id": recon[0]["run_id"]})
        self.assertTrue(any("template used" in (i["explanation"] or "") for i in stored))

    # ---- Telegram ---------------------------------------------------------------------------
    def test_telegram_approvals_and_commands(self):
        from cashsense.notify import handle_updates, send_pending

        propose(self.db, self.run_all(), scan(self.db, AS_OF))
        tg = FakeTg()
        self.assertEqual(send_pending(self.db, tg), 18)
        self.assertEqual(send_pending(self.db, tg), 0, "each card is sent once")
        first = self.db.query("approvals", order="approval_id")[0]
        cb = lambda chat, data, uid: {"update_id": uid, "callback_query": {  # noqa: E731
            "id": f"cb{uid}", "data": data, "from": {"first_name": "Ramnath"},
            "message": {"message_id": 5, "chat": {"id": chat}, "text": "card"}}}
        tg._updates = [cb(999, f"a:{first['approval_id']}:y", 1),               # stranger - ignored
                       cb(111, f"a:{first['approval_id']}:y", 2),               # the CA approves
                       {"update_id": 3, "message": {"message_id": 9, "chat": {"id": 111}, "text": "/status"}}]
        out = handle_updates(self.db, tg)
        self.assertEqual(out["ignored"], 1)
        self.assertEqual(len(out["decisions"]), 1)
        self.assertEqual(self.db.query("approvals", {"approval_id": first["approval_id"]})[0]["decided_by"],
                         "telegram:Ramnath")
        self.assertIn("Not authorised", tg.answers)
        self.assertTrue(tg.edits and "by Ramnath" in tg.edits[0][1])
        self.assertTrue(any("CashSense status" in t for t, _ in tg.sent))
        self.assertEqual(self.db.get_state("telegram_offset"), "3")

    def test_telegram_network_blips_lose_nothing(self):
        """Regression: one live poll hit 'Cannot reach Telegram'. A failed fetch must return cleanly, and a
        failed reply after a decision must not undo or repeat the decision."""
        from cashsense.messaging.telegram import TelegramError
        from cashsense.notify import handle_updates

        propose(self.db, self.run_all(), None)
        first = self.db.query("approvals", order="approval_id")[0]

        class Down(FakeTg):
            def get_updates(self, offset=None, wait=0):
                raise TelegramError("Cannot reach Telegram (ConnectionError)")

        out = handle_updates(self.db, Down())
        self.assertIn("will retry", out["error"])

        class EditFails(FakeTg):
            def edit_message(self, mid, text, chat_id=None):
                raise TelegramError("Cannot reach Telegram (ConnectionError)")

        tg = EditFails(updates=[{"update_id": 50, "callback_query": {
            "id": "c1", "data": f"a:{first['approval_id']}:y", "from": {"first_name": "Ramnath"},
            "message": {"message_id": 5, "chat": {"id": 111}, "text": "card"}}}])
        out = handle_updates(self.db, tg)
        self.assertEqual(out["warnings"], ["Cannot reach Telegram (ConnectionError)"])
        self.assertEqual(self.db.query("approvals", {"approval_id": first["approval_id"]})[0]["status"], "approved")
        self.assertEqual(self.db.get_state("telegram_offset"), "50")

    # ---- local API ---------------------------------------------------------------------------
    def test_api_requires_key(self):
        from fastapi.testclient import TestClient

        from cashsense.api import app

        with mock.patch.dict(os.environ, {"CASHSENSE_API_KEY": "test-key", "CASHSENSE_DB": "sqlite",
                                          "CASHSENSE_SQLITE": str(self.dbpath)}):
            c = TestClient(app)
            self.assertEqual(c.get("/api/health").status_code, 200)
            self.assertEqual(c.get("/api/approvals").status_code, 401)
            self.assertEqual(c.get("/api/approvals", headers={"X-CashSense-Key": "wrong"}).status_code, 401)
            self.assertEqual(c.get("/api/approvals", headers={"X-CashSense-Key": "test-key"}).status_code, 200)
            bad = c.post("/api/import-file", json={"file": "../../.env"}, headers={"X-CashSense-Key": "test-key"})
            self.assertEqual(bad.status_code, 400)


def _edge_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(channel="msedge", headless=True).close()
        return True
    except Exception:
        return False


@unittest.skipUnless(_edge_available(), "Playwright with Microsoft Edge not available")
class BrowserAgentTests(unittest.TestCase):
    def test_verifications_match_answer_key(self):
        from cashsense.agents.browser_verify import BankVerifier

        if not (P3 / "manifest.json").exists():
            gen3(P1, P3)
        expected = json.loads((P3 / "answer_key" / "expected_verifications.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp, BankVerifier(evidence_dir=Path(tmp)) as v:
            for e in expected:
                r = v.verify_account(e["ifsc"], e["account_no"], e["vendor_name"], f"t_{e['party_id']}")
                self.assertTrue(r["account_found"])
                self.assertEqual(r["holder"], e["expected_holder"])
                self.assertEqual(r["name_match"], e["expected_result"] == "match")
                self.assertTrue(Path(r["screenshot"]).exists() or (ROOT / r["screenshot"]).exists())
            self.assertTrue(v.lookup_ifsc("ZZQB0DEL404")["found"])
            self.assertFalse(v.lookup_ifsc("ABCD0123456")["found"])
            self.assertFalse(v.verify_account("ZZQB0DEL404", "000000000000", "X", "t_none")["account_found"])


if __name__ == "__main__":
    unittest.main()
