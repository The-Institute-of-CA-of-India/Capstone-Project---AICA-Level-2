"""REST API for the PWA and its offline sync queue. Session-cookie auth; JSON only."""
import base64
import binascii
import json
from datetime import datetime

from flask import Blueprint, abort, current_app, jsonify, request
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

from ..approvals import service as approval_service
from ..approvals.service import ApprovalError
from ..invoices.service import ingest_file
from ..models import Client, Invoice, OfflineSyncQueue, Vendor, db, utcnow
from ..reports.data import dashboard_data
from ..utils import audit, get_client_or_403, next_code, valid_gstin, valid_pan

bp = Blueprint("api", __name__, url_prefix="/api")
OFFICE_ROLES = ("admin", "manager", "accountant")
UPLOAD_ROLES = OFFICE_ROLES + ("field_staff",)


def invoice_json(invoice):
    return {"id": invoice.id, "client_id": invoice.client_id, "client_name": invoice.client.name,
            "vendor": invoice.display_vendor, "invoice_number": invoice.display_number,
            "invoice_date": invoice.display_date.isoformat() if invoice.display_date else None,
            "amount": float(invoice.amount) if invoice.amount is not None else None,
            "category": invoice.expense_category, "cost_centre": invoice.cost_centre.name if invoice.cost_centre else None,
            "status": invoice.status, "level": invoice.current_level,
            "submitted_by": invoice.reviewer.full_name if invoice.reviewer else None,
            "confidence": invoice.ocr_confidence_score,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None}


def _audit_read(entity, entity_id=None):
    audit("download", entity, entity_id, {"api": request.path})
    db.session.commit()


def _pending_for_user():
    query = Invoice.query.filter_by(status="pending_approval")
    if current_user.role not in ("admin", "manager"):
        query = query.filter_by(current_approver_id=current_user.id)
    return query.order_by(Invoice.submitted_at).limit(200).all()


@bp.route("/health")
def health():
    return jsonify(status="ok", version=current_app.config["VERSION"])


@bp.route("/csrf")
@login_required
def csrf_token():
    return jsonify(csrf_token=generate_csrf())


@bp.route("/bootstrap")
@login_required
def bootstrap():
    """What the device caches for offline use: identity, client list, pending approvals."""
    uploadable = current_user.accessible_clients() if current_user.role in UPLOAD_ROLES else []
    return jsonify(user={"id": current_user.id, "name": current_user.full_name, "role": current_user.role},
                   clients=[{"id": c.id, "code": c.code, "name": c.name} for c in uploadable],
                   pending=[invoice_json(i) for i in _pending_for_user()],
                   my_pending_count=Invoice.query.filter_by(status="pending_approval", current_approver_id=current_user.id).count())


def _office_client(client_id):
    if current_user.role not in OFFICE_ROLES:
        abort(403)
    return get_client_or_403(client_id)


@bp.route("/clients/<int:client_id>/invoices")
@login_required
def client_invoices(client_id):
    _office_client(client_id)
    query = Invoice.query.filter_by(client_id=client_id)
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    invoices = query.order_by(Invoice.created_at.desc()).limit(500).all()
    _audit_read("invoice_list", client_id)
    return jsonify(invoices=[invoice_json(i) for i in invoices])


@bp.route("/clients/<int:client_id>/invoices/pending")
@login_required
def client_pending(client_id):
    query = Invoice.query.filter_by(client_id=client_id, status="pending_approval")
    if current_user.role in ("admin", "manager"):
        pass
    elif current_user.role == "approver":
        query = query.filter_by(current_approver_id=current_user.id)
    else:
        _office_client(client_id)
    invoices = query.order_by(Invoice.submitted_at).all()
    _audit_read("invoice_list", client_id)
    return jsonify(invoices=[invoice_json(i) for i in invoices])


