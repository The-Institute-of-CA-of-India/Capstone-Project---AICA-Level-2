"""Vendor master, duplicate detection and public self-registration."""
import time
from collections import defaultdict, deque
from difflib import SequenceMatcher

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from ..clients.routes import OFFICE_ROLES
from ..models import SPEND_STATUSES, Client, Invoice, Vendor, VendorDocument, db, utcnow
from ..utils import absolute_file_path, audit, get_client_or_403, next_code, paginate, roles_required, store_file
from .forms import PublicRegistrationForm, VendorDocumentForm, VendorForm

bp = Blueprint("vendors", __name__)

_registrations_by_ip = defaultdict(deque)


def _normalise(name):
    return " ".join((name or "").lower().replace(".", " ").replace(",", " ").split())


def find_duplicates(client_id, pan, gstin, name, exclude_id=None):
    """Existing vendors sharing a PAN or GSTIN, or with a name more than 80% similar."""
    matches = []
    target = _normalise(name)
    for vendor in Vendor.query.filter(Vendor.client_id == client_id, Vendor.status != "archived"):
        if vendor.id == exclude_id:
            continue
        reasons = []
        if pan and vendor.pan == pan:
            reasons.append("same PAN")
        if gstin and vendor.gstin == gstin:
            reasons.append("same GSTIN")
        ratio = SequenceMatcher(None, target, _normalise(vendor.trade_name)).ratio()
        if ratio > 0.8:
            reasons.append(f"{ratio:.0%} name match")
        if reasons:
            matches.append((vendor, ", ".join(reasons)))
    return matches


def _new_vendor_code(client_id):
    return next_code("V", [c for (c,) in db.session.query(Vendor.code).filter_by(client_id=client_id)])


def _get_vendor(client_id, vendor_id):
    vendor = Vendor.query.filter_by(id=vendor_id, client_id=client_id).first()
    if vendor is None:
        abort(404)
    return vendor


@bp.route("/clients/<int:client_id>/vendors")
@roles_required(*OFFICE_ROLES)
def list_vendors(client_id):
    client = get_client_or_403(client_id)
    term = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Vendor.query.filter_by(client_id=client_id)
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Vendor.status != "archived")
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Vendor.trade_name.ilike(like), Vendor.legal_name.ilike(like),
                                 Vendor.pan.ilike(like), Vendor.gstin.ilike(like), Vendor.code.ilike(like)))
    page = paginate(query.order_by(Vendor.code))

    live = Vendor.query.filter(Vendor.client_id == client_id, Vendor.status != "archived")
    total = live.count()
    msme = live.filter(Vendor.msme_registered.is_(True)).count()
    top = (db.session.query(Vendor, func.sum(Invoice.final_total_amount).label("spend"))
           .join(Invoice, Invoice.vendor_id == Vendor.id)
           .filter(Vendor.client_id == client_id, Invoice.status.in_(SPEND_STATUSES), Invoice.is_duplicate_flag.is_(False))
           .group_by(Vendor.id).order_by(func.sum(Invoice.final_total_amount).desc()).limit(10).all())
    stats = {"total": total, "pending": live.filter(Vendor.status == "pending").count(),
             "msme_pct": round(msme * 100 / total) if total else 0}
    recent = live.order_by(Vendor.created_at.desc()).limit(5).all()
    return render_template("vendors/list.html", client=client, page=page, stats=stats, top=top, recent=recent,
                           term=term, status=status)


@bp.route("/clients/<int:client_id>/vendors/new", methods=["GET", "POST"])
@roles_required(*OFFICE_ROLES)
def new_vendor(client_id):
    client = get_client_or_403(client_id)
    form = VendorForm()
    if request.method == "GET":
        form.trade_name.data = request.args.get("name", "")
        form.gstin.data = request.args.get("gstin", "")
        if form.gstin.data and len(form.gstin.data) == 15:
            form.pan.data = form.gstin.data[2:12]
    duplicates = []
    if form.validate_on_submit():
        duplicates = find_duplicates(client_id, form.pan.data, form.gstin.data, form.trade_name.data)
        if not duplicates or form.confirm_duplicate.data:
            vendor = Vendor(client_id=client_id, code=_new_vendor_code(client_id), registered_by="internal",
                            status="active", approved_by=current_user.id, approved_at=utcnow())
            _apply_form(form, vendor)
            db.session.add(vendor)
            db.session.flush()
            audit("create", "vendor", vendor.id, {"code": vendor.code, "name": vendor.trade_name,
                                                  "duplicates_overridden": [v.code for v, _ in duplicates]})
            db.session.commit()
            flash(f"Vendor {vendor.code} created.", "success")
            return redirect(url_for("vendors.detail", client_id=client_id, vendor_id=vendor.id))
    return render_template("vendors/form.html", client=client, form=form, vendor=None, duplicates=duplicates)


