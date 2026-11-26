"""Deterministic double-entry accounting engine.

AI may *suggest* classifications; every amount and every voucher line is computed here with
Decimal arithmetic from validated invoice / bank data using explicit rules. Vouchers are created
as drafts and must be approved by a user with ``approve_vouchers``. Unbalanced vouchers can never
be approved, uncertain classifications are flagged ``needs_review`` and are never auto-approved.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal

from services.audit_service import audit
from services.db import IntegrityError, get_db, now_iso
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, fy_bounds, fy_label_for, to_date
from utils.permissions import PermissionDenied

# ---------------------------------------------------------------- chart of accounts
GROUP_NATURE = {
    "Capital Account": "equity", "Reserves & Surplus": "equity",
    "Loans (Liability)": "liability", "Secured Loans": "liability", "Unsecured Loans": "liability",
    "Current Liabilities": "liability", "Sundry Creditors": "liability", "Duties & Taxes": "liability",
    "Provisions": "liability",
    "Fixed Assets": "asset", "Investments": "asset", "Current Assets": "asset", "Sundry Debtors": "asset",
    "Bank Accounts": "asset", "Cash-in-Hand": "asset", "Stock-in-Hand": "asset", "Loans & Advances (Asset)": "asset",
    "Deposits (Asset)": "asset", "Suspense A/c": "asset",
    "Sales Accounts": "income", "Direct Incomes": "income", "Indirect Incomes": "income",
    "Purchase Accounts": "expense", "Direct Expenses": "expense", "Indirect Expenses": "expense",
}

# (ledger name, group, mapping key or None)
DEFAULT_LEDGERS = [
    ("Sales", "Sales Accounts", "sales_default"),
    ("Sales Returns", "Sales Accounts", "sales_returns"),
    ("Export Sales", "Sales Accounts", "sales_export"),
    ("Exempt / Nil Rated Sales", "Sales Accounts", "sales_exempt"),
    ("Purchases", "Purchase Accounts", "purchase_default"),
    ("Purchase Returns", "Purchase Accounts", "purchase_returns"),
    ("Output CGST", "Duties & Taxes", "output_cgst"),
    ("Output SGST", "Duties & Taxes", "output_sgst"),
    ("Output IGST", "Duties & Taxes", "output_igst"),
    ("Output Cess", "Duties & Taxes", "output_cess"),
    ("Input CGST", "Duties & Taxes", "input_cgst"),
    ("Input SGST", "Duties & Taxes", "input_sgst"),
    ("Input IGST", "Duties & Taxes", "input_igst"),
    ("Input Cess", "Duties & Taxes", "input_cess"),
    ("RCM CGST Payable", "Duties & Taxes", "rcm_cgst"),
    ("RCM SGST Payable", "Duties & Taxes", "rcm_sgst"),
    ("RCM IGST Payable", "Duties & Taxes", "rcm_igst"),
    ("GST Payment (Cash Ledger)", "Duties & Taxes", "tax_payment"),
    ("TDS Payable", "Duties & Taxes", "tds_payable"),
    ("Round Off", "Indirect Expenses", "round_off"),
    ("Bank Charges", "Indirect Expenses", "exp:bank_charges"),
    ("Salaries & Wages", "Indirect Expenses", "exp:salary"),
    ("Rent", "Indirect Expenses", "exp:rent"),
    ("Telephone & Internet", "Indirect Expenses", "exp:telephone"),
    ("Travelling & Conveyance", "Indirect Expenses", "exp:travel"),
    ("Professional Fees", "Indirect Expenses", "exp:professional"),
    ("Printing & Stationery", "Indirect Expenses", "exp:printing"),
    ("Electricity Charges", "Indirect Expenses", "exp:electricity"),
    ("Repairs & Maintenance", "Indirect Expenses", "exp:repairs"),
    ("Advertisement", "Indirect Expenses", "exp:advertisement"),
    ("Staff Welfare", "Indirect Expenses", "exp:staff_welfare"),
    ("Office Expenses", "Indirect Expenses", "exp:general"),
    ("Freight Inward", "Direct Expenses", "exp:freight"),
    ("Interest Paid", "Indirect Expenses", "exp:interest"),
    ("Depreciation", "Indirect Expenses", "exp:depreciation"),
    ("Interest Received", "Indirect Incomes", "income:interest"),
    ("Cash", "Cash-in-Hand", "cash"),
    ("Suspense Account", "Suspense A/c", "suspense"),
    ("Capital Account", "Capital Account", "capital"),
    ("Unsecured Loans", "Unsecured Loans", "loan"),
    ("Stock-in-Hand", "Stock-in-Hand", "stock"),
]

EXPENSE_KEYWORDS = {
    "exp:rent": ["rent", "lease", "premises"],
    "exp:telephone": ["telephone", "mobile", "internet", "broadband", "airtel", "jio", "vodafone", "bsnl"],
    "exp:travel": ["travel", "taxi", "cab", "uber", "ola", "flight", "airline", "hotel", "conveyance", "railway"],
    "exp:professional": ["professional", "consultancy", "consulting", "legal", "audit fee", "advocate"],
    "exp:printing": ["printing", "stationery", "xerox", "paper"],
    "exp:electricity": ["electricity", "power", "discom", "bescom", "tneb", "msedcl"],
    "exp:repairs": ["repair", "maintenance", "amc", "service charge"],
    "exp:advertisement": ["advertis", "marketing", "promotion", "google ads", "facebook"],
    "exp:staff_welfare": ["staff welfare", "canteen", "refreshment", "tea", "food"],
    "exp:freight": ["freight", "transport", "courier", "logistics", "cartage"],
    "exp:bank_charges": ["bank charges", "processing fee"],
    "exp:salary": ["salary", "wages", "payroll"],
}

# Section 17(5) style heads where ITC is normally blocked — CA must confirm.
BLOCKED_ITC_HEADS = {"exp:staff_welfare"}

VOUCHER_PREFIX = {"Sales": "SAL", "Purchase": "PUR", "Receipt": "RCT", "Payment": "PMT", "Journal": "JRN",
                  "Contra": "CTR", "Credit Note": "CRN", "Debit Note": "DBN"}
VOUCHER_TYPES = list(VOUCHER_PREFIX)


class AccountingError(Exception):
    pass


class UnbalancedVoucher(AccountingError):
    pass


class DuplicateVoucher(AccountingError):
    pass


@dataclass
class Line:
    ledger_id: str
    dr_cr: str
    amount: Decimal
    cost_centre_id: str | None = None
    bill_ref: str | None = None


@dataclass
class VoucherDraft:
    voucher_type: str
    voucher_date: dt.date
    lines: list[Line]
    narration: str = ""
    party_ledger_id: str | None = None
    reference_no: str | None = None
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)


def ensure_chart_of_accounts(firm_id: str, client_id: str) -> None:
    db = get_db()
    existing = {r["name"]: r["id"] for r in db.fetchall("select id, name from ledgers where client_id = ?", [client_id])}
    mapped = {r["mapping_key"] for r in db.fetchall("select mapping_key from ledger_mappings where client_id = ?", [client_id])}
    for name, group, key in DEFAULT_LEDGERS:
        lid = existing.get(name)
        if lid is None:
            lid = db.insert("ledgers", {"firm_id": firm_id, "client_id": client_id, "name": name, "group_name": group,
                                        "nature": GROUP_NATURE[group], "is_system": True, "created_at": now_iso()})
            existing[name] = lid
        if key and key not in mapped:
            db.insert("ledger_mappings", {"firm_id": firm_id, "client_id": client_id, "mapping_key": key,
                                          "ledger_id": lid, "created_at": now_iso()})


def mapped_ledger(client_id: str, key: str) -> dict:
    db = get_db()
    row = db.fetchone("select l.* from ledger_mappings m join ledgers l on l.id = m.ledger_id "
                      "where m.client_id = ? and m.mapping_key = ?", [client_id, key])
    if row is None:
        raise AccountingError(f"No ledger mapped for '{key}'. Configure it in Accounting → Ledger mapping.")
    return row


def set_mapping(ctx: AuthContext, client_id: str, key: str, ledger_id: str) -> None:
    client = require_client(ctx, client_id, "manage_ledgers")
    led = scoped_get(ctx, "ledgers", ledger_id, "manage_ledgers")
    if led["client_id"] != client_id:
        raise PermissionDenied("Ledger belongs to another client")
    db = get_db()
    row = db.fetchone("select id, ledger_id from ledger_mappings where client_id = ? and mapping_key = ?", [client_id, key])
    if row:
        db.update("ledger_mappings", row["id"], {"ledger_id": ledger_id})
    else:
        db.insert("ledger_mappings", {"firm_id": client["firm_id"], "client_id": client_id, "mapping_key": key,
                                      "ledger_id": ledger_id, "created_at": now_iso()})
    audit(ctx, "ledger_mapping.set", "ledger_mappings", key, client_id=client_id,
          before={"ledger_id": row["ledger_id"] if row else None}, after={"ledger_id": ledger_id})


def list_ledgers(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select * from ledgers where client_id = ? order by group_name, name", [client_id])


def list_mappings(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select m.mapping_key, m.ledger_id, l.name as ledger_name from ledger_mappings m "
                             "join ledgers l on l.id = m.ledger_id where m.client_id = ? order by m.mapping_key", [client_id])


def create_ledger(ctx: AuthContext, client_id: str, name: str, group_name: str, party_gstin: str | None = None) -> str:
    client = require_client(ctx, client_id, "manage_ledgers")
    if group_name not in GROUP_NATURE:
        raise AccountingError(f"Unknown ledger group {group_name}")
    name = name.strip()
    if not name:
        raise AccountingError("Ledger name required")
    try:
        lid = get_db().insert("ledgers", {"firm_id": client["firm_id"], "client_id": client_id, "name": name,
                                          "group_name": group_name, "nature": GROUP_NATURE[group_name],
                                          "party_gstin": party_gstin, "created_at": now_iso()})
    except IntegrityError as exc:
        raise AccountingError(f"Ledger '{name}' already exists") from exc
    audit(ctx, "ledger.created", "ledgers", lid, client_id=client_id, after={"name": name, "group": group_name})
    return lid


def get_or_create_party_ledger(client: dict, name: str, gstin: str | None, kind: str) -> dict:
    """kind: 'debtor' | 'creditor'. Matches by GSTIN first, then exact name."""
    db = get_db()
    group = "Sundry Debtors" if kind == "debtor" else "Sundry Creditors"
    if gstin:
        row = db.fetchone("select * from ledgers where client_id = ? and party_gstin = ? and group_name = ?",
                          [client["id"], gstin, group])
        if row:
            return row
    name = (name or "").strip() or ("Unknown Customer" if kind == "debtor" else "Unknown Supplier")
    row = db.fetchone("select * from ledgers where client_id = ? and name = ?", [client["id"], name])
    if row and row["group_name"] == group and (not gstin or not row.get("party_gstin") or row["party_gstin"] == gstin):
        if gstin and not row.get("party_gstin"):
            db.update("ledgers", row["id"], {"party_gstin": gstin})
        return row
    if row:  # same name used by another group/GSTIN -> disambiguate
        name = f"{name} ({gstin or group})"
        existing = db.fetchone("select * from ledgers where client_id = ? and name = ?", [client["id"], name])
        if existing:
            return existing
    lid = db.insert("ledgers", {"firm_id": client["firm_id"], "client_id": client["id"], "name": name, "group_name": group,
                                "nature": GROUP_NATURE[group], "party_gstin": gstin,
                                "state_code": gstin[:2] if gstin else None, "created_at": now_iso()})
    return db.get("ledgers", lid)


def classify_expense_head(text: str) -> tuple[str, bool]:
    """Return (mapping key, confident?). Unknown text falls back to general expenses (not confident)."""
    t = (text or "").lower()
    for key, words in EXPENSE_KEYWORDS.items():
        if any(w in t for w in words):
            return key, True
    return "exp:general", False


# ---------------------------------------------------------------- invoice -> voucher rules
def build_invoice_voucher(client: dict, inv: dict) -> VoucherDraft:
    cid = client["id"]
    L = lambda key: mapped_ledger(cid, key)["id"]  # noqa: E731
    category, note = inv["category"], inv.get("note_type") or "invoice"
    taxable = D(inv["taxable_value"])
    cgst, sgst, igst, cess = D(inv["cgst"]), D(inv["sgst"]), D(inv["igst"]), D(inv["cess"])
    ro = D(inv.get("round_off"))
    stated_total = D(inv["total"])
    rcm = bool(inv.get("reverse_charge"))
    reasons: list[str] = []
    date = to_date(inv["invoice_date"])
    narration = f"{'Sales' if category == 'sales' else 'Purchase'} {note.replace('_', ' ')} {inv['invoice_no']} — {inv['party_name']}"

    party = get_or_create_party_ledger(client, inv["party_name"], inv.get("party_gstin"),
                                       "debtor" if category == "sales" else "creditor")
    lines: list[Line] = []

    def add(ledger_id, dr_cr, amount):
        amount = D(amount)
        if amount == ZERO:
            return
        if amount < 0:  # negative amount flips side
            dr_cr, amount = ("Cr" if dr_cr == "Dr" else "Dr"), -amount
        lines.append(Line(ledger_id, dr_cr, amount, bill_ref=inv["invoice_no"]))

    tax_total = cgst + sgst + igst + cess
    if category == "sales":
        supply = inv.get("supply_type") or "taxable"
        sales_key = {"export_wpay": "sales_export", "export_wopay": "sales_export", "sez_wpay": "sales_export",
                     "sez_wopay": "sales_export", "nil": "sales_exempt", "exempt": "sales_exempt",
                     "non_gst": "sales_exempt"}.get(supply, "sales_default")
        party_amount = taxable + tax_total + ro
        # normal (invoice / debit note) : party Dr, income Cr ; credit note : reverse
        sign = "Dr" if note in ("invoice", "debit_note") else "Cr"
        opp = "Cr" if sign == "Dr" else "Dr"
        vtype = {"invoice": "Sales", "debit_note": "Debit Note", "credit_note": "Credit Note"}[note]
        income_ledger = L("sales_returns") if note == "credit_note" else L(sales_key)
        add(party["id"], sign, party_amount)
        add(income_ledger, opp, taxable)
        add(L("output_cgst"), opp, cgst)
        add(L("output_sgst"), opp, sgst)
        add(L("output_igst"), opp, igst)
        add(L("output_cess"), opp, cess)
        add(L("round_off"), opp, ro)
    else:
        # purchase or expense
        if category == "expense" or inv.get("expense_head"):
            key = inv.get("expense_head")
            if not key:
                key, confident = classify_expense_head(f"{inv['party_name']} {inv.get('_items_text', '')}")
                if not confident:
                    reasons.append("Expense head could not be determined — defaulted to Office Expenses")
            cost_ledger = L(key)
        else:
            key = "purchase_default"
            cost_ledger = L(key)
        itc = inv.get("itc_eligibility") or "pending"
        if key in BLOCKED_ITC_HEADS and itc == "pending":
            itc = "blocked"
            reasons.append("Expense head is commonly blocked under Sec 17(5); ITC treated as blocked — confirm")
        if itc == "pending" and tax_total:
            reasons.append("ITC eligibility not confirmed")
        claim_itc = itc in ("eligible", "pending")
        sign = "Dr" if note in ("invoice", "debit_note") else "Cr"  # purchase-side credit note reverses
        opp = "Cr" if sign == "Dr" else "Dr"
        vtype = {"invoice": "Purchase", "debit_note": "Journal", "credit_note": "Debit Note"}[note]
        cost_ledger_for_note = L("purchase_returns") if (note == "credit_note" and key == "purchase_default") else cost_ledger
        if rcm:
            # Supplier does not charge tax; recipient pays tax under RCM.
            add(cost_ledger_for_note, sign, taxable + (ZERO if claim_itc else tax_total))
            if claim_itc:
                add(L("input_cgst"), sign, cgst)
                add(L("input_sgst"), sign, sgst)
                add(L("input_igst"), sign, igst)
                add(L("input_cess"), sign, cess)
            add(L("rcm_cgst"), opp, cgst)
            add(L("rcm_sgst"), opp, sgst)
            add(L("rcm_igst"), opp, igst)
            add(L("output_cess"), opp, cess)
            party_amount = taxable + ro
            reasons.append("Reverse charge supply — verify RCM liability and ITC")
        else:
            add(cost_ledger_for_note, sign, taxable + (ZERO if claim_itc else tax_total))
            if claim_itc:
                add(L("input_cgst"), sign, cgst)
                add(L("input_sgst"), sign, sgst)
                add(L("input_igst"), sign, igst)
                add(L("input_cess"), sign, cess)
            party_amount = taxable + tax_total + ro
        add(L("round_off"), sign, ro)
        add(party["id"], opp, party_amount)

    if party_amount != stated_total:
        reasons.append(f"Computed party amount {party_amount} differs from invoice total {stated_total}")
    if not inv.get("party_gstin") and category != "sales" and tax_total:
        reasons.append("Supplier GSTIN missing on a taxed purchase")
    return VoucherDraft(vtype, date, lines, narration=narration, party_ledger_id=party["id"],
                        reference_no=inv["invoice_no"], needs_review=bool(reasons), review_reasons=reasons)


# ---------------------------------------------------------------- voucher persistence
def totals(lines: list[Line] | list[dict]) -> tuple[Decimal, Decimal]:
    dr = cr = ZERO
    for ln in lines:
        side = ln.dr_cr if isinstance(ln, Line) else ln["dr_cr"]
        amt = D(ln.amount if isinstance(ln, Line) else ln["amount"])
        if side == "Dr":
            dr += amt
        else:
            cr += amt
    return dr, cr


def assert_balanced(lines) -> Decimal:
    if not lines or len(lines) < 2:
        raise UnbalancedVoucher("A voucher needs at least one debit and one credit line")
    dr, cr = totals(lines)
    if dr != cr:
        raise UnbalancedVoucher(f"Voucher not balanced: Dr {dr} ≠ Cr {cr}")
    if dr == ZERO:
        raise UnbalancedVoucher("Voucher total is zero")
    for ln in lines:
        amt = D(ln.amount if isinstance(ln, Line) else ln["amount"])
        if amt < 0:
            raise UnbalancedVoucher("Negative line amounts are not allowed; use the opposite side")
    return dr


def next_voucher_no(client: dict, voucher_type: str, date: dt.date) -> tuple[str, str]:
    db = get_db()
    fy = fy_label_for(date, client.get("fy_start_month") or 4)
    with db.transaction():
        row = db.fetchone("select * from voucher_sequences where client_id = ? and voucher_type = ? and fy_label = ?",
                          [client["id"], voucher_type, fy])
        if row is None:
            n = 1
            db.insert("voucher_sequences", {"firm_id": client["firm_id"], "client_id": client["id"],
                                            "voucher_type": voucher_type, "fy_label": fy, "next_no": 2})
        else:
            n = int(row["next_no"])
            db.update("voucher_sequences", row["id"], {"next_no": n + 1})
    return f"{VOUCHER_PREFIX[voucher_type]}/{fy}/{n:05d}", fy


def create_voucher(ctx: AuthContext, client_id: str, draft: VoucherDraft, *, source_type: str = "manual",
                   source_id: str | None = None) -> str:
    from services.period_service import assert_period_open

    client = require_client(ctx, client_id, "prepare_vouchers")
    if draft.voucher_type not in VOUCHER_PREFIX:
        raise AccountingError(f"Unknown voucher type {draft.voucher_type}")
    total = assert_balanced(draft.lines)
    assert_period_open(client_id, draft.voucher_date)
    db = get_db()
    # every ledger must belong to this client
    ids = {ln.ledger_id for ln in draft.lines}
    marks = ",".join("?" for _ in ids)
    found = db.scalar(f"select count(*) from ledgers where client_id = ? and id in ({marks})", [client_id, *ids])
    if found != len(ids):
        raise PermissionDenied("Voucher references a ledger outside this client")
    if source_id and db.fetchone("select id from accounting_vouchers where client_id = ? and source_type = ? and source_id = ? "
                                 "and status not in ('cancelled','rejected')", [client_id, source_type, source_id]):
        raise DuplicateVoucher("A voucher already exists for this source document/transaction")
    if draft.reference_no and draft.party_ledger_id:
        dup = db.fetchone("select id, voucher_no from accounting_vouchers where client_id = ? and voucher_type = ? and "
                          "party_ledger_id = ? and reference_no = ? and total_amount = ? and status not in ('cancelled','rejected')",
                          [client_id, draft.voucher_type, draft.party_ledger_id, draft.reference_no, total])
        if dup:
            raise DuplicateVoucher(f"Possible duplicate of voucher {dup['voucher_no']} (same party, reference and amount)")
    with db.transaction():
        vno, fy = next_voucher_no(client, draft.voucher_type, draft.voucher_date)
        vid = db.insert("accounting_vouchers", {
            "firm_id": client["firm_id"], "client_id": client_id, "voucher_type": draft.voucher_type, "voucher_no": vno,
            "voucher_date": draft.voucher_date, "fy_label": fy, "narration": draft.narration,
            "party_ledger_id": draft.party_ledger_id, "reference_no": draft.reference_no, "source_type": source_type,
            "source_id": source_id, "status": "draft", "needs_review": draft.needs_review,
            "review_reason": "; ".join(draft.review_reasons) or None, "total_amount": total, "created_by": ctx.user_id,
            "created_at": now_iso(),
        })
        for i, ln in enumerate(draft.lines, start=1):
            db.insert("accounting_voucher_entries", {"firm_id": client["firm_id"], "client_id": client_id, "voucher_id": vid,
                                                     "line_no": i, "ledger_id": ln.ledger_id, "dr_cr": ln.dr_cr,
                                                     "amount": D(ln.amount), "cost_centre_id": ln.cost_centre_id,
                                                     "bill_ref": ln.bill_ref})
        audit(ctx, "voucher.created", "accounting_vouchers", vid, client_id=client_id,
              after={"voucher_no": vno, "type": draft.voucher_type, "amount": str(total), "source": source_type})
    return vid


def update_voucher(ctx: AuthContext, voucher_id: str, lines: list[Line], narration: str | None = None,
                   voucher_date: dt.date | None = None) -> None:
    from services.period_service import assert_period_open

    v = scoped_get(ctx, "accounting_vouchers", voucher_id, "prepare_vouchers")
    if v["status"] not in ("draft", "rejected"):
        raise AccountingError("Only draft or rejected vouchers can be edited. Approved vouchers must be reversed.")
    assert_balanced(lines)
    assert_period_open(v["client_id"], to_date(v["voucher_date"]))
    if voucher_date:
        assert_period_open(v["client_id"], voucher_date)
    db = get_db()
    ids = {ln.ledger_id for ln in lines}
    marks = ",".join("?" for _ in ids)
    if db.scalar(f"select count(*) from ledgers where client_id = ? and id in ({marks})", [v["client_id"], *ids]) != len(ids):
        raise PermissionDenied("Voucher references a ledger outside this client")
    before = get_voucher_lines(voucher_id)
    with db.transaction():
        db.execute("delete from accounting_voucher_entries where voucher_id = ?", [voucher_id])
        for i, ln in enumerate(lines, start=1):
            db.insert("accounting_voucher_entries", {"firm_id": v["firm_id"], "client_id": v["client_id"], "voucher_id": voucher_id,
                                                     "line_no": i, "ledger_id": ln.ledger_id, "dr_cr": ln.dr_cr,
                                                     "amount": D(ln.amount), "cost_centre_id": ln.cost_centre_id,
                                                     "bill_ref": ln.bill_ref})
        upd = {"total_amount": totals(lines)[0], "status": "draft"}
        if narration is not None:
            upd["narration"] = narration
        if voucher_date:
            upd["voucher_date"] = voucher_date
        db.update("accounting_vouchers", voucher_id, upd)
        audit(ctx, "voucher.edited", "accounting_vouchers", voucher_id, client_id=v["client_id"],
              before={"lines": [{k: str(x[k]) for k in ("ledger_id", "dr_cr", "amount")} for x in before]},
              after={"lines": [{"ledger_id": ln.ledger_id, "dr_cr": ln.dr_cr, "amount": str(ln.amount)} for ln in lines]})


def get_voucher_lines(voucher_id: str) -> list[dict]:
    return get_db().fetchall("select e.*, l.name as ledger_name, l.group_name from accounting_voucher_entries e "
                             "join ledgers l on l.id = e.ledger_id where e.voucher_id = ? order by e.line_no", [voucher_id])


def bulk_voucher_lines(voucher_ids: list[str]) -> dict[str, list[dict]]:
    """Bulk version of get_voucher_lines — one query for N vouchers instead of N queries, for callers (e.g. Tally
    export, which previously re-queried per voucher) that need every voucher's lines in one pass."""
    if not voucher_ids:
        return {}
    marks = ",".join("?" for _ in voucher_ids)
    rows = get_db().fetchall(f"select e.*, l.name as ledger_name, l.group_name from accounting_voucher_entries e "
                             f"join ledgers l on l.id = e.ledger_id where e.voucher_id in ({marks}) order by e.voucher_id, e.line_no",
                             voucher_ids)
    out: dict[str, list[dict]] = {vid: [] for vid in voucher_ids}
    for r in rows:
        out[r["voucher_id"]].append(r)
    return out


