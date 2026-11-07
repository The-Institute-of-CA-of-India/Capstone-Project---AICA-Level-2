"""Invoice upload, OCR review, listing, payment."""
import io
import json
from decimal import Decimal

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..approvals.service import ApprovalError, submit_for_approval
from ..clients.routes import OFFICE_ROLES
from ..models import EDITABLE_STATUSES, INVOICE_STATUSES, CostCentre, Invoice, InvoiceLineItem, Vendor, db, utcnow
from ..utils import absolute_file_path, audit, can_view_invoice, get_client_or_403, paginate, roles_required, to_decimal
from .forms import PaymentForm, ReviewForm
from .ocr_engine import render_preview, tesseract_status
from .service import find_same_invoice, ingest_file, suggest_vendors

bp = Blueprint("invoices", __name__)


def _get_invoice(invoice_id, office_only=False):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        abort(404)
    if not can_view_invoice(current_user, invoice):
        abort(403)
    if office_only and (current_user.role not in OFFICE_ROLES or not current_user.can_access_client(invoice.client_id)):
        abort(403)
    return invoice


@bp.route("/clients/<int:client_id>/invoices")
@roles_required(*OFFICE_ROLES, "field_staff")
def list_invoices(client_id):
    client = get_client_or_403(client_id)
    query = Invoice.query.filter_by(client_id=client_id)
    if current_user.role == "field_staff":
        query = query.filter_by(uploaded_by=current_user.id)
    status = request.args.get("status", "")
    term = request.args.get("q", "").strip()
    if status == "to_review":
        query = query.filter(Invoice.status.in_(("auto_captured", "pending_review")))
    elif status in INVOICE_STATUSES:
        query = query.filter_by(status=status)
    if term:
        like = f"%{term}%"
        query = query.outerjoin(Vendor).filter(or_(
            Invoice.final_invoice_number.ilike(like), Invoice.ocr_invoice_number.ilike(like),
            Invoice.final_vendor_name.ilike(like), Invoice.ocr_vendor_name.ilike(like), Vendor.trade_name.ilike(like)))
    page = paginate(query.order_by(Invoice.created_at.desc(), Invoice.id.desc()))
    return render_template("invoices/list.html", client=client, page=page, status=status, term=term, statuses=INVOICE_STATUSES)


@bp.route("/clients/<int:client_id>/invoices/upload", methods=["GET", "POST"])
@roles_required(*OFFICE_ROLES, "field_staff")
def upload(client_id):
    client = get_client_or_403(client_id)
    if request.method == "GET":
        return render_template("invoices/upload.html", client=client, ocr=tesseract_status())

    wants_json = request.accept_mimetypes.best == "application/json"
    files = [f for f in request.files.getlist("files") if f and f.filename]
    results = []
    for storage in files:
        source = "camera" if request.form.get("captured") == "1" else "upload"
        try:
            invoice = ingest_file(client, storage.read(), storage.filename, source=source, user=current_user)
            audit("upload", "invoice", invoice.id, {"file": invoice.original_filename, "source": source,
                                                    "confidence": invoice.ocr_confidence_score})
            db.session.commit()
            results.append({"file": storage.filename, "ok": True, "id": invoice.id,
                            "vendor": invoice.display_vendor, "confidence": invoice.ocr_confidence_score,
                            "duplicate": invoice.is_duplicate_flag,
                            "url": url_for("invoices.review", invoice_id=invoice.id) if current_user.role != "field_staff"
                            else url_for("invoices.list_invoices", client_id=client_id)})
        except ValueError as exc:
            db.session.rollback()
            results.append({"file": storage.filename, "ok": False, "error": str(exc)})
    if wants_json:
        return jsonify(results=results)
    for result in results:
        if result["ok"]:
            flash(f"{result['file']}: captured at {result['confidence']:.0%} confidence.", "success")
        else:
            flash(f"{result['file']}: {result['error']}", "danger")
    if not files:
        flash("Choose at least one file.", "danger")
    if len(results) == 1 and results[0]["ok"]:
        return redirect(results[0]["url"])
    return redirect(url_for("invoices.list_invoices", client_id=client_id))


