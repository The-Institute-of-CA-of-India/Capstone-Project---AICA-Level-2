"""Phase 1 acceptance tests: data integrity, seeded items, database load and ERP adapter.

Run:  python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from cashsense.datagen.phase1 import FY_END, IFSC_RE, generate, is_working
from cashsense.db.adapter import SQLiteDatabase
from cashsense.db.load import load_phase1, statement_line_id
from cashsense.erp.mock_erp import MockERP
from cashsense.money import fmt_inr, to_paise

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "phase1"


def rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Phase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "manifest.json").exists():
            generate(DATA)
        cls.index = rows(DATA / "statement_index.csv")
        cls.accounts = {a["account_id"]: a for a in rows(DATA / "bank_accounts.csv")}
        cls.parties = rows(DATA / "counterparties.csv")
        cls.books = rows(DATA / "book_entries.csv")
        cls.key = json.loads((DATA / "answer_key" / "recon_items_2026-03-31.json").read_text(encoding="utf-8"))
        cls.risks = json.loads((DATA / "answer_key" / "risk_flags.json").read_text(encoding="utf-8"))
        cls.lines = {}
        for s in cls.index:
            for i, r in enumerate(rows(DATA / s["file"]), 1):
                cls.lines[statement_line_id(s["account_id"], s["period"], i)] = {**r, "account_id": s["account_id"]}

    # ---- statements -----------------------------------------------------------
    def test_running_balances_and_closing(self):
        for s in self.index:
            bal = to_paise(s["opening"])
            for r in rows(DATA / s["file"]):
                bal += to_paise(r["credit"]) - to_paise(r["debit"])
                self.assertEqual(bal, to_paise(r["balance"]), f"running balance broken in {s['file']}")
            self.assertEqual(bal, to_paise(s["closing"]), s["file"])

    def test_month_to_month_continuity(self):
        for acc in self.accounts:
            months = [s for s in self.index if s["account_id"] == acc]
            self.assertEqual(len(months), 12)
            self.assertEqual(to_paise(months[0]["opening"]), int(self.accounts[acc]["opening_balance_minor"]))
            for prev, cur in zip(months, months[1:]):
                self.assertEqual(prev["closing"], cur["opening"], f"{acc} {cur['period']}")

    def test_balances_respect_limits(self):
        cc_limit = int(self.accounts["CC01"]["limit_minor"])
        self.assertEqual(set(self.accounts), {"CA01", "CC01", "CL01", "EF01"})
        for lid, r in self.lines.items():
            bal = to_paise(r["balance"])
            if r["account_id"] in ("CA01", "CL01", "EF01"):
                self.assertGreaterEqual(bal, 0, f"{lid} negative")
            else:
                self.assertGreaterEqual(bal, -cc_limit, f"{lid} exceeds CC limit")

    def test_dates_inside_financial_year(self):
        for lid, r in self.lines.items():
            self.assertTrue("2025-04-01" <= r["txn_date"] <= "2026-03-31", lid)
        for b in self.books:
            self.assertTrue("2025-04-01" <= b["entry_date"] <= "2026-03-31", b["entry_id"])

    # ---- reconciliation answer key -------------------------------------------
    def test_brs_closes_for_every_account(self):
        for acc, rec in self.key.items():
            book_bal = int(self.accounts[acc]["opening_balance_minor"]) + sum(
                to_paise(b["amount"]) for b in self.books if b["account_id"] == acc)
            self.assertEqual(book_bal, to_paise(rec["balance_per_books"]), acc)
            bank_close = to_paise([s for s in self.index if s["account_id"] == acc][-1]["closing"])
            self.assertEqual(bank_close, to_paise(rec["balance_per_bank"]), acc)
            adj = sum(to_paise(i["adjust_to_reach_bank"]) for i in rec["items"])
            self.assertEqual(book_bal + adj, bank_close, f"BRS does not close for {acc}")

    def test_seeded_difference_counts(self):
        expected = {
            "CA01": {"cheque_issued_not_presented": 3, "amount_mismatch": 1, "duplicate_debit": 1,
                     "bank_charges_not_booked": 1, "gst_on_bank_charges_not_booked": 1},
            "CC01": {"interest_debited_not_booked": 1},
            "CL01": {"deposit_not_yet_credited": 1, "unidentified_receipt": 1, "cheque_returned": 1,
                     "interest_credited_not_booked": 1, "bank_charges_not_booked": 2,
                     "gst_on_bank_charges_not_booked": 2},
            "EF01": {"bank_charges_not_booked": 1},
        }
        for acc, exp in expected.items():
            self.assertEqual(dict(Counter(i["category"] for i in self.key[acc]["items"])), exp, acc)

    def test_answer_key_references_exist(self):
        entry_ids = {b["entry_id"] for b in self.books}
        for rec in self.key.values():
            for i in rec["items"]:
                if "line_id" in i:
                    self.assertIn(i["line_id"], self.lines)
                if "entry_id" in i:
                    self.assertIn(i["entry_id"], entry_ids)
        for r in self.risks:
            for ref in [r] + r.get("lines", []):
                if ref.get("line_id"):
                    self.assertIn(ref["line_id"], self.lines, r["flag_id"])
        self.assertEqual(len(self.risks), 8)

    def test_matches_are_one_to_one(self):
        m = rows(DATA / "answer_key" / "matches.csv")
        self.assertEqual(len({r["entry_id"] for r in m}), len(m))
        self.assertEqual(len({r["line_id"] for r in m}), len(m))
        mismatched = [r for r in m if r["bank_amount"] != r["book_amount"]]
        self.assertEqual(len(mismatched), 1)
        # every bank line is either matched or listed as a bank-only reconciling item
        bank_only = {i["line_id"] for rec in self.key.values() for i in rec["items"] if i["side"] == "bank_only"}
        self.assertEqual({r["line_id"] for r in m} | bank_only, set(self.lines))

    # ---- masters and SAMPLE marking ----------------------------------------------
    def test_masters_valid(self):
        ids = [p["party_id"] for p in self.parties]
        self.assertEqual(len(ids), len(set(ids)))
        for p in self.parties:
            if p["ifsc"]:
                self.assertRegex(p["ifsc"], IFSC_RE)
                self.assertTrue(p["ifsc"].startswith("ZZ"), "fictitious IFSC codes start with ZZ")
        for a in self.accounts.values():
            self.assertRegex(a["ifsc"], IFSC_RE)
        known = set(ids)
        for b in self.books:
            if b["party_id"]:
                self.assertIn(b["party_id"], known, b["entry_id"])
        unknown = [b for b in self.books if b["mode"] == "IMPS"]
        self.assertEqual(len(unknown), 1)
        self.assertIn("not in vendor master", unknown[0]["counter_ledger"])

    def test_sample_marking(self):
        company = json.loads((DATA / "company.json").read_text(encoding="utf-8"))
        self.assertIn("SAMPLE", company["name"])
        for a in self.accounts.values():
            self.assertIn("SAMPLE", a["bank_name"])
        for p in self.parties:
            if p["party_type"] in ("vendor", "customer"):
                self.assertIn("(SAMPLE)", p["name"], p["party_id"])

    def test_open_items(self):
        terms = {p["party_id"]: int(p["terms_days"]) for p in self.parties}
        ap = rows(DATA / "ap_open.csv")
        overdue_msme = [r for r in ap if r["msme"] == "1"
                        and date.fromisoformat(r["bill_date"]) + timedelta(days=45) < FY_END]
        self.assertEqual({r["party_id"] for r in overdue_msme}, {"V002", "V005"})
        for r in rows(DATA / "ar_open.csv"):
            if not r["note"]:
                due = date.fromisoformat(r["invoice_date"]) + timedelta(days=terms[r["party_id"]])
                self.assertEqual(due.isoformat(), r["due_date"], r["invoice_no"])
        commits = rows(DATA / "commitments.csv")
        self.assertTrue(all("2026-04-01" <= c["due_date"] <= "2026-06-30" for c in commits))

    # ---- reproducibility ----------------------------------------------------------
    def test_generator_is_deterministic(self):
        saved = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["files"]
        with tempfile.TemporaryDirectory() as tmp:
            fresh = generate(Path(tmp) / "p1")["files"]
        self.assertEqual(saved, fresh, "data files differ from a fresh run with the same seed")

    # ---- database and ERP adapter ----------------------------------------------
    def test_load_into_sqlite_and_mock_erp(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = SQLiteDatabase(Path(tmp) / "t.db")
            try:
                counts = load_phase1(db, DATA, actor="test")
                self.assertEqual(counts["bank_lines"], len(self.lines))
                self.assertEqual(counts["book_entries"], len(self.books))
                erp = MockERP(db)
                for acc, rec in self.key.items():
                    self.assertEqual(erp.book_balance(acc, FY_END), to_paise(rec["balance_per_books"]), acc)
                    total = db.sql("SELECT SUM(amount_minor) s FROM bank_lines WHERE account_id = ?", (acc,))[0]["s"]
                    self.assertEqual(int(self.accounts[acc]["opening_balance_minor"]) + total,
                                     to_paise(rec["balance_per_bank"]), acc)
                tables = {r["name"] for r in db.sql("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertFalse(any("key" in t or "match" in t for t in tables), "answer key must not be loaded")
                self.assertEqual(len(db.query("audit_log")), 1)
                self.assertEqual(len(erp.get_commitments(date(2026, 4, 1), date(2026, 4, 30))), 9)
                with self.assertRaises(ValueError):
                    db.query("bank_lines; DROP TABLE company")
                # reloading is idempotent
                load_phase1(db, DATA, actor="test")
                self.assertEqual(len(db.query("bank_lines")), len(self.lines))
            finally:
                db.close()

    # ---- enhancements: holidays, GST on charges, EEFC -----------------------------
    def test_branch_items_only_on_bank_working_days(self):
        """Cheque clearing and statutory/payroll debits happen only on bank working days.
        (NEFT/RTGS/IMPS run 24x7, so own-account transfers may fall on holidays.)"""
        branch = ("CHQ PAID", "CLG CR", "CHQ RTN", "TAX PMT", "GST PMT", "EPFO", "ESIC", "BULK NEFT", "ACH DR")
        for lid, r in self.lines.items():
            if r["description"].startswith(branch):
                self.assertTrue(is_working(date.fromisoformat(r["txn_date"])), f"{lid} {r['description']}")
        self.assertFalse(is_working(date(2026, 3, 14)), "2nd Saturday is a bank holiday")
        self.assertTrue(is_working(date(2026, 3, 7)), "1st Saturday is a working day")
        self.assertFalse(is_working(date(2026, 1, 26)))

    def test_gst_on_bank_charges(self):
        ordered = list(self.lines.items())
        gst_lines = [(i, lid, r) for i, (lid, r) in enumerate(ordered) if r["description"].startswith("GST @18% ON")]
        self.assertGreaterEqual(len(gst_lines), 24)
        for i, lid, r in gst_lines:
            _, base = ordered[i - 1]
            self.assertEqual(base["account_id"], r["account_id"])
            self.assertEqual(to_paise(r["debit"]), to_paise(base["debit"]) * 18 // 100, lid)
        itc_books = [b for b in self.books if b["counter_ledger"].startswith("Input GST on bank charges")]
        self.assertEqual(len(itc_books), 22)  # 11 months x 2 accounts; March not yet booked

    def test_eefc_conversions_pair_up(self):
        conv_dr = [r for r in self.lines.values() if r["description"].startswith("FX CONV DR")]
        conv_cr = [r for r in self.lines.values() if r["description"].startswith("FX CONV CR")]
        self.assertEqual(len(conv_dr), 12)
        self.assertEqual(len(conv_dr), len(conv_cr))
        for dr, cr in zip(conv_dr, conv_cr):
            self.assertEqual(dr["account_id"], "EF01")
            self.assertEqual(cr["account_id"], "CL01")
            self.assertEqual(dr["txn_date"], cr["txn_date"])
            rate = float(dr["description"].split("@")[1].split("-")[0])
            self.assertAlmostEqual(to_paise(dr["debit"]) * rate, to_paise(cr["credit"]), delta=1)
        remits = [r for r in self.lines.values() if r["description"].startswith("INWARD REMIT-USD")]
        self.assertTrue(remits and all(r["account_id"] == "EF01" for r in remits))
        usd_ar = [r for r in rows(DATA / "ar_open.csv") if r["currency"] == "USD"]
        self.assertTrue(all(to_paise(r["amount"]) <= 30000 * 100 for r in usd_ar), "USD invoices are in USD")

    def test_money_helpers(self):
        self.assertEqual(to_paise("1,23,456.78"), 12345678)
        self.assertEqual(fmt_inr(12345678900), "Rs 12,34,56,789.00")
        self.assertEqual(fmt_inr(-99950), "-Rs 999.50")


if __name__ == "__main__":
    unittest.main()