def approve_voucher(ctx: AuthContext, voucher_id: str, *, acknowledge_review: bool = False) -> None:
    from services.period_service import assert_period_open

    v = scoped_get(ctx, "accounting_vouchers", voucher_id, "approve_vouchers")
    if v["status"] == "approved":
        return
    if v["status"] == "cancelled":
        raise AccountingError("Cancelled vouchers cannot be approved")
    if v["needs_review"] and not acknowledge_review:
        raise AccountingError(f"Voucher {v['voucher_no']} is flagged for review: {v.get('review_reason')}. "
                              "Review the classification and confirm explicitly.")
    assert_period_open(v["client_id"], to_date(v["voucher_date"]))
    assert_balanced(get_voucher_lines(voucher_id))
    get_db().update("accounting_vouchers", voucher_id, {"status": "approved", "approved_by": ctx.user_id,
                                                        "approved_at": now_iso(), "needs_review": False})
    audit(ctx, "voucher.approved", "accounting_vouchers", voucher_id, client_id=v["client_id"],
          after={"voucher_no": v["voucher_no"], "acknowledged_review": acknowledge_review})


def reject_voucher(ctx: AuthContext, voucher_id: str, reason: str) -> None:
    from services.period_service import assert_period_open

    v = scoped_get(ctx, "accounting_vouchers", voucher_id, "approve_vouchers")
    if v["status"] == "approved":
        raise AccountingError("Approved vouchers cannot be rejected; cancel and reverse instead")
    assert_period_open(v["client_id"], to_date(v["voucher_date"]))
    get_db().update("accounting_vouchers", voucher_id, {"status": "rejected", "review_reason": reason})
    audit(ctx, "voucher.rejected", "accounting_vouchers", voucher_id, client_id=v["client_id"], after={"reason": reason})