def _prefill(form, invoice):
    """Corrected values if they exist, otherwise what OCR read."""
    pairs = {"final_vendor_name": invoice.final_vendor_name or invoice.ocr_vendor_name,
             "final_gstin": invoice.final_gstin or invoice.ocr_gstin,
             "final_invoice_number": invoice.final_invoice_number or invoice.ocr_invoice_number,
             "final_invoice_date": invoice.final_invoice_date or invoice.ocr_invoice_date,
             "due_date": invoice.due_date,
             "final_taxable_amount": _first(invoice.final_taxable_amount, invoice.ocr_taxable_amount),
             "final_cgst": _first(invoice.final_cgst, invoice.ocr_cgst),
             "final_sgst": _first(invoice.final_sgst, invoice.ocr_sgst),
             "final_igst": _first(invoice.final_igst, invoice.ocr_igst),
             "final_total_amount": _first(invoice.final_total_amount, invoice.ocr_total_amount),
             "final_tds_section": invoice.final_tds_section or invoice.ocr_tds_section or "",
             "final_tds_rate": _first(invoice.final_tds_rate, invoice.ocr_tds_rate),
             "final_hsn_sac": invoice.final_hsn_sac, "expense_category": invoice.expense_category or "",
             "cost_centre_id": invoice.cost_centre_id or 0, "gl_account": invoice.gl_account,
             "final_description": invoice.final_description, "narration": invoice.narration,
             "vendor_id": invoice.vendor_id or 0}
    for name, value in pairs.items():
        getattr(form, name).data = value


def _first(*values):
    return next((v for v in values if v is not None), None)


def _save_line_items(invoice):
    descriptions = request.form.getlist("li_description")
    hsns, quantities = request.form.getlist("li_hsn"), request.form.getlist("li_quantity")
    rates, taxables = request.form.getlist("li_unit_price"), request.form.getlist("li_taxable")
    invoice.line_items.clear()
    db.session.flush()
    for i, description in enumerate(descriptions):
        if not description.strip():
            continue
        invoice.line_items.append(InvoiceLineItem(
            description=description.strip()[:300], hsn_sac=(hsns[i] if i < len(hsns) else "")[:10],
            quantity=to_decimal(quantities[i]) if i < len(quantities) else None,
            unit_price=to_decimal(rates[i]) if i < len(rates) else None,
            taxable_amount=to_decimal(taxables[i]) if i < len(taxables) else None))


def _submission_errors(form, invoice):
    errors = []
    for field, label in ((form.final_vendor_name, "vendor name"), (form.final_invoice_number, "invoice number"),
                         (form.final_invoice_date, "invoice date"), (form.final_total_amount, "total amount")):
        if not field.data:
            field.errors = list(field.errors) + ["Required to submit for approval."]
            errors.append(label)
    if invoice.vendor and invoice.vendor.status == "blacklisted":
        errors.append("vendor is blacklisted")
    taxes = sum((form[f].data or Decimal(0)) for f in ("final_cgst", "final_sgst", "final_igst"))
    if form.final_taxable_amount.data is not None and form.final_total_amount.data is not None:
        if abs(form.final_taxable_amount.data + taxes - form.final_total_amount.data) > Decimal("1.00"):
            form.final_total_amount.errors = list(form.final_total_amount.errors) + [
                "Taxable value plus taxes does not equal this total (more than ₹1 apart)."]
            errors.append("arithmetic")
    return errors