def _apply_form(form, vendor):
    for name in ("trade_name", "legal_name", "pan", "gstin", "category", "msme_registered", "udyam_number",
                 "bank_account_no", "bank_ifsc", "bank_branch", "contact_person", "contact_email",
                 "contact_phone", "address"):
        setattr(vendor, name, getattr(form, name).data)
    if hasattr(form, "notes"):
        vendor.notes = form.notes.data


@bp.route("/clients/<int:client_id>/vendors/<int:vendor_id>")
@roles_required(*OFFICE_ROLES)
def detail(client_id, vendor_id):
    client = get_client_or_403(client_id)
    vendor = _get_vendor(client_id, vendor_id)
    spend = db.session.query(func.coalesce(func.sum(Invoice.final_total_amount), 0)).filter(
        Invoice.vendor_id == vendor.id, Invoice.status.in_(SPEND_STATUSES), Invoice.is_duplicate_flag.is_(False)).scalar()
    invoices = vendor.invoices.order_by(Invoice.invoice_date.desc()).limit(20).all()
    duplicates = find_duplicates(client_id, vendor.pan, vendor.gstin, vendor.trade_name, exclude_id=vendor.id)
    return render_template("vendors/detail.html", client=client, vendor=vendor, spend=spend, invoices=invoices,
                           duplicates=duplicates, doc_form=VendorDocumentForm(), documents=vendor.documents.all())