def cancel_voucher(ctx: AuthContext, voucher_id: str, reason: str) -> None:
    from services.period_service import assert_period_open

    v = scoped_get(ctx, "accounting_vouchers", voucher_id, "approve_vouchers")
    assert_period_open(v["client_id"], to_date(v["voucher_date"]))
    get_db().update("accounting_vouchers", voucher_id, {"status": "cancelled", "review_reason": reason})
    audit(ctx, "voucher.cancelled", "accounting_vouchers", voucher_id, client_id=v["client_id"],
          before={"status": v["status"]}, after={"reason": reason})


def list_vouchers(ctx: AuthContext, client_id: str, *, date_from=None, date_to=None, status: str | None = None,
                  voucher_type: str | None = None) -> list[dict]:
    require_client(ctx, client_id, "view")
    sql = ("select v.*, l.name as party_name from accounting_vouchers v left join ledgers l on l.id = v.party_ledger_id "
           "where v.client_id = ?")
    params: list = [client_id]
    if date_from:
        sql += " and v.voucher_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " and v.voucher_date <= ?"
        params.append(date_to)
    if status:
        sql += " and v.status = ?"
        params.append(status)
    if voucher_type:
        sql += " and v.voucher_type = ?"
        params.append(voucher_type)
    return get_db().fetchall(sql + " order by v.voucher_date, v.voucher_no", params)


