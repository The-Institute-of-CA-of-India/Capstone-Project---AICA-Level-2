"""Financial reporting from APPROVED vouchers (+ opening balances, closing stock).

Every figure is computed with Decimal in Python. The Balance Sheet is ALWAYS labelled provisional
unless all completeness checks pass (opening balances tally, closing stock, depreciation, no drafts,
no suspense, months finalized). Even then it is "prepared from records" — not an audited statement.
"""
from __future__ import annotations

import datetime as dt
import io
from collections import defaultdict
from decimal import Decimal

from services import accounting_engine as ae
from services.audit_service import audit
from services.db import get_db, now_iso
from services.storage_service import get_storage
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, fy_bounds, fy_label_for, fy_months, money, month_bounds, prev_month, to_date

REPORT_TYPES = {
    "pnl": "Profit and Loss Account", "bs": "Balance Sheet", "tb": "Trial Balance", "sales_register": "Sales Register",
    "purchase_register": "Purchase Register", "expense_register": "Expense Register", "cash_book": "Cash Book",
    "bank_book": "Bank Book", "ledger": "General Ledger", "debtors": "Debtors Report", "creditors": "Creditors Report",
    "brs": "Bank Reconciliation Statement", "gst_summary": "GST Summary", "voucher_register": "Voucher Register",
}


def _fy(client: dict, d: dt.date) -> tuple[str, dt.date, dt.date]:
    sm = client.get("fy_start_month") or 4
    label = fy_label_for(d, sm)
    s, e = fy_bounds(label, sm)
    return label, s, e


def closing_balances(client: dict, as_of: dt.date) -> dict[str, Decimal]:
    label, fy_start, _ = _fy(client, as_of)
    ob = ae.opening_balances(client["id"], label)
    mv = ae.ledger_movements(client["id"], fy_start, as_of)
    out = dict(ob)
    for k, v in mv.items():
        out[k] = out.get(k, ZERO) + v
    return out


# ---------------------------------------------------------------- trial balance
def trial_balance_rows(client_id: str, start: dt.date, end: dt.date) -> list[dict]:
    client = get_db().get("clients", client_id)
    label, fy_start, _ = _fy(client, end)
    ledgers = ae.ledger_index(client_id)
    ob = ae.opening_balances(client_id, label)
    before = ae.ledger_movements(client_id, fy_start, start - dt.timedelta(days=1)) if start > fy_start else {}
    period = defaultdict(lambda: [ZERO, ZERO])
    for r in get_db().fetchall("select e.ledger_id, e.dr_cr, e.amount from accounting_voucher_entries e join accounting_vouchers v "
                               "on v.id = e.voucher_id where v.client_id = ? and v.status = 'approved' and v.voucher_date between ? and ?",
                               [client_id, start, end]):
        period[r["ledger_id"]][0 if r["dr_cr"] == "Dr" else 1] += D(r["amount"])
    rows = []
    for lid, led in ledgers.items():
        opening = ob.get(lid, ZERO) + before.get(lid, ZERO)
        if led["nature"] in ("income", "expense") and start > fy_start:
            pass  # nominal accounts accumulate within the FY
        dr, cr = period[lid]
        closing = opening + dr - cr
        if opening == ZERO and dr == ZERO and cr == ZERO:
            continue
        rows.append({"ledger_id": lid, "ledger": led["name"], "group": led["group_name"], "nature": led["nature"],
                     "opening": opening, "period_debit": dr, "period_credit": cr, "closing": closing,
                     "debit": closing if closing > 0 else ZERO, "credit": -closing if closing < 0 else ZERO})
    return sorted(rows, key=lambda r: (r["group"], r["ledger"]))


def trial_balance(ctx: AuthContext, client_id: str, start: dt.date, end: dt.date) -> dict:
    require_client(ctx, client_id, "view")
    rows = trial_balance_rows(client_id, start, end)
    td = sum((r["debit"] for r in rows), ZERO)
    tc = sum((r["credit"] for r in rows), ZERO)
    return {"rows": rows, "total_debit": td, "total_credit": tc, "difference": td - tc}