@bp.route("/clients/<int:client_id>/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
@roles_required(*OFFICE_ROLES)
def edit(client_id, vendor_id):
    client = get_client_or_403(client_id)
    vendor = _get_vendor(client_id, vendor_id)
    form = VendorForm(obj=vendor)
    duplicates = []
    if form.validate_on_submit():
        duplicates = find_duplicates(client_id, form.pan.data, form.gstin.data, form.trade_name.data, exclude_id=vendor.id)
        if not duplicates or form.confirm_duplicate.data:
            bank_changed = (form.bank_account_no.data != vendor.bank_account_no or form.bank_ifsc.data != vendor.bank_ifsc)
            _apply_form(form, vendor)
            audit("update", "vendor", vendor.id, {"code": vendor.code, "bank_details_changed": bank_changed})
            db.session.commit()
            flash("Vendor updated.", "success")
            return redirect(url_for("vendors.detail", client_id=client_id, vendor_id=vendor.id))
    return render_template("vendors/form.html", client=client, form=form, vendor=vendor, duplicates=duplicates)


@bp.route("/clients/<int:client_id>/vendors/<int:vendor_id>/status", methods=["POST"])
@roles_required(*OFFICE_ROLES)
def change_status(client_id, vendor_id):
    get_client_or_403(client_id)
    vendor = _get_vendor(client_id, vendor_id)
    action = request.form.get("action")
    if action == "approve":
        vendor.status, vendor.approved_by, vendor.approved_at = "active", current_user.id, utcnow()
        vendor.blacklist_reason = None
    elif action == "blacklist":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("A reason is required to blacklist a vendor.", "danger")
            return redirect(url_for("vendors.detail", client_id=client_id, vendor_id=vendor.id))
        vendor.status, vendor.blacklist_reason = "blacklisted", reason
    elif action == "archive":
        vendor.status = "archived"
    elif action == "restore":
        vendor.status = "active"
    else:
        abort(400)
    audit("approve" if action == "approve" else "update", "vendor", vendor.id, {"action": action})
    db.session.commit()
    flash(f"Vendor {vendor.code} is now {vendor.status}.", "success")
    return redirect(url_for("vendors.detail", client_id=client_id, vendor_id=vendor.id))


@bp.route("/clients/<int:client_id>/vendors/<int:vendor_id>/documents", methods=["POST"])
@roles_required(*OFFICE_ROLES)
def upload_document(client_id, vendor_id):
    client = get_client_or_403(client_id)
    vendor = _get_vendor(client_id, vendor_id)
    form = VendorDocumentForm()
    if form.validate_on_submit() and form.document.data:
        try:
            _save_doc(client, vendor, form.doc_type.data, form.document.data)
            audit("upload", "vendor_document", vendor.id, {"doc_type": form.doc_type.data})
            db.session.commit()
            flash("Document uploaded.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
    else:
        flash("Choose a file to upload.", "danger")
    return redirect(url_for("vendors.detail", client_id=client_id, vendor_id=vendor.id))


def _save_doc(client, vendor, doc_type, storage):
    name, path, digest = store_file(storage.read(), storage.filename, client.code, "vendor_docs")
    document = VendorDocument(vendor_id=vendor.id, doc_type=doc_type, filename=name, filepath=path, file_hash=digest)
    db.session.add(document)
    return document


@bp.route("/clients/<int:client_id>/vendors/<int:vendor_id>/documents/<int:doc_id>")
@roles_required(*OFFICE_ROLES)
def download_document(client_id, vendor_id, doc_id):
    get_client_or_403(client_id)
    vendor = _get_vendor(client_id, vendor_id)
    document = VendorDocument.query.filter_by(id=doc_id, vendor_id=vendor.id).first_or_404()
    audit("download", "vendor_document", document.id)
    db.session.commit()
    return send_file(absolute_file_path(document.filepath), as_attachment=True, download_name=document.filename)


# ---- Public self-registration (no login) -------------------------------------------

def _rate_limited():
    window = _registrations_by_ip[request.remote_addr]
    cutoff = time.monotonic() - 3600
    while window and window[0] < cutoff:
        window.popleft()
    return len(window) >= current_app.config["VENDOR_REG_LIMIT_PER_HOUR"]


@bp.route("/vendor/register/<token>", methods=["GET", "POST"])
def register_public(token):
    client = Client.query.filter_by(vendor_registration_token=token, is_archived=False).first()
    if client is None:
        abort(404)
    form = PublicRegistrationForm()
    if form.validate_on_submit():
        files = {"pan_card": form.doc_pan.data, "gst_cert": form.doc_gst.data,
                 "cancelled_cheque": form.doc_cheque.data, "msme_cert": form.doc_msme.data}
        if not files["pan_card"]:
            form.doc_pan.errors = ["Please attach your PAN card copy."]
        if not files["cancelled_cheque"]:
            form.doc_cheque.errors = ["Please attach a cancelled cheque."]
        if form.gstin.data and not files["gst_cert"]:
            form.doc_gst.errors = ["Please attach your GST certificate."]
        if not (form.doc_pan.errors or form.doc_cheque.errors or form.doc_gst.errors):
            if _rate_limited():
                abort(429)
            try:
                vendor = _create_self_registered(client, form, files)
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            else:
                _registrations_by_ip[request.remote_addr].append(time.monotonic())
                return render_template("vendors/register_done.html", client=client, vendor=vendor)
    return render_template("vendors/register_public.html", client=client, form=form)


def _create_self_registered(client, form, files):
    vendor = Vendor(client_id=client.id, code=_new_vendor_code(client.id), registered_by="self", status="pending")
    _apply_form(form, vendor)
    # Duplicates go to the accountant only; the public form must not reveal who else is on the vendor list.
    duplicates = find_duplicates(client.id, form.pan.data, form.gstin.data, form.trade_name.data)
    if duplicates:
        vendor.notes = "Possible duplicate of: " + "; ".join(f"{v.code} ({why})" for v, why in duplicates)
    db.session.add(vendor)
    db.session.flush()
    for doc_type, storage in files.items():
        if storage:
            _save_doc(client, vendor, doc_type, storage)
    audit("create", "vendor", vendor.id, {"code": vendor.code, "registered_by": "self"})
    db.session.commit()
    return vendor