def post_invoice(ctx: AuthContext, invoice_id: str) -> str:
    """Generate the draft voucher for an approved invoice."""
    inv = scoped_get(ctx, "invoices", invoice_id, "prepare_vouchers")
    client = require_client(ctx, inv["client_id"], "prepare_vouchers")
    items = get_db().fetchall("select description from invoice_items where invoice_id = ?", [invoice_id])
    inv = dict(inv, _items_text=" ".join(i.get("description") or "" for i in items))
    draft = build_invoice_voucher(client, inv)
    return create_voucher(ctx, inv["client_id"], draft, source_type="invoice", source_id=invoice_id)


# ---------------------------------------------------------------- balances
def ledger_movements(client_id: str, date_from: dt.date | None, date_to: dt.date, statuses=("approved",)) -> dict[str, Decimal]:
    """Net Dr(+)/Cr(-) movement per ledger for vouchers dated in [date_from, date_to]."""
    db = get_db()
    marks = ",".join("?" for _ in statuses)
    sql = (f"select e.ledger_id, e.dr_cr, e.amount from accounting_voucher_entries e join accounting_vouchers v on v.id = e.voucher_id "
           f"where v.client_id = ? and v.status in ({marks}) and v.voucher_date <= ?")
    params: list = [client_id, *statuses, date_to]
    if date_from:
        sql += " and v.voucher_date >= ?"
        params.append(date_from)
    out: dict[str, Decimal] = {}
    for r in db.fetchall(sql, params):
        amt = D(r["amount"])
        out[r["ledger_id"]] = out.get(r["ledger_id"], ZERO) + (amt if r["dr_cr"] == "Dr" else -amt)
    return out


