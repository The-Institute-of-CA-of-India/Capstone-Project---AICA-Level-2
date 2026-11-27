#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSME Interest Calculator
========================

Desktop application (PyQt5) that computes interest payable by a buyer on delayed
payments to Micro and Small Enterprise (MSE) suppliers under the Micro, Small and
Medium Enterprises Development Act, 2006 ("MSMED Act"):

* Sec. 2(b)  - "appointed day": the day following the expiry of 15 days from the day
               of acceptance / deemed acceptance of goods or services.
* Sec. 15    - payment must be made on or before the agreed date; the agreed period
               can never exceed 45 days from acceptance. With no written agreement,
               payment is due before the appointed day (i.e. within 15 days).
* Sec. 16    - on delay, compound interest with MONTHLY RESTS at three times the bank
               rate notified by the RBI, from the appointed day / agreed date.
* Sec. 23    - such interest is not allowed as a deduction under the Income-tax Act.

Tax linkage: Sec. 43B(h) of the Income-tax Act, 1961 (and Sec. 37(2)(g) of the
Income-tax Act, 2025) allows the principal owed to a Micro/Small enterprise only in the
year of actual payment if it is paid beyond the Sec. 15 time limit.

Structure (single file, as required):
    MSMECalculator  -> pure calculation logic, no GUI code
    ExcelHandler    -> read input, validate, write template / formatted output
    PDFExporter     -> PDF report (reportlab)
    MainWindow      -> PyQt5 GUI
    run_self_test() -> mandatory statutory test case + extra sanity checks

Run:
    python MSME_Interest_Calculator.py              # opens the GUI
    python MSME_Interest_Calculator.py --selftest   # runs self-test in the console

All money is held as Decimal; rounding to 2 decimals happens only at final output.
"""

from __future__ import annotations

import datetime as dt
import functools
import itertools
import math
import os
import re
import sys
import traceback
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext
from typing import Any, Iterable, Optional
from xml.sax.saxutils import escape as xml_escape

import csv
from dateutil.relativedelta import relativedelta

# openpyxl - formatted Excel output
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# reportlab - PDF output
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

# High precision for intermediate Decimal arithmetic (compounding powers).
getcontext().prec = 34

# =============================================================================
# Constants
# =============================================================================
APP_NAME = "MSME Interest Calculator"
APP_VERSION = "1.0.0"

DEFAULT_BANK_RATE = Decimal("5.75")     # % p.a. - verify at rbi.org.in before use
MAX_AGREED_DAYS = 45                    # Sec. 15 proviso
DAYS_NO_AGREEMENT = 15                  # Sec. 2(b) / Sec. 15
DAYS_IN_YEAR = Decimal(365)
TWO_PLACES = Decimal("0.01")
ZERO = Decimal(0)

STATUS_WITHIN = "Within Time"
STATUS_PAID_LATE = "Overdue – Paid Late"
STATUS_UNPAID = "Overdue – Unpaid"
STATUS_ERROR = "Data Error"

TAX_FLAG_TEXT = "Disallowable u/s 43B(h) ITA 1961 / 37(2)(g) ITA 2025 until paid"
SEC23_REMARK = "Not deductible – Sec. 23 MSMED Act"

# Manual interest settlement entries (Repayment / Waiver tab)
ADJ_REPAID = "Interest Repaid"
ADJ_WAIVED = "Interest Waived"
ADJ_SHEET_NAME = "Interest Adjustments"
ADJ_HEADERS = ["Party Name", "Invoice Number", "Type", "Date", "Amount", "Certificate Available",
               "Certificate / Reference No.", "Remarks"]
WAIVER_RULE = (
    "A waiver of interest by the vendor is considered only if the vendor's written waiver "
    "certificate is available as at the As-on Date (certificate dated on or before the As-on Date). "
    "Without it the interest remains payable u/s 16."
)

INT_STATUS_NONE = "No Interest"
INT_STATUS_PAYABLE = "Interest Payable"
INT_STATUS_PARTLY = "Partly Settled"
INT_STATUS_PAID = "Interest Repaid"
INT_STATUS_WAIVED = "Interest Waived"
INT_STATUS_PAID_WAIVED = "Repaid & Waived"

LEGAL_BASIS = (
    "Sec. 2(b), 15, 16 & 23 of the MSMED Act, 2006; Sec. 43B(h) of the Income-tax Act, "
    "1961 / Sec. 37(2)(g) of the Income-tax Act, 2025."
)

ABOUT_TEXT = (
    "Interest computed u/s 16 of the MSMED Act, 2006. The supplier must hold valid Udyam "
    "registration on the invoice date. Traders are excluded from Sec. 15–16 benefits "
    "(MoMSME OM dated 02-07-2021). Verify the RBI Bank Rate at rbi.org.in before use."
)

METHOD_TEXT = (
    "Interest = P × (1 + R/12)^n × (1 + R × d/365) − P, where R = 3 × Bank Rate, "
    "n = completed calendar months and d = leftover days of delay counted from the "
    "appointed day (Due Date + 1)."
)

# Excel date serial epoch (Excel's 1900 system, already adjusted for the 1900 leap bug)
EXCEL_EPOCH = dt.date(1899, 12, 30)

# Text date formats accepted in input files (DD-MM-YYYY and DD/MM/YYYY first).
DATE_FORMATS = (
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
    "%Y-%m-%d", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y",
    "%d-%b-%y", "%d %b, %Y",
)

# Indian digit grouping in Excel: 1,23,45,678.00
INR_EXCEL_FORMAT = r"[>=10000000]##\,##\,##\,##0.00;[>=100000]##\,##\,##0.00;##,##0.00"
DATE_EXCEL_FORMAT = "DD-MM-YYYY"


# =============================================================================
# Generic helpers
# =============================================================================
def is_blank(value: Any) -> bool:
    """True for None, NaN, NaT and empty / placeholder strings."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("", "nan", "none", "nat", "null", "-", "n/a", "na")
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, Decimal):
        return value.is_nan()
    return False


def to_decimal(value: Any) -> Decimal:
    """Convert int/float/str/Decimal to Decimal without binary-float noise."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(str(value))


def q2(value: Decimal) -> Decimal:
    """Round to 2 decimals (half-up) - used ONLY at final output."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt_inr(value: Optional[Decimal]) -> str:
    """Format a number with Indian digit grouping, e.g. 1234567.5 -> '12,34,567.50'."""
    if value is None:
        return ""
    d = q2(value)
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


def fmt_date(value: Optional[dt.date]) -> str:
    """Date as DD-MM-YYYY (blank for None)."""
    return value.strftime("%d-%m-%Y") if value else ""