@bp.route("/invoices/<int:invoice_id>/review", methods=["GET", "POST"])
@login_required
def review(invoice_id):
    invoice = _get_invoice(invoice_id, office_only=True)
    if invoice.status not in EDITABLE_STATUSES:
        flash(f"This invoice is {invoice.status.replace('_', ' ')} and can no longer be edited.", "info")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))
    form = ReviewForm()
    vendors = Vendor.query.filter(Vendor.client_id == invoice.client_id, Vendor.status != "archived").order_by(Vendor.trade_name).all()
    form.vendor_id.choices = [(0, "- Not linked -")] + [
        (v.id, f"{v.trade_name} ({v.code}){' - BLACKLISTED' if v.status == 'blacklisted' else ''}") for v in vendors]
    centres = CostCentre.query.filter_by(client_id=invoice.client_id, is_active=True).order_by(CostCentre.code).all()
    form.cost_centre_id.choices = [(0, "- Select -")] + [(c.id, f"{c.code} - {c.name}") for c in centres]

    if request.method == "GET":
        _prefill(form, invoice)
    elif form.validate_on_submit():
        for name in ("final_vendor_name", "final_gstin", "final_invoice_number", "final_invoice_date", "due_date",
                     "final_taxable_amount", "final_cgst", "final_sgst", "final_igst", "final_total_amount",
                     "final_tds_rate", "final_hsn_sac", "gl_account", "final_description", "narration"):
            setattr(invoice, name, form[name].data or (form[name].data if form[name].data == 0 else None))
        invoice.final_tds_section = form.final_tds_section.data or None
        invoice.expense_category = form.expense_category.data or None
        invoice.cost_centre_id = form.cost_centre_id.data or None
        invoice.vendor_id = form.vendor_id.data or None
        invoice.invoice_number = invoice.final_invoice_number
        invoice.invoice_date = invoice.final_invoice_date
        _save_line_items(invoice)
        db.session.flush()

        same = find_same_invoice(invoice)
        confirmed = request.form.get("confirm_not_duplicate") == "1"
        invoice.is_duplicate_flag, invoice.duplicate_of_id = (bool(same), same.id if same else None) if not confirmed else (False, None)

        if "submit_approval" in request.form:
            problems = _submission_errors(form, invoice)
            if invoice.is_duplicate_flag:
                problems.append("possible duplicate")
                flash("Possible duplicate. Compare it with the earlier invoice, or tick the confirmation box.", "warning")
            if problems:
                db.session.commit()  # keep the accountant's corrections
                if "vendor is blacklisted" in problems:
                    flash("This vendor is blacklisted, so the invoice cannot go for approval.", "danger")
                else:
                    flash("Please resolve the marked items before submitting.", "danger")
            else:
                invoice.reviewed_by, invoice.reviewed_at = current_user.id, utcnow()
                invoice.status = "reviewed"
                audit("update", "invoice", invoice.id, {"action": "reviewed", "corrections": _corrections(invoice)})
                try:
                    routed = submit_for_approval(invoice, current_user)
                except ApprovalError as exc:
                    routed = False
                    flash(str(exc), "danger")
                db.session.commit()
                if routed:
                    flash(f"Sent to {invoice.current_approver.full_name} for approval.", "success")
                    return redirect(url_for("invoices.list_invoices", client_id=invoice.client_id, status="to_review"))
                flash("Saved as reviewed. No approval rule matches this invoice, so add one to the approval matrix.", "warning")
                return redirect(url_for("invoices.detail", invoice_id=invoice.id))
        else:
            invoice.status = "pending_review"
            audit("update", "invoice", invoice.id, {"action": "saved"})
            db.session.commit()
            flash("Saved. You can come back to this invoice later.", "success")
            return redirect(url_for("invoices.list_invoices", client_id=invoice.client_id, status="to_review"))

    duplicate_of = invoice.duplicate_of if invoice.is_duplicate_flag else None
    unknown_vendor = invoice.vendor_id is None
    return render_template("invoices/review.html", invoice=invoice, client=invoice.client, form=form,
                           confidence=json.loads(invoice.ocr_field_confidence or "{}"),
                           warnings=json.loads(invoice.ocr_warnings or "[]"),
                           duplicate_of=duplicate_of, unknown_vendor=unknown_vendor,
                           suggestions=suggest_vendors(invoice.client_id, invoice.ocr_vendor_name) if unknown_vendor else [],
                           accept_values=_accept_values(invoice))


