"""Phase 1 data generator for CashSense.

Creates a fictitious manufacturer (SAMPLE), its masters, its bank ledger (books) and
monthly bank statements for four accounts for FY 2025-26 (three INR accounts and one
USD EEFC account), plus open receivables, open payables and known commitments as at
31-Mar-2026.

Deliberate differences and risk items are seeded in March 2026 and written to an
answer key (data/phase1/answer_key) that the app never loads - it is only used by
tests to measure the agents in later phases.

Amounts are integer minor units of the account currency (paise for INR, cents for USD).
Everything is deterministic: the same seed always produces identical files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ..money import paise_to_str, rupees

SEED = 2026
FY_START = date(2025, 4, 1)
FY_END = date(2026, 3, 31)
FY_LABEL = "25-26"
LAKH = rupees(100_000)
CRORE = rupees(10_000_000)
GST_RATE_PCT = 18

RECEIPTS_BASE = 2.47 * CRORE     # monthly customer receipts (INR value) before seasonality
VENDOR_BASE = 1.56 * CRORE        # monthly supplier payments before seasonality
SEASONALITY = {4: 0.85, 5: 0.90, 6: 0.95, 7: 1.00, 8: 1.00, 9: 1.05,
               10: 1.10, 11: 1.00, 12: 1.05, 1: 1.10, 2: 1.10, 3: 1.25}

# Illustrative Maharashtra bank holidays for the SAMPLE data - not an official RBI calendar.
BANK_HOLIDAYS = {
    date(2025, 4, 14): "Dr Ambedkar Jayanti", date(2025, 4, 18): "Good Friday", date(2025, 5, 1): "Maharashtra Day",
    date(2025, 8, 15): "Independence Day", date(2025, 8, 27): "Ganesh Chaturthi", date(2025, 10, 2): "Gandhi Jayanti",
    date(2025, 10, 21): "Diwali (Lakshmi Puja)", date(2025, 10, 22): "Diwali (Balipratipada)",
    date(2025, 11, 5): "Guru Nanak Jayanti", date(2025, 12, 25): "Christmas", date(2026, 1, 26): "Republic Day",
    date(2026, 2, 19): "Chhatrapati Shivaji Maharaj Jayanti", date(2026, 3, 19): "Gudi Padwa",
}

COMPANY = {
    "company_id": "SPC",
    "name": "Sample Precision Components Pvt Ltd (SAMPLE)",
    "city": "Pune",
    "state": "Maharashtra",
    "industry": "Auto components manufacturing",
    "fy_start": FY_START.isoformat(),
    "fy_end": FY_END.isoformat(),
    "currency": "INR",
    "approval_threshold_paise": 5 * LAKH,
    "note": "Fictitious company created for the AICA Level 2 capstone. Not a real entity.",
}

ACCOUNTS = [
    {"account_id": "CA01", "name": "Operating Current Account", "account_type": "current", "currency": "INR",
     "bank_name": "Sample Bank of India (SAMPLE)", "ifsc": "ZZSB0PUN001", "account_no": "50200011223344",
     "opening_balance_minor": 45 * LAKH, "limit_minor": 0, "interest_rate": 0.0, "min_balance_minor": 10 * LAKH,
     "statement_format": "csv"},
    {"account_id": "CC01", "name": "Cash Credit Account", "account_type": "cash_credit", "currency": "INR",
     "bank_name": "Sample Heritage Bank (SAMPLE)", "ifsc": "ZZHB0PUN014", "account_no": "33010099887766",
     "opening_balance_minor": -120 * LAKH, "limit_minor": 200 * LAKH, "interest_rate": 10.5, "min_balance_minor": 0,
     "statement_format": "pdf"},
    {"account_id": "CL01", "name": "Collections Account (FD linked)", "account_type": "collections", "currency": "INR",
     "bank_name": "Sample Kaveri Bank (SAMPLE)", "ifsc": "ZZKB0PUN007", "account_no": "71100055443322",
     "opening_balance_minor": 8 * LAKH, "limit_minor": 0, "interest_rate": 7.1, "min_balance_minor": 5 * LAKH,
     "statement_format": "photo"},
    {"account_id": "EF01", "name": "EEFC Account (USD)", "account_type": "eefc", "currency": "USD",
     "bank_name": "Sample Kaveri Bank (SAMPLE)", "ifsc": "ZZKB0PUN007", "account_no": "71100055449911",
     "opening_balance_minor": 1_250_000, "limit_minor": 0, "interest_rate": 0.0, "min_balance_minor": 0,
     "statement_format": "pdf"},
]
ACC = {a["account_id"]: a for a in ACCOUNTS}
FD_PRINCIPAL = 100 * LAKH
FD_NUMBER = "FD7110093"
CONTRA_KINDS = {"own_transfer_out", "own_transfer_in", "fx_conversion_out", "fx_conversion_in"}

VENDOR_SPECS = [  # name, category, weight, terms, msme
    ("Steelco Alloys", "raw_material", 18, 60, False),
    ("Deccan Castings", "raw_material", 14, 45, True),
    ("Sahyadri Forgings", "raw_material", 12, 45, True),
    ("Bharat Bearings Traders", "raw_material", 8, 30, False),
    ("Konkan Polymers", "raw_material", 7, 45, True),
    ("Precision Tools Hub", "consumables", 5, 30, True),
    ("Lubrichem Industries", "consumables", 3, 30, False),
    ("Weldtech Gases", "consumables", 3, 30, True),
    ("Corrupack Industries", "packaging", 4, 30, True),
    ("Safewrap Packaging", "packaging", 3, 30, True),
    ("Expressway Logistics", "logistics", 6, 15, False),
    ("Western Freight Carriers", "logistics", 4, 15, True),
    ("Vigil Security Services", "services", 2, 30, False),
    ("Cleanpro Facility Services", "services", 2, 30, True),
    ("Accurate Calibration Labs", "services", 1, 30, True),
    ("Nexus IT Services", "services", 2, 30, False),
    ("Mechtron CNC Machines", "capex", 0, 30, False),
]
CUSTOMER_SPECS = [  # name, weight, terms, currency
    ("Apex Auto Assemblies", 16, 60, "INR"),
    ("Vardhan Motors", 12, 45, "INR"),
    ("Shivneri Tractors", 10, 60, "INR"),
    ("Indus Two Wheelers", 9, 45, "INR"),
    ("Godavari Engineering", 6, 30, "INR"),
    ("Sunrise Pumps", 5, 30, "INR"),
    ("Orbit Electricals", 4, 30, "INR"),
    ("Malwa Agro Equipment", 5, 45, "INR"),
    ("Coastal Marine Engines", 4, 60, "INR"),
    ("Highland Gensets", 5, 45, "INR"),
    ("Trident Compressors", 4, 30, "INR"),
    ("Narmada Rail Components", 4, 60, "INR"),
    ("Rhein Automotive GmbH", 8, 90, "USD"),
    ("Great Lakes Motor Parts Inc", 8, 90, "USD"),
]
OTHER_SPECS = [  # id, type, name, category, has bank details
    ("GOV-CBDT", "government", "Income Tax Department - CBDT (TDS / Advance Tax)", "statutory", False),
    ("GOV-GST", "government", "GSTN - Electronic Cash Ledger", "statutory", False),
    ("GOV-EPFO", "government", "EPFO - Provident Fund", "statutory", False),
    ("GOV-ESIC", "government", "ESIC - Employees State Insurance", "statutory", False),
    ("EMP-PAYROLL", "employees", "Employees - Salary Batch", "payroll", False),
    ("UTIL-POWER", "vendor", "Sample State Power Distribution Co (SAMPLE)", "utilities", True),
    ("RENT-ESTATES", "vendor", "Sample Estates LLP (SAMPLE)", "rent", True),
    ("BANK-TL", "lender", "Sample Heritage Bank - Term Loan (SAMPLE)", "loan", False),
    ("INS-GENERAL", "vendor", "Sample General Insurance Co (SAMPLE)", "insurance", True),
]
BANK_CODES = ["ZZAB", "ZZCB", "ZZDB", "ZZEB", "ZZFB", "ZZGB"]
CITIES = ["PUN", "MUM", "NSK", "AUR", "KOL", "CHN", "BLR", "AMD"]
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


# ----------------------------------------------------------------------------- helpers
def month_starts():
    d = FY_START
    while d <= FY_END:
        yield d
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def month_end(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def is_working(d: date) -> bool:
    """Bank working day: not a Sunday, not the 2nd/4th Saturday, not a listed holiday."""
    if d in BANK_HOLIDAYS or d.weekday() == 6:
        return False
    if d.weekday() == 5:
        return (d.day - 1) // 7 + 1 not in (2, 4)
    return True


def next_working(d: date) -> date:
    while not is_working(d):
        d += timedelta(days=1)
    return d


def prev_working(d: date) -> date:
    while not is_working(d):
        d -= timedelta(days=1)
    return d


def add_working_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if is_working(d):
            n -= 1
    return d


def working_days(ms: date) -> list[date]:
    me = month_end(ms)
    return [ms + timedelta(days=i) for i in range((me - ms).days + 1) if is_working(ms + timedelta(days=i))]


def last_working(ms: date) -> date:
    return prev_working(month_end(ms))


def short_name(name: str) -> str:
    name = name.replace("(SAMPLE)", "")
    name = re.sub(r"[^A-Za-z0-9 ]", " ", name).upper()
    return re.sub(r"\s+", " ", name).strip()


def short20(name: str) -> str:
    return short_name(name)[:20].strip()


def round_rupee(p: float) -> int:
    return int(round(p / 100.0)) * 100


@dataclass
class Party:
    party_id: str
    party_type: str
    name: str
    category: str
    ifsc: str = ""
    account_no: str = ""
    terms_days: int = 0
    msme: bool = False
    currency: str = "INR"
    weight: float = 0.0


@dataclass
class Event:
    seq: int
    account_id: str
    kind: str
    amount: int                      # signed minor units as it hits the bank (+ in, - out)
    party_id: str = ""
    book_date: date | None = None
    bank_date: date | None = None
    mode: str = ""
    bank_desc: str = ""
    ref_no: str = ""
    counter_ledger: str = ""
    narration: str = ""
    instrument_no: str = ""
    book_amount: int | None = None   # set only when the books carry a different amount
    inr_amount: int | None = None    # INR value in paise for foreign-currency accounts
    order: int = 1                   # intra-day ordering on the statement
    tag: str = ""
    vgroup: int | None = None        # events sharing one voucher (transfer legs, charge + GST)

    @property
    def event_id(self) -> str:
        return f"EV{self.seq:05d}"

    @property
    def in_books(self) -> bool:
        return self.book_date is not None and self.book_date <= FY_END

    @property
    def in_bank(self) -> bool:
        return self.bank_date is not None and self.bank_date <= FY_END

    @property
    def booked_amount(self) -> int:
        return self.amount if self.book_amount is None else self.book_amount

    @property
    def booked_inr(self) -> int:
        return self.booked_amount if self.inr_amount is None else self.inr_amount


# ----------------------------------------------------------------------------- generator
class Phase1Generator:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self.seed = seed
        self.events: list[Event] = []
        self._seq = 0
        self._cheque = 400431
        self.usd_rate = 83.40
        self.eefc_bal = ACC["EF01"]["opening_balance_minor"]
        self.vendors, self.customers, self.others = self._build_parties()
        self.party = {p.party_id: p for p in self.vendors + self.customers + self.others}
        self.ar_open: list[dict] = []
        self.ap_open: list[dict] = []
        self.commitments: list[dict] = []

    # -- masters --------------------------------------------------------------
    def _ifsc(self) -> str:
        return f"{self.rng.choice(BANK_CODES)}0{self.rng.choice(CITIES)}{self.rng.randint(1, 999):03d}"

    def _acct(self) -> str:
        return str(self.rng.randint(10**11, 10**12 - 1))

    def _build_parties(self):
        vendors = [Party(f"V{i:03d}", "vendor", f"{n} (SAMPLE)", cat, self._ifsc(), self._acct(), terms, msme, "INR", w)
                   for i, (n, cat, w, terms, msme) in enumerate(VENDOR_SPECS, 1)]
        customers = [Party(f"C{i:03d}", "customer", f"{n} (SAMPLE)", "customer", self._ifsc(), self._acct(), terms, False, cur, w)
                     for i, (n, w, terms, cur) in enumerate(CUSTOMER_SPECS, 1)]
        others = []
        for pid, ptype, name, cat, bank in OTHER_SPECS:
            others.append(Party(pid, ptype, name, cat, self._ifsc() if bank else "", self._acct() if bank else ""))
        return vendors, customers, others

    # -- primitives -----------------------------------------------------------
    def add(self, **kw) -> Event:
        self._seq += 1
        ev = Event(seq=self._seq, **kw)
        self.events.append(ev)
        return ev

    def utr(self, prefix: str, d: date) -> str:
        return f"{prefix}{d:%y%m%d}{self.rng.randint(10_000_000, 99_999_999)}"

    def next_cheque(self) -> str:
        self._cheque += 1
        return f"{self._cheque:06d}"

    def pick(self, parties: list[Party]) -> Party:
        pool = [p for p in parties if p.weight > 0]
        return self.rng.choices(pool, weights=[p.weight for p in pool])[0]

    def next_rate(self) -> float:
        self.usd_rate = min(87.5, max(82.5, self.usd_rate + self.rng.uniform(-0.25, 0.35)))
        return round(self.usd_rate, 4)

    # -- event builders ---------------------------------------------------------
    def vendor_payment(self, v: Party, amt: int, d: date, mode: str | None = None, *, bank_date: date | None = None,
                       book: bool = True, book_amount: int | None = None, tag: str = "",
                       bene_ifsc: str | None = None, bene_acct: str | None = None,
                       counter_ledger: str | None = None) -> Event:
        mode = mode or ("NEFT" if amt < 2 * LAKH else "RTGS")
        ifsc, acct = bene_ifsc or v.ifsc, bene_acct or v.account_no
        chq = ""
        if mode == "CHQ":
            chq = self.next_cheque()
            ref = chq
            desc = f"CHQ PAID-{chq}-{short20(v.name)}"
            bank_date = bank_date or add_working_days(d, self.rng.randint(2, 6))
        elif mode == "IMPS":
            ref = self.utr("I", d)
            desc = f"IMPS/P2A/{ref}/{short20(v.name)}"
        else:
            ref = self.utr(mode[0], d)
            desc = f"{mode} DR-{ifsc}-{short20(v.name)}-A/C XX{acct[-4:]}-{ref}"
        return self.add(account_id="CA01", kind="vendor_payment", amount=-amt, party_id=v.party_id,
                        book_date=d if book else None, bank_date=bank_date or d, mode=mode, bank_desc=desc,
                        ref_no=ref, instrument_no=chq,
                        counter_ledger=counter_ledger or f"Sundry Creditors: {v.name}",
                        narration=f"Payment to {v.name} by {mode}" + (f" cheque {chq}" if chq else ""),
                        book_amount=book_amount, tag=tag)

    def customer_receipt(self, c: Party, amt: int, d: date, mode: str | None = None, *,
                         bank_date: date | None = None, tag: str = "") -> Event:
        if c.currency == "USD":  # export receipts are credited in USD to the EEFC account
            rate = self.next_rate()
            cents = int(round(amt / rate))  # amt is the INR value in paise; paise / rate = cents
            ref = self.utr("S", d)
            return self.add(account_id="EF01", kind="export_receipt", amount=cents, party_id=c.party_id,
                            book_date=d, bank_date=d, mode="SWIFT", ref_no=ref,
                            bank_desc=f"INWARD REMIT-USD {cents / 100:,.2f}-{short20(c.name)}-{ref}",
                            counter_ledger=f"Sundry Debtors: {c.name}", inr_amount=int(round(cents * rate)),
                            narration=f"Export receipt USD {cents / 100:,.2f} @ {rate:.4f} from {c.name}", tag=tag)
        mode = mode or ("NEFT" if amt < 2 * LAKH else "RTGS")
        if mode == "CHQ":
            chq = f"{self.rng.randint(100000, 999999)}"
            return self.add(account_id="CL01", kind="customer_receipt", amount=amt, party_id=c.party_id,
                            book_date=d, bank_date=bank_date or add_working_days(d, 1), mode="CHQ",
                            ref_no=chq, instrument_no=chq, bank_desc=f"CLG CR-CHQ {chq}-{short20(c.name)}",
                            counter_ledger=f"Sundry Debtors: {c.name}",
                            narration=f"Cheque {chq} received from {c.name}", tag=tag)
        ref = self.utr(mode[0], d)
        return self.add(account_id="CL01", kind="customer_receipt", amount=amt, party_id=c.party_id,
                        book_date=d, bank_date=d, mode=mode, ref_no=ref,
                        bank_desc=f"{mode} CR-{c.ifsc}-{short20(c.name)}-{ref}",
                        counter_ledger=f"Sundry Debtors: {c.name}",
                        narration=f"Receipt from {c.name} by {mode}", tag=tag)

    def fixed(self, account: str, kind: str, party_id: str, amt: int, d: date, mode: str, desc: str,
              ledger: str, narration: str, *, book: bool = True, order: int = 1, tag: str = "") -> Event:
        return self.add(account_id=account, kind=kind, amount=amt, party_id=party_id,
                        book_date=d if book else None, bank_date=d, mode=mode, bank_desc=desc,
                        ref_no=desc.split("-")[-1], counter_ledger=ledger, narration=narration,
                        order=order, tag=tag)

    def bank_charge(self, account: str, base: int, d: date, desc: str, narration: str, *, book: bool = True,
                    order: int = 3, tag: str = "") -> None:
        """A bank charge and the 18% GST on it, shown as two lines and booked as one voucher."""
        gst = base * GST_RATE_PCT // 100
        group = self._seq + 1
        ref = desc.split("-")[-1]
        self.add(account_id=account, kind="bank_charges", amount=-base, book_date=d if book else None, bank_date=d,
                 mode="CHG", bank_desc=desc, ref_no=ref, counter_ledger="Bank Charges", narration=narration,
                 order=order, tag=tag, vgroup=group)
        self.add(account_id=account, kind="gst_on_charges", amount=-gst, book_date=d if book else None, bank_date=d,
                 mode="CHG", bank_desc=f"GST @{GST_RATE_PCT}% ON {desc.split('-')[0]}-G{ref}", ref_no=f"G{ref}",
                 counter_ledger="Input GST on bank charges (ITC)", narration=f"GST @18% on {narration.lower()}",
                 order=order, tag=f"{tag}-GST" if tag else "", vgroup=group)

    def transfer(self, src: str, dst: str, amt: int, d: date, order: int, purpose: str) -> None:
        ref = self.utr("N", d)
        a = self.add(account_id=src, kind="own_transfer_out", amount=-amt, book_date=d, bank_date=d, mode="NEFT",
                     ref_no=ref, bank_desc=f"NEFT DR-{ACC[dst]['ifsc']}-SAMPLE PRECISION COMP-OWN AC TRF-{ref}",
                     counter_ledger=f"Bank: {dst} {ACC[dst]['name']}",
                     narration=f"Own account transfer to {dst} ({purpose})", order=order)
        b = self.add(account_id=dst, kind="own_transfer_in", amount=amt, book_date=d, bank_date=d, mode="NEFT",
                     ref_no=ref, bank_desc=f"NEFT CR-{ACC[src]['ifsc']}-SAMPLE PRECISION COMP-OWN AC TRF-{ref}",
                     counter_ledger=f"Bank: {src} {ACC[src]['name']}",
                     narration=f"Own account transfer from {src} ({purpose})", order=order)
        a.vgroup = b.vgroup = a.seq

    def fx_conversion(self, cents: int, d: date) -> None:
        """Convert USD in the EEFC account to INR in the collections account at the bank's buying rate."""
        rate = round(self.next_rate() - 0.15, 4)
        inr = int(round(cents * rate))
        ref, usd = self.utr("F", d), f"{cents / 100:,.2f}"
        a = self.add(account_id="EF01", kind="fx_conversion_out", amount=-cents, book_date=d, bank_date=d, mode="FX",
                     ref_no=ref, inr_amount=-inr,
                     bank_desc=f"FX CONV DR-USD {usd} @{rate:.4f}-TO A/C XX{ACC['CL01']['account_no'][-4:]}-{ref}",
                     counter_ledger="Bank: CL01 Collections Account (FD linked)",
                     narration=f"Converted USD {usd} @ {rate:.4f} to INR", order=2)
        b = self.add(account_id="CL01", kind="fx_conversion_in", amount=inr, book_date=d, bank_date=d, mode="FX",
                     ref_no=ref, bank_desc=f"FX CONV CR-USD {usd} @{rate:.4f}-FR EEFC A/C "
                                           f"XX{ACC['EF01']['account_no'][-4:]}-{ref}",
                     counter_ledger="Bank: EF01 EEFC Account (USD)",
                     narration=f"INR proceeds of USD {usd} @ {rate:.4f}", order=2)
        a.vgroup = b.vgroup = a.seq

    # -- monthly activity -------------------------------------------------------
    def gen_month(self, ms: date) -> None:
        rng, f, wd = self.rng, SEASONALITY[ms.month], working_days(ms)
        is_last_month = ms.month == FY_END.month and ms.year == FY_END.year
        P = self.party

        # customer receipts: INR to collections account, USD to EEFC
        n = rng.randint(20, 26)
        ws = [rng.uniform(0.4, 1.6) for _ in range(n)]
        for w in ws:
            c = self.pick(self.customers)
            amt = round_rupee(RECEIPTS_BASE * f * w / sum(ws))
            d = rng.choice(wd)
            if c.currency == "INR" and amt < 3 * LAKH and d.day <= 24 and rng.random() < 0.12:
                self.customer_receipt(c, amt, d, "CHQ")
            else:
                self.customer_receipt(c, amt, d)

        # convert 80% of available USD to INR around the 26th (in multiples of USD 100)
        conv_d = prev_working(ms.replace(day=26))
        usd_in = [e for e in self.events if e.account_id == "EF01" and e.kind == "export_receipt"
                  and ms <= e.bank_date <= month_end(ms)]
        avail = self.eefc_bal + sum(e.amount for e in usd_in if e.bank_date < conv_d)
        conv = (avail * 8 // 10) // 10_000 * 10_000
        if conv > 0:
            self.fx_conversion(conv, conv_d)
        self.eefc_bal = avail - conv + sum(e.amount for e in usd_in if e.bank_date >= conv_d)

        # supplier payments from the current account
        n = rng.randint(16, 22)
        ws = [rng.uniform(0.4, 1.6) for _ in range(n)]
        for w in ws:
            v = self.pick(self.vendors)
            amt = round_rupee(VENDOR_BASE * f * w / sum(ws))
            d = rng.choice(wd)
            if amt < 3 * LAKH and rng.random() < 0.15:
                bd = add_working_days(d, rng.randint(2, 6))
                if bd > FY_END:  # keep unplanned cheques inside the year; seeded ones are added separately
                    d = rng.choice([x for x in wd if x.day <= 18])
                    bd = add_working_days(d, rng.randint(2, 6))
                self.vendor_payment(v, amt, d, "CHQ", bank_date=bd)
            else:
                self.vendor_payment(v, amt, d)

        mon = f"{ms:%b%y}".upper()
        day = lambda n_: next_working(ms.replace(day=n_))  # noqa: E731
        self.vendor_payment(P["RENT-ESTATES"], rupees(275000), day(5), "NEFT", counter_ledger="Rent - Factory")
        self.fixed("CA01", "loan_emi", "BANK-TL", -rupees(618450), day(5), "ACH",
                   f"ACH DR-SAMPLE HERITAGE BANK TL EMI-UMRN{ms:%y%m}0457", "Term Loan - Sample Heritage Bank",
                   f"Term loan EMI {mon}")
        tds = rupees(rng.randint(220000, 310000))
        self.fixed("CA01", "tds_payment", "GOV-CBDT", -tds, day(7), "NETBANKING",
                   f"TAX PMT-CBDT-ITNS281-CIN{ms:%y%m}07{rng.randint(1000, 9999)}", "TDS Payable",
                   f"TDS deposit for previous month ({mon})")
        self.vendor_payment(P["UTIL-POWER"], rupees(int(rng.randint(320000, 400000) * f)), day(10), "NEFT",
                            counter_ledger="Power and Fuel")
        self.fixed("CA01", "pf_payment", "GOV-EPFO", -rupees(rng.randint(450000, 475000)), day(15), "NETBANKING",
                   f"EPFO ECR-TRRN{ms:%y%m}15{rng.randint(10000, 99999)}", "PF Payable", f"PF contribution {mon}")
        self.fixed("CA01", "esi_payment", "GOV-ESIC", -rupees(rng.randint(82000, 90000)), day(15), "NETBANKING",
                   f"ESIC CHALLAN-{ms:%y%m}15{rng.randint(10000, 99999)}", "ESI Payable", f"ESI contribution {mon}")
        self.fixed("CA01", "gst_payment", "GOV-GST", -rupees(int(rng.randint(800000, 1100000) * f)), day(20),
                   "NETBANKING", f"GST PMT-CPIN{ms:%y%m}20{rng.randint(100000, 999999)}",
                   "GST Payable (Electronic Cash Ledger)", f"GST payment for previous month ({mon})")
        adv = {6: 18, 9: 36, 12: 36, 3: 30}.get(ms.month)
        if adv:
            self.fixed("CA01", "advance_tax", "GOV-CBDT", -adv * LAKH, day(15), "NETBANKING",
                       f"TAX PMT-CBDT-ITNS280-CIN{ms:%y%m}15{rng.randint(1000, 9999)}",
                       "Advance Income Tax FY 2025-26", f"Advance tax instalment {mon}")
        self.fixed("CA01", "salary", "EMP-PAYROLL", -rupees(rng.randint(3850000, 4150000)), last_working(ms),
                   "NEFT", f"BULK NEFT DR-SALARY {mon}-{rng.randint(118, 126)} TXNS-B{ms:%y%m}01",
                   "Salaries Payable", f"Salary {mon}")
        if ms.month == 10:
            self.fixed("CA01", "salary", "EMP-PAYROLL", -32 * LAKH, last_working(ms), "NEFT",
                       f"BULK NEFT DR-BONUS {mon}-121 TXNS-B{ms:%y%m}02", "Bonus Payable", "Diwali bonus")
        if ms == date(2025, 11, 1):
            self.vendor_payment(P["V017"], 25 * LAKH, date(2025, 11, 14), "RTGS",
                                counter_ledger="Capital Advances: Mechtron CNC Machines (SAMPLE)")

        # month-end bank charges + GST (not yet booked in March - seeded difference)
        me = month_end(ms)
        self.bank_charge("CA01", rupees(rng.choice([1000, 1500, 2000, 3000])), me,
                         f"SERVICE CHGS-{mon}-SC{ms:%y%m}", f"Bank charges {mon}", book=not is_last_month,
                         tag="MAR-CHG-CA01" if is_last_month else "")
        self.bank_charge("CL01", rupees(rng.choice([500, 1000])), me, f"ACCOUNT MAINT CHGS-{mon}-AM{ms:%y%m}",
                         f"Account maintenance charges {mon}", book=not is_last_month,
                         tag="MAR-CHG-CL01" if is_last_month else "")
        if ms.month in (6, 9, 12, 3):
            gross = FD_PRINCIPAL * 71 // 1000 // 4
            tds_fd = gross // 10
            self.fixed("CL01", "fd_interest", "", gross - tds_fd, me, "INT",
                       f"FD INT CR-{FD_NUMBER}-NET OF TDS {paise_to_str(tds_fd)}-FI{ms:%y%m}",
                       "Interest Income - FD (TDS receivable separately)", f"FD interest quarter ending {mon}",
                       book=not is_last_month, order=3, tag="MAR-FDINT" if is_last_month else "")

    # -- seeded March items -----------------------------------------------------
    def seed_march(self) -> None:
        P, m = self.party, (lambda d_: date(2026, 3, d_))
        for d_ in (9, 10, 12, 13, 16, 18, 20, 23, 24, 25, 27, 30, 31):
            assert is_working(m(d_)), f"seeded date {m(d_)} is not a bank working day"
        # cheques issued but not presented by 31-Mar
        self.vendor_payment(P["V006"], rupees(126480), m(27), "CHQ", bank_date=date(2026, 4, 2), tag="S01")
        self.vendor_payment(P["V009"], rupees(84350), m(30), "CHQ", bank_date=date(2026, 4, 3), tag="S02")
        self.vendor_payment(P["V013"], rupees(142000), m(30), "CHQ", bank_date=date(2026, 4, 6), tag="S03")
        # cheque deposited on 31-Mar, credited by bank in April
        self.customer_receipt(P["C005"], rupees(640000), m(31), "CHQ", bank_date=date(2026, 4, 2), tag="S04")
        # amount keyed wrongly in the books (transposition 1,84,500 -> 1,85,400)
        self.vendor_payment(P["V004"], rupees(184500), m(12), "NEFT", book_amount=-rupees(185400), tag="S05")
        # same supplier paid twice by the bank; books have it once
        self.vendor_payment(P["V011"], rupees(348720), m(16), "NEFT", tag="S06")
        self.vendor_payment(P["V011"], rupees(348720), m(18), "NEFT", book=False, tag="S06-DUP")
        # credit from an unknown party
        ref = self.utr("N", m(24))
        self.add(account_id="CL01", kind="unidentified_receipt", amount=rupees(236000), bank_date=m(24), mode="NEFT",
                 ref_no=ref, bank_desc=f"NEFT CR-ZZXB0PUN555-M S RAJ TRADERS-{ref}", tag="S07")
        # customer cheque returned unpaid, plus return charges and GST
        dep = self.customer_receipt(P["C007"], rupees(412300), m(9), "CHQ", bank_date=m(10), tag="S08-DEP")
        self.add(account_id="CL01", kind="cheque_returned", amount=-rupees(412300), party_id="C007", bank_date=m(13),
                 mode="CHQ", ref_no=dep.instrument_no, bank_desc=f"CHQ RTN-{dep.instrument_no}-FUNDS INSUFFICIENT",
                 tag="S08")
        self.bank_charge("CL01", rupees(500), m(13), f"CHQ RTN CHGS-RC{dep.instrument_no}",
                         "Cheque return charges", book=False, order=1, tag="S08-CHG")
        # foreign bank charges deducted from an export remittance (no GST), not booked
        rate = round(self.usd_rate, 4)
        self.add(account_id="EF01", kind="bank_charges", amount=-1500, bank_date=m(23), mode="CHG",
                 ref_no="RC260323", bank_desc="INWARD REMIT CHGS-USD 15.00-RC260323", inr_amount=-int(round(1500 * rate)),
                 tag="MAR-FXCHG")
        # risk items (booked and paid - they reconcile, but should be flagged)
        self.vendor_payment(P["V002"], rupees(785600), m(20), "RTGS", bene_ifsc="ZZQB0DEL404",
                            bene_acct="918273645501", tag="R01")
        self.vendor_payment(Party("", "vendor", "QuickFix Solutions", "unknown"), 5 * LAKH, m(22), "IMPS",
                            counter_ledger="Advance to Suppliers: QuickFix Solutions (not in vendor master)",
                            tag="R02")
        self.vendor_payment(P["V003"], rupees(495000), m(25), "NEFT", tag="R03-A")
        self.vendor_payment(P["V003"], rupees(490000), m(25), "NEFT", tag="R03-B")

    # -- daily cash simulation: funding, sweeps and CC interest ----------------
    def simulate(self) -> None:
        bal = {a["account_id"]: a["opening_balance_minor"] for a in ACCOUNTS}
        by_day: dict[date, list[Event]] = defaultdict(list)
        for e in self.events:
            if e.in_bank:
                by_day[e.bank_date].append(e)
        drawn_days = 0
        cc_limit = ACC["CC01"]["limit_minor"]
        d = FY_START
        while d <= FY_END:
            todays = sorted(by_day.get(d, []), key=lambda e: (e.order, e.seq))
            day_sum = defaultdict(int)
            for e in todays:
                day_sum[e.account_id] += e.amount
            # fund the current account from CC before payments go out
            ca_after = bal["CA01"] + day_sum["CA01"]
            if ca_after < ACC["CA01"]["min_balance_minor"]:
                need = math.ceil((25 * LAKH - ca_after) / (25 * LAKH)) * 25 * LAKH
                self.transfer("CC01", "CA01", need, d, 0, "funding")
                ca_after += need
                day_sum["CC01"] -= need
            # Friday sweeps: surplus to CC to cut interest
            if d.weekday() == 4:
                if ca_after > 60 * LAKH:
                    excess = ((ca_after - 30 * LAKH) // (10 * LAKH)) * 10 * LAKH
                    self.transfer("CA01", "CC01", excess, d, 2, "surplus sweep")
                    day_sum["CC01"] += excess
                    ca_after -= excess
                cl_after = bal["CL01"] + day_sum["CL01"]
                if cl_after > 6 * LAKH:
                    amt = ((cl_after - 5 * LAKH) // LAKH) * LAKH
                    self.transfer("CL01", "CC01", amt, d, 2, "collections sweep")
                    day_sum["CL01"] -= amt
                    day_sum["CC01"] += amt
            for acc in bal:
                bal[acc] += day_sum[acc]
            bal["CA01"] = ca_after
            if -bal["CC01"] > cc_limit:
                raise ValueError(f"CC limit breached on {d}: {bal['CC01']}")
            for acc in ("CA01", "CL01", "EF01"):
                if bal[acc] < 0:
                    raise ValueError(f"{acc} negative on {d}: {bal[acc]}")
            drawn_days += max(0, -bal["CC01"])
            if d == month_end(d):
                interest = round(drawn_days * 0.105 / 365)
                last = d.month == FY_END.month and d.year == FY_END.year
                self.add(account_id="CC01", kind="cc_interest", amount=-interest, book_date=None if last else d,
                         bank_date=d, mode="INT", ref_no=f"CI{d:%y%m}",
                         bank_desc=f"INT DEBITED CC A/C-{d:%b%y}-CI{d:%y%m}".upper(),
                         counter_ledger="Interest on Cash Credit", narration=f"CC interest {d:%b %Y}",
                         order=4, tag="MAR-CCINT" if last else "")
                bal["CC01"] -= interest
                drawn_days = 0
            d += timedelta(days=1)

    # -- open items and commitments (ERP data as at 31-Mar-2026) -------------
    def gen_open_items(self) -> None:
        rng, n = self.rng, 0
        for c in self.customers:
            for _ in range(2 if c.currency == "USD" else rng.randint(1, 3)):
                n += 1
                inv = date(2026, 1, 10) + timedelta(days=rng.randint(0, 80))
                amt = rng.randint(4000, 30000) * 100 if c.currency == "USD" else rupees(rng.randint(300000, 2800000))
                self.ar_open.append({"invoice_no": f"INV/{FY_LABEL}/{n:04d}", "party_id": c.party_id,
                                     "invoice_date": inv.isoformat(),
                                     "due_date": (inv + timedelta(days=c.terms_days)).isoformat(),
                                     "currency": c.currency, "amount_minor": amt, "note": ""})
        n += 1
        self.ar_open.append({"invoice_no": f"INV/{FY_LABEL}/{n:04d}", "party_id": "C007", "invoice_date": "2026-01-28",
                             "due_date": "2026-02-27", "currency": "INR", "amount_minor": rupees(412300),
                             "note": "Cheque returned unpaid on 13-Mar-2026 - follow up"})
        n = 0
        for v in self.vendors:
            if v.weight <= 0:
                continue
            for _ in range(rng.randint(1, 3)):
                n += 1
                start = date(2026, 2, 20) if v.msme else date(2026, 2, 1)
                bill = start + timedelta(days=rng.randint(0, (FY_END - start).days))
                self.ap_open.append({"bill_no": f"BILL/{FY_LABEL}/{n:04d}", "party_id": v.party_id,
                                     "bill_date": bill.isoformat(),
                                     "due_date": (bill + timedelta(days=v.terms_days)).isoformat(),
                                     "amount_paise": rupees(rng.randint(80000, 1500000)), "msme": v.msme, "note": ""})
        for pid, bill, amt in [("V002", date(2026, 1, 20), 648000), ("V005", date(2026, 2, 5), 392500)]:
            n += 1
            self.ap_open.append({"bill_no": f"BILL/{FY_LABEL}/{n:04d}", "party_id": pid, "bill_date": bill.isoformat(),
                                 "due_date": (bill + timedelta(days=45)).isoformat(), "amount_paise": rupees(amt),
                                 "msme": True, "note": "MSME bill unpaid beyond 45 days (sec 43B(h) risk)"})
        n += 1
        self.ap_open.append({"bill_no": f"BILL/{FY_LABEL}/{n:04d}", "party_id": "V017", "bill_date": "2025-11-10",
                             "due_date": "2026-05-15", "amount_paise": 60 * LAKH, "msme": False,
                             "note": "CNC machine balance payable on installation"})

        c = []

        def add_c(d_, acc, desc, cat, amt, certainty="fixed"):
            c.append({"commit_id": f"CM{len(c) + 1:03d}", "due_date": d_.isoformat(), "account_id": acc,
                      "description": desc, "category": cat, "amount_paise": amt, "certainty": certainty})

        for ms in [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]:
            day = lambda n_: next_working(ms.replace(day=n_))  # noqa: E731
            mon = f"{ms:%b %Y}"
            add_c(day(5), "CA01", f"Factory rent {mon}", "rent", -rupees(275000))
            add_c(day(5), "CA01", f"Term loan EMI {mon}", "loan", -rupees(618450))
            if ms.month == 4:
                add_c(next_working(date(2026, 4, 30)), "CA01", "TDS for March 2026 (due 30 April)", "statutory",
                      -rupees(340000), "estimated")
            else:
                add_c(day(7), "CA01", f"TDS deposit {mon}", "statutory", -rupees(280000), "estimated")
            add_c(day(10), "CA01", f"Electricity {mon}", "utilities", -rupees(380000), "estimated")
            add_c(day(15), "CA01", f"PF contribution {mon}", "statutory", -rupees(470000), "estimated")
            add_c(day(15), "CA01", f"ESI contribution {mon}", "statutory", -rupees(88000), "estimated")
            gst = {4: 1150000, 5: 900000, 6: 920000}[ms.month]
            add_c(day(20), "CA01", f"GST payment {mon}", "statutory", -rupees(gst), "estimated")
            add_c(last_working(ms), "CA01", f"Salary {mon}", "payroll", -41 * LAKH, "estimated")
        add_c(date(2026, 4, 20), "CA01", "Annual insurance premium", "insurance", -rupees(740000))
        add_c(date(2026, 5, 15), "CA01", "Mechtron CNC machine balance (capex)", "capex", -60 * LAKH)
        add_c(next_working(date(2026, 6, 15)), "CA01", "Advance tax 1st instalment FY 2026-27", "statutory",
              -rupees(1950000), "estimated")
        add_c(date(2026, 6, 30), "CL01", f"FD {FD_NUMBER} maturity (principal)", "fd_maturity", FD_PRINCIPAL)
        add_c(date(2026, 6, 30), "CL01", f"FD {FD_NUMBER} interest Q1 (net of TDS)", "fd_interest",
              FD_PRINCIPAL * 71 // 1000 // 4 * 9 // 10)
        self.commitments = c

    # -- run ------------------------------------------------------------------
    def run(self) -> None:
        for ms in month_starts():
            self.gen_month(ms)
        self.seed_march()
        self.simulate()
        self.gen_open_items()


# ----------------------------------------------------------------------------- output
def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line_id(account_id: str, period: str, idx: int) -> str:
    return f"{account_id}-{period.replace('-', '')}-{idx:04d}"


RECON_CATEGORY = {"bank_charges": "bank_charges_not_booked", "gst_on_charges": "gst_on_bank_charges_not_booked",
                  "cc_interest": "interest_debited_not_booked", "fd_interest": "interest_credited_not_booked",
                  "vendor_payment": "duplicate_debit", "unidentified_receipt": "unidentified_receipt",
                  "cheque_returned": "cheque_returned"}


def generate(out_dir: Path, seed: int = SEED) -> dict:
    """Generate all Phase 1 files into out_dir. Returns the manifest."""
    g = Phase1Generator(seed)
    g.run()
    out_dir.mkdir(parents=True, exist_ok=True)
    key_dir = out_dir / "answer_key"

    (out_dir / "company.json").write_text(json.dumps(COMPANY, indent=2), encoding="utf-8")
    acc_cols = list(ACCOUNTS[0].keys())
    _write_csv(out_dir / "bank_accounts.csv", acc_cols + ["opening_date"],
               [[a[k] for k in acc_cols] + [FY_START.isoformat()] for a in ACCOUNTS])
    _write_csv(out_dir / "counterparties.csv",
               ["party_id", "party_type", "name", "category", "ifsc", "account_no", "terms_days", "msme", "currency"],
               [[p.party_id, p.party_type, p.name, p.category, p.ifsc, p.account_no, p.terms_days,
                 int(p.msme), p.currency] for p in g.vendors + g.customers + g.others])
    _write_csv(out_dir / "bank_holidays.csv", ["date", "holiday"],
               [[d.isoformat(), n] for d, n in sorted(BANK_HOLIDAYS.items())])

    # bank statements: one CSV per account per month
    bank_events = sorted([e for e in g.events if e.in_bank], key=lambda e: (e.bank_date, e.order, e.seq))
    event_line: dict[int, str] = {}
    index_rows = []
    for a in ACCOUNTS:
        aid, bal = a["account_id"], a["opening_balance_minor"]
        for ms in month_starts():
            period = f"{ms:%Y-%m}"
            evs = [e for e in bank_events if e.account_id == aid and ms <= e.bank_date <= month_end(ms)]
            opening, rows, dr, cr = bal, [], 0, 0
            for i, e in enumerate(evs, 1):
                bal += e.amount
                dr += -e.amount if e.amount < 0 else 0
                cr += e.amount if e.amount > 0 else 0
                rows.append([e.bank_date.isoformat(), e.bank_date.isoformat(), e.bank_desc, e.ref_no,
                             paise_to_str(-e.amount) if e.amount < 0 else "",
                             paise_to_str(e.amount) if e.amount > 0 else "", paise_to_str(bal)])
                event_line[e.seq] = line_id(aid, period, i)
            fname = f"statements/{aid}_{period}.csv"
            _write_csv(out_dir / fname, ["txn_date", "value_date", "description", "ref_no", "debit", "credit",
                                         "balance"], rows)
            index_rows.append([aid, a["currency"], period, fname, paise_to_str(opening), paise_to_str(dr),
                               paise_to_str(cr), paise_to_str(bal), len(rows)])
    _write_csv(out_dir / "statement_index.csv",
               ["account_id", "currency", "period", "file", "opening", "debits", "credits", "closing", "line_count"],
               index_rows)

    # books: bank ledger entries (one row per bank account leg)
    book_events = sorted([e for e in g.events if e.in_books], key=lambda e: (e.book_date, e.order, e.seq))
    counters = defaultdict(int)
    group_voucher: dict[int, tuple[str, str]] = {}
    voucher_of: dict[int, str] = {}
    entry_of: dict[int, str] = {}
    book_rows = []
    for i, e in enumerate(book_events, 1):
        if e.vgroup is not None and e.vgroup in group_voucher:
            vno, vtype = group_voucher[e.vgroup]
        else:
            vtype = "CONTRA" if e.kind in CONTRA_KINDS else ("RECEIPT" if e.booked_amount > 0 else "PAYMENT")
            prefix = {"CONTRA": "CT", "RECEIPT": "BR", "PAYMENT": "BP"}[vtype]
            counters[prefix] += 1
            vno = f"{prefix}/{FY_LABEL}/{counters[prefix]:04d}"
            if e.vgroup is not None:
                group_voucher[e.vgroup] = (vno, vtype)
        voucher_of[e.seq] = vno
        entry_of[e.seq] = f"BE-{i:05d}"
        book_rows.append([entry_of[e.seq], vno, vtype, e.book_date.isoformat(), e.account_id, ACC[e.account_id]["currency"],
                          e.counter_ledger, e.party_id, e.narration, paise_to_str(e.booked_amount),
                          paise_to_str(e.booked_inr), e.mode, e.instrument_no])
    _write_csv(out_dir / "book_entries.csv", ["entry_id", "voucher_no", "voucher_type", "entry_date", "account_id",
                                              "currency", "counter_ledger", "party_id", "narration", "amount",
                                              "inr_amount", "mode", "instrument_no"], book_rows)

    _write_csv(out_dir / "ar_open.csv", ["invoice_no", "party_id", "invoice_date", "due_date", "currency", "amount",
                                         "note"],
               [[r["invoice_no"], r["party_id"], r["invoice_date"], r["due_date"], r["currency"],
                 paise_to_str(r["amount_minor"]), r["note"]] for r in g.ar_open])
    _write_csv(out_dir / "ap_open.csv", ["bill_no", "party_id", "bill_date", "due_date", "amount", "msme", "note"],
               [[r["bill_no"], r["party_id"], r["bill_date"], r["due_date"], paise_to_str(r["amount_paise"]),
                 int(r["msme"]), r["note"]] for r in g.ap_open])
    _write_csv(out_dir / "commitments.csv", ["commit_id", "due_date", "account_id", "description", "category",
                                             "amount", "certainty"],
               [[r["commit_id"], r["due_date"], r["account_id"], r["description"], r["category"],
                 paise_to_str(r["amount_paise"]), r["certainty"]] for r in g.commitments])

    # ---- answer key (never loaded by the app) ----
    _write_csv(key_dir / "matches.csv", ["event_id", "entry_id", "voucher_no", "line_id", "bank_amount",
                                         "book_amount"],
               [[e.event_id, entry_of[e.seq], voucher_of[e.seq], event_line[e.seq], paise_to_str(e.amount),
                 paise_to_str(e.booked_amount)] for e in sorted(g.events, key=lambda x: x.seq)
                if e.in_books and e.in_bank])
    _write_csv(key_dir / "line_kinds.csv", ["line_id", "account_id", "kind", "party_id", "party_category", "tag"],
               [[event_line[e.seq], e.account_id, e.kind, e.party_id,
                 g.party[e.party_id].category if e.party_id in g.party else "", e.tag]
                for e in sorted(bank_events, key=lambda x: event_line[x.seq])])

    recon = {}
    for a in ACCOUNTS:
        aid = a["account_id"]
        book_bal = a["opening_balance_minor"] + sum(e.booked_amount for e in g.events if e.account_id == aid and e.in_books)
        bank_bal = a["opening_balance_minor"] + sum(e.amount for e in g.events if e.account_id == aid and e.in_bank)
        items = []
        for e in sorted(g.events, key=lambda x: x.seq):
            if e.account_id != aid:
                continue
            if e.in_books and not e.in_bank:
                cat = "cheque_issued_not_presented" if e.amount < 0 else "deposit_not_yet_credited"
                items.append({"category": cat, "side": "books_only", "entry_id": entry_of[e.seq],
                              "voucher_no": voucher_of[e.seq], "date": e.book_date.isoformat(),
                              "amount": paise_to_str(e.booked_amount),
                              "adjust_to_reach_bank": paise_to_str(-e.booked_amount), "tag": e.tag})
            elif e.in_bank and not e.in_books:
                items.append({"category": RECON_CATEGORY[e.kind], "side": "bank_only", "line_id": event_line[e.seq],
                              "date": e.bank_date.isoformat(), "amount": paise_to_str(e.amount),
                              "adjust_to_reach_bank": paise_to_str(e.amount), "tag": e.tag})
            elif e.in_bank and e.in_books and e.book_amount is not None:
                items.append({"category": "amount_mismatch", "side": "both", "entry_id": entry_of[e.seq],
                              "line_id": event_line[e.seq], "date": e.bank_date.isoformat(),
                              "book_amount": paise_to_str(e.book_amount), "bank_amount": paise_to_str(e.amount),
                              "adjust_to_reach_bank": paise_to_str(e.amount - e.book_amount), "tag": e.tag})
        adj = sum(rupees(i["adjust_to_reach_bank"]) for i in items)
        if book_bal + adj != bank_bal:
            raise AssertionError(f"BRS does not close for {aid}")
        recon[aid] = {"as_at": FY_END.isoformat(), "currency": a["currency"],
                      "balance_per_books": paise_to_str(book_bal), "balance_per_bank": paise_to_str(bank_bal),
                      "items": items}
    (key_dir / "recon_items_2026-03-31.json").write_text(json.dumps(recon, indent=2), encoding="utf-8")

    by_tag = {e.tag: e for e in g.events if e.tag}

    def ref(tag):
        e = by_tag[tag]
        return {"line_id": event_line.get(e.seq, ""), "entry_id": entry_of.get(e.seq, ""),
                "amount": paise_to_str(e.amount), "date": (e.bank_date or e.book_date).isoformat()}

    risks = [
        {"flag_id": "R01", "type": "vendor_bank_details_changed", "party_id": "V002", **ref("R01"),
         "why": "RTGS to Deccan Castings went to IFSC ZZQB0DEL404 / A/C XX5501, not the account in the vendor master."},
        {"flag_id": "R02", "type": "weekend_payment_to_unknown_payee", "party_id": "", **ref("R02"),
         "why": "Round-sum IMPS of Rs 5,00,000 on Sunday 22-Mar-2026 to QuickFix Solutions, not in the vendor master."},
        {"flag_id": "R03", "type": "split_payment_below_threshold", "party_id": "V003",
         "lines": [ref("R03-A"), ref("R03-B")],
         "why": "Two payments to Sahyadri Forgings on 25-Mar-2026 (4,95,000 and 4,90,000), each just under the Rs 5 lakh approval limit."},
        {"flag_id": "R04", "type": "duplicate_payment", "party_id": "V011", "lines": [ref("S06"), ref("S06-DUP")],
         "why": "Same amount Rs 3,48,720 paid twice to Expressway Logistics within 2 days."},
        {"flag_id": "R05", "type": "unidentified_receipt", "party_id": "", **ref("S07"),
         "why": "Credit of Rs 2,36,000 from M S RAJ TRADERS, not a known customer."},
        {"flag_id": "R06", "type": "cheque_returned", "party_id": "C007", **ref("S08"),
         "why": "Customer cheque Rs 4,12,300 from Orbit Electricals returned unpaid (funds insufficient)."},
        {"flag_id": "R07", "type": "msme_payment_overdue", "party_id": "V002",
         "bill_no": g.ap_open[-3]["bill_no"],
         "why": "MSME bill dated 20-Jan-2026 unpaid beyond 45 days; expense deduction at risk under sec 43B(h)."},
        {"flag_id": "R08", "type": "msme_payment_overdue", "party_id": "V005",
         "bill_no": g.ap_open[-2]["bill_no"],
         "why": "MSME bill dated 05-Feb-2026 unpaid beyond 45 days; expense deduction at risk under sec 43B(h)."},
    ]
    (key_dir / "risk_flags.json").write_text(json.dumps(risks, indent=2), encoding="utf-8")

    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "manifest.json"
                   and p.suffix in (".csv", ".json"))
    manifest = {
        "phase": 1, "seed": seed, "fy": f"{FY_START} to {FY_END}",
        "counts": {"bank_lines": len(bank_events), "book_entries": len(book_rows),
                   "counterparties": len(g.party), "ar_open": len(g.ar_open), "ap_open": len(g.ap_open),
                   "commitments": len(g.commitments), "statement_files": len(index_rows)},
        "files": {p.relative_to(out_dir).as_posix(): _sha(p) for p in files},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
