"""Versioned TDS (Tax Deducted at Source) section rates and thresholds — Income Tax Act, 1961.

Covers deduction on a BUSINESS's own payments to its resident vendors/professionals/contractors
(the data this app already has from purchase/expense invoices). Salary TDS (Sec 192 / Form 24Q) and
non-resident TDS (Sec 195 / Form 27Q) are NOT covered — they need payroll and foreign-remittance data
this app does not collect.

Like gst_rules.py: never edit a published version in place — add a new one and re-point
TDS_RULES_VERSION, because rates/thresholds change by Finance Act.
"""
from __future__ import annotations

from decimal import Decimal

TDS_RULES_VERSION = "2025.1"

RULES = {
    "2025.1": {
        "label": "TDS sections as understood for FY 2025-26 (non-salary, resident payees)",
        # key -> (section label, rate %, rate % if payee has no PAN (Sec 206AA, usually 20%), single-payment
        #         threshold, aggregate-in-FY threshold, applies_to hint)
        "sections": {
            "194C_IND": {"label": "194C — Contractor payment (individual/HUF contractor)", "rate": Decimal("1.00"),
                        "no_pan_rate": Decimal("20.00"), "single_limit": Decimal("30000"), "annual_limit": Decimal("100000"),
                        "hint": ["contract", "works contract", "labour", "job work", "amc", "transport contractor"]},
            "194C_OTH": {"label": "194C — Contractor payment (other than individual/HUF)", "rate": Decimal("2.00"),
                        "no_pan_rate": Decimal("20.00"), "single_limit": Decimal("30000"), "annual_limit": Decimal("100000"),
                        "hint": ["contract", "works contract", "annual maintenance"]},
            "194J_PROF": {"label": "194J — Professional / technical fees", "rate": Decimal("10.00"),
                         "no_pan_rate": Decimal("20.00"), "single_limit": Decimal("0"), "annual_limit": Decimal("30000"),
                         "hint": ["professional", "consultancy", "consulting", "legal fees", "audit fee", "technical fee",
                                  "royalty", "advocate"]},
            "194J_TECH": {"label": "194J — Technical services / certain royalty (reduced rate)", "rate": Decimal("2.00"),
                         "no_pan_rate": Decimal("20.00"), "single_limit": Decimal("0"), "annual_limit": Decimal("30000"),
                         "hint": ["technical services"]},
            "194H": {"label": "194H — Commission or brokerage", "rate": Decimal("2.00"), "no_pan_rate": Decimal("20.00"),
                    "single_limit": Decimal("0"), "annual_limit": Decimal("20000"),
                    "hint": ["commission", "brokerage"]},
            "194I_LAND": {"label": "194I — Rent of land/building/furniture", "rate": Decimal("10.00"),
                         "no_pan_rate": Decimal("20.00"), "single_limit": Decimal("0"), "annual_limit": Decimal("240000"),
                         "hint": ["rent", "lease", "premises"]},
            "194I_PLANT": {"label": "194I — Rent of plant & machinery", "rate": Decimal("2.00"), "no_pan_rate": Decimal("20.00"),
                          "single_limit": Decimal("0"), "annual_limit": Decimal("240000"),
                          "hint": ["equipment rent", "machinery rent", "plant rent"]},
            "194Q": {"label": "194Q — Purchase of goods (buyer turnover > ₹10 cr in preceding FY)",
                    "rate": Decimal("0.10"), "no_pan_rate": Decimal("5.00"), "single_limit": Decimal("0"),
                    "annual_limit": Decimal("5000000"), "hint": []},
        },
        "notes": [
            "Section selection is always offered as a suggestion, never applied automatically — the CA confirms it.",
            "Thresholds are checked against cumulative payments to the SAME vendor (by GSTIN, else by name) in the "
            "financial year, including the current invoice.",
            "194Q applies only if the buyer's turnover exceeded ₹10 crore in the preceding FY, and only if 206C(1H) "
            "TCS does not already apply on the same transaction — both need manual confirmation.",
            "Rates shown are standard (non-PAN) rates for FY 2025-26; verify against the current Finance Act before relying on them.",
        ],
    },
}


def get_rules(version: str) -> dict:
    if version not in RULES:
        raise KeyError(f"Unknown TDS rules version {version}")
    return RULES[version]


def suggest_section(rules: dict, description: str) -> str | None:
    """Best-effort suggestion from the expense head / party name text — always just a suggestion."""
    text = (description or "").lower()
    for key, sec in rules["sections"].items():
        if any(h in text for h in sec.get("hint", [])):
            return key
    return None