@bp.route("/clients/<int:client_id>/invoices", methods=["POST"])
@login_required
def create_invoice(client_id):
    if current_user.role not in UPLOAD_ROLES:
        abort(403)
    client = get_client_or_403(client_id)
    storage = request.files.get("file")
    if not storage:
        return jsonify(error="attach a file in the 'file' field"), 400
    try:
        invoice = ingest_file(client, storage.read(), storage.filename, source=request.form.get("source", "upload")
                              if request.form.get("source") in ("upload", "camera") else "upload", user=current_user)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400
    audit("upload", "invoice", invoice.id, {"api": True, "file": invoice.original_filename})
    db.session.commit()
    return jsonify(invoice=invoice_json(invoice)), 201


def _approval_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        abort(404)
    return invoice


@bp.route("/invoices/<int:invoice_id>/approve", methods=["PATCH"])
@login_required
def approve(invoice_id):
    invoice = _approval_invoice(invoice_id)
    body = request.get_json(silent=True) or {}
    try:
        done = approval_service.approve(invoice, current_user, body.get("comments"))
    except ApprovalError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 409
    db.session.commit()
    return jsonify(invoice=invoice_json(invoice), fully_approved=done)


@bp.route("/invoices/<int:invoice_id>/reject", methods=["PATCH"])
@login_required
def reject(invoice_id):
    invoice = _approval_invoice(invoice_id)
    body = request.get_json(silent=True) or {}
    try:
        approval_service.reject(invoice, current_user, body.get("reason"))
    except ApprovalError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 409
    db.session.commit()
    return jsonify(invoice=invoice_json(invoice))


@bp.route("/clients/<int:client_id>/vendors")
@login_required
def vendors(client_id):
    _office_client(client_id)
    rows = Vendor.query.filter(Vendor.client_id == client_id, Vendor.status != "archived").order_by(Vendor.trade_name).all()
    _audit_read("vendor_list", client_id)
    return jsonify(vendors=[{"id": v.id, "code": v.code, "trade_name": v.trade_name, "gstin": v.gstin, "pan": v.pan,
                             "status": v.status, "category": v.category, "msme": v.msme_registered} for v in rows])


@bp.route("/clients/<int:client_id>/dashboard")
@login_required
def dashboard(client_id):
    _office_client(client_id)
    _audit_read("dashboard", client_id)
    return jsonify(dashboard_data(client_id))


# ---- Offline sync ------------------------------------------------------------------

class _Conflict(Exception):
    pass


def _sync_approval(payload, item):
    invoice = db.session.get(Invoice, int(payload.get("invoice_id", 0)))
    if invoice is None:
        raise ValueError("Invoice no longer exists.")
    item.invoice_id = invoice.id
    if current_user.role == "field_staff":
        raise ValueError("Your role cannot approve invoices.")
    decision = payload.get("decision")
    seen = payload.get("seen_updated_at")
    current = invoice.updated_at.isoformat() if invoice.updated_at else None
    moved_on = invoice.status != "pending_approval" or not approval_service.can_act(invoice, current_user)
    if moved_on or (seen and seen != current):
        raise _Conflict(f"Invoice changed while you were offline. It is now '{invoice.status.replace('_', ' ')}'. Your '{decision}' was not applied.")
    if decision == "approve":
        approval_service.approve(invoice, current_user, payload.get("comments"))
    elif decision == "reject":
        approval_service.reject(invoice, current_user, payload.get("comments"))
    else:
        raise ValueError("Unknown decision.")
    return {"invoice_id": invoice.id, "status": invoice.status}


