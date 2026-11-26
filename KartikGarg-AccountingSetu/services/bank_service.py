"""Bank statements: parsing, classification, matching, voucher generation, BRS."""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import re
from decimal import Decimal

from services import accounting_engine as ae
from services.audit_service import audit
from services.db import get_db, now_iso
from services.ocr_service import extract_pdf, read_table
from services.period_service import assert_period_open
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, name_similarity, normalize_invoice_no, to_date
from utils.permissions import PermissionDenied

CATEGORIES = {
    "customer_receipt": "Customer Receipts", "supplier_payment": "Supplier Payments", "salary": "Salary Payments",
    "bank_charges": "Bank Charges", "loan": "Loan Transactions", "interest": "Interest", "expense_payment": "Expense Payments",
    "tax_payment": "Tax Payments", "transfer": "Transfers", "unknown": "Unknown Transactions",
}
MATCH_STATUSES = ["matched", "unmatched", "partially_matched", "duplicate", "suspense", "needs_review"]

RULES: list[tuple[str, list[str], str | None]] = [
    # (category, keywords, direction 'dr'|'cr'|None)
    ("bank_charges", ["charges", "chrg", "chgs", "sms alert", "annual fee", "min bal", "amc fee", "gst on chg", "commission"], "dr"),
    ("interest", ["int.pd", "interest", "int cr", "int.cr", "int paid", "int coll"], None),
    ("loan", ["loan", "emi", " ln ", "od int"], None),
    ("salary", ["salary", "sal for", "payroll", "wages"], "dr"),
    ("tax_payment", ["gst challan", "gstn", "cbdt", "tds", "advance tax", "income tax", "cpin", "gst pmt", "itns", "challan"], "dr"),
    ("transfer", ["self", "own a/c", "own account", "sweep", "cash withdrawal", "atm wdl", "atw", "cash wdl", "fd ", "to fd"], None),
    ("expense_payment", ["rent", "electricity", "bescom", "msedcl", "telephone", "airtel", "jio", "insurance", "fuel",
                         "petrol", "swiggy", "zomato", "amazon", "flipkart", "uber", "ola"], "dr"),
]


# ---------------------------------------------------------------- parsing
def _map_bank_columns(cols: list[str]) -> dict[str, str]:
    norm = {c: " ".join(re.sub(r"[^a-z0-9 ]", " ", str(c).lower()).split()) for c in cols}
    want = {
        "txn_date": ["txn date", "transaction date", "tran date", "date", "posting date", "trans date"],
        "value_date": ["value date", "value dt"],
        "narration": ["narration", "description", "particulars", "remarks", "transaction details", "details"],
        "reference": ["chq ref no", "chq no", "cheque no", "ref no", "reference", "reference no", "utr", "chq ref number",
                      "ref no cheque no", "cheque number"],
        "debit": ["debit", "withdrawal", "withdrawal amt", "withdrawals", "debit amount", "dr", "withdrawal dr"],
        "credit": ["credit", "deposit", "deposit amt", "deposits", "credit amount", "cr", "deposit cr"],
        "balance": ["balance", "closing balance", "running balance", "balance inr"],
        "amount": ["amount", "transaction amount"],
        "drcr": ["dr cr", "type", "cr dr", "debit credit"],
    }
    out: dict[str, str] = {}
    for key, syns in want.items():
        for syn in syns:
            hit = next((c for c, n in norm.items() if n == syn and c not in out.values()), None)
            if hit is None:
                hit = next((c for c, n in norm.items() if n.startswith(syn) and c not in out.values()), None)
            if hit:
                out[key] = hit
                break
    return out


def _continuity(txns: list[dict], opening: Decimal | None) -> list[str]:
    warnings = []
    prev = opening
    for i, t in enumerate(txns, start=1):
        bal = D(t.get("balance"), None)
        if prev is not None and bal is not None:
            expected = prev + D(t["credit"]) - D(t["debit"])
            if expected != bal:
                warnings.append(f"Row {i}: balance {bal} does not follow from previous balance ({expected})")
        prev = bal if bal is not None else (prev + D(t["credit"]) - D(t["debit"]) if prev is not None else None)
    return warnings[:20]


