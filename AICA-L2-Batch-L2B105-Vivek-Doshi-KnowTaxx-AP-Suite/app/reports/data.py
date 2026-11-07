"""Report calculations, shared by the HTML pages, Excel/PDF exports and the REST API."""
from collections import defaultdict
from datetime import date, timedelta

from ..models import OPEN_AP_STATUSES, SPEND_STATUSES, Budget, CostCentre, Invoice
from ..utils import inr

MSME_LIMIT_DAYS = 45
MSME_WARN_DAYS = 30
AGING_BUCKETS = ("Current", "1-30", "31-60", "61-90", "90+")
MONTH_NAMES = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parse_period(text, default=None):
    """'YYYY-MM' to (year, month), falling back to the default or this month."""
    try:
        year, month = (int(p) for p in (text or "").split("-"))
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    except ValueError:
        pass
    today = date.today()
    return default or (today.year, today.month)


def month_range(year, month):
    start = date(year, month, 1)
    return start, (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def fiscal_quarter_months(year, month):
    """Indian financial year quarters (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar) each sit inside one calendar year."""
    start_month = (month - 1) // 3 * 3 + 1
    return [(year, start_month + offset) for offset in range(3)]


def spend_query(client_id, start=None, end=None):
    query = Invoice.query.filter(Invoice.client_id == client_id, Invoice.status.in_(SPEND_STATUSES),
                                 Invoice.is_duplicate_flag.is_(False))
    if start:
        query = query.filter(Invoice.final_invoice_date >= start)
    if end:
        query = query.filter(Invoice.final_invoice_date <= end)
    return query


def _f(value):
    return float(value or 0)


def dashboard_data(client_id):
    today = date.today()
    start, end = month_range(today.year, today.month)
    this_month = spend_query(client_id, start, end).all()
    overdue = [i for i in Invoice.query.filter(Invoice.client_id == client_id, Invoice.status.in_(OPEN_AP_STATUSES),
                                               Invoice.is_duplicate_flag.is_(False)) if effective_due(i) < today]
    kpis = {
        "invoice_count": len(this_month),
        "total_amount": round(sum(_f(i.final_total_amount) for i in this_month), 2),
        "pending_approvals": Invoice.query.filter_by(client_id=client_id, status="pending_approval").count(),
        "overdue_count": len(overdue),
        "overdue_amount": round(sum(_f(i.final_total_amount) for i in overdue), 2),
    }

    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.insert(0, (year, month))
        year, month = previous_month(year, month)
    first = date(months[0][0], months[0][1], 1)
    invoices = spend_query(client_id, first, end).all()

    by_month = defaultdict(float)
    by_category = defaultdict(float)
    by_vendor = defaultdict(float)
    for invoice in invoices:
        d = invoice.final_invoice_date
        by_month[(d.year, d.month)] += _f(invoice.final_total_amount)
        by_category[invoice.expense_category or "Uncategorised"] += _f(invoice.final_total_amount)
        by_vendor[invoice.display_vendor] += _f(invoice.final_total_amount)

    # Doughnut stays readable: top five categories, the rest folded into "Other"
    ranked = sorted(by_category.items(), key=lambda kv: -kv[1])
    category_rows = ranked[:5]
    if len(ranked) > 5:
        category_rows.append(("Other", sum(v for _, v in ranked[5:])))

    status_rows = defaultdict(lambda: defaultdict(int))
    status_query = Invoice.query.filter(Invoice.client_id == client_id, Invoice.invoice_date >= first,
                                        Invoice.is_duplicate_flag.is_(False))
    for invoice in status_query:
        d = invoice.invoice_date
        status_rows[(d.year, d.month)][invoice.status] += 1
    active_months = [m for m in months if m in status_rows][-6:] or months[-1:]
    status_names = ("approved", "paid", "pending_approval", "reviewed", "pending_review", "auto_captured", "rejected", "cancelled")
    used = [s for s in status_names if any(status_rows[m][s] for m in active_months)]

    return {
        "kpis": kpis,
        "trend": {"labels": [f"{MONTH_NAMES[m - 1]} {str(y)[2:]}" for y, m in months],
                  "values": [round(by_month[m], 2) for m in months]},
        "category": {"labels": [k for k, _ in category_rows], "values": [round(v, 2) for _, v in category_rows]},
        "vendors": {"labels": [k for k, _ in sorted(by_vendor.items(), key=lambda kv: -kv[1])[:10]],
                    "values": [round(v, 2) for _, v in sorted(by_vendor.items(), key=lambda kv: -kv[1])[:10]]},
        "status": {"labels": [f"{MONTH_NAMES[m - 1]} {str(y)[2:]}" for y, m in active_months],
                   "series": {s: [status_rows[m][s] for m in active_months] for s in used}},
    }


def cost_centre_tree(client_id, start, end):
    """Flat depth-first list of centres with own spend and rolled-up spend."""
    centres = CostCentre.query.filter_by(client_id=client_id).order_by(CostCentre.code).all()
    own = defaultdict(float)
    counts = defaultdict(int)
    unallocated, unallocated_count = 0.0, 0
    for invoice in spend_query(client_id, start, end):
        if invoice.cost_centre_id:
            own[invoice.cost_centre_id] += _f(invoice.final_taxable_amount)
            counts[invoice.cost_centre_id] += 1
        else:
            unallocated += _f(invoice.final_taxable_amount)
            unallocated_count += 1
    children = defaultdict(list)
    for centre in centres:
        children[centre.parent_id].append(centre)

    rows = []

    def walk(centre, depth):
        row = {"centre": centre, "depth": depth, "own": own[centre.id], "count": counts[centre.id], "total": own[centre.id]}
        rows.append(row)
        for child in children[centre.id]:
            row["total"] += walk(child, depth + 1)
        return row["total"]

    for root in children[None]:
        walk(root, 0)
    return rows, {"amount": unallocated, "count": unallocated_count}


def _period_actuals(client_id, periods):
    """Spend per cost centre for a list of (year, month), on taxable value (GST is normally creditable)."""
    totals = defaultdict(float)
    for year, month in periods:
        start, end = month_range(year, month)
        for invoice in spend_query(client_id, start, end):
            totals[invoice.cost_centre_id] += _f(invoice.final_taxable_amount)
    return totals


def traffic_light(variance_pct):
    """Only overspend is adverse. Green within 5%, amber 5-15%, red above 15%."""
    if variance_pct is None:
        return "gray"
    adverse = max(variance_pct, 0)
    return "green" if adverse <= 5 else ("amber" if adverse <= 15 else "red")


def variance_data(client_id, year, month):
    centres = CostCentre.query.filter_by(client_id=client_id).order_by(CostCentre.code).all()
    budgets = defaultdict(float)
    for budget in Budget.query.filter_by(client_id=client_id, period_year=year, period_month=month):
        budgets[budget.cost_centre_id] += _f(budget.budget_amount)
    actuals = _period_actuals(client_id, [(year, month)])

    rows = []
    for centre in centres:
        budget, actual = budgets[centre.id], actuals[centre.id]
        if not budget and not actual:
            continue
        variance = actual - budget
        pct = round(variance * 100 / budget, 1) if budget else None
        rows.append({"centre": centre, "budget": budget, "actual": actual, "variance": variance, "pct": pct,
                     "light": traffic_light(pct) if budget else "red"})
    if actuals[None]:
        rows.append({"centre": None, "budget": 0.0, "actual": actuals[None], "variance": actuals[None], "pct": None, "light": "gray"})
    totals = {"budget": sum(r["budget"] for r in rows), "actual": sum(r["actual"] for r in rows)}
    totals["variance"] = totals["actual"] - totals["budget"]
    totals["pct"] = round(totals["variance"] * 100 / totals["budget"], 1) if totals["budget"] else None

    start, end = month_range(year, month)
    invoices = spend_query(client_id, start, end).all()
    adverse = sorted((r for r in rows if r["centre"] is not None and r["variance"] > 0), key=lambda r: -r["variance"])[:3]
    commentary = [_commentary(row, [i for i in invoices if i.cost_centre_id == row["centre"].id]) for row in adverse]

    prev_y, prev_m = previous_month(year, month)
    quarter = fiscal_quarter_months(year, month)
    quarter_py = [(y - 1, m) for y, m in quarter]
    last_month = _period_actuals(client_id, [(prev_y, prev_m)])
    this_q, py_q = _period_actuals(client_id, quarter), _period_actuals(client_id, quarter_py)
    comparison = []
    for centre in centres:
        values = (actuals[centre.id], last_month[centre.id], this_q[centre.id], py_q[centre.id])
        if any(values):
            comparison.append({"centre": centre, "this_month": values[0], "last_month": values[1],
                               "this_quarter": values[2], "py_quarter": values[3]})
    labels = {"last_month": f"{MONTH_NAMES[prev_m - 1]} {prev_y}", "this_month": f"{MONTH_NAMES[month - 1]} {year}",
              "this_quarter": f"{MONTH_NAMES[quarter[0][1] - 1]}-{MONTH_NAMES[quarter[2][1] - 1]} {quarter[2][0]}",
              "py_quarter": f"{MONTH_NAMES[quarter_py[0][1] - 1]}-{MONTH_NAMES[quarter_py[2][1] - 1]} {quarter_py[2][0]}"}
    return {"rows": rows, "totals": totals, "commentary": commentary, "comparison": comparison, "labels": labels}


def _commentary(row, invoices):
    """Rule-based narrative. States only what the data shows; causes are for the reader to confirm."""
    name, over = row["centre"].name, inr(row["variance"], decimals=0)
    if not row["budget"]:
        return f"{name} spent {inr(row['actual'], decimals=0)} with no budget set for the period. Recommend setting a budget or reclassifying the spend."
    by_vendor = defaultdict(float)
    by_category = defaultdict(float)
    for invoice in invoices:
        by_vendor[invoice.display_vendor] += _f(invoice.final_taxable_amount)
        by_category[invoice.expense_category or "Uncategorised"] += _f(invoice.final_taxable_amount)
    driver = ""
    if by_vendor:
        vendor, amount = max(by_vendor.items(), key=lambda kv: kv[1])
        category = max(by_category.items(), key=lambda kv: kv[1])[0]
        share = round(amount * 100 / row["actual"]) if row["actual"] else 0
        driver = f" The largest item is {vendor} at {inr(amount, decimals=0)} ({share}% of actual), and the main category is {category}."
    pct = row["pct"] or 0
    action = ("Recommend a budget revision for the next quarter, or a review of the commitment." if pct > 15
              else "Recommend monitoring next month before revising the budget.")
    return f"{name} exceeded budget by {over} ({pct}%).{driver} {action}"


def effective_due(invoice):
    """Due date if known. Otherwise invoice date plus 45 days (MSME) or 30 days (others)."""
    if invoice.due_date:
        return invoice.due_date
    base = invoice.display_date or invoice.created_at.date()
    return base + timedelta(days=MSME_LIMIT_DAYS if invoice.vendor and invoice.vendor.msme_registered else 30)


def bucket_for(days_overdue):
    if days_overdue <= 0:
        return "Current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def aging_data(client_id, as_of=None):
    as_of = as_of or date.today()
    invoices = Invoice.query.filter(Invoice.client_id == client_id, Invoice.status.in_(OPEN_AP_STATUSES),
                                    Invoice.is_duplicate_flag.is_(False)).all()
    empty = lambda: {b: 0.0 for b in AGING_BUCKETS}  # noqa: E731
    by_vendor, by_centre, totals = defaultdict(empty), defaultdict(empty), empty()
    msme = []
    for invoice in invoices:
        amount = _f(invoice.final_total_amount)
        bucket = bucket_for((as_of - effective_due(invoice)).days)
        by_vendor[invoice.display_vendor][bucket] += amount
        by_centre[invoice.cost_centre.name if invoice.cost_centre else "Unallocated"][bucket] += amount
        totals[bucket] += amount
        if invoice.vendor and invoice.vendor.msme_registered and invoice.display_date:
            age = (as_of - invoice.display_date).days
            limit_date = invoice.display_date + timedelta(days=MSME_LIMIT_DAYS)
            state = "breached" if age > MSME_LIMIT_DAYS else ("approaching" if age >= MSME_WARN_DAYS else "ok")
            msme.append({"invoice": invoice, "age": age, "limit_date": limit_date, "days_left": MSME_LIMIT_DAYS - age,
                         "state": state, "amount": amount})
    msme.sort(key=lambda m: -m["age"])

    def table(source):
        rows = [{"name": name, **values, "total": sum(values.values())} for name, values in source.items()]
        return sorted(rows, key=lambda r: -r["total"])

    return {"by_vendor": table(by_vendor), "by_centre": table(by_centre), "msme": msme,
            "totals": {**totals, "total": sum(totals.values())}, "buckets": AGING_BUCKETS, "as_of": as_of}
