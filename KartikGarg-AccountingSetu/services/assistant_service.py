"""AI Financial Assistant.

The question is mapped to one of a fixed set of intents (by Claude when configured, otherwise by a
deterministic keyword matcher). Each intent is answered by a Python function that reads ONLY the
records the authenticated user may access (tenancy.require_client / accessible_client_ids) and
computes figures with Decimal. The language model never sees other tenants' data and never
produces numbers.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
from collections import defaultdict
from decimal import Decimal

from services import ai_service, gst_service, report_service
from services.db import get_db
from services.tenancy import AuthContext, accessible_client_ids, require_client
from utils.helpers import D, ZERO, fy_bounds, fy_label_for, money, month_bounds, normalize_invoice_no, prev_month

INTENTS = {
    "sales_total": "Total sales for a period",
    "purchase_total": "Total purchases for a period",
    "expense_total": "Total expenses for a period",
    "profit": "Profit / loss for a period",
    "gst_liability": "Estimated GST liability for a period",
    "missing_in_2b": "Purchase invoices missing from GSTR-2B",
    "unmatched_bank": "Unmatched bank transactions",
    "compare_months": "Compare a month with the previous month",
    "pending_submissions": "Which clients have not submitted documents (firm staff only)",
    "duplicate_invoices": "Invoices with duplicate numbers",
    "receivables": "Outstanding receivables / debtors",
    "payables": "Outstanding payables / creditors",
    "top_customers": "Top customers by sales",
    "top_suppliers": "Top suppliers by purchases",
    "document_status": "Status of uploaded documents",
}

KEYWORDS = [
    ("pending_submissions", [r"not submitted", r"pending submission", r"haven'?t submitted", r"which clients"]),
    ("missing_in_2b", [r"2b", r"gstr-?2b"]),
    ("unmatched_bank", [r"unmatched", r"unreconciled", r"bank transactions?"]),
    ("duplicate_invoices", [r"duplicate"]),
    ("compare_months", [r"compare", r"versus", r"\bvs\b", r"previous month"]),
    ("gst_liability", [r"gst liability", r"gst payable", r"\bgst\b", r"tax liability"]),
    ("top_customers", [r"top customers?", r"biggest customers?", r"largest customers?"]),
    ("top_suppliers", [r"top suppliers?", r"top vendors?", r"biggest suppliers?"]),
    ("receivables", [r"receivable", r"debtors?", r"owed to (me|us)", r"outstanding from"]),
    ("payables", [r"payable", r"creditors?", r"(i|we) owe"]),
    ("profit", [r"profit", r"loss", r"net income", r"margin"]),
    ("expense_total", [r"expense", r"spend", r"spent"]),
    ("purchase_total", [r"purchase"]),
    ("sales_total", [r"sales", r"revenue", r"turnover", r"sold"]),
    ("document_status", [r"document", r"upload", r"status"]),
]


def keyword_intent(question: str) -> str | None:
    q = question.lower()
    for intent, pats in KEYWORDS:
        if any(re.search(p, q) for p in pats):
            return intent
    return None


def parse_period(text: str, client: dict | None, today: dt.date | None = None) -> tuple[dt.date, dt.date, str]:
    today = today or dt.date.today()
    t = (text or "").lower()
    sm = (client or {}).get("fy_start_month") or 4
    if "last month" in t or "previous month" in t or t == "last_month":
        y, m = prev_month(today.year, today.month)
        s, e = month_bounds(y, m)
        return s, e, f"{calendar.month_name[m]} {y}"
    if re.search(r"(last|previous) (fy|financial year|year)", t) or t == "last_fy":
        label = fy_label_for(today.replace(year=today.year - 1), sm)
        s, e = fy_bounds(label, sm)
        return s, e, f"FY {label}"
    if re.search(r"(this|current) (fy|financial year|year)|year to date|ytd", t) or t == "this_fy":
        label = fy_label_for(today, sm)
        s, _ = fy_bounds(label, sm)
        return s, today, f"FY {label} (to date)"
    m = re.search(r"(\d{4})-(\d{2})", t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        s, e = month_bounds(y, mo)
        return s, e, f"{calendar.month_name[mo]} {y}"
    for i in range(1, 13):
        names = (calendar.month_name[i].lower(), calendar.month_abbr[i].lower())
        mm = re.search(rf"\b({names[0]}|{names[1]})\b\s*,?\s*(\d{{4}})?", t)
        if mm:
            y = int(mm.group(2)) if mm.group(2) else (today.year if i <= today.month else today.year - 1)
            s, e = month_bounds(y, i)
            return s, e, f"{calendar.month_name[i]} {y}"
    s, e = month_bounds(today.year, today.month)
    return s, e, f"{calendar.month_name[today.month]} {today.year} (this month)"


def _inv_sum(client_id: str, cats: tuple, s: dt.date, e: dt.date) -> tuple[Decimal, Decimal, int, list[dict]]:
    marks = ",".join("?" for _ in cats)
    rows = get_db().fetchall(f"select id, invoice_no, invoice_date, party_name, note_type, taxable_value, total from invoices "
                             f"where client_id = ? and status = 'approved' and category in ({marks}) and invoice_date between ? and ?",
                             [client_id, *cats, s, e])
    taxable = total = ZERO
    for r in rows:
        sign = Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1)
        taxable += sign * D(r["taxable_value"])
        total += sign * D(r["total"])
    return taxable, total, len(rows), rows


def answer(ctx: AuthContext, question: str, client_id: str | None, today: dt.date | None = None) -> dict:
    question = (question or "").strip()[:500]
    if not question:
        return {"answer": "Please type a question.", "records": [], "notes": []}
    intent, period_hint, top_n = None, question, 5
    provider = ai_service.get_provider()
    used_ai = False
    if provider.is_ai:
        try:
            r = provider.interpret_question(question, INTENTS)
            if r and r.get("intent") in INTENTS:
                intent, used_ai = r["intent"], True
                if r.get("period") and r["period"] not in ("", "unspecified"):
                    period_hint = r["period"] if re.match(r"\d{4}-\d{2}|this_|last_", r["period"]) else question
                top_n = max(1, min(int(r.get("top_n") or 5), 25))
        except Exception:
            intent = None
    if intent is None:
        intent = keyword_intent(question)
    if intent is None:
        return {"answer": "I can answer questions about sales, purchases, expenses, profit, GST liability, GSTR-2B gaps, "
                          "unmatched bank transactions, duplicates, receivables/payables, top customers/suppliers and "
                          "document status. Please rephrase.", "records": [], "notes": [], "intent": None}
    if intent == "pending_submissions":
        return _pending_submissions(ctx, question, today)
    client = require_client(ctx, client_id, "view")
    s, e, label = parse_period(period_hint, client, today)
    notes = [f"Interpreted by {'AI' if used_ai else 'keyword matching'}; figures computed from approved records only."]
    drafts = get_db().scalar("select count(*) from documents where client_id = ? and status in ('uploaded','processing','processed','needs_review') "
                             "and period_year = ? and period_month = ?", [client["id"], s.year, s.month])
    if drafts:
        notes.append(f"{drafts} document(s) for {s:%b %Y} are not yet approved and are NOT included.")
    out: dict = {"intent": intent, "period": label, "records": [], "notes": notes}

    if intent in ("sales_total", "purchase_total", "expense_total"):
        cats = {"sales_total": ("sales",), "purchase_total": ("purchase",), "expense_total": ("expense",)}[intent]
        taxable, total, n, rows = _inv_sum(client["id"], cats, s, e)
        word = {"sales_total": "Sales", "purchase_total": "Purchases", "expense_total": "Expense bills"}[intent]
        out["answer"] = (f"{word} for {label}: ₹{money(taxable)} taxable value (₹{money(total)} including GST) "
                         f"across {n} approved document(s).")
        out["records"] = [{"invoice_no": r["invoice_no"], "date": str(r["invoice_date"]), "party": r["party_name"],
                           "type": r["note_type"], "total": D(r["total"])} for r in rows[:50]]
        if intent == "expense_total":
            p = report_service.profit_and_loss_data(client, s, e)
            out["answer"] += f" Total expenses in the books (direct + indirect, incl. bank-posted): ₹{money(p['direct_expenses'] + p['indirect_expenses'])}."
    elif intent == "profit":
        p = report_service.profit_and_loss_data(client, s, e)
        out["answer"] = (f"Provisional net {'profit' if p['net_profit'] >= 0 else 'loss'} for {label}: ₹{money(abs(p['net_profit']))} "
                         f"(net sales ₹{money(p['net_sales'])}, gross profit ₹{money(p['gross_profit'])}).")
        out["notes"] += p["notes"]
        out["records"] = report_service.pnl_rows(p)
    elif intent == "gst_liability":
        g = gst_service.gst_summary(ctx, client["id"], s, e)
        net = g["estimated_net_liability"]
        total = sum(net.values(), ZERO)
        out["answer"] = (f"Estimated GST position for {label}: output ₹{money(sum(g['output'].values(), ZERO))}, eligible ITC "
                         f"₹{money(sum(g['input_eligible'].values(), ZERO))}, RCM ₹{money(sum(g['rcm'].values(), ZERO))} → "
                         f"estimated net {'payable' if total >= 0 else 'credit'} ₹{money(abs(total))}. "
                         "Actual cash payable depends on Rule 88A set-off and GSTR-2B; see the GSTR-3B page.")
        out["records"] = [{"head": h.upper(), "output": g["output"][h], "itc_eligible": g["input_eligible"][h], "rcm": g["rcm"][h],
                           "net": net[h]} for h in ("igst", "cgst", "sgst", "cess")]
        pending = get_db().scalar("select count(*) from invoices where client_id = ? and itc_eligibility = 'pending' and invoice_date between ? and ?",
                                  [client["id"], s, e])
        if pending:
            out["notes"].append(f"{pending} purchase invoice(s) with ITC eligibility undecided are excluded from ITC.")
    elif intent == "missing_in_2b":
        rec = get_db().fetchone("select * from gst_reconciliations where client_id = ? and period = ? order by created_at desc",
                                [client["id"], f"{s.month:02d}{s.year}"])
        if not rec:
            out["answer"] = f"No GSTR-2B reconciliation has been run for {label}. Upload GSTR-2B on the GST page first."
        else:
            items = get_db().fetchall("select details from gst_reconciliation_items where reconciliation_id = ? and status = 'missing_in_2b'",
                                      [rec["id"]])
            out["answer"] = f"{len(items)} purchase invoice(s) in the books are missing from GSTR-2B for {label}."
            out["records"] = [i["details"] for i in items]
    elif intent == "unmatched_bank":
        rows = get_db().fetchall("select txn_date, narration, debit, credit, match_status from bank_transactions where client_id = ? "
                                 "and match_status in ('unmatched','needs_review','suspense','partially_matched') and txn_date between ? and ? "
                                 "order by txn_date", [client["id"], s, e])
        amt = sum((D(r["debit"]) + D(r["credit"]) for r in rows), ZERO)
        out["answer"] = f"{len(rows)} bank transaction(s) are not fully matched for {label}, totalling ₹{money(amt)}."
        out["records"] = [{"date": str(r["txn_date"]), "narration": r["narration"][:80], "debit": D(r["debit"]),
                           "credit": D(r["credit"]), "status": r["match_status"]} for r in rows[:100]]
    elif intent == "compare_months":
        c = report_service.comparison(ctx, client["id"], s.year, s.month)
        cur = next(r for r in c["rows"] if r["metric"] == "Net Profit")
        sales = next(r for r in c["rows"] if r["metric"] == "Net Sales")
        if c["previous_available"]:
            delta = sales["current"] - sales["previous_month"]
            out["answer"] = (f"{label}: net sales ₹{money(sales['current'])} vs ₹{money(sales['previous_month'])} in the previous month "
                             f"({'+' if delta >= 0 else '−'}₹{money(abs(delta))}); net profit ₹{money(cur['current'])} vs "
                             f"₹{money(cur['previous_month'])}.")
        else:
            out["answer"] = f"{label}: net sales ₹{money(sales['current'])}. No approved data exists for the previous month to compare."
        out["records"] = c["rows"]
    elif intent == "duplicate_invoices":
        groups = defaultdict(list)
        for r in get_db().fetchall("select id, category, invoice_no, invoice_date, party_name, party_gstin, total, status from invoices "
                                   "where client_id = ? and status <> 'cancelled'", [client["id"]]):
            groups[(r["category"], normalize_invoice_no(r["invoice_no"]))].append(r)
        dups = [g for g in groups.values() if len(g) > 1]
        doc_dups = get_db().fetchall("select original_filename, review_flags from documents where client_id = ? and status in "
                                     "('needs_review','processed')", [client["id"]])
        flagged = [d for d in doc_dups if any("uplicate" in f for f in (d["review_flags"] or []))]
        out["answer"] = (f"{len(dups)} invoice number(s) appear more than once in approved records (possibly from different parties), "
                         f"and {len(flagged)} document(s) awaiting review are flagged as possible duplicates.")
        out["records"] = [{"invoice_no": r["invoice_no"], "category": r["category"], "party": r["party_name"], "date": str(r["invoice_date"]),
                           "total": D(r["total"])} for g in dups for r in g][:100]
        out["records"] += [{"document": d["original_filename"], "flag": "possible duplicate"} for d in flagged]
        out["period"] = "all periods"
    elif intent in ("receivables", "payables"):
        group = "Sundry Debtors" if intent == "receivables" else "Sundry Creditors"
        rows = report_service.party_balances(ctx, client["id"], e if e <= dt.date.today() else dt.date.today(), group)
        total = sum((r["balance"] for r in rows), ZERO)
        out["answer"] = (f"Outstanding {'receivables' if intent == 'receivables' else 'payables'} as on {min(e, dt.date.today()):%d %b %Y}: "
                         f"₹{money(total)} across {len(rows)} part{'y' if len(rows) == 1 else 'ies'} (from approved vouchers).")
        out["records"] = rows[:50]
        out["period"] = f"as on {min(e, dt.date.today()):%d %b %Y}"
    elif intent in ("top_customers", "top_suppliers"):
        cats = ("sales",) if intent == "top_customers" else ("purchase", "expense")
        if "this month" in label and not re.search(r"month", question.lower()):
            label_fy = fy_label_for(dt.date.today(), client.get("fy_start_month") or 4)
            s, _ = fy_bounds(label_fy, client.get("fy_start_month") or 4)
            e, label = dt.date.today(), f"FY {label_fy} (to date)"
        _, _, _, rows = _inv_sum(client["id"], cats, s, e)
        agg: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for r in rows:
            agg[r["party_name"]] += (Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1)) * D(r["taxable_value"])
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:top_n]
        out["period"] = label
        out["answer"] = (f"Top {len(top)} {'customers' if intent == 'top_customers' else 'suppliers'} for {label}: " +
                         ", ".join(f"{k} (₹{money(v)})" for k, v in top) if top else f"No approved records for {label}.")
        out["records"] = [{"party": k, "taxable_value": v} for k, v in top]
    elif intent == "document_status":
        rows = get_db().fetchall("select status, count(*) as n from documents where client_id = ? and period_year = ? and period_month = ? "
                                 "group by status", [client["id"], s.year, s.month])
        out["answer"] = f"Documents for {s:%B %Y}: " + (", ".join(f"{r['n']} {r['status'].replace('_', ' ')}" for r in rows) or "none uploaded") + "."
        out["records"] = rows
    return out


def _pending_submissions(ctx: AuthContext, question: str, today: dt.date | None) -> dict:
    from services.firm_service import deadline_for

    if not ctx.is_staff:
        return {"answer": "This question is available to CA firm staff only.", "records": [], "notes": []}
    today = today or dt.date.today()
    s, e, label = parse_period(question if re.search(r"month|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}", question.lower())
                               else "last month", None, today)
    db = get_db()
    ids = accessible_client_ids(ctx)
    rows = []
    for cid in ids:
        c = db.get("clients", cid)
        if c["status"] != "active":
            continue
        sub = db.fetchone("select submitted_at from document_submissions where client_id = ? and period_year = ? and period_month = ? "
                          "and status <> 'draft'", [cid, s.year, s.month])
        if not sub:
            rows.append({"client": c["name"], "deadline": str(deadline_for(c, s.year, s.month))})
    return {"intent": "pending_submissions", "period": label, "records": rows,
            "answer": f"{len(rows)} of {len(ids)} accessible client(s) have not submitted documents for {label}.",
            "notes": ["Covers only clients you are assigned to (or all firm clients if you have that permission)."]}