# ---------------------------------------------------------------- P&L
def _stock_value(client: dict, d: dt.date, opening: bool) -> Decimal | None:
    db = get_db()
    if opening:
        label, fy_start, _ = _fy(client, d)
        if d == fy_start:
            stock_ids = [r["id"] for r in db.fetchall("select id from ledgers where client_id = ? and group_name = 'Stock-in-Hand'",
                                                      [client["id"]])]
            ob = ae.opening_balances(client["id"], label)
            vals = [ob[i] for i in stock_ids if i in ob]
            if vals:
                return sum(vals, ZERO)
            prior = ae.closing_stock_at(client["id"], d - dt.timedelta(days=1))
            return prior
        return ae.closing_stock_at(client["id"], d - dt.timedelta(days=1))
    return ae.closing_stock_at(client["id"], d)


def profit_and_loss_data(client: dict, start: dt.date, end: dt.date) -> dict:
    mv = ae.ledger_movements(client["id"], start, end)
    ledgers = ae.ledger_index(client["id"])
    try:
        sales_ret_id = ae.mapped_ledger(client["id"], "sales_returns")["id"]
        purch_ret_id = ae.mapped_ledger(client["id"], "purchase_returns")["id"]
    except ae.AccountingError:
        sales_ret_id = purch_ret_id = None
    sec = defaultdict(list)
    for lid, amt in mv.items():
        led = ledgers.get(lid)
        if not led or led["nature"] not in ("income", "expense"):
            continue
        sec[led["group_name"]].append({"ledger": led["name"], "ledger_id": lid, "amount": amt})
    gross_sales = sum((-r["amount"] for r in sec["Sales Accounts"] if r["ledger_id"] != sales_ret_id), ZERO)
    sales_returns = sum((r["amount"] for r in sec["Sales Accounts"] if r["ledger_id"] == sales_ret_id), ZERO)
    net_sales = gross_sales - sales_returns
    purchases = sum((r["amount"] for r in sec["Purchase Accounts"] if r["ledger_id"] != purch_ret_id), ZERO)
    purchase_returns = sum((-r["amount"] for r in sec["Purchase Accounts"] if r["ledger_id"] == purch_ret_id), ZERO)
    direct_exp = sum((r["amount"] for r in sec["Direct Expenses"]), ZERO)
    direct_inc = sum((-r["amount"] for r in sec["Direct Incomes"]), ZERO)
    indirect_exp = sum((r["amount"] for r in sec["Indirect Expenses"]), ZERO)
    indirect_inc = sum((-r["amount"] for r in sec["Indirect Incomes"]), ZERO)
    opening_stock = _stock_value(client, start, True)
    closing_stock = _stock_value(client, end, False)
    notes = []
    if closing_stock is None:
        notes.append("Closing stock not entered — gross profit excludes inventory change")
    if opening_stock is None and closing_stock is not None:
        notes.append("Opening stock not available — treated as nil")
    # Without a closing-stock valuation, inventory is treated as unchanged (opening stock stays on the Balance Sheet).
    opening_eff = (opening_stock or ZERO) if closing_stock is not None else ZERO
    gross_profit = (net_sales + direct_inc + (closing_stock or ZERO) - opening_eff
                    - (purchases - purchase_returns) - direct_exp)
    net_profit = gross_profit + indirect_inc - indirect_exp
    return {"period": (start, end), "gross_sales": gross_sales, "sales_returns": sales_returns, "net_sales": net_sales,
            "purchases": purchases, "purchase_returns": purchase_returns, "net_purchases": purchases - purchase_returns,
            "opening_stock": opening_stock, "closing_stock": closing_stock, "direct_expenses": direct_exp,
            "direct_incomes": direct_inc, "gross_profit": gross_profit, "indirect_incomes": indirect_inc,
            "indirect_expenses": indirect_exp, "net_profit": net_profit,
            "detail": {k: sorted(v, key=lambda r: -abs(r["amount"])) for k, v in sec.items()}, "notes": notes}


