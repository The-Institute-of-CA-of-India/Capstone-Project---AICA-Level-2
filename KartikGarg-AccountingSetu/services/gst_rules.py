"""Versioned GST rule parameters. GST law and portal formats change; never edit an existing
version in place — add a new version and point GST_RULES_VERSION at it.

These are return-PREPARATION rules. Verify against the current GSTN offline-tool schema and
notifications before uploading anything to the portal.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

RULES = {
    "2025.1": {
        "label": "GST rules as understood for FY 2025-26 preparation",
        # B2C (Large): inter-state invoices to unregistered persons above this value (Notification 12/2024-CT,
        # w.e.f. 1 Aug 2024 the threshold is ₹1,00,000; earlier ₹2,50,000).
        "b2cl_threshold": [(dt.date(2024, 8, 1), Decimal("100000")), (dt.date(2017, 7, 1), Decimal("250000"))],
        # Table 4: ITC blocked u/s 17(5) is reported in 4(A) and reversed in 4(B)(1);
        # ITC ineligible u/s 16(4) / place-of-supply is reported in 4(D)(2) only.
        "blocked_itc_reported_in_4A_and_reversed_4B1": True,
        "hsn_min_digits_upto_5cr": 4,
        "hsn_min_digits_above_5cr": 6,
        "hsn_split_b2b_b2c": True,
        "match_tolerance": Decimal("1.00"),
        "gstr1_json_version": "GST3.2",
        "notes": [
            "Prepared data only. Filing happens on the GST portal by an authorised signatory.",
            "Verify JSON against the current GSTN Returns Offline Tool schema before upload.",
        ],
    },
}


def get_rules(version: str) -> dict:
    if version not in RULES:
        raise KeyError(f"Unknown GST rules version {version}")
    return RULES[version]


def b2cl_threshold(rules: dict, invoice_date: dt.date) -> Decimal:
    for start, value in rules["b2cl_threshold"]:
        if invoice_date >= start:
            return value
    return rules["b2cl_threshold"][-1][1]