def resource_path(relative: str) -> str:
    """Absolute path to a bundled resource (works for PyInstaller --onefile too)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# =============================================================================
# Data structures
# =============================================================================
@dataclass
class Payment:
    """One payment against an invoice. amount=None means 'balance paid in full'."""
    date: dt.date
    amount: Optional[Decimal]
    source_row: int


@dataclass
class InvoiceRecord:
    """A validated input invoice (one per Party + Invoice Number)."""
    row_no: int                                   # Excel row number of the first row
    party: str
    invoice_no: str
    invoice_date: Optional[dt.date]
    amount: Optional[Decimal]
    acceptance_date: Optional[dt.date] = None
    payments: list = field(default_factory=list)  # list[Payment]
    agreed_days: Optional[int] = None
    category: str = ""                            # micro / small / medium / trader / ""
    udyam_no: str = ""
    flags: list = field(default_factory=list)     # validation problems (row is flagged)
    notes: list = field(default_factory=list)     # informational remarks

    @property
    def key(self) -> tuple:
        return invoice_key(self.party, self.invoice_no)


def invoice_key(party: str, invoice_no: str) -> tuple:
    """Case/space-insensitive key used to link invoices and settlement entries."""
    return (re.sub(r"\s+", " ", party or "").strip().lower(),
            re.sub(r"\s+", " ", invoice_no or "").strip().lower())


_ADJ_IDS = itertools.count(1)


@dataclass
class InterestAdjustment:
    """Manual entry: interest repaid to the vendor, or interest waived by the vendor.

    date   - repayment date (Repaid) or date of the vendor's waiver certificate (Waived)
    amount - None means 'the full interest balance remaining'
    certificate - Waived only: vendor's waiver certificate available as at the As-on Date
    """
    party: str
    invoice_no: str
    kind: str                                     # ADJ_REPAID / ADJ_WAIVED
    date: Optional[dt.date]
    amount: Optional[Decimal] = None
    certificate: bool = False
    cert_ref: str = ""
    remarks: str = ""
    uid: int = field(default_factory=lambda: next(_ADJ_IDS))

    @property
    def key(self) -> tuple:
        return invoice_key(self.party, self.invoice_no)


@dataclass
class InvoiceResult:
    """Computed output for one invoice. Money is unrounded Decimal."""
    record: InvoiceRecord
    acceptance_date: Optional[dt.date] = None
    allowed_days: Optional[int] = None
    due_date: Optional[dt.date] = None
    interest_start: Optional[dt.date] = None
    end_date: Optional[dt.date] = None            # payment date or As-on date
    end_basis: str = ""                           # "Paid" / "As-on"
    aging_days: Optional[int] = None
    delay_days: int = 0
    months: int = 0
    days: int = 0
    rate_pct: Decimal = ZERO
    amount_paid: Decimal = ZERO
    outstanding: Decimal = ZERO
    interest: Decimal = ZERO                      # gross interest u/s 16
    interest_repaid: Decimal = ZERO               # manual entries considered
    interest_waived: Decimal = ZERO               # waivers backed by a certificate
    interest_status: str = INT_STATUS_NONE
    status: str = STATUS_WITHIN
    tax_flag: str = ""
    remarks: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    adjustment_evals: dict = field(default_factory=dict)   # uid -> (considered, applied, note)

    @property
    def is_overdue(self) -> bool:
        return self.status in (STATUS_PAID_LATE, STATUS_UNPAID)

    @property
    def is_flagged(self) -> bool:
        return bool(self.flags)

    @property
    def net_interest(self) -> Decimal:
        """Interest still payable = gross − repaid − waived (never negative)."""
        return max(ZERO, q2(self.interest) - self.interest_repaid - self.interest_waived)

    @property
    def total_payable(self) -> Decimal:
        """Principal still outstanding + net interest u/s 16 still payable."""
        return q2(self.outstanding) + self.net_interest

    @property
    def category_label(self) -> str:
        return self.record.category.title() if self.record.category else ""


# =============================================================================
# Calculation engine (no GUI code)
# =============================================================================
class MSMECalculator:
    """Pure calculation logic for Sec. 15/16 MSMED Act interest."""

    ELIGIBLE_CATEGORIES = ("micro", "small", "")   # "" = not given, assumed MSE

    def __init__(self, bank_rate_pct: Any, written_agreement: bool, as_on_date: dt.date):
        self.bank_rate_pct = to_decimal(bank_rate_pct)
        if self.bank_rate_pct <= 0:
            raise ValueError("RBI Bank Rate must be greater than zero.")
        if not isinstance(as_on_date, dt.date):
            raise ValueError("As-on Date is required.")
        self.written_agreement = bool(written_agreement)
        self.as_on_date = as_on_date

    # ---- rates -------------------------------------------------------------
    @property
    def applicable_rate_pct(self) -> Decimal:
        """Sec. 16: three times the RBI bank rate (% p.a.)."""
        return self.bank_rate_pct * 3

    @property
    def annual_rate(self) -> Decimal:
        """R as a fraction, e.g. 0.1725."""
        return self.applicable_rate_pct / 100

    # ---- periods -----------------------------------------------------------
    def allowed_days(self, agreed_days: Optional[int]) -> tuple:
        """Return (allowed_days, remarks, flags) per Sec. 15.

        Written agreement: agreed credit days, capped at 45; blank -> 45.
        No written agreement: 15 days (Sec. 2(b) appointed day).
        """
        remarks, flags = [], []
        if not self.written_agreement:
            if agreed_days is not None and agreed_days > MAX_AGREED_DAYS:
                flags.append(f"Agreed Credit Days {agreed_days} > 45 (ignored – no written agreement)")
            elif agreed_days is not None and agreed_days != DAYS_NO_AGREEMENT:
                remarks.append("Agreed days ignored – no written agreement, 15 days applied")
            return DAYS_NO_AGREEMENT, remarks, flags
        if agreed_days is None:
            remarks.append("Agreed Credit Days blank – 45 days applied")
            return MAX_AGREED_DAYS, remarks, flags
        if agreed_days > MAX_AGREED_DAYS:
            flags.append(f"Agreed Credit Days {agreed_days} > 45 – capped at 45 (Sec. 15 proviso)")
            return MAX_AGREED_DAYS, remarks, flags
        return agreed_days, remarks, flags

    @staticmethod
    def delay_split(due_date: dt.date, end_date: dt.date) -> tuple:
        """Split the delay into (completed calendar months, leftover days).

        Interest runs from the appointed day (Due Date + 1) up to and including the
        payment / As-on date; that span equals relativedelta(end, due).
        Example: due 16-04-2026, paid 30-06-2026 -> 2 months + 14 days (75 days).
        """
        if end_date <= due_date:
            return 0, 0
        rd = relativedelta(end_date, due_date)
        return rd.years * 12 + rd.months, rd.days

    def compound_interest(self, principal: Decimal, due_date: dt.date, end_date: dt.date) -> Decimal:
        """Sec. 16 compound interest with monthly rests (unrounded Decimal).

        Interest = P × (1 + R/12)^n × (1 + R × d/365) − P
        """
        principal = to_decimal(principal)
        if principal <= 0 or end_date <= due_date:
            return ZERO
        n, d = self.delay_split(due_date, end_date)
        r = self.annual_rate
        factor = (Decimal(1) + r / 12) ** n * (Decimal(1) + r * Decimal(d) / DAYS_IN_YEAR)
        return principal * factor - principal

    # ---- per invoice -------------------------------------------------------
    def calculate(self, rec: InvoiceRecord, adjustments: Iterable = ()) -> InvoiceResult:
        """Compute due date, delay, interest, status and tax flag for one invoice.

        adjustments: InterestAdjustment entries (repayment / waiver) for this invoice.
        """
        res = InvoiceResult(record=rec, remarks=list(rec.notes), flags=list(rec.flags))
        res.rate_pct = self.applicable_rate_pct

        # Invoices without a usable date or amount cannot be computed - flagged, not dropped.
        if rec.invoice_date is None or rec.amount is None or rec.amount <= 0:
            res.status = STATUS_ERROR
            res.outstanding = rec.amount if (rec.amount is not None and rec.amount > 0) else ZERO
            res.remarks.append("Interest not computed – correct the flagged data")
            self.apply_adjustments(res, adjustments)
            return res

        # Sec. 2(b): acceptance / deemed acceptance; falls back to invoice date.
        res.acceptance_date = rec.acceptance_date or rec.invoice_date
        res.allowed_days, rmk, flg = self.allowed_days(rec.agreed_days)
        res.remarks.extend(rmk)
        res.flags.extend(flg)
        res.due_date = res.acceptance_date + dt.timedelta(days=res.allowed_days)
        res.interest_start = res.due_date + dt.timedelta(days=1)

        # ---- payments: segment-by-segment on the reducing balance ----------
        # Each paid tranche bears interest from the appointed day to its own payment
        # date; the unpaid balance bears interest up to the As-on date. Payments are
        # appropriated to principal first (oldest-first, in date order).
        balance = rec.amount
        interest = ZERO
        last_payment: Optional[dt.date] = None
        for pay in sorted(rec.payments, key=lambda p: p.date):
            if pay.date > self.as_on_date:
                res.remarks.append(
                    f"Payment dated {fmt_date(pay.date)} is after As-on Date – treated as outstanding")
                continue
            if balance <= 0:
                res.flags.append(f"Excess payment on {fmt_date(pay.date)} ignored (invoice already settled)")
                continue
            if pay.amount is None:
                applied = balance                      # date given, amount blank -> full balance
            else:
                if pay.amount > balance:
                    res.flags.append(
                        f"Payment {fmt_inr(pay.amount)} exceeds balance {fmt_inr(balance)} – excess ignored")
                applied = min(pay.amount, balance)
            interest += self.compound_interest(applied, res.due_date, pay.date)
            balance -= applied
            res.amount_paid += applied
            last_payment = pay.date

        if balance > 0:
            res.end_date, res.end_basis = self.as_on_date, "As-on"
            interest += self.compound_interest(balance, res.due_date, self.as_on_date)
        else:
            res.end_date, res.end_basis = last_payment, "Paid"
        res.outstanding = balance if balance > 0 else ZERO
        if len([p for p in rec.payments if p.date <= self.as_on_date]) > 1:
            res.remarks.append("Part payments – interest computed on reducing balance")

        # Aging and delay
        res.aging_days = (res.end_date - rec.invoice_date).days
        if res.aging_days < 0:
            if not any("before Invoice Date" in f for f in res.flags):
                res.flags.append("Payment / As-on Date is before Invoice Date")
            res.aging_days = 0
        res.delay_days = max(0, (res.end_date - res.due_date).days)
        res.months, res.days = self.delay_split(res.due_date, res.end_date)

        # Status
        if res.delay_days == 0:
            res.status = STATUS_WITHIN
        elif res.outstanding > 0:
            res.status = STATUS_UNPAID
        else:
            res.status = STATUS_PAID_LATE

        # Eligibility: only Micro & Small enterprises are "suppliers" u/s 2(n);
        # traders are excluded by MoMSME OM dated 02-07-2021.
        cat = rec.category
        if cat not in self.ELIGIBLE_CATEGORIES:
            if interest > 0:
                res.remarks.append(
                    f"{cat.title()} – Sec. 15–16 not applicable; interest of Rs. {fmt_inr(interest)} not payable")
            else:
                res.remarks.append(f"{cat.title()} – Sec. 15–16 not applicable")
            interest = ZERO
        elif cat == "":
            res.remarks.append("MSE Category not given – assumed Micro/Small, verify Udyam")
        res.interest = interest

        # Udyam check for MSEs
        if cat in ("micro", "small") and not rec.udyam_no:
            res.remarks.append("Udyam No. not given – verify registration on invoice date")

        # Tax flag (Micro/Small only)
        if cat in ("medium", "trader"):
            res.tax_flag = "N.A."
        elif res.status == STATUS_UNPAID:
            res.tax_flag = TAX_FLAG_TEXT if cat else f"If Micro/Small: {TAX_FLAG_TEXT}"
        elif res.status == STATUS_PAID_LATE:
            res.tax_flag = f"43B(h): principal allowable only in year of payment ({fmt_date(res.end_date)})"
        else:
            res.tax_flag = ""

        if q2(res.interest) > 0:
            res.remarks.append(SEC23_REMARK)
        self.apply_adjustments(res, adjustments)
        return res

    # ---- interest repayment / waiver ---------------------------------------
    def apply_adjustments(self, res: InvoiceResult, adjustments: Iterable) -> None:
        """Apply manual interest repayments / vendor waivers to one result (in date order).

        Rules:
        * Only entries dated on or before the As-on Date are considered.
        * A waiver is considered ONLY if the vendor's waiver certificate is available
          as at the As-on Date; otherwise the interest stays payable.
        * Amount blank = the full interest balance remaining at that point.
        * Amounts beyond the remaining interest balance are ignored (flagged).
        Settlement works on the gross interest rounded to paise.
        """
        gross = q2(res.interest)
        balance = gross
        repaid = waived = ZERO
        waiver_refs = []
        order = sorted(adjustments, key=lambda e: (e.date or dt.date.max, 0 if e.kind == ADJ_REPAID else 1))
        for e in order:
            label = "Waiver" if e.kind == ADJ_WAIVED else "Repayment"
            note = None
            if res.status == STATUS_ERROR:
                note = "Invoice has data errors – not considered"
            elif e.date is None:
                note = "Date missing – not considered"
            elif e.date > self.as_on_date:
                note = f"Dated after As-on Date {fmt_date(self.as_on_date)} – not considered"
            elif e.kind == ADJ_WAIVED and not e.certificate:
                note = "Vendor waiver certificate not available as at As-on Date – waiver not considered"
                res.remarks.append("Waiver claimed without vendor certificate – interest remains payable")
            elif e.amount is not None and e.amount <= 0:
                note = "Amount must be greater than zero – not considered"
            elif gross == 0:
                note = "No interest due on this invoice – not applied"
            elif balance <= 0:
                note = "Interest already fully settled – not applied"
            if note is not None:
                res.adjustment_evals[e.uid] = (False, ZERO, note)
                continue

            applied = balance if e.amount is None else min(q2(e.amount), balance)
            note = f"{label} applied"
            if e.amount is not None and q2(e.amount) > balance:
                excess = q2(e.amount) - balance
                note += f"; excess Rs. {fmt_inr(excess)} over interest balance ignored"
                res.flags.append(f"{label} of Rs. {fmt_inr(e.amount)} exceeds interest balance – excess ignored")
            balance -= applied
            if e.kind == ADJ_WAIVED:
                waived += applied
                waiver_refs.append(f"{e.cert_ref or 'certificate'} dated {fmt_date(e.date)}")
            else:
                repaid += applied
            res.adjustment_evals[e.uid] = (True, applied, note)

        res.interest_repaid, res.interest_waived = repaid, waived
        if repaid > 0:
            res.remarks.append(f"Interest of Rs. {fmt_inr(repaid)} repaid to vendor")
        if waived > 0:
            res.remarks.append(f"Interest of Rs. {fmt_inr(waived)} waived by vendor ("
                               + "; ".join(waiver_refs) + ") – not payable")
            if repaid == 0 and balance == 0 and SEC23_REMARK in res.remarks:
                res.remarks.remove(SEC23_REMARK)
                res.remarks.append("Interest fully waived – no Sec. 23 disallowance")

        if gross == 0:
            res.interest_status = INT_STATUS_NONE
        elif balance == 0:
            res.interest_status = (INT_STATUS_PAID_WAIVED if repaid and waived
                                   else INT_STATUS_WAIVED if waived else INT_STATUS_PAID)
        elif repaid or waived:
            res.interest_status = INT_STATUS_PARTLY
        else:
            res.interest_status = INT_STATUS_PAYABLE

    def calculate_all(self, records: Iterable[InvoiceRecord], adjustments: Iterable = ()) -> list:
        """Compute all invoices. Evaluations of every adjustment entry are stored in
        self.adjustment_evaluations (uid -> (considered, applied, note))."""
        by_key: dict = {}
        for e in adjustments:
            by_key.setdefault(e.key, []).append(e)
        results = []
        self.adjustment_evaluations = {}
        for rec in records:
            res = self.calculate(rec, by_key.pop(rec.key, ()))
            self.adjustment_evaluations.update(res.adjustment_evals)
            results.append(res)
        for orphans in by_key.values():              # entries whose invoice is not in the file
            for e in orphans:
                self.adjustment_evaluations[e.uid] = (False, ZERO, "Invoice not found in uploaded file")
        return results

    # ---- aggregates --------------------------------------------------------
    @staticmethod
    def summarise(results: list) -> dict:
        """Totals for summary cards / reports (sums of per-invoice rounded values)."""
        return {
            "total_invoices": len(results),
            "overdue_count": sum(1 for r in results if r.is_overdue),
            "flagged_count": sum(1 for r in results if r.is_flagged),
            "total_amount": sum((q2(r.record.amount or ZERO) for r in results), ZERO),
            "total_paid": sum((q2(r.amount_paid) for r in results), ZERO),
            "total_outstanding": sum((q2(r.outstanding) for r in results), ZERO),
            "total_interest": sum((q2(r.interest) for r in results), ZERO),
            "total_repaid": sum((r.interest_repaid for r in results), ZERO),
            "total_waived": sum((r.interest_waived for r in results), ZERO),
            "net_interest": sum((r.net_interest for r in results), ZERO),
            "total_payable": sum((r.total_payable for r in results), ZERO),
            "mse_outstanding": sum((q2(r.outstanding) for r in results
                                    if r.record.category in MSMECalculator.ELIGIBLE_CATEGORIES), ZERO),
        }

    @staticmethod
    def party_summary(results: list) -> list:
        """Party-wise outstanding, overdue amount and interest."""
        parties: dict = {}
        for r in results:
            key = r.record.party or "(blank)"
            p = parties.setdefault(key, {
                "party": key, "invoices": 0, "amount": ZERO, "paid": ZERO, "outstanding": ZERO,
                "overdue_count": 0, "overdue_amount": ZERO, "interest": ZERO, "repaid": ZERO,
                "waived": ZERO, "net_interest": ZERO, "payable": ZERO})
            p["invoices"] += 1
            p["amount"] += q2(r.record.amount or ZERO)
            p["paid"] += q2(r.amount_paid)
            p["outstanding"] += q2(r.outstanding)
            if r.is_overdue:
                p["overdue_count"] += 1
            if r.status == STATUS_UNPAID:
                p["overdue_amount"] += q2(r.outstanding)
            p["interest"] += q2(r.interest)
            p["repaid"] += r.interest_repaid
            p["waived"] += r.interest_waived
            p["net_interest"] += r.net_interest
            p["payable"] += r.total_payable
        return sorted(parties.values(), key=lambda x: x["party"].lower())

    AGING_BUCKETS = (("0–15 days", 0, 15), ("16–45 days", 16, 45), ("46–90 days", 46, 90),
                     ("91–180 days", 91, 180), (">180 days", 181, None))

    @classmethod
    def aging_summary(cls, results: list) -> list:
        """Aging buckets on Aging Days (Payment/As-on Date − Invoice Date)."""
        rows = [{"bucket": name, "lo": lo, "hi": hi, "count": 0, "amount": ZERO, "outstanding": ZERO,
                 "overdue_amount": ZERO, "interest": ZERO} for name, lo, hi in cls.AGING_BUCKETS]
        not_computed = {"bucket": "Not computed (data error)", "count": 0, "amount": ZERO,
                        "outstanding": ZERO, "overdue_amount": ZERO, "interest": ZERO}
        for r in results:
            target = not_computed
            if r.aging_days is not None:
                for b in rows:
                    if r.aging_days >= b["lo"] and (b["hi"] is None or r.aging_days <= b["hi"]):
                        target = b
                        break
            target["count"] += 1
            target["amount"] += q2(r.record.amount or ZERO)
            target["outstanding"] += q2(r.outstanding)
            if r.status == STATUS_UNPAID:
                target["overdue_amount"] += q2(r.outstanding)
            target["interest"] += q2(r.interest)
        if not_computed["count"]:
            rows.append(not_computed)
        return rows


# =============================================================================
# Excel input / output
# =============================================================================
class ExcelHandler:
    """Reads and validates the input file; writes the template and formatted output."""

    TEMPLATE_HEADERS = [
        "Party Name", "Invoice Number", "Invoice Date", "Invoice Amount",
        "Acceptance/Delivery Date", "Payment Date", "Amount Paid", "Agreed Credit Days",
        "MSE Category", "Udyam No.",
    ]
    REQUIRED_FIELDS = ("party", "invoice_no", "invoice_date", "amount")

    # Normalised header aliases (lower-case, only letters/digits) for each field.
    FIELD_ALIASES = {
        "party": ["partyname", "party", "vendorname", "vendor", "suppliername", "supplier",
                  "creditorname", "creditor", "nameofparty", "nameofsupplier"],
        "invoice_no": ["invoicenumber", "invoiceno", "invno", "invoice", "billno", "billnumber",
                       "invoicenum", "voucherno", "refno"],
        "invoice_date": ["invoicedate", "invdate", "billdate", "dateofinvoice"],
        "amount": ["invoiceamount", "amount", "invamount", "billamount", "invoicevalue",
                   "invoiceamt", "grossamount"],
        "acceptance_date": ["acceptancedeliverydate", "acceptanceordeliverydate", "acceptancedate",
                            "deliverydate", "dateofacceptance", "dateofdelivery", "grndate",
                            "deemedacceptancedate", "receiptdate"],
        "payment_date": ["paymentdate", "paiddate", "dateofpayment", "paidon"],
        "amount_paid": ["amountpaid", "paidamount", "paymentamount", "amtpaid"],
        "agreed_days": ["agreedcreditdays", "creditdays", "agreeddays", "creditperiod",
                        "agreedcreditperiod", "creditperioddays", "paymenttermsdays"],
        "category": ["msecategory", "category", "msmecategory", "enterprisecategory",
                     "msetype", "msmetype", "msmeclassification"],
        "udyam": ["udyamno", "udyamnumber", "udyam", "udyamregistrationno",
                  "udyamregistrationnumber", "udyamregno", "uamno"],
    }

    # ---- header helpers ----------------------------------------------------
    @staticmethod
    def normalise_header(text: Any) -> str:
        """Lower-case and drop spaces, dots and other punctuation."""
        return re.sub(r"[^a-z0-9]", "", str(text).lower())

    @classmethod
    def map_columns(cls, headers: list) -> dict:
        """Map field name -> column index using flexible header matching."""
        lookup = {alias: fld for fld, aliases in cls.FIELD_ALIASES.items() for alias in aliases}
        mapping: dict = {}
        for idx, h in enumerate(headers):
            if is_blank(h):
                continue
            fld = lookup.get(cls.normalise_header(h))
            if fld and fld not in mapping:
                mapping[fld] = idx
        return mapping

    # ---- value parsers -----------------------------------------------------
    @staticmethod
    def parse_date(value: Any) -> Optional[dt.date]:
        """Parse DD-MM-YYYY, DD/MM/YYYY, Excel serials and real dates.

        Returns None for blank; raises ValueError for anything unparseable.
        """
        if is_blank(value):
            return None
        if isinstance(value, dt.datetime):            # includes pandas.Timestamp
            return value.date()
        if isinstance(value, dt.date):
            return value
        if isinstance(value, bool):
            raise ValueError(f"invalid date '{value}'")
        if isinstance(value, (int, float, Decimal)):
            return ExcelHandler._from_serial(float(value))
        text = str(value).strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T]\d{1,2}:\d{2}(:\d{2})?(\.\d+)?$", text)
        if m:                                         # "2026-04-01 00:00:00"
            text = m.group(1)
        if re.fullmatch(r"\d+(\.\d+)?", text):        # serial stored as text
            return ExcelHandler._from_serial(float(text))
        for fmt in DATE_FORMATS:
            try:
                return dt.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"invalid date '{text}'")

    @staticmethod
    def _from_serial(serial: float) -> dt.date:
        if math.isnan(serial) or not 1 <= serial <= 2958465:
            raise ValueError(f"invalid Excel date serial '{serial}'")
        return EXCEL_EPOCH + dt.timedelta(days=int(serial))

    @staticmethod
    def parse_amount(value: Any) -> Optional[Decimal]:
        """Parse amounts like 100000, '1,00,000.00', '₹ 5,000', '(500)'. None if blank."""
        if is_blank(value):
            return None
        if isinstance(value, bool):
            raise ValueError(f"invalid amount '{value}'")
        if isinstance(value, (int, float, Decimal)):
            return to_decimal(value)
        text = str(value).strip()
        negative = text.startswith("(") and text.endswith(")")
        cleaned = re.sub(r"(?i)(rs\.?|inr|₹|,|\s|\(|\))", "", text)
        try:
            amt = Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"invalid amount '{text}'") from None
        return -amt if negative else amt

    @staticmethod
    def parse_days(value: Any) -> Optional[int]:
        """Parse credit days: 30, 30.0, '30', '30 days'. None if blank."""
        if is_blank(value):
            return None
        text = str(value).strip()
        m = re.fullmatch(r"(?i)(\d+)(\.0+)?\s*(days?)?", text)
        if not m:
            raise ValueError(f"invalid credit days '{text}'")
        return int(m.group(1))

    @staticmethod
    def parse_category(value: Any) -> tuple:
        """Return (category, flag) with category in micro/small/medium/trader/''."""
        if is_blank(value):
            return "", None
        s = re.sub(r"[^a-z]", "", str(value).lower())
        for key in ("micro", "small", "medium"):
            if s.startswith(key):
                return key, None
        if s.startswith("trad"):
            return "trader", None
        return "", f"Unknown MSE Category '{value}' – treated as not given"

    @staticmethod
    def cell_text(value: Any) -> str:
        """Cell as clean text (101.0 -> '101')."""
        if is_blank(value):
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    # ---- reading -----------------------------------------------------------
    @staticmethod
    def _xlrd():
        """Import xlrd (optional, only for legacy .xls files)."""
        try:
            import xlrd                                              # noqa: PLC0415
        except ImportError:
            raise ValueError("Reading .xls files needs the 'xlrd' package "
                             "(pip install xlrd) – or save the file as .xlsx.") from None
        return xlrd

    @classmethod
    def sheet_names(cls, path: str) -> list:
        """Worksheet names of an .xlsx/.xlsm/.xls workbook."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xls":
            return cls._xlrd().open_workbook(path, on_demand=True).sheet_names()
        wb = load_workbook(path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    @classmethod
    def _read_raw(cls, path: str, sheet: Any = 0) -> list:
        """Read one sheet as a list of row tuples (no header processing), so the header
        row can be located. Uses openpyxl / csv directly - no pandas - to keep the .exe small.
        sheet: index or name (ignored for .csv)."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            for enc in ("utf-8-sig", "latin-1"):
                try:
                    with open(path, newline="", encoding=enc) as fh:
                        return [tuple(r) for r in csv.reader(fh)]
                except UnicodeDecodeError:
                    continue
        if ext in (".xlsx", ".xlsm"):
            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
                return [tuple(r) for r in ws.iter_rows(values_only=True)]
            finally:
                wb.close()
        if ext == ".xls":
            xlrd = cls._xlrd()
            book = xlrd.open_workbook(path)
            sh = book.sheet_by_index(sheet) if isinstance(sheet, int) else book.sheet_by_name(sheet)
            rows = []
            for r in range(sh.nrows):
                row = []
                for cell in sh.row(r):
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        row.append(None)
                    else:
                        row.append(cell.value)
                rows.append(tuple(row))
            return rows
        raise ValueError(f"Unsupported file type '{ext}'. Use .xlsx, .xls or .csv.")

    @classmethod
    def read_input(cls, path: str) -> tuple:
        """Read and validate the input file.

        Returns (records, info) where info = {'rows': int, 'warnings': [str]}.
        Bad rows are FLAGGED (kept), never dropped.
        """
        if not os.path.isfile(path):
            raise ValueError(f"File not found: {path}")
        raw = cls._read_raw(path)
        if not raw or all(all(is_blank(v) for v in r) for r in raw):
            raise ValueError("The file is empty.")

        # Locate the header row (allows title rows above the table).
        header_idx, mapping = None, {}
        for idx in range(min(25, len(raw))):
            m = cls.map_columns(list(raw[idx]))
            if all(f in m for f in cls.REQUIRED_FIELDS):
                header_idx, mapping = idx, m
                break
        if header_idx is None:
            found = [cls.cell_text(h) for h in raw[0] if not is_blank(h)]
            missing = [h for h, f in zip(cls.TEMPLATE_HEADERS[:4], cls.REQUIRED_FIELDS)
                       if f not in cls.map_columns(list(raw[0]))]
            raise ValueError("Required column(s) not found: " + ", ".join(missing)
                             + "\nHeaders found: " + (", ".join(found) or "(none)")
                             + "\nUse 'Download Template' for the expected layout.")

        warnings = []
        optional_missing = [f for f in cls.FIELD_ALIASES if f not in mapping]
        if optional_missing:
            warnings.append("Optional columns not found: " + ", ".join(optional_missing))

        def get(row, fld):
            idx = mapping.get(fld)
            return row[idx] if idx is not None and idx < len(row) else None

        records: list = []
        by_key: dict = {}
        data_rows = 0
        for offset, row in enumerate(raw[header_idx + 1:]):
            excel_row = header_idx + 2 + offset          # 1-based row number in the sheet
            if all(is_blank(v) for v in row):
                continue
            data_rows += 1
            rec = cls._parse_row(excel_row, row, get)

            # Repeated Party + Invoice Number rows = additional (part) payments.
            key = (rec.party.lower(), rec.invoice_no.lower())
            if rec.party and rec.invoice_no and key in by_key:
                master = by_key[key]
                master.payments.extend(rec.payments)
                master.flags.extend(f"Row {excel_row}: {f}" for f in rec.flags)
                if rec.amount is not None and master.amount is not None and rec.amount != master.amount:
                    master.flags.append(f"Row {excel_row}: invoice amount differs – first row used")
                master.notes.append(f"Payments merged from row {excel_row}")
                continue
            by_key[key] = rec
            records.append(rec)

        if not records:
            raise ValueError("No data rows found below the header row.")

        # Optional "Interest Adjustments" sheet in the same workbook
        adjustments = None
        sheet = cls.find_adjustment_sheet(path)
        if sheet is not None:
            adjustments, adj_warn = cls.read_adjustments(path, sheet)
            warnings.extend(adj_warn)
        return records, {"rows": data_rows, "warnings": warnings, "header_row": header_idx + 1,
                         "adjustments": adjustments}

    # ---- interest repayment / waiver entries -------------------------------
    ADJ_ALIASES = {
        "party": FIELD_ALIASES["party"],
        "invoice_no": FIELD_ALIASES["invoice_no"],
        "kind": ["type", "adjustmenttype", "action", "repaymentwaiver", "nature"],
        "date": ["date", "repaymentdate", "waiverdate", "certificatedate", "paymentdate",
                 "dateofrepayment", "dateofcertificate"],
        "amount": ["amount", "interestamount", "amountrepaid", "amountwaived", "interestrepaid",
                   "interestwaived"],
        "certificate": ["certificateavailable", "certificate", "waivercertificate",
                        "waivercertificateavailable", "certificatereceived"],
        "cert_ref": ["certificatereferenceno", "certificateref", "certificateno", "referenceno",
                     "reference", "refno", "utr", "utrno"],
        "remarks": ["remarks", "remark", "notes", "narration"],
    }

    @classmethod
    def find_adjustment_sheet(cls, path: str) -> Optional[str]:
        """Name of a sheet holding interest repayment / waiver entries, if any."""
        if os.path.splitext(path)[1].lower() not in (".xlsx", ".xlsm", ".xls"):
            return None
        try:
            names = cls.sheet_names(path)
        except Exception:                                          # noqa: BLE001
            return None
        for i, name in enumerate(names):
            n = cls.normalise_header(name)
            if i > 0 and any(k in n for k in ("adjust", "waiv", "repay", "settle")):
                return name
        return None

    @staticmethod
    def parse_kind(value: Any) -> Optional[str]:
        s = re.sub(r"[^a-z]", "", str(value).lower())
        if "waiv" in s:
            return ADJ_WAIVED
        if any(k in s for k in ("repa", "paid", "pay")):
            return ADJ_REPAID
        return None

    @staticmethod
    def parse_yes_no(value: Any) -> bool:
        return str(value).strip().lower() in ("yes", "y", "true", "1", "available", "received")

    @classmethod
    def read_adjustments(cls, path: str, sheet: Any = 0) -> tuple:
        """Read repayment / waiver entries. Returns (entries, warnings).

        Columns: Party Name, Invoice Number, Type (Interest Repaid / Interest Waived), Date,
        Amount (blank = full balance), Certificate Available (Yes/No), Certificate Ref, Remarks.
        """
        raw = cls._read_raw(path, sheet)
        lookup = {a: f for f, al in cls.ADJ_ALIASES.items() for a in al}
        header_idx, mapping = None, {}
        for idx in range(min(25, len(raw))):
            m: dict = {}
            for c, h in enumerate(raw[idx]):
                f = lookup.get(cls.normalise_header(h)) if not is_blank(h) else None
                if f and f not in m:
                    m[f] = c
            if all(k in m for k in ("party", "invoice_no", "kind")):
                header_idx, mapping = idx, m
                break
        if header_idx is None:
            raise ValueError("Interest adjustment sheet needs columns: " + ", ".join(ADJ_HEADERS))

        entries, warnings = [], []
        for offset, row in enumerate(raw[header_idx + 1:]):
            excel_row = header_idx + 2 + offset
            if all(is_blank(v) for v in row):
                continue
            get = lambda f: row[mapping[f]] if f in mapping and mapping[f] < len(row) else None  # noqa: E731
            kind = cls.parse_kind(get("kind"))
            party, inv = cls.cell_text(get("party")), cls.cell_text(get("invoice_no"))
            if not party or not inv or kind is None:
                warnings.append(f"Adjustments row {excel_row}: party, invoice no. or type missing/invalid – skipped")
                continue
            try:
                date = cls.parse_date(get("date"))
            except ValueError:
                warnings.append(f"Adjustments row {excel_row}: invalid date – entry kept without date")
                date = None
            try:
                amount = cls.parse_amount(get("amount"))
            except ValueError:
                warnings.append(f"Adjustments row {excel_row}: invalid amount – treated as full balance")
                amount = None
            entries.append(InterestAdjustment(
                party=party, invoice_no=inv, kind=kind, date=date, amount=amount,
                certificate=cls.parse_yes_no(get("certificate")) if kind == ADJ_WAIVED else False,
                cert_ref=cls.cell_text(get("cert_ref")), remarks=cls.cell_text(get("remarks"))))
        return entries, warnings

    @classmethod
    def _adjustment_sheet(cls, ws, rows_from: int = 1001) -> None:
        """Format an (empty or filled) Interest Adjustments sheet: headers, validations."""
        for c, h in enumerate(ADJ_HEADERS, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = cls.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = cls.BORDER
            ws.column_dimensions[get_column_letter(c)].width = 34 if c in (1, 8) else 22
        ws.row_dimensions[1].height = 32
        ws.freeze_panes = "A2"
        for r in range(2, rows_from + 1):
            ws.cell(row=r, column=4).number_format = DATE_EXCEL_FORMAT
            ws.cell(row=r, column=5).number_format = INR_EXCEL_FORMAT
        dv_type = DataValidation(type="list", formula1=f'"{ADJ_REPAID},{ADJ_WAIVED}"', allow_blank=True)
        dv_yes = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
        ws.add_data_validation(dv_type)
        ws.add_data_validation(dv_yes)
        dv_type.add(f"C2:C{rows_from}")
        dv_yes.add(f"F2:F{rows_from}")

    @classmethod
    def write_adjustments(cls, path: str, entries: list) -> None:
        """Save repayment / waiver entries in a re-importable workbook."""
        wb = Workbook()
        ws = wb.active
        ws.title = ADJ_SHEET_NAME
        cls._adjustment_sheet(ws, max(1001, len(entries) + 1))
        for r, e in enumerate(entries, start=2):
            vals = [e.party, e.invoice_no, e.kind, e.date,
                    float(q2(e.amount)) if e.amount is not None else None,
                    ("Yes" if e.certificate else "No") if e.kind == ADJ_WAIVED else "",
                    e.cert_ref, e.remarks]
            for c, v in enumerate(vals, start=1):
                ws.cell(row=r, column=c, value=v).border = cls.BORDER
        wb.save(path)

    @classmethod
    def _parse_row(cls, excel_row: int, row: tuple, get) -> InvoiceRecord:
        """Validate one row and build an InvoiceRecord with flags."""
        flags: list = []
        party = cls.cell_text(get(row, "party"))
        inv_no = cls.cell_text(get(row, "invoice_no"))
        if not party:
            flags.append("Party Name missing")
        if not inv_no:
            flags.append("Invoice Number missing")

        def date_field(fld, label, required=False):
            raw_val = get(row, fld)
            try:
                d = cls.parse_date(raw_val)
            except ValueError:
                flags.append(f"Invalid {label} '{cls.cell_text(raw_val)}'")
                return None
            if d is None and required:
                flags.append(f"{label} missing")
            return d

        inv_date = date_field("invoice_date", "Invoice Date", required=True)
        acc_date = date_field("acceptance_date", "Acceptance/Delivery Date")
        pay_date = date_field("payment_date", "Payment Date")

        amount = None
        try:
            amount = cls.parse_amount(get(row, "amount"))
            if amount is None:
                flags.append("Invoice Amount missing")
            elif amount <= 0:
                flags.append("Invoice Amount is zero or negative")
        except ValueError:
            flags.append(f"Invalid Invoice Amount '{cls.cell_text(get(row, 'amount'))}'")

        paid_amt = None
        try:
            paid_amt = cls.parse_amount(get(row, "amount_paid"))
            if paid_amt is not None and paid_amt < 0:
                flags.append("Amount Paid is negative – ignored")
                paid_amt = None
        except ValueError:
            flags.append(f"Invalid Amount Paid '{cls.cell_text(get(row, 'amount_paid'))}'")

        agreed = None
        try:
            agreed = cls.parse_days(get(row, "agreed_days"))
        except ValueError:
            flags.append(f"Invalid Agreed Credit Days '{cls.cell_text(get(row, 'agreed_days'))}'")

        category, cat_flag = cls.parse_category(get(row, "category"))
        if cat_flag:
            flags.append(cat_flag)

        notes: list = []
        payments: list = []
        if pay_date is not None:
            if inv_date is not None and pay_date < inv_date:
                flags.append("Payment Date is before Invoice Date")
            if paid_amt is None or paid_amt > 0:
                payments.append(Payment(pay_date, paid_amt, excel_row))
            else:
                notes.append("Amount Paid is 0 – payment ignored")
        elif paid_amt is not None and paid_amt > 0:
            flags.append("Amount Paid without Payment Date – treated as unpaid")

        if acc_date is not None and inv_date is not None and acc_date < inv_date:
            notes.append("Acceptance date precedes invoice date")

        return InvoiceRecord(
            row_no=excel_row, party=party, invoice_no=inv_no, invoice_date=inv_date,
            amount=amount, acceptance_date=acc_date, payments=payments, agreed_days=agreed,
            category=category, udyam_no=cls.cell_text(get(row, "udyam")), flags=flags, notes=notes)

    # ---- formatting helpers ------------------------------------------------
    HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
    REQUIRED_FILL = PatternFill("solid", fgColor="C00000")
    OVERDUE_FILL = PatternFill("solid", fgColor="F8CBAD")
    FLAG_FILL = PatternFill("solid", fgColor="FFF2CC")
    TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")
    THIN = Side(style="thin", color="BFBFBF")
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

    @classmethod
    def _write_table(cls, ws, headers: list, types: list, rows: list, total_cols: Iterable = (),
                     row_fills: Optional[list] = None, wrap_cols: Iterable = ()) -> None:
        """Write a formatted table: bold header, frozen top row, filters, auto width.

        types: per column 'text' | 'date' | 'money' | 'int' | 'pct'
        total_cols: 0-based column indexes that get a SUM() in a totals row.
        """
        wrap_cols = set(wrap_cols)
        for c, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = cls.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = cls.BORDER
        widths = [len(str(h)) for h in headers]

        for r, values in enumerate(rows, start=2):
            fill = row_fills[r - 2] if row_fills else None
            for c, (val, typ) in enumerate(zip(values, types), start=1):
                if typ == "money" and val is not None:
                    val = float(q2(val))
                elif typ == "pct" and val is not None:
                    val = float(val)
                cell = ws.cell(row=r, column=c, value=val)
                cell.border = cls.BORDER
                if typ == "money":
                    cell.number_format = INR_EXCEL_FORMAT
                    shown = fmt_inr(to_decimal(val)) if val is not None else ""
                elif typ == "date":
                    cell.number_format = DATE_EXCEL_FORMAT
                    cell.alignment = Alignment(horizontal="center")
                    shown = "00-00-0000" if val else ""
                elif typ == "pct":
                    cell.number_format = "0.00"
                    shown = f"{val:.2f}" if val is not None else ""
                elif typ == "int":
                    cell.number_format = "0"
                    cell.alignment = Alignment(horizontal="center")
                    shown = str(val) if val is not None else ""
                else:
                    shown = "" if val is None else str(val)
                    if c - 1 in wrap_cols:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                if fill is not None:
                    cell.fill = fill
                widths[c - 1] = max(widths[c - 1], len(shown))

        total_cols = list(total_cols)
        if total_cols and rows:
            tr = len(rows) + 2
            label = ws.cell(row=tr, column=1, value="TOTAL")
            for c in range(1, len(headers) + 1):
                cell = ws.cell(row=tr, column=c)
                cell.font = Font(bold=True)
                cell.fill = cls.TOTAL_FILL
                cell.border = cls.BORDER
            label.font = Font(bold=True)
            for ci in total_cols:
                col = get_column_letter(ci + 1)
                cell = ws.cell(row=tr, column=ci + 1, value=f"=SUM({col}2:{col}{tr - 1})")
                cell.number_format = INR_EXCEL_FORMAT if types[ci] == "money" else "0"

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(rows) + 1)}"
        for c, w in enumerate(widths, start=1):
            limit = 60 if (c - 1) in wrap_cols else 45
            ws.column_dimensions[get_column_letter(c)].width = min(limit, max(10, w + 3))
        ws.row_dimensions[1].height = 32

    # ---- template ----------------------------------------------------------
    @classmethod
    def write_template(cls, path: str) -> None:
        """Create a blank input template with the required columns and an instruction sheet."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Invoices"
        for c, h in enumerate(cls.TEMPLATE_HEADERS, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = cls.REQUIRED_FILL if c <= 4 else cls.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = cls.BORDER
            ws.column_dimensions[get_column_letter(c)].width = max(16, len(h) + 4)
        ws.row_dimensions[1].height = 32
        ws.freeze_panes = "A2"
        # Formats for the first 1,000 data rows
        for r in range(2, 1002):
            for c in (3, 5, 6):
                ws.cell(row=r, column=c).number_format = DATE_EXCEL_FORMAT
            for c in (4, 7):
                ws.cell(row=r, column=c).number_format = INR_EXCEL_FORMAT
        dv = DataValidation(type="list", formula1='"Micro,Small,Medium,Trader"', allow_blank=True)
        dv.error, dv.errorTitle = "Choose Micro, Small, Medium or Trader", "MSE Category"
        ws.add_data_validation(dv)
        dv.add("I2:I1001")

        cls._adjustment_sheet(wb.create_sheet(ADJ_SHEET_NAME))

        info = wb.create_sheet("Instructions")
        lines = [
            ("MSME Interest Calculator – Input Template", True),
            ("", False),
            ("Required columns (red): Party Name, Invoice Number, Invoice Date, Invoice Amount", False),
            ("Optional columns (blue): Acceptance/Delivery Date, Payment Date, Amount Paid, "
             "Agreed Credit Days, MSE Category, Udyam No.", False),
            ("Dates: DD-MM-YYYY, DD/MM/YYYY or real Excel dates.", False),
            ("Acceptance/Delivery Date blank -> Invoice Date is used as the date of acceptance.", False),
            ("Payment Date blank -> invoice treated as unpaid up to the As-on Date.", False),
            ("Amount Paid blank with a Payment Date -> treated as full payment.", False),
            ("Part payments: repeat the row with the same Party Name + Invoice Number, giving each "
             "payment's date and amount.", False),
            ("Agreed Credit Days are used only when 'Written Agreement = Yes' and are capped at 45.", False),
            ("MSE Category: Micro / Small / Medium / Trader. Medium & Trader get no Sec. 16 interest.", False),
            ("", False),
            (f"Sheet '{ADJ_SHEET_NAME}' (optional): record interest repaid to / waived by the vendor. "
             "Type = Interest Repaid or Interest Waived; Date = repayment date or waiver certificate date; "
             "Amount blank = full interest balance; Certificate Available = Yes/No (waivers only).", False),
            (WAIVER_RULE, False),
            ("Entries can also be added in the app on the 'Interest Repayment / Waiver' tab.", False),
            ("", False),
            (ABOUT_TEXT, False),
        ]
        for i, (text, bold) in enumerate(lines, start=1):
            cell = info.cell(row=i, column=1, value=text)
            cell.font = Font(bold=bold, size=13 if bold else 11)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        info.column_dimensions["A"].width = 110
        wb.save(path)

    # ---- output ------------------------------------------------------------
    DETAIL_HEADERS = [
        "Row", "Party", "Invoice No.", "Invoice Date", "Amount", "Acceptance Date", "Allowed Days",
        "Due Date", "Interest From", "Payment/As-on Date", "Basis", "Aging Days", "Delay Days",
        "Months", "Days", "Rate %", "Amount Paid", "Outstanding", "Interest", "Interest Repaid",
        "Interest Waived", "Net Interest Payable", "Total Payable", "Status", "Interest Status",
        "MSE Category", "Udyam No.", "43B(h) Flag", "Remarks", "Validation Flags",
    ]
    DETAIL_TYPES = [
        "int", "text", "text", "date", "money", "date", "int", "date", "date", "date", "text",
        "int", "int", "int", "int", "pct", "money", "money", "money", "money", "money", "money",
        "money", "text", "text", "text", "text", "text", "text", "text",
    ]

    @staticmethod
    def detail_row(r: InvoiceResult) -> list:
        """One output row (shared by Excel and GUI). Money stays Decimal here."""
        rec = r.record
        return [
            rec.row_no, rec.party, rec.invoice_no, rec.invoice_date, rec.amount, r.acceptance_date,
            r.allowed_days, r.due_date, r.interest_start, r.end_date, r.end_basis, r.aging_days,
            r.delay_days, r.months, r.days, r.rate_pct, r.amount_paid, r.outstanding, r.interest,
            r.interest_repaid, r.interest_waived, r.net_interest, r.total_payable, r.status,
            r.interest_status, r.category_label, rec.udyam_no, r.tax_flag,
            "; ".join(r.remarks), "; ".join(r.flags),
        ]

    @classmethod
    def write_output(cls, path: str, results: list, calc: MSMECalculator, source_file: str = "",
                     adjustments: Iterable = ()) -> None:
        """Write the formatted output workbook (Detail, Party, Aging, Assumptions, Settlement)."""
        adjustments = list(adjustments)
        wb = Workbook()

        # Sheet 1 - Invoice Detail
        ws = wb.active
        ws.title = "Invoice Detail"
        fills = [cls.OVERDUE_FILL if r.is_overdue else (cls.FLAG_FILL if r.is_flagged else None)
                 for r in results]
        cls._write_table(ws, cls.DETAIL_HEADERS, cls.DETAIL_TYPES,
                         [cls.detail_row(r) for r in results],
                         total_cols=(4, 16, 17, 18, 19, 20, 21, 22), row_fills=fills, wrap_cols=(28, 29))

        # Sheet 2 - Party Summary
        ws2 = wb.create_sheet("Party Summary")
        prow = [[p["party"], p["invoices"], p["amount"], p["paid"], p["outstanding"],
                 p["overdue_count"], p["overdue_amount"], p["interest"], p["repaid"], p["waived"],
                 p["net_interest"], p["payable"]]
                for p in MSMECalculator.party_summary(results)]
        cls._write_table(ws2, ["Party", "Invoices", "Invoice Amount", "Amount Paid", "Outstanding",
                               "Overdue Invoices", "Overdue Amount (Unpaid)", "Interest u/s 16",
                               "Interest Repaid", "Interest Waived", "Net Interest Payable",
                               "Total Payable"],
                         ["text", "int", "money", "money", "money", "int", "money", "money", "money",
                          "money", "money", "money"],
                         prow, total_cols=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11))

        # Sheet 3 - Aging
        ws3 = wb.create_sheet("Aging")
        arow = [[a["bucket"], a["count"], a["amount"], a["outstanding"], a["overdue_amount"],
                 a["interest"]] for a in MSMECalculator.aging_summary(results)]
        cls._write_table(ws3, ["Aging Bucket", "Invoices", "Invoice Amount", "Outstanding",
                               "Overdue Amount (Unpaid)", "Interest u/s 16"],
                         ["text", "int", "money", "money", "money", "money"],
                         arow, total_cols=(1, 2, 3, 4, 5))
        note_row = len(arow) + 4
        ws3.cell(row=note_row, column=1,
                 value="Aging Days = Payment Date (or As-on Date if unpaid) − Invoice Date").font = Font(italic=True)

        # Sheet 4 - Assumptions
        ws4 = wb.create_sheet("Assumptions")
        s = MSMECalculator.summarise(results)
        allowed_rule = ("Yes – Agreed Credit Days (max 45; blank = 45)" if calc.written_agreement
                        else "No – 15 days from acceptance (Sec. 2(b))")
        assumptions = [
            ["RBI Bank Rate (% p.a.)", f"{calc.bank_rate_pct:.2f}"],
            ["Applied Rate u/s 16 (% p.a.)", f"{calc.applicable_rate_pct:.2f} (3 × Bank Rate)"],
            ["Written Agreement with Vendor", allowed_rule],
            ["As-on Date (for unpaid invoices)", fmt_date(calc.as_on_date)],
            ["Run Timestamp", dt.datetime.now().strftime("%d-%m-%Y %H:%M:%S")],
            ["Source File", source_file],
            ["Invoices Processed", str(s["total_invoices"])],
            ["Overdue Invoices", str(s["overdue_count"])],
            ["Flagged Rows", str(s["flagged_count"])],
            ["Total Outstanding (Rs.)", fmt_inr(s["total_outstanding"])],
            ["Total Interest u/s 16 (Rs.)", fmt_inr(s["total_interest"])],
            ["Interest Repaid to Vendors (Rs.)", fmt_inr(s["total_repaid"])],
            ["Interest Waived by Vendors (Rs.)", fmt_inr(s["total_waived"])],
            ["Net Interest Payable (Rs.)", fmt_inr(s["net_interest"])],
            ["Legal Basis", LEGAL_BASIS],
            ["Method", METHOD_TEXT],
            ["Acceptance Date", "Acceptance/Delivery Date if given, else Invoice Date."],
            ["Due Date", "Acceptance Date + Allowed Days; interest from the next day (appointed day)."],
            ["Part Payments", "Payments are appropriated to principal in date order; each tranche bears "
                              "interest to its payment date, the balance to the As-on Date."],
            ["Payments after As-on Date", "Ignored – amount treated as outstanding on the As-on Date."],
            ["Eligibility", "Only Micro & Small enterprises are 'suppliers' u/s 2(n). Medium enterprises "
                            "and Traders get no Sec. 16 interest. Blank category is assumed Micro/Small."],
            ["Income-tax", f"Interest: {SEC23_REMARK}. Principal: {TAX_FLAG_TEXT} (Micro/Small)."],
            ["Rounding", "Computed in Decimal; rounded to 2 decimals only at final output."],
            ["Interest Repayment", "Repayments dated on or before the As-on Date reduce the interest "
                                   "payable; blank amount = full balance. No further interest is computed "
                                   "on unpaid interest after the principal is settled."],
            ["Interest Waiver", WAIVER_RULE],
            ["Disclaimer", ABOUT_TEXT],
        ]
        cls._write_table(ws4, ["Parameter", "Value"], ["text", "text"], assumptions, wrap_cols=(1,))
        ws4.column_dimensions["A"].width = 34
        ws4.column_dimensions["B"].width = 100
        ws4.auto_filter.ref = None

        # Sheet 5 - Interest Settlement (repayment / waiver entries + Sec. 22 disclosure)
        ws5 = wb.create_sheet("Interest Settlement")
        evals = getattr(calc, "adjustment_evaluations", {})
        srows, sfills = [], []
        for e in sorted(adjustments, key=lambda x: (x.party.lower(), x.invoice_no.lower(), x.date or dt.date.max)):
            considered, applied, note = evals.get(e.uid, (False, ZERO, "Not evaluated – click Calculate"))
            srows.append([e.party, e.invoice_no, e.kind, e.date, e.amount,
                          ("Yes" if e.certificate else "No") if e.kind == ADJ_WAIVED else "N.A.",
                          e.cert_ref, "Yes" if considered else "No", applied, note, e.remarks])
            sfills.append(None if considered else cls.FLAG_FILL)
        cls._write_table(ws5, ["Party", "Invoice No.", "Type", "Date (Repayment / Certificate)",
                               "Amount Entered (blank = full)", "Waiver Certificate Available",
                               "Certificate / Reference No.", "Considered", "Amount Applied", "Note",
                               "Remarks"],
                         ["text", "text", "text", "date", "money", "text", "text", "text", "money",
                          "text", "text"],
                         srows, total_cols=(8,) if srows else (), row_fills=sfills, wrap_cols=(9, 10))
        r0 = len(srows) + (4 if srows else 3)
        if not srows:
            ws5.cell(row=2, column=1, value="No interest repayment / waiver recorded.").font = Font(italic=True)
        ws5.cell(row=r0, column=1, value="Sec. 22 MSMED Act – indicative disclosure as at "
                 + fmt_date(calc.as_on_date)).font = Font(bold=True, size=12)
        disclosure = [
            ("(i) Principal amount remaining unpaid to Micro/Small suppliers", s["mse_outstanding"]),
            ("(ii) Interest u/s 16 due on delayed payments (gross)", s["total_interest"]),
            ("(iii) Interest paid u/s 16 (repaid to suppliers)", s["total_repaid"]),
            ("(iv) Interest waived by suppliers (supported by certificate)", s["total_waived"]),
            ("(v) Interest accrued and remaining unpaid (net payable)", s["net_interest"]),
        ]
        for i, (label, val) in enumerate(disclosure, start=r0 + 1):
            ws5.cell(row=i, column=1, value=label).border = cls.BORDER
            ws5.merge_cells(start_row=i, start_column=1, end_row=i, end_column=4)
            c = ws5.cell(row=i, column=5, value=float(q2(val)))
            c.number_format = INR_EXCEL_FORMAT
            c.border = cls.BORDER
            c.font = Font(bold=True)
        ws5.cell(row=r0 + 7, column=1, value=WAIVER_RULE).font = Font(italic=True)

        wb.save(path)


# =============================================================================
# PDF output
# =============================================================================
class PDFExporter:
    """Landscape A4 PDF: settings, summary, invoice detail, party summary, aging."""

    @staticmethod
    def export(path: str, results: list, calc: MSMECalculator, source_file: str = "",
               adjustments: Iterable = ()) -> None:
        adjustments = list(adjustments)
        styles = getSampleStyleSheet()
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7, leading=8.5)
        normal = ParagraphStyle("norm", parent=styles["Normal"], fontSize=9, leading=11)
        title = ParagraphStyle("title", parent=styles["Title"], fontSize=16, spaceAfter=4)
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4)
        run_time = dt.datetime.now().strftime("%d-%m-%Y %H:%M")

        def on_page(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.grey)
            canvas.drawString(12 * mm, 7 * mm, f"{APP_NAME} v{APP_VERSION} – generated {run_time}")
            canvas.drawRightString(285 * mm, 7 * mm, f"Page {doc.page}")
            canvas.restoreState()

        def table(data, widths, num_cols=(), overdue_rows=(), total_row=False):
            t = Table(data, colWidths=widths, repeatRows=1)
            st = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
            for c in num_cols:
                st.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
            for r in overdue_rows:
                st.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F8CBAD")))
            if total_row:
                st += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                       ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E1F2"))]
            t.setStyle(TableStyle(st))
            return t

        s = MSMECalculator.summarise(results)
        story = [
            Paragraph("MSME Interest Calculator – Interest on Delayed Payments u/s 16 MSMED Act, 2006", title),
            Paragraph(
                f"<b>RBI Bank Rate:</b> {calc.bank_rate_pct:.2f}% &nbsp; | &nbsp; <b>Applied Rate:</b> "
                f"{calc.applicable_rate_pct:.2f}% p.a. (3 × Bank Rate, monthly rests) &nbsp; | &nbsp; "
                f"<b>Written Agreement:</b> {'Yes (max 45 days)' if calc.written_agreement else 'No (15 days)'}"
                f" &nbsp; | &nbsp; <b>As-on Date:</b> {fmt_date(calc.as_on_date)}", normal),
            Paragraph(f"<b>Source:</b> {xml_escape(os.path.basename(source_file) or '-')}", normal),
            Spacer(1, 6),
        ]
        summary = [["Invoices", "Overdue", "Flagged", "Invoice Value (Rs.)", "Outstanding (Rs.)",
                    "Interest u/s 16 (Rs.)", "Repaid / Waived (Rs.)", "Net Interest (Rs.)",
                    "Total Payable (Rs.)"],
                   [str(s["total_invoices"]), str(s["overdue_count"]), str(s["flagged_count"]),
                    fmt_inr(s["total_amount"]), fmt_inr(s["total_outstanding"]),
                    fmt_inr(s["total_interest"]), fmt_inr(s["total_repaid"] + s["total_waived"]),
                    fmt_inr(s["net_interest"]), fmt_inr(s["total_payable"])]]
        story.append(table(summary, [w * mm for w in (20, 18, 18, 33, 33, 33, 35, 32, 33)],
                           num_cols=range(9)))

        # Invoice detail
        story.append(Paragraph("Invoice Detail", h2))
        head = ["Party", "Inv No.", "Inv Date", "Amount", "Due Date", "Paid/As-on", "Aging",
                "Delay", "M + D", "Outstanding", "Interest", "Paid/Waived", "Net Int.",
                "Total Payable", "Status", "43B(h)"]
        data, overdue = [head], []
        for i, r in enumerate(results, start=1):
            rec = r.record
            data.append([
                Paragraph(xml_escape(rec.party), small), Paragraph(xml_escape(rec.invoice_no), small),
                fmt_date(rec.invoice_date), fmt_inr(rec.amount), fmt_date(r.due_date),
                fmt_date(r.end_date), "" if r.aging_days is None else str(r.aging_days),
                str(r.delay_days), f"{r.months}m+{r.days}d" if r.delay_days else "-",
                fmt_inr(r.outstanding), fmt_inr(r.interest),
                fmt_inr(r.interest_repaid + r.interest_waived), fmt_inr(r.net_interest),
                fmt_inr(r.total_payable),
                Paragraph(xml_escape(r.status), small),
                Paragraph(xml_escape("Yes" if r.tax_flag.startswith(("Disallowable", "If Micro"))
                                     else ("Paid late" if r.tax_flag.startswith("43B") else
                                           r.tax_flag or "-")), small),
            ])
            if r.is_overdue:
                overdue.append(i)
        data.append(["TOTAL", "", "", fmt_inr(s["total_amount"]), "", "", "", "", "",
                     fmt_inr(s["total_outstanding"]), fmt_inr(s["total_interest"]),
                     fmt_inr(s["total_repaid"] + s["total_waived"]), fmt_inr(s["net_interest"]),
                     fmt_inr(s["total_payable"]), "", ""])
        widths = [32, 17, 16, 21, 16, 16, 10, 10, 13, 21, 18, 18, 18, 20, 19, 12]
        story.append(table(data, [w * mm for w in widths], num_cols=(3, 6, 7, 9, 10, 11, 12, 13),
                           overdue_rows=overdue, total_row=True))

        # Party summary
        story += [PageBreak(), Paragraph("Party Summary", h2)]
        pdata = [["Party", "Invoices", "Invoice Amount", "Outstanding", "Overdue (Unpaid)",
                  "Interest u/s 16", "Repaid / Waived", "Net Interest", "Total Payable"]]
        for p in MSMECalculator.party_summary(results):
            pdata.append([Paragraph(xml_escape(p["party"]), small), str(p["invoices"]),
                          fmt_inr(p["amount"]), fmt_inr(p["outstanding"]), fmt_inr(p["overdue_amount"]),
                          fmt_inr(p["interest"]), fmt_inr(p["repaid"] + p["waived"]),
                          fmt_inr(p["net_interest"]), fmt_inr(p["payable"])])
        story.append(table(pdata, [w * mm for w in (61, 16, 28, 28, 28, 28, 28, 28, 30)],
                           num_cols=range(1, 9)))

        # Interest repayment / waiver entries
        if adjustments:
            evals = getattr(calc, "adjustment_evaluations", {})
            story.append(Paragraph("Interest Repayment / Waiver by Vendor", h2))
            adata = [["Party", "Inv No.", "Type", "Date", "Amount", "Certificate", "Reference",
                      "Considered", "Applied", "Note"]]
            not_considered = []
            for i, e in enumerate(sorted(adjustments, key=lambda x: (x.party.lower(), x.invoice_no.lower())),
                                  start=1):
                considered, applied, note = evals.get(e.uid, (False, ZERO, "Not evaluated"))
                adata.append([Paragraph(xml_escape(e.party), small), Paragraph(xml_escape(e.invoice_no), small),
                              e.kind.replace("Interest ", ""), fmt_date(e.date),
                              fmt_inr(e.amount) if e.amount is not None else "Full",
                              ("Yes" if e.certificate else "No") if e.kind == ADJ_WAIVED else "N.A.",
                              Paragraph(xml_escape(e.cert_ref), small), "Yes" if considered else "No",
                              fmt_inr(applied), Paragraph(xml_escape(note), small)])
                if not considered:
                    not_considered.append(i)
            t = table(adata, [w * mm for w in (42, 22, 18, 18, 22, 18, 28, 17, 22, 70)],
                      num_cols=(4, 8))
            t.setStyle(TableStyle([("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FFF2CC"))
                                   for r in not_considered]))
            story.append(t)
            story.append(Paragraph("<i>" + xml_escape(WAIVER_RULE) + "</i>", small))

        # Sec. 22 disclosure
        story.append(Paragraph(f"Sec. 22 MSMED Act – indicative disclosure as at {fmt_date(calc.as_on_date)}", h2))
        ddata = [["Particulars", "Rs."],
                 ["(i) Principal remaining unpaid to Micro/Small suppliers", fmt_inr(s["mse_outstanding"])],
                 ["(ii) Interest u/s 16 due on delayed payments (gross)", fmt_inr(s["total_interest"])],
                 ["(iii) Interest paid u/s 16 (repaid to suppliers)", fmt_inr(s["total_repaid"])],
                 ["(iv) Interest waived by suppliers (supported by certificate)", fmt_inr(s["total_waived"])],
                 ["(v) Interest accrued and remaining unpaid (net payable)", fmt_inr(s["net_interest"])]]
        story.append(table(ddata, [120 * mm, 40 * mm], num_cols=(1,)))

        # Aging (heading kept on the same page as its table)
        adata = [["Bucket", "Invoices", "Invoice Amount", "Outstanding", "Overdue (Unpaid)", "Interest"]]
        for a in MSMECalculator.aging_summary(results):
            adata.append([a["bucket"], str(a["count"]), fmt_inr(a["amount"]), fmt_inr(a["outstanding"]),
                          fmt_inr(a["overdue_amount"]), fmt_inr(a["interest"])])
        story.append(KeepTogether([
            Paragraph("Aging (Payment / As-on Date − Invoice Date)", h2),
            table(adata, [55 * mm, 20 * mm, 40 * mm, 40 * mm, 40 * mm, 40 * mm], num_cols=range(1, 6))]))

        # Notes
        story += [
            Spacer(1, 10),
            Paragraph("<b>Method:</b> " + xml_escape(METHOD_TEXT), normal),
            Paragraph("<b>Income-tax:</b> Interest – " + xml_escape(SEC23_REMARK) + ". Principal owed to "
                      "Micro/Small enterprises beyond the Sec. 15 time limit – " + xml_escape(TAX_FLAG_TEXT)
                      + ".", normal),
            Paragraph("<b>Legal basis:</b> " + xml_escape(LEGAL_BASIS), normal),
            Spacer(1, 4),
            Paragraph("<i>" + xml_escape(ABOUT_TEXT) + "</i>", normal),
        ]
        doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                                topMargin=10 * mm, bottomMargin=12 * mm, title=APP_NAME,
                                author=APP_NAME)
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