def profit_and_loss(ctx: AuthContext, client_id: str, start: dt.date, end: dt.date) -> dict:
    client = require_client(ctx, client_id, "view")
    out = profit_and_loss_data(client, start, end)
    out["completeness"] = completeness_checks(client, start, end)
    out["is_provisional"] = bool(out["completeness"])
    return out


# ---------------------------------------------------------------- Balance Sheet
BS_LIAB_ORDER = ["Capital Account", "Reserves & Surplus", "Secured Loans", "Unsecured Loans", "Loans (Liability)",
                 "Sundry Creditors", "Duties & Taxes", "Provisions", "Current Liabilities"]
BS_ASSET_ORDER = ["Fixed Assets", "Investments", "Stock-in-Hand", "Sundry Debtors", "Cash-in-Hand", "Bank Accounts",
                  "Loans & Advances (Asset)", "Deposits (Asset)", "Current Assets", "Suspense A/c"]


def completeness_checks(client: dict, start: dt.date, end: dt.date) -> list[str]:
    db = get_db()
    label, fy_start, fy_end = _fy(client, end)
    reasons = []
    ob_count = db.scalar("select count(*) from opening_balances where client_id = ? and fy_label = ?", [client["id"], label])
    if not ob_count:
        reasons.append(f"Opening balances for FY {label} not entered (capital, loans, fixed assets, debtors, creditors, bank)")
    else:
        diff = ae.opening_difference(client["id"], label)
        if diff != ZERO:
            reasons.append(f"Opening balances do not tally (difference {money(diff)})")
    has_inventory = db.scalar("select count(*) from invoices where client_id = ? and category = 'purchase' and status = 'approved'",
                              [client["id"]])
    if has_inventory and ae.closing_stock_at(client["id"], end) is None:
        reasons.append(f"Closing stock as on {end:%d-%b-%Y} not entered")
    fa = db.scalar("select count(*) from ledgers where client_id = ? and group_name = 'Fixed Assets'", [client["id"]])
    if fa:
        dep = db.scalar("select count(*) from accounting_voucher_entries e join accounting_vouchers v on v.id = e.voucher_id "
                        "join ledgers l on l.id = e.ledger_id where v.client_id = ? and v.status = 'approved' and l.name = 'Depreciation' "
                        "and v.voucher_date between ? and ?", [client["id"], fy_start, end])
        if not dep:
            reasons.append("Depreciation not posted for fixed assets")
    drafts = db.scalar("select count(*) from accounting_vouchers where client_id = ? and status = 'draft' and voucher_date between ? and ?",
                       [client["id"], fy_start, end])
    if drafts:
        reasons.append(f"{drafts} unapproved voucher(s) excluded")
    try:
        susp = ae.mapped_ledger(client["id"], "suspense")["id"]
        bal = closing_balances(client, end).get(susp, ZERO)
        if bal != ZERO:
            reasons.append(f"Suspense account has a balance of {money(bal)}")
    except ae.AccountingError:
        pass
    months = [(y, m) for (y, m) in fy_months(label, client.get("fy_start_month") or 4) if dt.date(y, m, 1) <= end]
    fin = {(r["year"], r["month"]) for r in db.fetchall("select year, month from accounting_periods where client_id = ? and status = 'finalized'",
                                                        [client["id"]])}
    open_months = [f"{m:02d}/{y}" for (y, m) in months if (y, m) not in fin and dt.date(y, m, 1) >= start.replace(day=1)]
    if open_months:
        reasons.append(f"Months not finalized: {', '.join(open_months[:6])}{'…' if len(open_months) > 6 else ''}")
    pending_docs = db.scalar("select count(*) from documents where client_id = ? and status in ('uploaded','processing','processed','needs_review')",
                             [client["id"]])
    if pending_docs:
        reasons.append(f"{pending_docs} document(s) not yet reviewed")
    return reasons