def opening_balances(client_id: str, fy_label: str) -> dict[str, Decimal]:
    rows = get_db().fetchall("select ledger_id, dr_cr, amount from opening_balances where client_id = ? and fy_label = ?",
                             [client_id, fy_label])
    return {r["ledger_id"]: (D(r["amount"]) if r["dr_cr"] == "Dr" else -D(r["amount"])) for r in rows}


def set_opening_balance(ctx: AuthContext, client_id: str, fy_label: str, ledger_id: str, amount: Decimal, dr_cr: str) -> None:
    from services.period_service import assert_period_open

    client = require_client(ctx, client_id, "prepare_vouchers")
    led = scoped_get(ctx, "ledgers", ledger_id, "prepare_vouchers")
    if led["client_id"] != client_id or dr_cr not in ("Dr", "Cr"):
        raise AccountingError("Invalid ledger or side")
    start, _ = fy_bounds(fy_label, client.get("fy_start_month") or 4)
    assert_period_open(client_id, start)
    db = get_db()
    row = db.fetchone("select * from opening_balances where client_id = ? and fy_label = ? and ledger_id = ?",
                      [client_id, fy_label, ledger_id])
    amount = D(amount)
    if row:
        db.update("opening_balances", row["id"], {"amount": amount, "dr_cr": dr_cr})
    else:
        db.insert("opening_balances", {"firm_id": client["firm_id"], "client_id": client_id, "fy_label": fy_label,
                                       "ledger_id": ledger_id, "dr_cr": dr_cr, "amount": amount, "created_by": ctx.user_id,
                                       "created_at": now_iso()})
    audit(ctx, "opening_balance.set", "opening_balances", ledger_id, client_id=client_id,
          before={"amount": str(row["amount"]), "dr_cr": row["dr_cr"]} if row else None,
          after={"amount": str(amount), "dr_cr": dr_cr, "fy": fy_label})


