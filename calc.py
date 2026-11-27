"""Mini CFO calculation engine.

ALL arithmetic lives here, in plain Python. The AI (if used) only explains
the numbers produced by this module and never calculates anything.

Conventions (also shown in the app):
- P&L (sales, purchases, expenses, profit) uses the Amount column (excl. GST).
- Cash, receivables and payables use Amount + GST_Amount (the invoice total).
- Fixed monthly costs (salary, rent, EMI) are not in the data file; they are
  deducted from cash for every month present in the data.
- Receipt / Payment rows are cash-only entries (not part of P&L or receivables).
- "As of" date = last day of the latest month in the data.
"""
from __future__ import annotations

import calendar
import math
import re
from datetime import date, timedelta

import pandas as pd

REQUIRED = ["Date", "Type", "Category", "Party", "Description",
            "Amount", "GST_Amount", "Due_Date", "Status"]
TYPES = ["Sale", "Purchase", "Expense", "Receipt", "Payment"]
STATUSES = ["Paid", "Unpaid"]
WEEKS_PER_MONTH = 30 / 7


# ---------------------------------------------------------------- formatting
def inr(x: float) -> str:
    """Indian number format, e.g. 1250000 -> ₹12,50,000."""
    neg = x < 0
    s = str(int(round(abs(x))))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + "₹" + s


def pct_change(cur: float, prev: float):
    if prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100


# ---------------------------------------------------------------- validation
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_ACCOUNT = re.compile(r"\b\d{9,18}\b")