def balance_sheet(ctx: AuthContext, client_id: str, as_of: dt.date) -> dict:
    client = require_client(ctx, client_id, "view")
    label, fy_start, _ = _fy(client, as_of)
    bal = closing_balances(client, as_of)
    ledgers = ae.ledger_index(client_id)
    pnl = profit_and_loss_data(client, fy_start, as_of)
    liab, assets = defaultdict(list), defaultdict(list)
    for lid, amt in bal.items():
        led = ledgers.get(lid)
        if not led or led["nature"] in ("income", "expense") or amt == ZERO:
            continue
        g = led["group_name"]
        if g == "Stock-in-Hand" and pnl["closing_stock"] is not None:
            continue  # replaced by closing stock valuation below
        if led["nature"] == "asset":
            # credit balances on asset-type party/bank ledgers are shown as liabilities (e.g. overdraft, advances)
            (assets[g] if amt > 0 else liab["Current Liabilities" if g != "Bank Accounts" else "Loans (Liability)"]).append(
                {"ledger": led["name"], "amount": abs(amt)})
        else:
            (liab[g] if amt < 0 else assets["Current Assets" if g != "Sundry Creditors" else "Loans & Advances (Asset)"]).append(
                {"ledger": led["name"], "amount": abs(amt)})
    if pnl["closing_stock"] is not None:
        assets["Stock-in-Hand"].append({"ledger": "Closing Stock", "amount": pnl["closing_stock"]})
        # stock in the opening TB is part of the P&L via opening stock; remove the ledger to avoid double count
    np_ = pnl["net_profit"]
    liab["Reserves & Surplus"].append({"ledger": "Profit & Loss A/c (current period)" if np_ >= 0 else "Loss (current period)",
                                       "amount": np_})
    total_l = sum((r["amount"] for g in liab.values() for r in g), ZERO)
    total_a = sum((r["amount"] for g in assets.values() for r in g), ZERO)
    reasons = completeness_checks(client, fy_start, as_of)
    if total_l != total_a:
        reasons.insert(0, f"Balance Sheet does not tally: liabilities {money(total_l)} vs assets {money(total_a)}")
    order = lambda d, o: [(g, d[g]) for g in o if g in d] + [(g, v) for g, v in d.items() if g not in o]  # noqa: E731
    return {"as_of": as_of, "fy": label, "liabilities": order(liab, BS_LIAB_ORDER), "assets": order(assets, BS_ASSET_ORDER),
            "total_liabilities": total_l, "total_assets": total_a, "difference": total_l - total_a, "net_profit": np_,
            "is_provisional": True if reasons else False, "provisional_reasons": reasons,
            "label": ("PROVISIONAL / INCOMPLETE — not a final statement" if reasons
                      else "Prepared from approved records (unaudited)")}


# ---------------------------------------------------------------- registers & books
def register(ctx: AuthContext, client_id: str, category: str, start: dt.date, end: dt.date) -> list[dict]:
    require_client(ctx, client_id, "view")
    rows = get_db().fetchall("select * from invoices where client_id = ? and category = ? and status = 'approved' and invoice_date "
                             "between ? and ? order by invoice_date, invoice_no", [client_id, category, start, end])
    return [{"date": str(r["invoice_date"]), "invoice_no": r["invoice_no"], "type": r["note_type"], "party": r["party_name"],
             "gstin": r.get("party_gstin") or "", "pos": r.get("place_of_supply") or "", "taxable": D(r["taxable_value"]),
             "cgst": D(r["cgst"]), "sgst": D(r["sgst"]), "igst": D(r["igst"]), "cess": D(r["cess"]), "total": D(r["total"]),
             "rcm": "Y" if r["reverse_charge"] else "", "itc": r["itc_eligibility"] if category != "sales" else "",
             "invoice_id": r["id"]} for r in rows]