def _accept_values(invoice):
    """OCR values the 'Accept All' button copies into the form."""
    return {"final_vendor_name": invoice.ocr_vendor_name, "final_gstin": invoice.ocr_gstin,
            "final_invoice_number": invoice.ocr_invoice_number,
            "final_invoice_date": invoice.ocr_invoice_date.isoformat() if invoice.ocr_invoice_date else None,
            "final_taxable_amount": _money_text(invoice.ocr_taxable_amount), "final_cgst": _money_text(invoice.ocr_cgst),
            "final_sgst": _money_text(invoice.ocr_sgst), "final_igst": _money_text(invoice.ocr_igst),
            "final_total_amount": _money_text(invoice.ocr_total_amount)}


def _money_text(value):
    return f"{float(value):.2f}" if value is not None else None


def _corrections(invoice):
    pairs = (("vendor", invoice.ocr_vendor_name, invoice.final_vendor_name), ("gstin", invoice.ocr_gstin, invoice.final_gstin),
             ("number", invoice.ocr_invoice_number, invoice.final_invoice_number),
             ("total", _money_text(invoice.ocr_total_amount), _money_text(invoice.final_total_amount)))
    return {name: {"ocr": old, "final": new} for name, old, new in pairs if old != new}


@bp.route("/invoices/<int:invoice_id>")
@login_required
def detail(invoice_id):
    invoice = _get_invoice(invoice_id)
    return render_template("invoices/detail.html", invoice=invoice, client=invoice.client,
                           pay_form=PaymentForm(), warnings=json.loads(invoice.ocr_warnings or "[]"))


@bp.route("/invoices/<int:invoice_id>/file")
@login_required
def original_file(invoice_id):
    invoice = _get_invoice(invoice_id)
    if not invoice.original_filepath:
        abort(404)
    audit("download", "invoice", invoice.id, {"file": invoice.original_filename})
    db.session.commit()
    return send_file(absolute_file_path(invoice.original_filepath), as_attachment=True, download_name=invoice.original_filename)


@bp.route("/invoices/<int:invoice_id>/preview")
@login_required
def preview(invoice_id):
    invoice = _get_invoice(invoice_id)
    if not invoice.original_filepath:
        abort(404)
    path = absolute_file_path(invoice.original_filepath)
    if not path.exists():
        abort(404)
    png, count = render_preview(path, request.args.get("page", 1, type=int))
    response = send_file(io.BytesIO(png), mimetype="image/png", max_age=0)
    response.headers["X-Page-Count"] = str(count)
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


@bp.route("/invoices/<int:invoice_id>/pay", methods=["POST"])
@roles_required("admin", "manager", "accountant")
def pay(invoice_id):
    invoice = _get_invoice(invoice_id, office_only=True)
    form = PaymentForm()
    if invoice.status != "approved":
        flash("Only approved invoices can be marked as paid.", "danger")
    elif form.validate_on_submit():
        invoice.payment_date, invoice.payment_reference, invoice.status = form.payment_date.data, form.payment_reference.data, "paid"
        audit("update", "invoice", invoice.id, {"action": "paid", "reference": invoice.payment_reference})
        db.session.commit()
        flash("Marked as paid.", "success")
    else:
        flash("Enter the payment date and reference.", "danger")
    return redirect(url_for("invoices.detail", invoice_id=invoice.id))


@bp.route("/invoices/<int:invoice_id>/cancel", methods=["POST"])
@roles_required("admin", "manager", "accountant")
def cancel(invoice_id):
    invoice = _get_invoice(invoice_id, office_only=True)
    if invoice.status in ("paid", "cancelled"):
        flash("This invoice cannot be cancelled.", "danger")
    else:
        invoice.status, invoice.current_approver_id = "cancelled", None
        audit("update", "invoice", invoice.id, {"action": "cancelled"})
        db.session.commit()
        flash("Invoice cancelled.", "info")
    return redirect(url_for("invoices.detail", invoice_id=invoice.id))
