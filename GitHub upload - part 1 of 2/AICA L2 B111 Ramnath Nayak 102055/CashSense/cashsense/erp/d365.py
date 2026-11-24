"""Microsoft Dynamics 365 adapter - placeholder.

Planned for Phase 5 as an optional connector: OAuth client-credentials via a Microsoft
Entra ID app registration, then OData calls to the Dynamics 365 Finance / Business
Central API. Entity names differ by edition and tenant, so this is only built and
tested if a Dynamics 365 sandbox is available. Until then CashSense uses the mock ERP.
"""
from __future__ import annotations

from .base import ERPAdapter


class Dynamics365Adapter(ERPAdapter):
    name = "d365"

    def __init__(self):
        raise NotImplementedError(
            "The Dynamics 365 connector is not configured. Set CASHSENSE_ERP=mock, "
            "or provide a Dynamics 365 sandbox in Phase 5.")

    def list_bank_accounts(self): ...
    def get_bank_ledger(self, account_id, date_from, date_to): ...
    def get_vendors(self): ...
    def get_customers(self): ...
    def get_open_receivables(self): ...
    def get_open_payables(self): ...
    def get_commitments(self, date_from, date_to): ...