def general_ledger(ctx: AuthContext, client_id: str, ledger_id: str, start: dt.date, end: dt.date) -> dict:
    client = require_client(ctx, client_id, "view")
    led = scoped_get(ctx, "ledgers", ledger_id, "view")
    if led["client_id"] != client_id:
        raise ValueError("Ledger belongs to another client")
    label, fy_start, _ = _fy(client, start)
    opening = ae.opening_balances(client_id, label).get(ledger_id, ZERO)
    if start > fy_start:
        opening += ae.ledger_movements(client_id, fy_start, start - dt.timedelta(days=1)).get(ledger_id, ZERO)
    if led["nature"] in ("income", "expense") and start == fy_start:
        opening = ZERO
    rows = get_db().fetchall("select v.id as voucher_id, v.voucher_date, v.voucher_no, v.voucher_type, v.narration, e.dr_cr, e.amount "
                             "from accounting_voucher_entries e join accounting_vouchers v on v.id = e.voucher_id where e.ledger_id = ? "
                             "and v.status = 'approved' and v.voucher_date between ? and ? order by v.voucher_date, v.voucher_no",
                             [ledger_id, start, end])
    bal = opening
    out = []
    for r in rows:
        amt = D(r["amount"])
        bal += amt if r["dr_cr"] == "Dr" else -amt
        out.append({"date": str(r["voucher_date"]), "voucher_no": r["voucher_no"], "type": r["voucher_type"],
                    "narration": r["narration"], "debit": amt if r["dr_cr"] == "Dr" else ZERO,
                    "credit": amt if r["dr_cr"] == "Cr" else ZERO, "balance": bal, "voucher_id": r["voucher_id"]})
    return {"ledger": led["name"], "group": led["group_name"], "opening": opening, "rows": out, "closing": bal}


def book(ctx: AuthContext, client_id: str, group: str, start: dt.date, end: dt.date) -> list[dict]:
    """Cash Book (group 'Cash-in-Hand') or Bank Book ('Bank Accounts')."""
    require_client(ctx, client_id, "view")
    ids = [r["id"] for r in get_db().fetchall("select id from ledgers where client_id = ? and group_name = ?", [client_id, group])]
    return [general_ledger(ctx, client_id, i, start, end) for i in ids]


def party_balances(ctx: AuthContext, client_id: str, as_of: dt.date, group: str) -> list[dict]:
    client = require_client(ctx, client_id, "view")
    bal = closing_balances(client, as_of)
    ledgers = ae.ledger_index(client_id)
    db = get_db()
    out = []
    for lid, led in ledgers.items():
        if led["group_name"] != group:
            continue
        b = bal.get(lid, ZERO)
        if b == ZERO:
            continue
        # ageing from unpaid invoices (bank-matched amounts reduce outstanding)
        cat = ("sales",) if group == "Sundry Debtors" else ("purchase", "expense")
        marks = ",".join("?" for _ in cat)
        invs = db.fetchall(f"select id, invoice_date, total, party_name, party_gstin from invoices where client_id = ? and status = 'approved' "
                           f"and note_type = 'invoice' and category in ({marks}) and invoice_date <= ?", [client_id, *cat, as_of])
        ages = {"0-30": ZERO, "31-60": ZERO, "61-90": ZERO, "90+": ZERO}
        for inv in invs:
            if not ((led.get("party_gstin") and inv.get("party_gstin") == led["party_gstin"]) or inv["party_name"] == led["name"]):
                continue
            paid = sum((D(m["amount"]) for m in db.fetchall("select amount from bank_matches where target_type = 'invoice' and "
                                                             "target_id = ? and status = 'confirmed'", [inv["id"]])), ZERO)
            o = D(inv["total"]) - paid
            if o <= 0:
                continue
            days = (as_of - to_date(inv["invoice_date"])).days
            ages["0-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"] += o
        out.append({"party": led["name"], "gstin": led.get("party_gstin") or "",
                    "balance": b if group == "Sundry Debtors" else -b, "side": "Dr" if b > 0 else "Cr", **ages})
    return sorted(out, key=lambda r: -r["balance"])