def parse_statement_table(df) -> dict:
    cols = _map_bank_columns(list(df.columns))
    warnings: list[str] = []
    if "txn_date" not in cols or "narration" not in cols:
        return {"transactions": [], "warnings": ["Could not find Date/Narration columns"], "opening_balance": None,
                "closing_balance": None}
    txns = []
    for _, r in df.iterrows():
        d = to_date(str(r[cols["txn_date"]]).strip())
        if d is None:
            continue
        if "debit" in cols or "credit" in cols:
            debit = D(r[cols["debit"]]) if "debit" in cols else ZERO
            credit = D(r[cols["credit"]]) if "credit" in cols else ZERO
        elif "amount" in cols:
            amt = D(r[cols["amount"]])
            flag = str(r[cols["drcr"]]).strip().lower() if "drcr" in cols else ""
            debit, credit = (abs(amt), ZERO) if (flag.startswith("d") or amt < 0) else (ZERO, abs(amt))
        else:
            continue
        txns.append({"txn_date": d.isoformat(), "value_date": (to_date(str(r[cols["value_date"]])) or d).isoformat()
                     if "value_date" in cols else d.isoformat(), "narration": str(r[cols["narration"]]).strip()[:500],
                     "reference": str(r[cols["reference"]]).strip()[:100] if "reference" in cols else "",
                     "debit": str(abs(debit)), "credit": str(abs(credit)),
                     "balance": str(D(r[cols["balance"]], None)) if "balance" in cols and D(r[cols["balance"]], None) is not None else None})
    opening = None
    if txns and txns[0]["balance"] is not None:
        opening = D(txns[0]["balance"]) - D(txns[0]["credit"]) + D(txns[0]["debit"])
    warnings += _continuity(txns, opening)
    return {"transactions": txns, "warnings": warnings, "opening_balance": str(opening) if opening is not None else None,
            "closing_balance": txns[-1]["balance"] if txns else None}


ROW_RE = re.compile(r"^(?P<date>\d{1,2}[/\-.](?:\d{1,2}|[A-Za-z]{3})[/\-.]\d{2,4})\s+(?P<rest>.+)$")
AMT_RE = re.compile(r"(\d{1,3}(?:,\d{2,3})*\.\d{2}|\d+\.\d{2})(\s*(?:Cr|Dr|CR|DR))?")


