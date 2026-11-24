"""ERP adapter interface. Agents only call these methods, so the source can be the mock ERP
(local database), Microsoft Dynamics 365, or another ERP added later."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from .. import config


class ERPAdapter(ABC):
    name = "base"

    @abstractmethod
    def list_bank_accounts(self) -> list[dict]: ...

    @abstractmethod
    def get_bank_ledger(self, account_id: str, date_from: date, date_to: date) -> list[dict]: ...

    @abstractmethod
    def get_vendors(self) -> list[dict]: ...

    @abstractmethod
    def get_customers(self) -> list[dict]: ...

    @abstractmethod
    def get_open_receivables(self) -> list[dict]: ...

    @abstractmethod
    def get_open_payables(self) -> list[dict]: ...

    @abstractmethod
    def get_commitments(self, date_from: date, date_to: date) -> list[dict]: ...

    def book_balance(self, account_id: str, as_of: date) -> int:
        """Balance per books in the account's own currency (minor units)."""
        acc = next(a for a in self.list_bank_accounts() if a["account_id"] == account_id)
        start = date.fromisoformat(acc["opening_date"])
        return acc["opening_balance_minor"] + sum(e["amount_minor"] for e in self.get_bank_ledger(account_id, start, as_of))


def get_erp(db=None) -> ERPAdapter:
    backend = config.erp_backend()
    if backend == "d365":
        from .d365 import Dynamics365Adapter

        return Dynamics365Adapter()
    from ..db import get_database
    from .mock_erp import MockERP

    return MockERP(db or get_database())