def voucher_register(ctx: AuthContext, client_id: str, start: dt.date, end: dt.date, status: str | None = None) -> list[dict]:
    vs = ae.list_vouchers(ctx, client_id, date_from=start, date_to=end, status=status)
    return [{"date": str(v["voucher_date"]), "voucher_no": v["voucher_no"], "type": v["voucher_type"], "party": v.get("party_name") or "",
             "amount": D(v["total_amount"]), "status": v["status"], "source": v["source_type"],
             "review": v.get("review_reason") or "", "narration": v.get("narration") or "", "voucher_id": v["id"]} for v in vs]


def monthly_series(ctx: AuthContext, client_id: str, fy_label: str) -> list[dict]:
    client = require_client(ctx, client_id, "view")
    out = []
    for y, m in fy_months(fy_label, client.get("fy_start_month") or 4):
        s, e = month_bounds(y, m)
        if s > dt.date.today():
            break
        p = profit_and_loss_data(client, s, e)
        exp = p["direct_expenses"] + p["indirect_expenses"]
        out.append({"month": f"{s:%b %y}", "year": y, "mon": m, "sales": p["net_sales"], "purchases": p["net_purchases"],
                    "expenses": exp, "net_profit": p["net_profit"]})
    return out


def comparison(ctx: AuthContext, client_id: str, year: int, month: int) -> dict:
    client = require_client(ctx, client_id, "view")
    cur = profit_and_loss_data(client, *month_bounds(year, month))
    py, pm = prev_month(year, month)
    prev = profit_and_loss_data(client, *month_bounds(py, pm))
    ly = profit_and_loss_data(client, *month_bounds(year - 1, month))
    keys = ("net_sales", "net_purchases", "direct_expenses", "indirect_expenses", "gross_profit", "net_profit")

    def has_data(p):
        return any(p[k] != ZERO for k in keys)

    rows = []
    for k in keys:
        rows.append({"metric": k.replace("_", " ").title(), "current": cur[k], "previous_month": prev[k] if has_data(prev) else None,
                     "same_month_last_year": ly[k] if has_data(ly) else None})
    return {"rows": rows, "previous_available": has_data(prev), "last_year_available": has_data(ly)}


# ---------------------------------------------------------------- exports
def to_excel(sheets: dict[str, list[dict]], title: str = "") -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, rows in sheets.items():
            clean = [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in r.items() if not k.endswith("_id")} for r in rows]
            df = pd.DataFrame(clean) if clean else pd.DataFrame({"note": ["No data"]})
            df.to_excel(xw, sheet_name=name[:31], index=False, startrow=2 if title else 0)
            if title:
                xw.sheets[name[:31]].cell(row=1, column=1, value=title)
    return buf.getvalue()


def to_pdf(title: str, subtitle: str, sections: list[tuple[str, list[dict]]], notes: list[str] | None = None,
           banner: str | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    wide = any(len(rows[0]) > 6 for _, rows in sections if rows)
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if wide else A4, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28,
                            title=title)
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0B2545")
    story = [Paragraph(f"<font color='#0B2545'><b>{title}</b></font>", ss["Title"]), Paragraph(subtitle, ss["Normal"])]
    if banner:
        story += [Spacer(1, 6), Paragraph(f"<font color='#9A3412'><b>{banner}</b></font>", ss["Normal"])]
    for heading, rows in sections:
        story += [Spacer(1, 10), Paragraph(f"<b>{heading}</b>", ss["Heading3"])]
        if not rows:
            story.append(Paragraph("No data", ss["Normal"]))
            continue
        cols = [c for c in rows[0].keys() if not c.endswith("_id")]
        data = [[c.replace("_", " ").title() for c in cols]]
        for r in rows:
            data.append([money(r[c]) if isinstance(r[c], Decimal) else ("" if r[c] is None else str(r[c]))[:60] for c in cols])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F9")]),
                               ("ALIGN", (1, 1), (-1, -1), "RIGHT")]))
        story.append(t)
    for n in notes or []:
        story += [Spacer(1, 4), Paragraph(f"• {n}", ss["Normal"])]
    story += [Spacer(1, 12), Paragraph(f"<font size=7 color='#64748B'>Generated by Accounting Setu on {now_iso()[:16]} UTC</font>",
                                       ss["Normal"])]
    doc.build(story)
    return buf.getvalue()