# =============================================================================
# Self-test (mandatory statutory test case + extra checks)
# =============================================================================
def run_self_test() -> tuple:
    """Run the mandatory test case and sanity checks. Returns (all_passed, report_text)."""
    lines, ok_all = [], True

    def check(label: str, actual: Any, expected: Any) -> None:
        nonlocal ok_all
        ok = actual == expected
        ok_all &= ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}: got {actual!r}, expected {expected!r}")

    d = dt.date
    base = InvoiceRecord(row_no=2, party="Test Supplier", invoice_no="T-1", invoice_date=d(2026, 4, 1),
                         amount=Decimal("100000"), acceptance_date=d(2026, 4, 1),
                         payments=[Payment(d(2026, 6, 30), None, 2)], category="micro", udyam_no="UDYAM-XX")

    lines.append("Mandatory test: Rs.1,00,000 | Invoice/Acceptance 01-04-2026 | Paid 30-06-2026 | Bank Rate 5.75%")
    # Case 1 - no written agreement
    r1 = MSMECalculator("5.75", False, d(2026, 11, 19)).calculate(base)
    check("No agreement – Due Date", fmt_date(r1.due_date), "16-04-2026")
    check("No agreement – Delay Days", r1.delay_days, 75)
    check("No agreement – Months + Days", (r1.months, r1.days), (2, 14))
    check("No agreement – Interest", fmt_inr(r1.interest), "3,576.47")
    check("No agreement – Aging Days", r1.aging_days, 90)
    check("No agreement – Status", r1.status, STATUS_PAID_LATE)
    # Case 2 - written agreement, credit days blank -> 45
    r2 = MSMECalculator("5.75", True, d(2026, 11, 19)).calculate(base)
    check("Agreement – Due Date", fmt_date(r2.due_date), "16-05-2026")
    check("Agreement – Delay Days", r2.delay_days, 45)
    check("Agreement – Months + Days", (r2.months, r2.days), (1, 14))
    check("Agreement – Interest", fmt_inr(r2.interest), "2,108.65")
    check("Agreement – Aging Days", r2.aging_days, 90)

    lines.append("Additional checks:")
    check("Applicable rate", MSMECalculator("5.75", False, d(2026, 1, 1)).applicable_rate_pct, Decimal("17.25"))
    check("Date DD-MM-YYYY", ExcelHandler.parse_date("01-04-2026"), d(2026, 4, 1))
    check("Date DD/MM/YYYY", ExcelHandler.parse_date("01/04/2026"), d(2026, 4, 1))
    check("Date Excel serial", ExcelHandler.parse_date(46113), d(2026, 4, 1))
    check("Header match 'invoice no.'", ExcelHandler.map_columns(["INVOICE  No."]), {"invoice_no": 0})
    check("Amount '1,00,000.00'", ExcelHandler.parse_amount("₹ 1,00,000.00"), Decimal("100000.00"))
    check("Indian format", fmt_inr(Decimal("12345678.456")), "1,23,45,678.46")

    capped = InvoiceRecord(**{**base.__dict__, "agreed_days": 60, "payments": list(base.payments)})
    rc = MSMECalculator("5.75", True, d(2026, 11, 19)).calculate(capped)
    check("Agreed 60 days capped at 45", rc.allowed_days, 45)
    check("Cap is flagged", rc.is_flagged, True)

    trader = InvoiceRecord(**{**base.__dict__, "category": "trader", "payments": list(base.payments)})
    check("Trader – no interest", MSMECalculator("5.75", False, d(2026, 11, 19)).calculate(trader).interest, ZERO)

    calc = MSMECalculator("5.75", False, d(2026, 11, 19))
    part = InvoiceRecord(**{**base.__dict__, "payments": [Payment(d(2026, 4, 30), Decimal("40000"), 2),
                                                          Payment(d(2026, 6, 30), Decimal("60000"), 3)]})
    expected = (calc.compound_interest(Decimal("40000"), d(2026, 4, 16), d(2026, 4, 30))
                + calc.compound_interest(Decimal("60000"), d(2026, 4, 16), d(2026, 6, 30)))
    rp = calc.calculate(part)
    check("Part payment – reducing balance", fmt_inr(rp.interest), fmt_inr(expected))
    check("Part payment – fully paid", rp.outstanding, ZERO)

    unpaid = InvoiceRecord(**{**base.__dict__, "payments": []})
    ru = calc.calculate(unpaid)
    check("Unpaid – status", ru.status, STATUS_UNPAID)
    check("Unpaid – 43B(h) flag", ru.tax_flag, TAX_FLAG_TEXT)

    lines.append("Interest repayment / waiver checks (on the Rs.3,576.47 case, As-on 19-11-2026):")

    def adj(kind, date, amount=None, cert=False):
        return InterestAdjustment("Test Supplier", "T-1", kind, date,
                                  None if amount is None else Decimal(amount), cert)

    def net_after(*entries):
        return calc.calculate(base, entries)

    ra = net_after(adj(ADJ_REPAID, d(2026, 7, 15), "1000"))
    check("Repaid 1,000 – net interest", fmt_inr(ra.net_interest), "2,576.47")
    check("Repaid 1,000 – interest status", ra.interest_status, INT_STATUS_PARTLY)
    rb = net_after(adj(ADJ_REPAID, d(2026, 7, 15)))
    check("Repaid in full (blank amount) – net", fmt_inr(rb.net_interest), "0.00")
    rw = net_after(adj(ADJ_WAIVED, d(2026, 10, 1), cert=True))
    check("Waiver WITH certificate – net", fmt_inr(rw.net_interest), "0.00")
    check("Waiver WITH certificate – waived", fmt_inr(rw.interest_waived), "3,576.47")
    check("Waiver WITH certificate – no Sec. 23 remark", SEC23_REMARK in rw.remarks, False)
    rn = net_after(adj(ADJ_WAIVED, d(2026, 10, 1), cert=False))
    check("Waiver WITHOUT certificate – not considered", fmt_inr(rn.net_interest), "3,576.47")
    rf = net_after(adj(ADJ_WAIVED, d(2026, 12, 1), cert=True))
    check("Waiver certificate after As-on Date – not considered", fmt_inr(rf.net_interest), "3,576.47")
    rm = net_after(adj(ADJ_REPAID, d(2026, 7, 15), "1576.47"), adj(ADJ_WAIVED, d(2026, 8, 1), cert=True))
    check("Repaid 1,576.47 + waiver of balance – net", fmt_inr(rm.net_interest), "0.00")
    check("Repaid + waiver – waived amount", fmt_inr(rm.interest_waived), "2,000.00")
    check("Repaid + waiver – status", rm.interest_status, INT_STATUS_PAID_WAIVED)
    check("Repaid + waiver – total payable", fmt_inr(rm.total_payable), "0.00")

    lines.append(f"RESULT: {'ALL TESTS PASSED' if ok_all else 'SOME TESTS FAILED'}")
    return ok_all, "\n".join(lines)