def parse_statement_text(text: str) -> dict:
    """Parse a digital-PDF bank statement. Debit/credit sides are inferred only from balance movement."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    opening = None
    m = re.search(r"opening\s*balance\s*[:\-]?\s*(?:INR|Rs\.?)?\s*([\d,]+\.\d{2})", text, re.I)
    if m:
        opening = D(m.group(1))
    txns, warnings = [], []
    prev = opening
    for ln in lines:
        rm = ROW_RE.match(ln)
        if not rm:
            continue
        d = to_date(rm.group("date").replace(".", "/"))
        if d is None:
            continue
        amts = AMT_RE.findall(rm.group("rest"))
        if len(amts) < 2:
            continue
        amount, balance = D(amts[-2][0]), D(amts[-1][0])
        narration = AMT_RE.sub("", rm.group("rest")).strip()
        narration = re.sub(r"^\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\s+", "", narration)  # value date
        if prev is not None:
            if prev + amount == balance:
                debit, credit = ZERO, amount
            elif prev - amount == balance:
                debit, credit = amount, ZERO
            else:
                warnings.append(f"{d}: could not determine debit/credit for {amount}")
                debit, credit = ZERO, ZERO
        else:
            warnings.append(f"{d}: opening balance unknown — side of {amount} undetermined")
            debit, credit = ZERO, ZERO
        prev = balance
        ref = re.search(r"\b(?:UTR|REF|CHQ)[\s:.#]*([A-Z0-9]{6,22})", narration, re.I)
        txns.append({"txn_date": d.isoformat(), "value_date": d.isoformat(), "narration": narration[:500],
                     "reference": ref.group(1) if ref else "", "debit": str(debit), "credit": str(credit),
                     "balance": str(balance)})
    return {"transactions": txns, "warnings": warnings[:30], "opening_balance": str(opening) if opening is not None else None,
            "closing_balance": txns[-1]["balance"] if txns else None}


def parse_statement_file(data: bytes, ext: str) -> dict:
    if ext in (".csv", ".xlsx"):
        out = parse_statement_table(read_table(data, ext))
        out["raw_text"] = ""
        return out
    if ext == ".pdf":
        tr = extract_pdf(data)
        if tr.unreadable_pages and len(tr.unreadable_pages) == len(tr.pages):
            return {"transactions": [], "warnings": ["Scanned bank statement: OCR/AI required, or upload the bank's CSV/Excel export"],
                    "opening_balance": None, "closing_balance": None, "raw_text": ""}
        out = parse_statement_text(tr.text)
        out["raw_text"] = tr.text[:100000]
        return out
    return {"transactions": [], "warnings": ["Bank statement images are not supported — upload PDF/CSV/Excel"],
            "opening_balance": None, "closing_balance": None, "raw_text": ""}


# ---------------------------------------------------------------- classification
def classify_transaction(narration: str, debit: Decimal, credit: Decimal, parties: list[dict] | None = None) -> tuple[str, float, str | None]:
    n = f" {(narration or '').lower()} "
    side = "dr" if debit > 0 else "cr"
    for cat, words, direction in RULES:
        if direction and direction != side:
            continue
        if any(w in n for w in words):
            return cat, 0.85, None
    best, best_score = None, 0.0
    for p in parties or []:
        s = name_similarity(p["name"], narration)
        if s > best_score:
            best, best_score = p, s
    if best and best_score >= 0.5:
        if side == "cr" and best["group_name"] == "Sundry Debtors":
            return "customer_receipt", 0.6 + 0.3 * best_score, best["id"]
        if side == "dr" and best["group_name"] == "Sundry Creditors":
            return "supplier_payment", 0.6 + 0.3 * best_score, best["id"]
    if any(k in n for k in ("neft", "rtgs", "imps", "upi", "chq", "clg", "transfer")):
        return ("customer_receipt" if side == "cr" else "supplier_payment"), 0.4, None
    return "unknown", 0.2, None


# ---------------------------------------------------------------- accounts & import
def create_bank_account(ctx: AuthContext, client_id: str, bank_name: str, account_no: str = "", ifsc: str = "") -> str:
    client = require_client(ctx, client_id, "bank_reconcile")
    masked = ("XXXX" + account_no[-4:]) if account_no else None
    name = f"{bank_name.strip()} {masked or ''}".strip()
    db = get_db()
    with db.transaction():
        existing = db.fetchone("select id from ledgers where client_id = ? and name = ?", [client_id, name])
        lid = existing["id"] if existing else db.insert("ledgers", {
            "firm_id": client["firm_id"], "client_id": client_id, "name": name, "group_name": "Bank Accounts",
            "nature": "asset", "created_at": now_iso()})
        bid = db.insert("bank_accounts", {"firm_id": client["firm_id"], "client_id": client_id, "ledger_id": lid,
                                          "bank_name": bank_name.strip(), "account_no_masked": masked, "ifsc": ifsc or None,
                                          "created_at": now_iso()})
    audit(ctx, "bank_account.created", "bank_accounts", bid, client_id=client_id, after={"bank": bank_name})
    return bid


def list_bank_accounts(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select b.*, l.name as ledger_name from bank_accounts b join ledgers l on l.id = b.ledger_id "
                             "where b.client_id = ? order by b.bank_name", [client_id])


def _txn_hash(t: dict) -> str:
    key = "|".join(str(t.get(k) or "") for k in ("txn_date", "narration", "reference", "debit", "credit", "balance"))
    return hashlib.sha256(key.encode()).hexdigest()


def import_statement(ctx: AuthContext, client_id: str, bank_account_id: str, parsed: dict, document_id: str | None = None) -> dict:
    client = require_client(ctx, client_id, "bank_reconcile")
    acct = scoped_get(ctx, "bank_accounts", bank_account_id, "bank_reconcile")
    if acct["client_id"] != client_id:
        raise PermissionDenied("Bank account belongs to another client")
    txns = parsed.get("transactions") or []
    if not txns:
        raise ValueError("No transactions to import")
    db = get_db()
    parties = db.fetchall("select id, name, group_name from ledgers where client_id = ? and group_name in "
                          "('Sundry Debtors','Sundry Creditors')", [client_id])
    dates = [to_date(t["txn_date"]) for t in txns]
    for d in {(x.year, x.month) for x in dates}:
        assert_period_open(client_id, dt.date(d[0], d[1], 1))
    stats = {"imported": 0, "duplicates": 0}
    with db.transaction():
        sid = db.insert("bank_statements", {"firm_id": client["firm_id"], "client_id": client_id, "bank_account_id": bank_account_id,
                                            "document_id": document_id, "period_from": min(dates), "period_to": max(dates),
                                            "opening_balance": D(parsed.get("opening_balance"), None),
                                            "closing_balance": D(parsed.get("closing_balance"), None),
                                            "created_by": ctx.user_id, "created_at": now_iso()})
        seen: set[str] = set()
        for t in txns:
            h = _txn_hash(t)
            dup = h in seen or db.fetchone("select id from bank_transactions where bank_account_id = ? and txn_hash = ?",
                                           [bank_account_id, h]) is not None
            seen.add(h)
            debit, credit = D(t["debit"]), D(t["credit"])
            cat, conf, party = classify_transaction(t["narration"], debit, credit, parties)
            db.insert("bank_transactions", {
                "firm_id": client["firm_id"], "client_id": client_id, "bank_account_id": bank_account_id, "statement_id": sid,
                "txn_date": to_date(t["txn_date"]), "value_date": to_date(t.get("value_date")), "narration": t["narration"],
                "reference": t.get("reference") or None, "debit": debit, "credit": credit, "balance": D(t.get("balance"), None),
                "category": cat, "category_confidence": Decimal(str(round(conf * 100, 2))), "party_ledger_id": party,
                "match_status": "duplicate" if dup else "unmatched", "txn_hash": h, "created_at": now_iso()})
            stats["duplicates" if dup else "imported"] += 1
        if document_id:
            db.update("documents", document_id, {"status": "approved", "reviewed_by": ctx.user_id, "reviewed_at": now_iso()})
        audit(ctx, "bank_statement.imported", "bank_statements", sid, client_id=client_id, after=stats)
    return stats


def list_transactions(ctx: AuthContext, client_id: str, bank_account_id: str | None = None, date_from=None, date_to=None,
                      status: str | None = None) -> list[dict]:
    require_client(ctx, client_id, "view")
    sql = "select t.*, l.name as party_name from bank_transactions t left join ledgers l on l.id = t.party_ledger_id where t.client_id = ?"
    p: list = [client_id]
    for cond, val in (("t.bank_account_id = ?", bank_account_id), ("t.txn_date >= ?", date_from), ("t.txn_date <= ?", date_to),
                      ("t.match_status = ?", status)):
        if val:
            sql += f" and {cond}"
            p.append(val)
    return get_db().fetchall(sql + " order by t.txn_date, t.created_at", p)


def set_category(ctx: AuthContext, txn_id: str, category: str, party_ledger_id: str | None = None) -> None:
    t = scoped_get(ctx, "bank_transactions", txn_id, "bank_reconcile")
    if category not in CATEGORIES:
        raise ValueError("Unknown category")
    if party_ledger_id:
        led = scoped_get(ctx, "ledgers", party_ledger_id, "bank_reconcile")
        if led["client_id"] != t["client_id"]:
            raise PermissionDenied("Ledger belongs to another client")
    get_db().update("bank_transactions", txn_id, {"category": category, "category_confidence": Decimal("100"),
                                                  "party_ledger_id": party_ledger_id})
    audit(ctx, "bank_txn.categorised", "bank_transactions", txn_id, client_id=t["client_id"],
          before={"category": t["category"]}, after={"category": category})


# ---------------------------------------------------------------- matching
def _matched_amount(target_type: str, target_id: str) -> Decimal:
    rows = get_db().fetchall("select amount from bank_matches where target_type = ? and target_id = ? and status = 'confirmed'",
                             [target_type, target_id])
    return sum((D(r["amount"]) for r in rows), ZERO)


def _matched_amounts(target_type: str, target_ids: list[str]) -> dict[str, Decimal]:
    """Bulk version of _matched_amount — one query for all ids instead of one query per id."""
    if not target_ids:
        return {}
    marks = ",".join("?" for _ in target_ids)
    rows = get_db().fetchall(f"select target_id, amount from bank_matches where target_type = ? and target_id in ({marks}) "
                             f"and status = 'confirmed'", [target_type, *target_ids])
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r["target_id"]] = out.get(r["target_id"], ZERO) + D(r["amount"])
    return out


def open_invoices(client_id: str, side: str) -> list[dict]:
    """side 'cr' (money in) -> sales invoices; 'dr' -> purchase/expense invoices. Excludes notes."""
    cats = ("sales",) if side == "cr" else ("purchase", "expense")
    marks = ",".join("?" for _ in cats)
    rows = get_db().fetchall(f"select * from invoices where client_id = ? and status = 'approved' and note_type = 'invoice' "
                             f"and category in ({marks}) order by invoice_date", [client_id, *cats])
    matched = _matched_amounts("invoice", [r["id"] for r in rows])
    out = []
    for r in rows:
        r["outstanding"] = D(r["total"]) - matched.get(r["id"], ZERO)
        if r["outstanding"] > 0:
            out.append(r)
    return out


def _score_invoice(t: dict, inv: dict, amount: Decimal) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    if amount == inv["outstanding"]:
        score += 50
        reasons.append("amount equals outstanding")
    elif amount < inv["outstanding"]:
        score += 20
        reasons.append("part payment of outstanding")
    else:
        return 0.0, []
    tdate, idate = to_date(t["txn_date"]), to_date(inv["invoice_date"])
    gap = (tdate - idate).days
    if 0 <= gap <= 30:
        score += 15
        reasons.append(f"{gap} days after invoice")
    elif 30 < gap <= 120:
        score += 7
    elif gap < -3:
        score -= 20
        reasons.append("payment dated before invoice")
    sim = name_similarity(inv["party_name"], t["narration"])
    if t.get("party_ledger_id"):
        led = get_db().get("ledgers", t["party_ledger_id"])
        if led and (led.get("party_gstin") == inv.get("party_gstin") or led["name"] == inv["party_name"]):
            sim = max(sim, 1.0)
    score += 25 * sim
    if sim >= 0.5:
        reasons.append("party name in narration")
    no = normalize_invoice_no(inv["invoice_no"])
    if no and len(no) >= 3 and no in re.sub(r"[^A-Za-z0-9]", "", (t["narration"] or "") + (t.get("reference") or "")).upper():
        score += 20
        reasons.append("invoice number in narration")
    return min(score, 100.0), reasons


def _score_voucher(t: dict, v: dict, amount: Decimal) -> tuple[float, list[str]]:
    if D(v["total_amount"]) != amount:
        return 0.0, []
    score, reasons = 55.0, ["same amount"]
    gap = abs((to_date(t["txn_date"]) - to_date(v["voucher_date"])).days)
    if gap <= 3:
        score += 30
        reasons.append("date within 3 days")
    elif gap <= 10:
        score += 15
    ref = (v.get("reference_no") or "").upper()
    if ref and ref in ((t.get("reference") or "") + (t["narration"] or "")).upper():
        score += 15
        reasons.append("reference matches")
    return min(score, 100.0), reasons


def auto_match(ctx: AuthContext, client_id: str, bank_account_id: str | None = None) -> dict:
    require_client(ctx, client_id, "bank_reconcile")
    db = get_db()
    txns = [t for t in list_transactions(ctx, client_id, bank_account_id) if t["match_status"] in ("unmatched", "needs_review")
            and not t.get("voucher_id")]
    stats = {s: 0 for s in MATCH_STATUSES}
    linked_vouchers = {r["voucher_id"] for r in db.fetchall("select voucher_id from bank_transactions where client_id = ? and "
                                                            "voucher_id is not null", [client_id])}

    # Pull each side's open invoices and candidate vouchers once per auto_match run (not once per transaction) —
    # over a remote DB connection, repeating these queries per transaction made a batch of N transactions cost
    # roughly N times the open-invoice count in round trips. `matched_by_invoice` is updated in place as matches
    # are confirmed below, so outstanding amounts still reflect matches made earlier in this same run.
    def _raw_invoices(side: str) -> list[dict]:
        cats = ("sales",) if side == "cr" else ("purchase", "expense")
        marks = ",".join("?" for _ in cats)
        return db.fetchall(f"select * from invoices where client_id = ? and status = 'approved' and note_type = 'invoice' "
                           f"and category in ({marks}) order by invoice_date", [client_id, *cats])

    raw_invoices = {"cr": _raw_invoices("cr"), "dr": _raw_invoices("dr")}
    matched_by_invoice = _matched_amounts("invoice", [r["id"] for rows in raw_invoices.values() for r in rows])

    def open_invoices_live(side: str) -> list[dict]:
        out = []
        for r in raw_invoices[side]:
            outstanding = D(r["total"]) - matched_by_invoice.get(r["id"], ZERO)
            if outstanding > 0:
                rr = dict(r)
                rr["outstanding"] = outstanding
                out.append(rr)
        return out

    voucher_candidates: dict[tuple[str, str], list[dict]] = {}

    def _candidate_vouchers(ledger_id: str, vtype: str) -> list[dict]:
        key = (ledger_id, vtype)
        if key not in voucher_candidates:
            voucher_candidates[key] = db.fetchall(
                "select v.* from accounting_vouchers v join accounting_voucher_entries e on e.voucher_id = v.id "
                "where v.client_id = ? and v.voucher_type = ? and v.status in ('draft','approved') and e.ledger_id = ? "
                "and v.source_type <> 'bank'", [client_id, vtype, ledger_id])
        return voucher_candidates[key]

    for t in txns:
        side = "cr" if D(t["credit"]) > 0 else "dr"
        amount = D(t["credit"]) if side == "cr" else D(t["debit"])
        db.execute("delete from bank_matches where transaction_id = ? and status = 'suggested'", [t["id"]])
        cands: list[tuple[float, str, dict, list[str], Decimal]] = []
        if t["category"] in ("customer_receipt", "supplier_payment", "unknown", "expense_payment"):
            for inv in open_invoices_live(side):
                s, r = _score_invoice(t, inv, amount)
                if s >= 40:
                    cands.append((s, "invoice", inv, r, min(amount, inv["outstanding"])))
        acct = db.get("bank_accounts", t["bank_account_id"])
        vtypes = ("Receipt",) if side == "cr" else ("Payment",)
        for v in _candidate_vouchers(acct["ledger_id"], vtypes[0]):
            if v["id"] in linked_vouchers:
                continue
            s, r = _score_voucher(t, v, amount)
            if s >= 55:
                cands.append((s, "voucher", v, r, amount))
        cands.sort(key=lambda c: -c[0])
        status = "unmatched"
        if cands:
            best = cands[0]
            unique = len(cands) == 1 or cands[1][0] < best[0] - 15
            full = best[4] == amount and (best[1] == "voucher" or best[2]["outstanding"] == amount)
            if best[0] >= 85 and unique and full:
                status = "matched"
                db.insert("bank_matches", {"firm_id": t["firm_id"], "client_id": client_id, "transaction_id": t["id"],
                                           "target_type": best[1], "target_id": best[2]["id"], "amount": best[4],
                                           "score": Decimal(str(round(best[0], 2))), "reasons": best[3], "status": "confirmed",
                                           "confirmed_at": now_iso(), "created_at": now_iso()})
                if best[1] == "voucher":
                    db.update("bank_transactions", t["id"], {"voucher_id": best[2]["id"]})
                    linked_vouchers.add(best[2]["id"])
                else:
                    matched_by_invoice[best[2]["id"]] = matched_by_invoice.get(best[2]["id"], ZERO) + best[4]
            else:
                status = "partially_matched" if (best[1] == "invoice" and best[4] < best[2]["outstanding"]) else "needs_review"
                for s, ttype, target, reasons, amt in cands[:5]:
                    db.insert("bank_matches", {"firm_id": t["firm_id"], "client_id": client_id, "transaction_id": t["id"],
                                               "target_type": ttype, "target_id": target["id"], "amount": amt,
                                               "score": Decimal(str(round(s, 2))), "reasons": reasons, "status": "suggested",
                                               "created_at": now_iso()})
        if status == "unmatched" and side == "cr" and t["category"] in ("customer_receipt", "unknown"):
            # one receipt settling several invoices of the same party
            by_party: dict[str, list[dict]] = {}
            for inv in open_invoices_live(side):
                if name_similarity(inv["party_name"], t["narration"]) >= 0.5:
                    by_party.setdefault(inv["party_name"], []).append(inv)
            for invs in by_party.values():
                for k in (2, 3):
                    for combo in itertools.combinations(invs[:8], k):
                        if sum((i["outstanding"] for i in combo), ZERO) == amount:
                            status = "needs_review"
                            for inv in combo:
                                db.insert("bank_matches", {"firm_id": t["firm_id"], "client_id": client_id, "transaction_id": t["id"],
                                                           "target_type": "invoice", "target_id": inv["id"], "amount": inv["outstanding"],
                                                           "score": Decimal("70"), "reasons": ["combination of invoices sums to amount"],
                                                           "status": "suggested", "created_at": now_iso()})
                            break
                    if status != "unmatched":
                        break
        if status == "unmatched" and t["category"] == "unknown":
            status = "suspense"
        db.update("bank_transactions", t["id"], {"match_status": status,
                                                 "match_score": Decimal(str(round(cands[0][0], 2))) if cands else None})
        stats[status] += 1
    audit(ctx, "bank.auto_match", "bank_transactions", None, client_id=client_id, after=stats)
    return stats


def suggestions(ctx: AuthContext, txn_id: str) -> list[dict]:
    t = scoped_get(ctx, "bank_transactions", txn_id, "view")
    rows = get_db().fetchall("select * from bank_matches where transaction_id = ? order by score desc", [txn_id])
    for r in rows:
        tgt = get_db().get("invoices" if r["target_type"] == "invoice" else "accounting_vouchers", r["target_id"])
        if tgt and tgt["client_id"] == t["client_id"]:
            r["label"] = (f"Invoice {tgt['invoice_no']} · {tgt['party_name']} · {tgt['total']}" if r["target_type"] == "invoice"
                          else f"Voucher {tgt['voucher_no']} · {tgt['total_amount']}")
    return rows


def confirm_match(ctx: AuthContext, txn_id: str, targets: list[dict]) -> str:
    """Manual matching. targets: [{target_type, target_id, amount}]."""
    t = scoped_get(ctx, "bank_transactions", txn_id, "bank_reconcile")
    if t["match_status"] == "duplicate":
        raise ValueError("Duplicate transactions cannot be matched")
    amount = D(t["credit"]) if D(t["credit"]) > 0 else D(t["debit"])
    db = get_db()
    total = ZERO
    with db.transaction():
        db.execute("delete from bank_matches where transaction_id = ?", [txn_id])
        for tg in targets:
            table = "invoices" if tg["target_type"] == "invoice" else "accounting_vouchers"
            row = scoped_get(ctx, table, tg["target_id"], "bank_reconcile")
            if row["client_id"] != t["client_id"]:
                raise PermissionDenied("Target belongs to another client")
            amt = D(tg["amount"])
            if tg["target_type"] == "invoice":
                outstanding = D(row["total"]) - _matched_amount("invoice", row["id"])
                if amt > outstanding:
                    raise ValueError(f"Amount {amt} exceeds outstanding {outstanding} on invoice {row['invoice_no']}")
            total += amt
            db.insert("bank_matches", {"firm_id": t["firm_id"], "client_id": t["client_id"], "transaction_id": txn_id,
                                       "target_type": tg["target_type"], "target_id": tg["target_id"], "amount": amt,
                                       "score": Decimal("100"), "reasons": ["manual"], "status": "confirmed",
                                       "confirmed_by": ctx.user_id, "confirmed_at": now_iso(), "created_at": now_iso()})
            if tg["target_type"] == "voucher":
                db.update("bank_transactions", txn_id, {"voucher_id": tg["target_id"]})
        if total > amount:
            raise ValueError(f"Matched total {total} exceeds transaction amount {amount}")
        status = "matched" if total == amount else "partially_matched"
        db.update("bank_transactions", txn_id, {"match_status": status, "match_score": Decimal("100")})
        audit(ctx, "bank.manual_match", "bank_transactions", txn_id, client_id=t["client_id"],
              after={"targets": [{k: str(v) for k, v in x.items()} for x in targets], "status": status})
    return status


def unmatch(ctx: AuthContext, txn_id: str) -> None:
    t = scoped_get(ctx, "bank_transactions", txn_id, "bank_reconcile")
    db = get_db()
    if t.get("voucher_id"):
        v = db.get("accounting_vouchers", t["voucher_id"])
        if v and v["source_type"] == "bank" and v["status"] == "approved":
            raise ValueError("An approved voucher was generated from this transaction; cancel it first")
    with db.transaction():
        db.execute("delete from bank_matches where transaction_id = ?", [txn_id])
        db.update("bank_transactions", txn_id, {"match_status": "unmatched", "match_score": None, "voucher_id": None})
        if t.get("voucher_id"):
            v = db.get("accounting_vouchers", t["voucher_id"])
            if v and v["source_type"] == "bank" and v["status"] == "draft":
                db.update("accounting_vouchers", v["id"], {"status": "cancelled", "review_reason": "bank match removed"})
    audit(ctx, "bank.unmatch", "bank_transactions", txn_id, client_id=t["client_id"])


def mark_duplicate(ctx: AuthContext, txn_id: str, is_duplicate: bool = True) -> None:
    t = scoped_get(ctx, "bank_transactions", txn_id, "bank_reconcile")
    get_db().update("bank_transactions", txn_id, {"match_status": "duplicate" if is_duplicate else "unmatched"})
    audit(ctx, "bank.duplicate_flag", "bank_transactions", txn_id, client_id=t["client_id"], after={"duplicate": is_duplicate})


# ---------------------------------------------------------------- vouchers from bank
CATEGORY_LEDGER = {"bank_charges": "exp:bank_charges", "salary": "exp:salary", "tax_payment": "tax_payment",
                   "loan": "loan"}


def build_bank_voucher(client: dict, t: dict, bank_ledger_id: str) -> ae.VoucherDraft:
    cid = client["id"]
    L = lambda k: ae.mapped_ledger(cid, k)["id"]  # noqa: E731
    db = get_db()
    is_credit = D(t["credit"]) > 0
    amount = D(t["credit"]) if is_credit else D(t["debit"])
    reasons: list[str] = []
    counter: list[tuple[str, Decimal]] = []
    vtype = "Receipt" if is_credit else "Payment"
    matches = db.fetchall("select * from bank_matches where transaction_id = ? and status = 'confirmed' and target_type = 'invoice'",
                          [t["id"]])
    if matches:
        for m in matches:
            inv = db.get("invoices", m["target_id"])
            party = ae.get_or_create_party_ledger(client, inv["party_name"], inv.get("party_gstin"),
                                                  "debtor" if inv["category"] == "sales" else "creditor")
            counter.append((party["id"], D(m["amount"])))
        rest = amount - sum((a for _, a in counter), ZERO)
        if rest > 0:
            counter.append((L("suspense"), rest))
            reasons.append(f"{rest} not matched to invoices — posted to Suspense")
    else:
        cat = t["category"]
        n = (t["narration"] or "").lower()
        if cat == "interest":
            counter.append((L("income:interest") if is_credit else L("exp:interest"), amount))
        elif cat == "transfer" and any(k in n for k in ("cash", "atm", "atw")):
            vtype = "Contra"
            counter.append((L("cash"), amount))
        elif cat in CATEGORY_LEDGER:
            counter.append((L(CATEGORY_LEDGER[cat]), amount))
            if cat in ("tax_payment", "loan"):
                reasons.append(f"{CATEGORIES[cat]}: confirm the exact ledger (GST/TDS/income tax; principal vs interest)")
        elif cat == "expense_payment":
            key, confident = ae.classify_expense_head(t["narration"])
            counter.append((L(key), amount))
            if not confident:
                reasons.append("Expense head defaulted")
        elif cat in ("customer_receipt", "supplier_payment") and t.get("party_ledger_id"):
            counter.append((t["party_ledger_id"], amount))
            reasons.append("Posted on account to party (no invoice matched)")
        else:
            counter.append((L("suspense"), amount))
            reasons.append("Unidentified transaction posted to Suspense")
        if (t.get("category_confidence") is not None and D(t["category_confidence"]) < 80):
            reasons.append(f"Low classification confidence ({t['category_confidence']}%)")
    lines = [ae.Line(bank_ledger_id, "Dr" if is_credit else "Cr", amount)]
    for lid, amt in counter:
        lines.append(ae.Line(lid, "Cr" if is_credit else "Dr", amt))
    party_id = counter[0][0] if counter else None
    return ae.VoucherDraft(vtype, to_date(t["txn_date"]), lines, narration=(t["narration"] or "")[:250],
                           party_ledger_id=party_id, reference_no=t.get("reference") or None,
                           needs_review=bool(reasons), review_reasons=reasons)


def generate_vouchers(ctx: AuthContext, client_id: str, txn_ids: list[str]) -> dict:
    client = require_client(ctx, client_id, "prepare_vouchers")
    db = get_db()
    out = {"created": 0, "skipped": 0, "errors": []}
    for tid in txn_ids:
        t = scoped_get(ctx, "bank_transactions", tid, "prepare_vouchers")
        if t["client_id"] != client_id or t["match_status"] == "duplicate" or t.get("voucher_id"):
            out["skipped"] += 1
            continue
        acct = db.get("bank_accounts", t["bank_account_id"])
        try:
            draft = build_bank_voucher(client, t, acct["ledger_id"])
            vid = ae.create_voucher(ctx, client_id, draft, source_type="bank", source_id=tid)
            upd = {"voucher_id": vid}
            if t["match_status"] in ("unmatched", "suspense", "needs_review") and not draft.needs_review:
                upd["match_status"] = "matched"
            db.update("bank_transactions", tid, upd)
            out["created"] += 1
        except Exception as exc:
            out["errors"].append(f"{t['txn_date']} {t['narration'][:40]}: {exc}")
    return out


# ---------------------------------------------------------------- BRS
def reconciliation(ctx: AuthContext, client_id: str, bank_account_id: str, as_of: dt.date) -> dict:
    client = require_client(ctx, client_id, "view")
    acct = scoped_get(ctx, "bank_accounts", bank_account_id, "view")
    db = get_db()
    from utils.helpers import fy_bounds, fy_label_for

    fy = fy_label_for(as_of, client.get("fy_start_month") or 4)
    fy_start, _ = fy_bounds(fy, client.get("fy_start_month") or 4)
    lid = acct["ledger_id"]
    book = ae.opening_balances(client_id, fy).get(lid, ZERO) + ae.ledger_movements(client_id, fy_start, as_of).get(lid, ZERO)
    last = db.fetchone("select balance from bank_transactions where bank_account_id = ? and txn_date <= ? and balance is not null "
                       "and match_status <> 'duplicate' order by txn_date desc, created_at desc", [bank_account_id, as_of])
    stmt_balance = D(last["balance"]) if last else None
    linked = {r["voucher_id"] for r in db.fetchall("select voucher_id from bank_transactions where bank_account_id = ? and "
                                                   "voucher_id is not null", [bank_account_id])}
    entries = db.fetchall("select v.id, v.voucher_no, v.voucher_date, v.narration, e.dr_cr, e.amount from accounting_vouchers v "
                          "join accounting_voucher_entries e on e.voucher_id = v.id where v.client_id = ? and e.ledger_id = ? "
                          "and v.status = 'approved' and v.voucher_date <= ?", [client_id, lid, as_of])
    pending_dep = [e for e in entries if e["id"] not in linked and e["dr_cr"] == "Dr"]
    pending_pay = [e for e in entries if e["id"] not in linked and e["dr_cr"] == "Cr"]
    txns = db.fetchall("select t.*, v.status as vstatus from bank_transactions t left join accounting_vouchers v on v.id = t.voucher_id "
                       "where t.bank_account_id = ? and t.txn_date <= ? and t.match_status <> 'duplicate'", [bank_account_id, as_of])
    not_in_books = [t for t in txns if not t.get("voucher_id") or t.get("vstatus") != "approved"]
    matched = [t for t in txns if t.get("voucher_id") and t.get("vstatus") == "approved"]
    dep_total = sum((D(e["amount"]) for e in pending_dep), ZERO)
    pay_total = sum((D(e["amount"]) for e in pending_pay), ZERO)
    bank_cr = sum((D(t["credit"]) for t in not_in_books), ZERO)
    bank_dr = sum((D(t["debit"]) for t in not_in_books), ZERO)
    adjusted_bank = (stmt_balance or ZERO) + dep_total - pay_total
    adjusted_book = book + bank_cr - bank_dr
    return {"as_of": as_of, "bank_ledger": acct.get("bank_name"), "book_balance": book, "statement_balance": stmt_balance,
            "pending_deposits": pending_dep, "pending_payments": pending_pay, "not_in_books": not_in_books,
            "matched_count": len(matched), "pending_deposits_total": dep_total, "pending_payments_total": pay_total,
            "bank_credits_not_in_books": bank_cr, "bank_debits_not_in_books": bank_dr, "adjusted_bank_balance": adjusted_bank,
            "adjusted_book_balance": adjusted_book, "difference": adjusted_book - adjusted_bank,
            "statement_available": stmt_balance is not None}