def validate(df: pd.DataFrame):
    """Return (clean_df or None, errors, warnings). Never silently accepts bad data."""
    errors, warnings = [], []
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return None, [f"Missing columns: {', '.join(missing)}"], warnings
    df = df[REQUIRED]
    if df.empty:
        return None, ["The file has no rows."], warnings

    clean = df.copy()
    clean["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    clean["Due_Date"] = pd.to_datetime(df["Due_Date"], errors="coerce")
    clean["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    clean["GST_Amount"] = pd.to_numeric(df["GST_Amount"], errors="coerce")
    clean["Type"] = df["Type"].astype(str).str.strip().str.title()
    clean["Status"] = df["Status"].astype(str).str.strip().str.title()

    for i, row in clean.iterrows():
        n = i + 2  # row number as seen in Excel (header = row 1)
        if pd.isna(row["Date"]):
            errors.append(f"Row {n}: Date is missing or not a valid date.")
        if pd.isna(row["Due_Date"]):
            errors.append(f"Row {n}: Due_Date is missing or not a valid date.")
        if pd.isna(row["Amount"]) or row["Amount"] < 0:
            errors.append(f"Row {n}: Amount must be a number, zero or more.")
        if pd.isna(row["GST_Amount"]) or row["GST_Amount"] < 0:
            errors.append(f"Row {n}: GST_Amount must be a number, zero or more.")
        if row["Type"] not in TYPES:
            errors.append(f"Row {n}: Type '{row['Type']}' is not one of {', '.join(TYPES)}.")
        if row["Status"] not in STATUSES:
            errors.append(f"Row {n}: Status '{row['Status']}' must be Paid or Unpaid.")

    text_cols = ["Category", "Party", "Description"]
    for col in text_cols:
        for i, val in df[col].astype(str).items():
            n = i + 2
            if _PAN.search(val) or _AADHAAR.search(val) or _ACCOUNT.search(val):
                warnings.append(f"Row {n}, {col}: looks like a PAN, Aadhaar or bank account "
                                f"number. Please remove it before uploading.")
    if errors:
        return None, errors, warnings
    return clean, errors, warnings


# ---------------------------------------------------------------- core
def _month_end(period: pd.Period) -> date:
    return date(period.year, period.month,
                calendar.monthrange(period.year, period.month)[1])


def _bucket(days: int) -> str:
    if days <= 0:
        return "Not due"
    if days <= 30:
        return "1-30 days"
    if days <= 60:
        return "31-60 days"
    if days <= 90:
        return "61-90 days"
    return "90+ days"


def compute(df: pd.DataFrame, s: dict) -> dict:
    """s = client settings: opening_cash, fixed_costs, sales_target, profit_target."""
    df = df.copy()
    df["Period"] = df["Date"].dt.to_period("M")
    df["Total"] = df["Amount"] + df["GST_Amount"]
    cur_p = df["Period"].max()
    prev_p = cur_p - 1
    as_of = _month_end(cur_p)
    fixed = float(s["fixed_costs"])

    def month_totals(p):
        d = df[df["Period"] == p]
        sales = d.loc[d.Type == "Sale", "Amount"].sum()
        purch = d.loc[d.Type == "Purchase", "Amount"].sum()
        exp = d.loc[d.Type == "Expense", "Amount"].sum()
        return float(sales), float(purch), float(exp), float(sales - purch - exp)

    sales, purch, exp, profit = month_totals(cur_p)
    p_sales, p_purch, p_exp, p_profit = month_totals(prev_p)
    has_prev = (df["Period"] == prev_p).any()

    # cash ----------------------------------------------------------------
    paid = df[df.Status == "Paid"]
    cash_in = paid.loc[paid.Type == "Sale", "Total"].sum() + df.loc[df.Type == "Receipt", "Total"].sum()
    cash_out = (paid.loc[paid.Type.isin(["Purchase", "Expense"]), "Total"].sum()
                + df.loc[df.Type == "Payment", "Total"].sum())
    months_in_data = df["Period"].nunique()
    cash = float(s["opening_cash"]) + cash_in - cash_out - fixed * months_in_data

    # weekly outflow (average of months in data) ---------------------------
    monthly_out = []
    for p in sorted(df["Period"].unique()):
        d = df[(df["Period"] == p) & (df.Status == "Paid")]
        out = d.loc[d.Type.isin(["Purchase", "Expense"]), "Total"].sum()
        out += df[(df["Period"] == p) & (df.Type == "Payment")]["Total"].sum()
        monthly_out.append(float(out) + fixed)
    avg_monthly_out = sum(monthly_out) / len(monthly_out)
    weekly_out = avg_monthly_out / WEEKS_PER_MONTH
    runway = cash / weekly_out if weekly_out > 0 else float("inf")

    # receivables / payables ---------------------------------------------
    unpaid = df[(df.Status == "Unpaid")]
    rec = unpaid[unpaid.Type == "Sale"].copy()
    rec["Days_Overdue"] = rec["Due_Date"].apply(lambda d: (as_of - d.date()).days)
    rec["Bucket"] = rec["Days_Overdue"].apply(_bucket)
    receivables = (rec[["Party", "Description", "Total", "Due_Date", "Days_Overdue", "Bucket"]]
                   .sort_values("Days_Overdue", ascending=False).reset_index(drop=True))
    pay = unpaid[unpaid.Type.isin(["Purchase", "Expense"])].copy()
    pay["Days_To_Due"] = pay["Due_Date"].apply(lambda d: (d.date() - as_of).days)
    payables = (pay[["Party", "Description", "Total", "Due_Date", "Days_To_Due"]]
                .sort_values("Days_To_Due").reset_index(drop=True))
    total_rec = float(receivables["Total"].sum())
    overdue_rec = float(receivables.loc[receivables.Days_Overdue > 0, "Total"].sum())
    cur_sales_total = float(df[(df.Period == cur_p) & (df.Type == "Sale")]["Total"].sum())
    overdue_share = overdue_rec / cur_sales_total if cur_sales_total else 0.0

    # forecast (known items only) ---------------------------------------
    weekly_fixed = fixed / WEEKS_PER_MONTH
    rows, bal = [], cash
    for wk in range(1, 9):
        def in_week(days):
            return max(1, math.ceil(days / 7)) == wk
        r_in = float(rec.loc[rec["Due_Date"].apply(lambda d: in_week((d.date() - as_of).days)), "Total"].sum())
        r_out = float(pay.loc[pay["Due_Date"].apply(lambda d: in_week((d.date() - as_of).days)), "Total"].sum())
        bal = bal + r_in - r_out - weekly_fixed
        rows.append({"Week": wk, "Money in": r_in, "Money out": r_out + weekly_fixed, "Cash": bal})
    forecast = pd.DataFrame(rows)

    # GST estimate -----------------------------------------------------
    cm = df[df.Period == cur_p]
    gst_collected = float(cm.loc[cm.Type == "Sale", "GST_Amount"].sum())
    gst_input = float(cm.loc[cm.Type.isin(["Purchase", "Expense"]), "GST_Amount"].sum())

    # breakdowns ------------------------------------------------------
    def grp(p, types, key):
        d = df[(df.Period == p) & (df.Type.isin(types))]
        return d.groupby(key)["Amount"].sum()

    cust_cur, cust_prev = grp(cur_p, ["Sale"], "Party"), grp(prev_p, ["Sale"], "Party")
    cat_cur, cat_prev = grp(cur_p, ["Purchase", "Expense"], "Category"), grp(prev_p, ["Purchase", "Expense"], "Category")
    changes = []
    for name in set(cust_cur.index) | set(cust_prev.index):
        changes.append((f"Sales to {name}", float(cust_cur.get(name, 0) - cust_prev.get(name, 0)), "sales"))
    for name in set(cat_cur.index) | set(cat_prev.index):
        changes.append((f"{name} cost", float(cat_cur.get(name, 0) - cat_prev.get(name, 0)), "cost"))
    changes = sorted([c for c in changes if c[1] != 0], key=lambda c: abs(c[1]), reverse=True)[:5]

    top_customer = cust_cur.idxmax() if len(cust_cur) else None
    top_customer_sales = float(cust_cur.max()) if len(cust_cur) else 0.0
    cost_growth = (cat_cur.sub(cat_prev, fill_value=0)).sort_values(ascending=False)

    # health -----------------------------------------------------------
    profit_after_fixed = profit - fixed
    sales_pct = sales / s["sales_target"] * 100 if s["sales_target"] else None
    profit_pct = profit_after_fixed / s["profit_target"] * 100 if s["profit_target"] else None
    targets_missed = ((sales_pct is not None and sales_pct < 100)
                      or (profit_pct is not None and profit_pct < 100))
    reasons = []
    if profit_after_fixed < 0 or runway < 4:
        colour = "Red"
        if profit_after_fixed < 0:
            reasons.append("Profit after fixed costs is negative")
        if runway < 4:
            reasons.append(f"Cash runway is only {runway:.1f} weeks")
    elif runway <= 8 or overdue_share > 0.30 or targets_missed:
        colour = "Amber"
        if runway <= 8:
            reasons.append(f"Cash runway is {runway:.1f} weeks")
        if overdue_share > 0.30:
            reasons.append(f"Overdue receivables are {overdue_share:.0%} of this month's sales")
        if targets_missed:
            reasons.append("A monthly target is missed")
    else:
        colour = "Green"
        reasons.append("Profit is positive, runway is healthy and receivables are under control")

    return dict(
        cur_period=str(cur_p), prev_period=str(prev_p), has_prev=has_prev, as_of=as_of,
        sales=sales, purchases=purch, expenses=exp, profit=profit,
        prev_sales=p_sales, prev_purchases=p_purch, prev_expenses=p_exp, prev_profit=p_profit,
        sales_chg=pct_change(sales, p_sales), profit_chg=pct_change(profit, p_profit),
        fixed=fixed, profit_after_fixed=profit_after_fixed,
        cash=cash, weekly_outflow=weekly_out, runway=runway,
        receivables=receivables, payables=payables, total_receivables=total_rec,
        overdue_receivables=overdue_rec, overdue_share=overdue_share,
        total_payables=float(payables["Total"].sum()),
        forecast=forecast, lowest_cash=float(forecast["Cash"].min()),
        gst_collected=gst_collected, gst_input=gst_input, gst_net=gst_collected - gst_input,
        sales_pct=sales_pct, profit_pct=profit_pct,
        changes=changes, top_customer=top_customer, top_customer_sales=top_customer_sales,
        cost_growth=cost_growth, cust_sales=cust_cur.sort_values(ascending=False),
        health=colour, health_reasons=reasons,
    )


def discount_scenario(m: dict, pct: float = 5.0) -> dict:
    cut = m["top_customer_sales"] * pct / 100
    return dict(customer=m["top_customer"], cut=cut,
                new_profit=m["profit"] - cut, new_profit_after_fixed=m["profit_after_fixed"] - cut)


def can_afford(m: dict) -> dict:
    due_30 = float(m["payables"].loc[m["payables"].Days_To_Due <= 30, "Total"].sum())
    need = m["fixed"] + due_30 + max(m["gst_net"], 0)
    return dict(need=need, due_30=due_30, gst=max(m["gst_net"], 0), margin=m["cash"] - need)


def mask_map(m: dict) -> dict:
    """Real name -> masked name (Customer A, Supplier A ...)."""
    mapping, c, s = {}, 0, 0
    for p in m["receivables"]["Party"].tolist() + list(m["cust_sales"].index):
        if p not in mapping:
            mapping[p] = f"Customer {chr(65 + c)}"
            c += 1
    for p in m["payables"]["Party"].tolist():
        if p not in mapping:
            mapping[p] = f"Supplier {chr(65 + s)}"
            s += 1
    return mapping