# =============================================================================
# GUI (PyQt5)
# =============================================================================
from PyQt5.QtCore import QDate, Qt                                   # noqa: E402
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon                 # noqa: E402
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QApplication,  # noqa: E402
                             QButtonGroup, QCheckBox, QComboBox, QCompleter, QDateEdit,
                             QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
                             QMessageBox, QPushButton, QRadioButton, QTableWidget,
                             QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)


class SortableItem(QTableWidgetItem):
    """Table item that sorts by a hidden key (numbers / dates sort correctly)."""

    def __init__(self, text: str, sort_key: Any = None):
        super().__init__(text)
        self.setData(Qt.UserRole, sort_key if sort_key is not None else text.lower())

    def __lt__(self, other: QTableWidgetItem) -> bool:
        a, b = self.data(Qt.UserRole), other.data(Qt.UserRole)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


def gui_safe(func):
    """Decorator: any exception inside a GUI slot is shown in a QMessageBox, never a crash."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self)
        except Exception as exc:                                   # noqa: BLE001
            self.show_error(f"{func.__name__.replace('_', ' ').strip().title()} failed", exc)
            return None
    return wrapper


class SummaryCard(QFrame):
    """Small card with a caption and a big value."""

    def __init__(self, caption: str, accent: str):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(
            f"#card {{ background:#FFFFFF; border:1px solid #D0D7DE; border-left:5px solid {accent};"
            f" border-radius:6px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self.caption = QLabel(caption)
        self.caption.setStyleSheet("color:#57606A; font-size:9pt;")
        self.value = QLabel("–")
        self.value.setStyleSheet(f"color:{accent}; font-size:16pt; font-weight:bold;")
        lay.addWidget(self.caption)
        lay.addWidget(self.value)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class MainWindow(QMainWindow):
    """Single-window GUI."""

    # (header, index into ExcelHandler.detail_row, type)
    TABLE_COLUMNS = [
        ("Row", 0, "int"), ("Party", 1, "text"), ("Invoice No.", 2, "text"),
        ("Invoice Date", 3, "date"), ("Amount", 4, "money"), ("Acceptance Date", 5, "date"),
        ("Allowed Days", 6, "int"), ("Due Date", 7, "date"), ("Payment/As-on", 9, "date"),
        ("Aging Days", 11, "int"), ("Delay Days", 12, "int"), ("Months", 13, "int"),
        ("Days", 14, "int"), ("Rate %", 15, "pct"), ("Amount Paid", 16, "money"),
        ("Outstanding", 17, "money"), ("Interest", 18, "money"), ("Int. Repaid", 19, "money"),
        ("Int. Waived", 20, "money"), ("Net Interest", 21, "money"), ("Total Payable", 22, "money"),
        ("Status", 23, "text"), ("Interest Status", 24, "text"), ("Category", 25, "text"),
        ("43B(h) Flag", 27, "text"), ("Remarks", 28, "text"), ("Validation Flags", 29, "text"),
    ]
    STATUS_COL = [c[0] for c in TABLE_COLUMNS].index("Status")

    ADJ_COLUMNS = ["Party", "Invoice No.", "Gross Interest", "Type", "Date", "Amount Entered",
                   "Waiver Certificate", "Certificate / Ref No.", "Considered", "Amount Applied",
                   "Note", "Remarks"]

    def __init__(self):
        super().__init__()
        self.input_path = ""
        self.records: list = []
        self.results: list = []
        self.adjustments: list = []           # InterestAdjustment entries (manual tab)
        self._combo_keys: list = []           # invoice keys behind the invoice combo box
        self.calc: Optional[MSMECalculator] = None

        self.setWindowTitle(f"{APP_NAME} – MSMED Act, 2006 (Sec. 15, 16 & 23)")
        icon = resource_path("msme.ico")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))
        self.resize(1400, 820)
        self._build_menu()
        self._build_ui()
        self.update_rate_label()
        self.statusBar().showMessage("Ready – upload an Excel/CSV file or download the template.")

    # ---- UI construction ---------------------------------------------------
    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        for text, slot in (("&Upload Excel…", self.on_upload), ("Download &Template…", self.on_template),
                           ("Export to &Excel…", self.on_export_excel),
                           ("Export to &PDF…", self.on_export_pdf)):
            act = QAction(text, self)
            act.triggered.connect(lambda _=False, s=slot: s())
            file_menu.addAction(act)
        file_menu.addSeparator()
        quit_act = QAction("E&xit", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)
        help_menu = bar.addMenu("&Help")
        for text, slot in (("Run &Self-Test", self.on_self_test), ("&About", self.on_about)):
            act = QAction(text, self)
            act.triggered.connect(lambda _=False, s=slot: s())
            help_menu.addAction(act)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # File row
        file_box = QGroupBox("Input File")
        fl = QHBoxLayout(file_box)
        self.btn_upload = QPushButton("📂  Upload Excel")
        self.btn_upload.clicked.connect(lambda: self.on_upload())
        self.lbl_path = QLabel("No file selected (.xlsx / .xls / .csv)")
        self.lbl_path.setStyleSheet("color:#57606A;")
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_template = QPushButton("⬇  Download Template")
        self.btn_template.clicked.connect(lambda: self.on_template())
        fl.addWidget(self.btn_upload)
        fl.addWidget(self.lbl_path, 1)
        fl.addWidget(self.btn_template)
        root.addWidget(file_box)

        # Parameters row
        par_box = QGroupBox("Parameters")
        pl = QHBoxLayout(par_box)
        pl.addWidget(QLabel("RBI Bank Rate (% p.a.):"))
        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0.25, 50.0)
        self.spin_rate.setDecimals(2)
        self.spin_rate.setSingleStep(0.25)
        self.spin_rate.setValue(float(DEFAULT_BANK_RATE))
        self.spin_rate.valueChanged.connect(lambda _v: self.on_params_changed())
        pl.addWidget(self.spin_rate)
        self.lbl_rate = QLabel()
        self.lbl_rate.setStyleSheet("font-weight:bold; color:#1F4E78;")
        pl.addWidget(self.lbl_rate)
        pl.addSpacing(24)

        pl.addWidget(QLabel("Written Agreement with Vendor:"))
        self.rb_yes = QRadioButton("Yes (agreed days, max 45)")
        self.rb_no = QRadioButton("No (15 days)")
        self.rb_no.setChecked(True)
        self.grp_agree = QButtonGroup(self)
        self.grp_agree.addButton(self.rb_yes)
        self.grp_agree.addButton(self.rb_no)
        self.rb_yes.toggled.connect(lambda _c: self.on_params_changed())
        pl.addWidget(self.rb_yes)
        pl.addWidget(self.rb_no)
        pl.addSpacing(24)

        pl.addWidget(QLabel("As-on Date:"))
        self.date_ason = QDateEdit(QDate.currentDate())
        self.date_ason.setCalendarPopup(True)
        self.date_ason.setDisplayFormat("dd-MM-yyyy")
        self.date_ason.dateChanged.connect(lambda _d: self.on_params_changed())
        pl.addWidget(self.date_ason)
        pl.addStretch(1)

        self.btn_calc = QPushButton("▶  Calculate")
        self.btn_calc.setStyleSheet("QPushButton { background:#1F4E78; color:white; font-weight:bold;"
                                    " padding:6px 18px; border-radius:4px; }"
                                    "QPushButton:hover { background:#2E6DA4; }")
        self.btn_calc.clicked.connect(lambda: self.on_calculate())
        pl.addWidget(self.btn_calc)
        root.addWidget(par_box)

        # Summary cards
        cards = QHBoxLayout()
        self.card_total = SummaryCard("Total Invoices", "#1F4E78")
        self.card_overdue = SummaryCard("Overdue Count", "#C00000")
        self.card_outstanding = SummaryCard("Total Outstanding (₹)", "#B85C00")
        self.card_interest = SummaryCard("Total Interest u/s 16 (₹)", "#2E7D32")
        self.card_net = SummaryCard("Net Interest Payable (₹) after repaid / waived", "#6A1B9A")
        for c in (self.card_total, self.card_overdue, self.card_outstanding, self.card_interest,
                  self.card_net):
            cards.addWidget(c)
        root.addLayout(cards)

        # Tabs: results | manual interest repayment / waiver
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # Results table
        self.table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.TABLE_COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.table, "📋  Interest Calculation")
        self.tabs.addTab(self._build_adjustment_tab(), "✍  Interest Repayment / Waiver (Manual)")

        # Action buttons
        actions = QHBoxLayout()
        self.btn_xlsx = QPushButton("📊  Export to Excel")
        self.btn_xlsx.clicked.connect(lambda: self.on_export_excel())
        self.btn_pdf = QPushButton("📄  Export to PDF")
        self.btn_pdf.clicked.connect(lambda: self.on_export_pdf())
        self.btn_test = QPushButton("✔  Run Self-Test")
        self.btn_test.clicked.connect(lambda: self.on_self_test())
        self.btn_about = QPushButton("ℹ  About")
        self.btn_about.clicked.connect(lambda: self.on_about())
        for b in (self.btn_xlsx, self.btn_pdf):
            b.setEnabled(False)
            actions.addWidget(b)
        actions.addStretch(1)
        actions.addWidget(self.btn_test)
        actions.addWidget(self.btn_about)
        root.addLayout(actions)

        # Footer
        footer = QLabel(ABOUT_TEXT)
        footer.setWordWrap(True)
        footer.setStyleSheet("color:#57606A; font-size:8pt; font-style:italic; padding:2px;")
        root.addWidget(footer)

        self.setCentralWidget(central)

    def _build_adjustment_tab(self) -> QWidget:
        """Manual tab: record interest repaid to the vendor, or waived by the vendor."""
        page = QWidget()
        v = QVBoxLayout(page)

        intro = QLabel(
            "Record interest u/s 16 <b>repaid to the vendor</b> or <b>waived by the vendor</b>. "
            "Entries dated after the As-on Date are not considered. "
            "<b>A waiver is considered only if the vendor's waiver certificate is available as at the "
            "As-on Date</b> (certificate date on or before the As-on Date); otherwise the interest "
            "remains payable. Leave Amount blank for the full interest balance.")
        intro.setWordWrap(True)
        intro.setStyleSheet("background:#EEF4FB; border:1px solid #C9DAEE; border-radius:4px; padding:6px;")
        v.addWidget(intro)

        form = QGroupBox("Add / edit entry")
        g = QGridLayout(form)
        g.addWidget(QLabel("Invoice:"), 0, 0)
        self.cmb_invoice = QComboBox()
        self.cmb_invoice.setEditable(True)
        self.cmb_invoice.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_invoice.completer().setFilterMode(Qt.MatchContains)
        self.cmb_invoice.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.cmb_invoice.lineEdit().setPlaceholderText("Upload a file and click Calculate, then pick an invoice")
        g.addWidget(self.cmb_invoice, 0, 1, 1, 5)

        g.addWidget(QLabel("Type:"), 1, 0)
        self.rb_adj_repaid = QRadioButton("Interest Repaid to Vendor")
        self.rb_adj_waived = QRadioButton("Interest Waived by Vendor")
        self.rb_adj_repaid.setChecked(True)
        grp = QButtonGroup(page)
        grp.addButton(self.rb_adj_repaid)
        grp.addButton(self.rb_adj_waived)
        self.rb_adj_waived.toggled.connect(lambda _c: self._on_adj_type_changed())
        g.addWidget(self.rb_adj_repaid, 1, 1)
        g.addWidget(self.rb_adj_waived, 1, 2)

        self.lbl_adj_date = QLabel("Repayment Date:")
        g.addWidget(self.lbl_adj_date, 2, 0)
        self.adj_date = QDateEdit(QDate.currentDate())
        self.adj_date.setCalendarPopup(True)
        self.adj_date.setDisplayFormat("dd-MM-yyyy")
        g.addWidget(self.adj_date, 2, 1)
        g.addWidget(QLabel("Amount (₹):"), 2, 2)
        self.adj_amount = QLineEdit()
        self.adj_amount.setPlaceholderText("Blank = full interest balance")
        g.addWidget(self.adj_amount, 2, 3)

        self.chk_cert = QCheckBox("Waiver certificate received from vendor and available as at As-on Date")
        g.addWidget(self.chk_cert, 3, 1, 1, 3)
        g.addWidget(QLabel("Reference:"), 4, 0)
        self.adj_ref = QLineEdit()
        self.adj_ref.setPlaceholderText("UTR / cheque no. (repayment) or certificate no. (waiver)")
        g.addWidget(self.adj_ref, 4, 1)
        g.addWidget(QLabel("Remarks:"), 4, 2)
        self.adj_remarks = QLineEdit()
        g.addWidget(self.adj_remarks, 4, 3, 1, 3)

        btns = QHBoxLayout()
        self.btn_adj_add = QPushButton("➕  Add Entry")
        self.btn_adj_add.clicked.connect(lambda: self.on_adj_add())
        self.btn_adj_update = QPushButton("✎  Update Selected")
        self.btn_adj_update.clicked.connect(lambda: self.on_adj_update())
        self.btn_adj_delete = QPushButton("🗑  Delete Selected")
        self.btn_adj_delete.clicked.connect(lambda: self.on_adj_delete())
        self.btn_adj_clear = QPushButton("Clear Form")
        self.btn_adj_clear.clicked.connect(lambda: self._clear_adj_form())
        for b in (self.btn_adj_add, self.btn_adj_update, self.btn_adj_delete, self.btn_adj_clear):
            btns.addWidget(b)
        btns.addStretch(1)
        g.addLayout(btns, 5, 0, 1, 6)
        g.setColumnStretch(3, 1)
        g.setColumnStretch(5, 1)
        v.addWidget(form)

        self.adj_table = QTableWidget(0, len(self.ADJ_COLUMNS))
        self.adj_table.setHorizontalHeaderLabels(self.ADJ_COLUMNS)
        self.adj_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.adj_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.adj_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.adj_table.verticalHeader().setVisible(False)
        self.adj_table.horizontalHeader().setStretchLastSection(True)
        self.adj_table.itemSelectionChanged.connect(self._on_adj_selected)
        v.addWidget(self.adj_table, 1)

        bottom = QHBoxLayout()
        self.btn_adj_import = QPushButton("📥  Import Entries…")
        self.btn_adj_import.clicked.connect(lambda: self.on_adj_import())
        self.btn_adj_export = QPushButton("📤  Save Entries…")
        self.btn_adj_export.clicked.connect(lambda: self.on_adj_export())
        bottom.addWidget(self.btn_adj_import)
        bottom.addWidget(self.btn_adj_export)
        bottom.addStretch(1)
        self.lbl_adj_summary = QLabel("No entries.")
        self.lbl_adj_summary.setStyleSheet("font-weight:bold; color:#1F4E78;")
        bottom.addWidget(self.lbl_adj_summary)
        v.addLayout(bottom)

        self._on_adj_type_changed()
        return page

    # ---- manual repayment / waiver tab -------------------------------------
    def _on_adj_type_changed(self) -> None:
        waiver = self.rb_adj_waived.isChecked()
        self.lbl_adj_date.setText("Waiver Certificate Date:" if waiver else "Repayment Date:")
        self.chk_cert.setEnabled(waiver)
        if not waiver:
            self.chk_cert.setChecked(False)

    def _fill_invoice_combo(self) -> None:
        """List computed invoices (those with interest first) in the invoice picker."""
        current = self._selected_invoice_key()
        self.cmb_invoice.blockSignals(True)
        self.cmb_invoice.clear()
        self._combo_keys = []
        ordered = sorted(self.results, key=lambda r: (q2(r.interest) == 0, r.record.party.lower(),
                                                      r.record.invoice_no.lower()))
        for r in ordered:
            if r.status == STATUS_ERROR:
                continue
            self.cmb_invoice.addItem(
                f"{r.record.party}  |  {r.record.invoice_no}  |  Interest ₹{fmt_inr(r.interest)}"
                f"  |  Net payable ₹{fmt_inr(r.net_interest)}")
            self._combo_keys.append(r.record.key)
        if current in self._combo_keys:
            self.cmb_invoice.setCurrentIndex(self._combo_keys.index(current))
        else:
            self.cmb_invoice.setCurrentIndex(-1)
        self.cmb_invoice.blockSignals(False)

    def _selected_invoice_key(self) -> Optional[tuple]:
        idx = self.cmb_invoice.currentIndex()
        if 0 <= idx < len(self._combo_keys) and self.cmb_invoice.currentText() == self.cmb_invoice.itemText(idx):
            return self._combo_keys[idx]
        return None

    def _entry_from_form(self, uid: Optional[int] = None) -> Optional[InterestAdjustment]:
        """Validate the form and build an entry (None if the user cancelled)."""
        if not self.results:
            raise ValueError("Upload a file and click Calculate before recording repayment / waiver.")
        key = self._selected_invoice_key()
        if key is None:
            raise ValueError("Select an invoice from the list.")
        res = next(r for r in self.results if r.record.key == key)
        amount = ExcelHandler.parse_amount(self.adj_amount.text())
        if amount is not None and amount <= 0:
            raise ValueError("Amount must be greater than zero (or blank for the full balance).")
        q = self.adj_date.date()
        date = dt.date(q.year(), q.month(), q.day())
        waiver = self.rb_adj_waived.isChecked()
        if waiver and not self.chk_cert.isChecked():
            reply = QMessageBox.question(
                self, APP_NAME,
                "The vendor's waiver certificate is NOT marked as available.\n\n"
                "The waiver will be recorded but NOT considered – the interest remains payable "
                "u/s 16 until the certificate is received.\n\nRecord it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return None
        if self.calc and date > self.calc.as_on_date:
            QMessageBox.information(self, APP_NAME, f"The date is after the As-on Date "
                                    f"{fmt_date(self.calc.as_on_date)} – the entry will not be considered "
                                    "until the As-on Date is moved on.")
        entry = InterestAdjustment(
            party=res.record.party, invoice_no=res.record.invoice_no,
            kind=ADJ_WAIVED if waiver else ADJ_REPAID, date=date, amount=amount,
            certificate=waiver and self.chk_cert.isChecked(),
            cert_ref=self.adj_ref.text().strip(), remarks=self.adj_remarks.text().strip())
        if uid is not None:
            entry.uid = uid
        return entry

    def _selected_adj_uid(self) -> Optional[int]:
        rows = self.adj_table.selectionModel().selectedRows() if self.adj_table.selectionModel() else []
        if not rows:
            return None
        item = self.adj_table.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    @gui_safe
    def on_adj_add(self) -> None:
        entry = self._entry_from_form()
        if entry is None:
            return
        self.adjustments.append(entry)
        self._after_adjustment_change(f"{entry.kind} entry added for {entry.party} / {entry.invoice_no}.")
        self._clear_adj_form()

    @gui_safe
    def on_adj_update(self) -> None:
        uid = self._selected_adj_uid()
        if uid is None:
            QMessageBox.information(self, APP_NAME, "Select an entry in the list to update.")
            return
        entry = self._entry_from_form(uid)
        if entry is None:
            return
        self.adjustments = [entry if e.uid == uid else e for e in self.adjustments]
        self._after_adjustment_change("Entry updated.")

    @gui_safe
    def on_adj_delete(self) -> None:
        uid = self._selected_adj_uid()
        if uid is None:
            QMessageBox.information(self, APP_NAME, "Select an entry in the list to delete.")
            return
        if QMessageBox.question(self, APP_NAME, "Delete the selected entry?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.adjustments = [e for e in self.adjustments if e.uid != uid]
        self._after_adjustment_change("Entry deleted.")

    def _clear_adj_form(self) -> None:
        self.adj_amount.clear()
        self.adj_ref.clear()
        self.adj_remarks.clear()
        self.chk_cert.setChecked(False)
        self.rb_adj_repaid.setChecked(True)
        self.adj_table.clearSelection()

    def _on_adj_selected(self) -> None:
        """Load the selected entry into the form for editing."""
        uid = self._selected_adj_uid()
        e = next((x for x in self.adjustments if x.uid == uid), None)
        if e is None:
            return
        if e.key in self._combo_keys:
            self.cmb_invoice.setCurrentIndex(self._combo_keys.index(e.key))
        (self.rb_adj_waived if e.kind == ADJ_WAIVED else self.rb_adj_repaid).setChecked(True)
        if e.date:
            self.adj_date.setDate(QDate(e.date.year, e.date.month, e.date.day))
        self.adj_amount.setText("" if e.amount is None else f"{q2(e.amount)}")
        self.chk_cert.setChecked(e.certificate)
        self.adj_ref.setText(e.cert_ref)
        self.adj_remarks.setText(e.remarks)

    def _after_adjustment_change(self, message: str) -> None:
        if self.records:
            self._run_calculation()
        else:
            self._fill_adj_table()
        self.statusBar().showMessage(message + "  Totals and reports updated.", 10000)

    def _fill_adj_table(self) -> None:
        evals = getattr(self.calc, "adjustment_evaluations", {}) if self.calc else {}
        gross_by_key = {r.record.key: r.interest for r in self.results}
        self.adj_table.setRowCount(len(self.adjustments))
        yellow = QBrush(QColor("#FFF3CD"))
        green = QBrush(QColor("#E2F0D9"))
        repaid = waived = ZERO
        for row, e in enumerate(sorted(self.adjustments, key=lambda x: (x.party.lower(), x.invoice_no.lower(),
                                                                         x.date or dt.date.max))):
            considered, applied, note = evals.get(e.uid, (False, ZERO, "Not evaluated – click Calculate"))
            if considered:
                if e.kind == ADJ_WAIVED:
                    waived += applied
                else:
                    repaid += applied
            gross = gross_by_key.get(e.key)
            values = [e.party, e.invoice_no, "" if gross is None else fmt_inr(gross), e.kind,
                      fmt_date(e.date), "Full balance" if e.amount is None else fmt_inr(e.amount),
                      ("Available" if e.certificate else "NOT available") if e.kind == ADJ_WAIVED else "N.A.",
                      e.cert_ref, "Yes" if considered else "No", fmt_inr(applied), note, e.remarks]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.UserRole, e.uid)
                if col in (2, 5, 9):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setBackground(green if considered else yellow)
                if col == 10:
                    item.setToolTip(text)
                self.adj_table.setItem(row, col, item)
        self.adj_table.resizeColumnsToContents()
        for c in range(self.adj_table.columnCount()):
            if self.adj_table.columnWidth(c) > 300:
                self.adj_table.setColumnWidth(c, 300)
        if self.adjustments:
            not_used = sum(1 for e in self.adjustments if not evals.get(e.uid, (False,))[0])
            self.lbl_adj_summary.setText(
                f"{len(self.adjustments)} entr{'y' if len(self.adjustments) == 1 else 'ies'}  |  "
                f"Repaid ₹{fmt_inr(repaid)}  |  Waived ₹{fmt_inr(waived)}  |  "
                f"Not considered: {not_used}")
        else:
            self.lbl_adj_summary.setText("No entries.")
        self.tabs.setTabText(1, f"✍  Interest Repayment / Waiver (Manual)"
                                + (f"  [{len(self.adjustments)}]" if self.adjustments else ""))

    @gui_safe
    def on_adj_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import repayment / waiver entries", "",
                                              "Excel / CSV files (*.xlsx *.xlsm *.xls *.csv)")
        if not path:
            return
        sheet = ExcelHandler.find_adjustment_sheet(path)
        entries, warnings = ExcelHandler.read_adjustments(path, sheet if sheet is not None else 0)
        if not entries:
            raise ValueError("No repayment / waiver entries found in the file.")
        if self.adjustments:
            box = QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setText(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} found. "
                        "Replace the current entries or add to them?")
            b_replace = box.addButton("Replace", QMessageBox.AcceptRole)
            box.addButton("Add", QMessageBox.ActionRole)
            b_cancel = box.addButton(QMessageBox.Cancel)
            box.exec_()
            if box.clickedButton() is b_cancel:
                return
            if box.clickedButton() is b_replace:
                self.adjustments = []
        self.adjustments.extend(entries)
        msg = f"Imported {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}."
        if warnings:
            msg += "  " + " | ".join(warnings[:3])
        self._after_adjustment_change(msg)

    @gui_safe
    def on_adj_export(self) -> None:
        if not self.adjustments:
            QMessageBox.information(self, APP_NAME, "There are no entries to save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save repayment / waiver entries",
                                              "MSME_Interest_Adjustments.xlsx", "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        ExcelHandler.write_adjustments(path, self.adjustments)
        self.statusBar().showMessage(f"Entries saved: {path} (re-import with 'Import Entries…')")
        self._offer_open(path, "Repayment / waiver entries saved.")

    # ---- helpers -----------------------------------------------------------
    def show_error(self, title: str, exc: BaseException) -> None:
        """Error dialog + status bar message (full traceback in details)."""
        self.statusBar().showMessage(f"Error: {exc}", 15000)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(APP_NAME)
        box.setText(title)
        box.setInformativeText(str(exc))
        box.setDetailedText("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        box.exec_()

    def update_rate_label(self) -> None:
        rate = to_decimal(round(self.spin_rate.value(), 2)) * 3
        self.lbl_rate.setText(f"Applicable Rate = 3 × Bank Rate = {rate:.2f}%")

    def _make_calculator(self) -> MSMECalculator:
        q = self.date_ason.date()
        return MSMECalculator(f"{self.spin_rate.value():.2f}", self.rb_yes.isChecked(),
                              dt.date(q.year(), q.month(), q.day()))

    def _require_results(self) -> bool:
        if not self.results:
            QMessageBox.information(self, APP_NAME, "Please upload a file and click Calculate first.")
            return False
        return True

    # ---- slots -------------------------------------------------------------
    @gui_safe
    def on_upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select invoice file", os.path.dirname(self.input_path) if self.input_path else "",
            "Excel / CSV files (*.xlsx *.xlsm *.xls *.csv);;All files (*.*)")
        if not path:
            return
        records, info = ExcelHandler.read_input(path)
        self.input_path, self.records, self.results = path, records, []
        self.table.setRowCount(0)
        self._update_cards()
        self.btn_xlsx.setEnabled(False)
        self.btn_pdf.setEnabled(False)
        self.lbl_path.setText(path)
        self.lbl_path.setStyleSheet("color:#1F2328;")
        pre_flagged = sum(1 for r in records if r.flags)
        msg = (f"Loaded {len(records)} invoice(s) from {info['rows']} data row(s) "
               f"(header on row {info['header_row']}). Click Calculate.")
        if pre_flagged:
            msg += f"  {pre_flagged} row(s) have data issues."
        if info.get("adjustments"):
            self.adjustments = list(info["adjustments"])
            msg += f"  {len(self.adjustments)} repayment/waiver entr{'y' if len(self.adjustments) == 1 else 'ies'} loaded."
        self._fill_adj_table()
        if info["warnings"]:
            msg += "  " + " | ".join(info["warnings"])
        self.statusBar().showMessage(msg)

    @gui_safe
    def on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save input template", "MSME_Input_Template.xlsx",
                                              "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        ExcelHandler.write_template(path)
        self.statusBar().showMessage(f"Template saved: {path}")
        self._offer_open(path, "Template saved.")

    def on_params_changed(self) -> None:
        """Keep the rate label current and silently recalculate if results are shown."""
        self.update_rate_label()
        if self.results:
            try:
                self._run_calculation()
            except Exception as exc:                               # noqa: BLE001
                self.statusBar().showMessage(f"Error: {exc}", 15000)

    @gui_safe
    def on_calculate(self) -> None:
        if not self.records:
            QMessageBox.information(self, APP_NAME, "Please upload an Excel / CSV file first.")
            return
        flagged = self._run_calculation()
        if flagged:
            QMessageBox.warning(
                self, APP_NAME,
                f"{flagged} row(s) flagged during validation.\n\n"
                "They are kept in the results (highlighted, see the 'Validation Flags' column). "
                "Please review and correct the source data where needed.")

    def _run_calculation(self) -> int:
        """Compute, refresh table/cards and status. Returns the flagged-row count."""
        self.calc = self._make_calculator()
        self.results = self.calc.calculate_all(self.records, self.adjustments)
        self._fill_table()
        self._fill_invoice_combo()
        self._fill_adj_table()
        s = self._update_cards()
        self.btn_xlsx.setEnabled(True)
        self.btn_pdf.setEnabled(True)
        self.statusBar().showMessage(
            f"Calculated {s['total_invoices']} invoice(s) | Overdue: {s['overdue_count']} | "
            f"Flagged rows: {s['flagged_count']} | Rate {self.calc.applicable_rate_pct:.2f}% p.a. | "
            f"As-on {fmt_date(self.calc.as_on_date)}")
        return s["flagged_count"]

    def _fill_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))
        red = QBrush(QColor("#F8D7DA"))
        yellow = QBrush(QColor("#FFF3CD"))
        bold = QFont()
        bold.setBold(True)
        for r_idx, res in enumerate(self.results):
            values = ExcelHandler.detail_row(res)
            bg = red if res.is_overdue else (yellow if res.is_flagged else None)
            for c_idx, (_h, src, typ) in enumerate(self.TABLE_COLUMNS):
                val = values[src]
                if typ == "money":
                    text, key = fmt_inr(val), float(val) if val is not None else -1.0
                elif typ == "date":
                    text, key = fmt_date(val), val.toordinal() if val else -1
                elif typ == "pct":
                    text, key = f"{val:.2f}", float(val)
                elif typ == "int":
                    text, key = ("" if val is None else str(val)), (-1 if val is None else int(val))
                else:
                    text, key = ("" if val is None else str(val)), None
                item = SortableItem(text, key)
                if typ in ("money", "int", "pct"):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif typ == "date":
                    item.setTextAlignment(Qt.AlignCenter)
                if bg is not None:
                    item.setBackground(bg)
                if c_idx == self.STATUS_COL and res.is_overdue:
                    item.setFont(bold)
                    item.setForeground(QBrush(QColor("#9C0006")))
                if typ == "text" and len(text) > 40:
                    item.setToolTip(text.replace("; ", "\n"))
                self.table.setItem(r_idx, c_idx, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        for c in range(self.table.columnCount()):            # keep long text columns readable
            if self.table.columnWidth(c) > 320:
                self.table.setColumnWidth(c, 320)

    def _update_cards(self) -> dict:
        s = MSMECalculator.summarise(self.results)
        if self.results:
            self.card_total.set_value(str(s["total_invoices"]))
            self.card_overdue.set_value(str(s["overdue_count"]))
            self.card_outstanding.set_value(fmt_inr(s["total_outstanding"]))
            self.card_interest.set_value(fmt_inr(s["total_interest"]))
            self.card_net.set_value(fmt_inr(s["net_interest"]))
        else:
            for c in (self.card_total, self.card_overdue, self.card_outstanding, self.card_interest,
                      self.card_net):
                c.set_value("–")
        return s

    def _default_out_name(self, ext: str) -> str:
        stem = os.path.splitext(os.path.basename(self.input_path))[0] or "MSME"
        folder = os.path.dirname(self.input_path)
        name = f"{stem}_MSME_Interest_{self.calc.as_on_date.strftime('%d-%m-%Y')}.{ext}"
        return os.path.join(folder, name) if folder else name

    @gui_safe
    def on_export_excel(self) -> None:
        if not self._require_results():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", self._default_out_name("xlsx"),
                                              "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        ExcelHandler.write_output(path, self.results, self.calc, self.input_path, self.adjustments)
        self.statusBar().showMessage(f"Excel report saved: {path}")
        self._offer_open(path, "Excel report saved.")

    @gui_safe
    def on_export_pdf(self) -> None:
        if not self._require_results():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export to PDF", self._default_out_name("pdf"),
                                              "PDF files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        PDFExporter.export(path, self.results, self.calc, self.input_path, self.adjustments)
        self.statusBar().showMessage(f"PDF report saved: {path}")
        self._offer_open(path, "PDF report saved.")

    def _offer_open(self, path: str, message: str) -> None:
        reply = QMessageBox.question(self, APP_NAME, f"{message}\n\n{path}\n\nOpen it now?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes and hasattr(os, "startfile"):
            try:
                os.startfile(path)                                 # Windows only
            except OSError as exc:
                self.statusBar().showMessage(f"Could not open file: {exc}", 10000)

    @gui_safe
    def on_self_test(self) -> None:
        ok, report = run_self_test()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information if ok else QMessageBox.Warning)
        box.setWindowTitle(f"{APP_NAME} – Self-Test")
        box.setText("All self-tests PASSED." if ok else "Some self-tests FAILED – see details.")
        box.setDetailedText(report)
        box.exec_()
        self.statusBar().showMessage("Self-test passed." if ok else "Self-test FAILED.")

    @gui_safe
    def on_about(self) -> None:
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            f"<p>Interest on delayed payments to Micro &amp; Small Enterprises under Sections 2(b), "
            f"15, 16 and 23 of the MSMED Act, 2006.</p>"
            f"<p><b>Method:</b> {xml_escape(METHOD_TEXT)}</p>"
            f"<p><i>{xml_escape(ABOUT_TEXT)}</i></p>")


# =============================================================================
# Entry point
# =============================================================================
def _console_print(text: str) -> None:
    """print() that is safe when there is no console (PyInstaller --windowed)."""
    if sys.stdout is not None:
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode("ascii"))


def main() -> int:
    if "--selftest" in sys.argv:
        ok, report = run_self_test()
        _console_print(report)
        return 0 if ok else 1

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    window = MainWindow()

    def excepthook(exc_type, exc, tb):
        """Last-resort handler: show unexpected errors instead of crashing."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        exc.__traceback__ = tb
        window.show_error("Unexpected error", exc)

    sys.excepthook = excepthook
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