def opening_difference(client_id: str, fy_label: str) -> Decimal:
    return sum(opening_balances(client_id, fy_label).values(), ZERO)


def set_closing_stock(ctx: AuthContext, client_id: str, as_of: dt.date, amount: Decimal, basis: str = "") -> None:
    client = require_client(ctx, client_id, "prepare_vouchers")
    db = get_db()
    row = db.fetchone("select * from closing_stock where client_id = ? and as_of_date = ?", [client_id, as_of])
    if row:
        db.update("closing_stock", row["id"], {"amount": D(amount), "basis": basis})
    else:
        db.insert("closing_stock", {"firm_id": client["firm_id"], "client_id": client_id, "as_of_date": as_of,
                                    "amount": D(amount), "basis": basis, "created_by": ctx.user_id, "created_at": now_iso()})
    audit(ctx, "closing_stock.set", "closing_stock", str(as_of), client_id=client_id, after={"amount": str(amount)})


def closing_stock_at(client_id: str, as_of: dt.date) -> Decimal | None:
    row = get_db().fetchone("select amount from closing_stock where client_id = ? and as_of_date = ?", [client_id, as_of])
    return D(row["amount"]) if row else None


def ledger_index(client_id: str) -> dict[str, dict]:
    return {r["id"]: r for r in get_db().fetchall("select * from ledgers where client_id = ?", [client_id])}


def manual_journal(ctx: AuthContext, client_id: str, date: dt.date, rows: list[dict], narration: str,
                   voucher_type: str = "Journal") -> str:
    """rows: [{ledger_id, dr_cr, amount}] — used for adjustments, depreciation, provisions."""
    lines = [Line(r["ledger_id"], r["dr_cr"], D(r["amount"])) for r in rows if D(r.get("amount")) > 0]
    draft = VoucherDraft(voucher_type, date, lines, narration=narration)
    return create_voucher(ctx, client_id, draft, source_type="adjustment" if voucher_type == "Journal" else "manual")


SAFE_NAME = re.compile(r"[^\w &().,/-]")
