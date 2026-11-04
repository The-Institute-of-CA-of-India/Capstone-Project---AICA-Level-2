"""Data structures shared by parsers, allocation, storage and reports."""
from __future__ import annotations

from dataclasses import dataclass, field

CHARGE_KEYS = ["brokerage", "exchange", "clearing", "sebi", "ipf",
               "cgst", "sgst", "igst", "stt", "stamp", "other"]

CHARGE_LABELS = {
    "brokerage": "Brokerage",
    "exchange": "Exchange Txn Charges",
    "clearing": "Clearing Charges",
    "sebi": "SEBI Turnover Fees",
    "ipf": "IPF",
    "cgst": "CGST",
    "sgst": "SGST",
    "igst": "IGST",
    "stt": "STT",
    "stamp": "Stamp Duty",
    "other": "Other Charges",
}


@dataclass
class Trade:
    """One printed execution line (a fill)."""
    order_no: str
    order_time: str
    trade_no: str
    trade_time: str
    exchange: str
    symbol: str
    isin: str
    side: str            # BUY / SELL
    qty: float
    rate: float          # gross rate per unit
    brokerage_per_unit: float = 0.0

    @property
    def gross(self) -> float:
        return self.qty * self.rate


@dataclass
class ScripSide:
    """All trades of one ISIN on one side within a contract note."""
    isin: str
    symbol: str
    side: str
    qty: float
    gross: float                     # value before brokerage
    brokerage_direct: float = 0.0    # brokerage visible in rates
    exchanges: str = ""
    name_on_note: str = ""
    stt_hint: float | None = None    # per-ISIN STT if the note prints it
    alloc: dict = field(default_factory=dict)   # filled by allocate.py
    basis: dict = field(default_factory=dict)

    @property
    def avg_rate(self) -> float:
        return self.gross / self.qty if self.qty else 0.0


@dataclass
class ContractNote:
    broker: str
    format_name: str
    cn_no: str
    trade_date: str
    settlement_date: str = ""
    settlement_no: str = ""
    client_name: str = ""
    pan: str = ""
    ucc: str = ""
    source_file: str = ""
    source_hash: str = ""
    charges: dict = field(default_factory=lambda: {k: 0.0 for k in CHARGE_KEYS})
    net_amount: float = 0.0          # + payable by client (Dr), - receivable (Cr)
    combined_charges: bool = False   # broker prints exch+SEBI+IPF as one figure
    trades: list = field(default_factory=list)
    scrips: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    recon_diff: float | None = None

    @property
    def direction(self) -> str:
        return "Payable by client (Dr)" if self.net_amount >= 0 else "Receivable by client (Cr)"

    def key(self) -> tuple:
        return (self.broker.upper(), (self.ucc or self.pan).upper(), self.cn_no.upper())