def _sync_upload(payload, item):
    if current_user.role not in UPLOAD_ROLES:
        raise ValueError("Your role cannot upload invoices.")
    client_id = int(payload.get("client_id", 0))
    client = db.session.get(Client, client_id)
    if client is None or not current_user.can_access_client(client_id):
        raise ValueError("You do not have access to this client.")
    try:
        data = base64.b64decode(payload.get("image_base64", ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The captured image is corrupted.") from exc
    invoice = ingest_file(client, data, payload.get("filename") or "offline_capture.jpg", source="camera", user=current_user, offline=True)
    details = payload.get("details") or {}
    note = " | ".join(f"{k}: {str(v)[:200]}" for k, v in details.items() if v)
    if note:
        invoice.notes = f"Entered offline: {note}"
    if details.get("category"):
        invoice.expense_category = str(details["category"])[:40]
    item.invoice_id = invoice.id
    audit("upload", "invoice", invoice.id, {"source": "offline_sync", "device": item.device_id})
    return {"invoice_id": invoice.id, "confidence": invoice.ocr_confidence_score}


def _sync_vendor(payload, item):
    if current_user.role not in OFFICE_ROLES + ("field_staff",):
        raise ValueError("Your role cannot create vendors.")
    client_id = int(payload.get("client_id", 0))
    client = db.session.get(Client, client_id)
    if client is None or not current_user.can_access_client(client_id):
        raise ValueError("You do not have access to this client.")
    name = str(payload.get("trade_name") or "").strip()[:200]
    pan = str(payload.get("pan") or "").strip().upper()
    gstin = str(payload.get("gstin") or "").strip().upper()
    if not name or not valid_pan(pan):
        raise ValueError("A vendor needs a trade name and a valid PAN.")
    if gstin and not valid_gstin(gstin):
        raise ValueError("Invalid GSTIN.")
    if Vendor.query.filter_by(client_id=client_id, pan=pan).first():
        raise _Conflict(f"A vendor with PAN {pan} already exists for this client.")
    code = next_code("V", [c for (c,) in db.session.query(Vendor.code).filter_by(client_id=client_id)])
    vendor = Vendor(client_id=client_id, code=code, trade_name=name, pan=pan, gstin=gstin or None, status="pending",
                    registered_by="internal", notes="Created offline; awaiting verification.")
    db.session.add(vendor)
    db.session.flush()
    audit("create", "vendor", vendor.id, {"source": "offline_sync"})
    return {"vendor_id": vendor.id, "code": code}


_HANDLERS = {"approval": _sync_approval, "invoice_upload": _sync_upload, "vendor_create": _sync_vendor}


def _parse_device_time(text):
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _storable_payload(payload):
    """Never keep image bytes in the queue table: the file itself is stored with the invoice."""
    return json.dumps({k: v for k, v in payload.items() if k != "image_base64"})[:20000]


@bp.route("/sync", methods=["POST"])
@login_required
def sync():
    """Accept a batch of queued offline actions. Each is applied on its own; a retry is safe."""
    body = request.get_json(silent=True) or {}
    device_id = str(body.get("device_id") or "unknown")[:80]
    results = []
    for raw in (body.get("items") or [])[:20]:
        uuid_value = str(raw.get("uuid") or "")[:36]
        action_type = raw.get("action_type")
        payload = raw.get("payload") or {}
        existing = OfflineSyncQueue.query.filter_by(client_uuid=uuid_value).first() if uuid_value else None
        if existing:
            results.append({"uuid": uuid_value, "status": existing.sync_status, "detail": existing.conflict_details})
            continue
        if action_type not in _HANDLERS:
            results.append({"uuid": uuid_value, "status": "failed", "detail": "Unknown action type."})
            continue
        item = OfflineSyncQueue(client_uuid=uuid_value or None, device_id=device_id, user_id=current_user.id,
                                action_type=action_type, payload=_storable_payload(payload),
                                created_at_device=_parse_device_time(raw.get("created_at")), synced_at=utcnow())
        result = {"uuid": uuid_value}
        try:
            result["data"] = _HANDLERS[action_type](payload, item)
            item.sync_status = "synced"
        except _Conflict as exc:
            db.session.rollback()
            item.sync_status, item.conflict_details = "conflict", str(exc)
            result["detail"] = str(exc)
        except (ValueError, ApprovalError) as exc:
            db.session.rollback()
            item.sync_status, item.conflict_details = "failed", str(exc)
            result["detail"] = str(exc)
        result["status"] = item.sync_status
        db.session.add(item)
        audit("update", "offline_sync", None, {"action": action_type, "status": item.sync_status, "device": device_id})
        db.session.commit()
        results.append(result)
    counts = {status: sum(1 for r in results if r["status"] == status) for status in ("synced", "conflict", "failed")}
    return jsonify(results=results, **counts)
