"""Mock ERP: serves the SAMPLE company's books from the CashSense database."""
from __future__ import annotations

from datetime import date

from ..db.adapter import Database
from .base import ERPAdapter


class MockERP(ERPAdapter):
    name = "mock"

    def __init__(self, db: Database):
        self.db = db

    def list_bank_accounts(self) -> list[dict]:
        return self.db.query("bank_accounts", order="account_id")

    def get_bank_ledger(self, account_id: str, date_from: date, date_to: date) -> list[dict]:
        rows = self.db.query("book_entries", {"account_id": account_id}, order="entry_id")
        lo, hi = date_from.isoformat(), date_to.isoformat()
        return [r for r in rows if lo <= r["entry_date"] <= hi]

    def get_vendors(self) -> list[dict]:
        return [p for p in self.db.query("counterparties", order="party_id") if p["party_type"] != "customer"]

    def get_customers(self) -> list[dict]:
        return self.db.query("counterparties", {"party_type": "customer"}, order="party_id")

    def get_open_receivables(self) -> list[dict]:
        return self.db.query("ar_open", order="invoice_no")

    def get_open_payables(self) -> list[dict]:
        return self.db.query("ap_open", order="bill_no")

    def get_commitments(self, date_from: date, date_to: date) -> list[dict]:
        lo, hi = date_from.isoformat(), date_to.isoformat()
        return [c for c in self.db.query("commitments", order="due_date") if lo <= c["due_date"] <= hi]