def pnl_rows(p: dict) -> list[dict]:
    R = lambda label, v: {"particulars": label, "amount": v if v is not None else "not entered"}  # noqa: E731
    return [R("Gross Sales", p["gross_sales"]), R("Less: Sales Returns", p["sales_returns"]), R("Net Sales", p["net_sales"]),
            R("Add: Direct Incomes", p["direct_incomes"]), R("Opening Stock", p["opening_stock"]),
            R("Purchases (net of returns)", p["net_purchases"]), R("Direct Expenses", p["direct_expenses"]),
            R("Closing Stock", p["closing_stock"]), R("Gross Profit", p["gross_profit"]), R("Indirect Incomes", p["indirect_incomes"]),
            R("Indirect Expenses", p["indirect_expenses"]), R("Net Profit / (Loss)", p["net_profit"])]


def bs_rows(bs: dict, side: str) -> list[dict]:
    rows = []
    for group, items in bs[side]:
        rows.append({"group": group, "ledger": "", "amount": sum((i["amount"] for i in items), ZERO)})
        rows += [{"group": "", "ledger": i["ledger"], "amount": i["amount"]} for i in items]
    return rows


# ---------------------------------------------------------------- saved reports / sharing
def save_report(ctx: AuthContext, client_id: str, report_type: str, title: str, content: bytes, fmt: str,
                period_from: dt.date | None, period_to: dt.date | None, is_provisional: bool) -> str:
    client = require_client(ctx, client_id, "generate_reports")
    path = f"{client['firm_id']}/{client_id}/reports/{report_type}_{now_iso().replace(':', '')}.{fmt}"
    get_storage().put_overwrite(path, content)
    rid = get_db().insert("reports", {"firm_id": client["firm_id"], "client_id": client_id, "report_type": report_type, "title": title,
                                      "period_from": period_from, "period_to": period_to, "file_format": fmt, "storage_path": path,
                                      "status": "draft", "is_provisional": is_provisional, "generated_by": ctx.user_id,
                                      "created_at": now_iso()})
    audit(ctx, "report.generated", "reports", rid, client_id=client_id, after={"type": report_type, "format": fmt})
    return rid


def approve_and_share(ctx: AuthContext, report_id: str, share: bool = True) -> None:
    from services.notification_service import notify_client_users

    r = scoped_get(ctx, "reports", report_id, "approve_reports")
    get_db().update("reports", report_id, {"status": "shared" if share else "approved", "approved_by": ctx.user_id,
                                           "shared_at": now_iso() if share else None})
    audit(ctx, "report.shared" if share else "report.approved", "reports", report_id, client_id=r["client_id"])
    if share:
        notify_client_users(r["client_id"], "New report from your CA", r["title"])


def withdraw_report(ctx: AuthContext, report_id: str) -> None:
    r = scoped_get(ctx, "reports", report_id, "approve_reports")
    get_db().update("reports", report_id, {"status": "withdrawn"})
    audit(ctx, "report.withdrawn", "reports", report_id, client_id=r["client_id"])


def list_reports(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    sql = "select * from reports where client_id = ?"
    if ctx.is_client:
        sql += " and status = 'shared'"
    return get_db().fetchall(sql + " order by created_at desc", [client_id])


def report_bytes(ctx: AuthContext, report_id: str) -> tuple[bytes, dict]:
    r = scoped_get(ctx, "reports", report_id, "view")
    if ctx.is_client and r["status"] != "shared":
        from utils.permissions import NotFound

        raise NotFound("Report not found")
    return get_storage().get(r["storage_path"]), r
