"""Bank-line categories used by the Categoriser agent (agreed with the CA in Phase 1 review)."""
from __future__ import annotations

# code: (label, direction "in" / "out" / "either", definition shown to the AI)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "supplier_payment": ("Supplier payment", "out", "Payment to a vendor for goods, services or capex (NEFT/RTGS/IMPS/cheque)."),
    "customer_receipt": ("Customer receipt", "in", "Receipt from a domestic customer (NEFT/RTGS/cheque clearing)."),
    "export_receipt": ("Export receipt", "in", "Inward foreign remittance from an overseas customer."),
    "salary": ("Salary / bonus", "out", "Bulk salary or bonus payout to employees."),
    "gst_payment": ("GST payment", "out", "GST deposited to the electronic cash ledger (CPIN / PMT-06)."),
    "tds_payment": ("TDS payment", "out", "TDS deposited (challan ITNS 281)."),
    "pf_esi": ("PF / ESI", "out", "Provident fund (EPFO ECR) or ESIC contribution."),
    "advance_tax": ("Advance tax", "out", "Advance income tax (challan ITNS 280)."),
    "loan_emi": ("Loan EMI", "out", "Term-loan instalment, usually by ACH / NACH debit."),
    "rent": ("Rent", "out", "Rent paid to the landlord."),
    "utilities": ("Utilities", "out", "Electricity, water or other utility bills."),
    "own_transfer": ("Own-account transfer", "either", "Transfer between the company's own bank accounts (funding / sweeps)."),
    "fx_conversion": ("FX conversion (EEFC)", "either", "Conversion of foreign currency in the EEFC account to INR."),
    "bank_charges": ("Bank charges", "out", "Service, maintenance, remittance or cheque-return charges levied by the bank."),
    "gst_on_bank_charges": ("GST on bank charges", "out", "GST levied by the bank on its charges (eligible input tax credit)."),
    "interest_debit": ("Interest debited", "out", "Interest charged by the bank on cash credit / overdraft."),
    "interest_credit": ("Interest credited", "in", "Interest received, e.g. on fixed deposits (may be net of TDS)."),
    "cheque_return": ("Cheque return", "either", "A deposited cheque returned unpaid, reversing an earlier credit."),
    "unidentified": ("Unidentified", "either", "Cannot be identified from the description or the masters - needs a human."),
}
CATEGORY_CODES = tuple(CATEGORIES)
PARTY_REQUIRED = {"supplier_payment", "customer_receipt", "export_receipt"}

_KIND_TO_CATEGORY = {
    "customer_receipt": "customer_receipt", "export_receipt": "export_receipt", "salary": "salary",
    "gst_payment": "gst_payment", "tds_payment": "tds_payment", "pf_payment": "pf_esi", "esi_payment": "pf_esi",
    "advance_tax": "advance_tax", "loan_emi": "loan_emi", "own_transfer_out": "own_transfer",
    "own_transfer_in": "own_transfer", "fx_conversion_out": "fx_conversion", "fx_conversion_in": "fx_conversion",
    "bank_charges": "bank_charges", "gst_on_charges": "gst_on_bank_charges", "cc_interest": "interest_debit",
    "fd_interest": "interest_credit", "cheque_returned": "cheque_return", "unidentified_receipt": "unidentified",
}


def truth_category(kind: str, party_category: str) -> str:
    """Ground-truth category for a generated line (used only by tests / evaluation)."""
    if kind == "vendor_payment":
        return {"rent": "rent", "utilities": "utilities"}.get(party_category, "supplier_payment")
    return _KIND_TO_CATEGORY[kind]


def direction_ok(category: str, amount_minor: int) -> bool:
    d = CATEGORIES[category][1]
    return d == "either" or (d == "in" and amount_minor > 0) or (d == "out" and amount_minor < 0)
