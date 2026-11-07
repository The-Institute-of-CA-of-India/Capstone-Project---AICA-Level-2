"""Dashboards, cost centre report, variance analysis, aging and exports."""
import io

from flask import Blueprint, Response, abort, render_template, request, send_file

from ..approvals.service import sla_stats
from ..clients.routes import OFFICE_ROLES
from ..models import CostCentre, Invoice, db
from ..utils import audit, get_client_or_403, paginate, roles_required
from . import data as report_data
from . import export

bp = Blueprint("reports", __name__, url_prefix="/clients/<int:client_id>/reports")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _period_label(year, month):
    return f"{report_data.MONTH_NAMES[month - 1]} {year}"


@bp.route("/dashboard")
@roles_required(*OFFICE_ROLES)
def dashboard(client_id):
    client = get_client_or_403(client_id)
    return render_template("reports/dashboard.html", client=client, data=report_data.dashboard_data(client_id), sla=sla_stats([client_id]))


@bp.route("/cost-centre")
@roles_required(*OFFICE_ROLES)
def cost_centre(client_id):
    client = get_client_or_403(client_id)
    year, month = report_data.parse_period(request.args.get("period"))
    start, end = report_data.month_range(year, month)
    rows, unallocated = report_data.cost_centre_tree(client_id, start, end)
    selected, drill = None, None
    cc_id = request.args.get("cc", type=int)
    if cc_id:
        selected = CostCentre.query.filter_by(id=cc_id, client_id=client_id).first()
    if selected or request.args.get("cc") == "none":
        query = report_data.spend_query(client_id, start, end).filter(Invoice.cost_centre_id == (selected.id if selected else None))
        drill = paginate(query.order_by(Invoice.final_invoice_date.desc()))
    return render_template("reports/cost_centre.html", client=client, rows=rows, unallocated=unallocated, selected=selected,
                           drill=drill, period=f"{year}-{month:02d}", label=_period_label(year, month))


@bp.route("/variance")
@roles_required(*OFFICE_ROLES)
def variance(client_id):
    client = get_client_or_403(client_id)
    year, month = report_data.parse_period(request.args.get("period"))
    return render_template("reports/variance.html", client=client, data=report_data.variance_data(client_id, year, month),
                           period=f"{year}-{month:02d}", label=_period_label(year, month))


@bp.route("/aging")
@roles_required(*OFFICE_ROLES)
def aging(client_id):
    client = get_client_or_403(client_id)
    return render_template("reports/aging.html", client=client, data=report_data.aging_data(client_id))


def _send_xlsx(buffer, name):
    return send_file(buffer, mimetype=XLSX, as_attachment=True, download_name=name)


@bp.route("/export/<name>")
@roles_required(*OFFICE_ROLES)
def export_report(client_id, name):
    client = get_client_or_403(client_id)
    year, month = report_data.parse_period(request.args.get("period"))
    label, stamp = _period_label(year, month), f"{year}-{month:02d}"
    if name == "dashboard.xlsx":
        response = _send_xlsx(export.dashboard_xlsx(client, report_data.dashboard_data(client_id)), f"{client.code}_dashboard.xlsx")
    elif name == "dashboard.pdf":
        pdf = export.dashboard_pdf(client, report_data.dashboard_data(client_id), sla_stats([client_id]))
        response = send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"{client.code}_dashboard.pdf")
    elif name == "cost-centre.xlsx":
        rows, unallocated = report_data.cost_centre_tree(client_id, *report_data.month_range(year, month))
        response = _send_xlsx(export.cost_centre_xlsx(client, rows, unallocated, label), f"{client.code}_cost_centres_{stamp}.xlsx")
    elif name == "variance.xlsx":
        response = _send_xlsx(export.variance_xlsx(client, report_data.variance_data(client_id, year, month), label), f"{client.code}_variance_{stamp}.xlsx")
    elif name == "aging.xlsx":
        response = _send_xlsx(export.aging_xlsx(client, report_data.aging_data(client_id)), f"{client.code}_ap_aging.xlsx")
    elif name == "invoices.xlsx":
        invoices = Invoice.query.filter_by(client_id=client_id).order_by(Invoice.invoice_date.desc()).all()
        response = _send_xlsx(export.invoices_xlsx(client, invoices), f"{client.code}_invoices.xlsx")
    elif name == "tally.csv":
        start, end = report_data.month_range(year, month)
        invoices = (Invoice.query.filter(Invoice.client_id == client_id, Invoice.status.in_(("approved", "paid")),
                                         Invoice.is_duplicate_flag.is_(False), Invoice.final_invoice_date >= start,
                                         Invoice.final_invoice_date <= end).order_by(Invoice.final_invoice_date).all())
        # BOM so Excel reads the file as UTF-8
        response = Response("﻿" + export.tally_csv(invoices), mimetype="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{client.code}_tally_{stamp}.csv"'})
    else:
        abort(404)
    audit("export", "report", client_id, {"report": name, "period": stamp})
    db.session.commit()
    return response
