"""Invoice intake shared by web upload, email ingestion and offline sync."""
import json
from datetime import timedelta

from flask import current_app

from ..models import Invoice, InvoiceLineItem, Vendor, db
from ..utils import absolute_file_path, store_file
from .ocr_engine import extract_invoice_data, name_similarity


def match_vendor(client_id, gstin):
    """Auto-link only on an exact GSTIN match. A name match is a suggestion, never a link."""
    if not gstin:
        return None
    return Vendor.query.filter(Vendor.client_id == client_id, Vendor.gstin == gstin, Vendor.status != "archived").first()


def suggest_vendors(client_id, name):
    if not name:
        return []
    vendors = Vendor.query.filter(Vendor.client_id == client_id, Vendor.status.in_(("active", "pending"))).all()
    scored = [(name_similarity(name, v.trade_name), v) for v in vendors]
    return [v for score, v in sorted(scored, key=lambda s: -s[0]) if score > 0.8][:3]


def find_same_file(client_id, file_hash, exclude_id=None):
    query = Invoice.query.filter_by(client_id=client_id, file_hash=file_hash)
    if exclude_id:
        query = query.filter(Invoice.id != exclude_id)
    return query.order_by(Invoice.id).first()


def find_same_invoice(invoice):
    """Same invoice number, vendor and amount already on file for this client."""
    number = invoice.final_invoice_number or invoice.ocr_invoice_number
    amount = invoice.amount
    if not number or amount is None:
        return None
    candidates = Invoice.query.filter(Invoice.client_id == invoice.client_id, Invoice.id != invoice.id,
                                      Invoice.status != "cancelled", Invoice.is_duplicate_flag.is_(False),
                                      (Invoice.final_invoice_number == number) | (Invoice.ocr_invoice_number == number)).all()
    vendor_key = invoice.vendor_id or (invoice.final_gstin or invoice.ocr_gstin) or (invoice.final_vendor_name or invoice.ocr_vendor_name)
    for other in candidates:
        other_key = other.vendor_id or (other.final_gstin or other.ocr_gstin) or (other.final_vendor_name or other.ocr_vendor_name)
        if other_key == vendor_key and other.amount is not None and abs(float(other.amount) - float(amount)) < 0.01:
            return other
    return None


def ingest_file(client, data, original_name, source="upload", user=None, email_meta=None, offline=False):
    """Store the file, run OCR, create the Invoice. The caller commits. Raises ValueError for a bad file."""
    subfolder = "invoices" if source != "camera" else "expenses"
    safe_name, rel_path, digest = store_file(data, original_name, client.code, subfolder)
    max_pages = current_app.config.get("OCR_MAX_PDF_PAGES", 10)
    ocr = extract_invoice_data(absolute_file_path(rel_path), exclude_gstin=client.gstin, max_pages=max_pages)

    invoice = Invoice(
        client_id=client.id, source=source, original_filename=safe_name, original_filepath=rel_path, file_hash=digest,
        uploaded_by=user.id if user else None, synced_from_offline=offline,
        invoice_number=ocr["invoice_number"], invoice_date=ocr["invoice_date"], due_date=ocr["due_date"],
        ocr_vendor_name=ocr["vendor_name"], ocr_gstin=ocr["gstin"], ocr_invoice_number=ocr["invoice_number"],
        ocr_invoice_date=ocr["invoice_date"], ocr_total_amount=ocr["total_amount"],
        ocr_taxable_amount=ocr["taxable_amount"], ocr_cgst=ocr["cgst"], ocr_sgst=ocr["sgst"], ocr_igst=ocr["igst"],
        ocr_tds_applicable=ocr["tds_applicable"], ocr_tds_section=ocr["tds_section"], ocr_tds_rate=ocr["tds_rate"],
        ocr_confidence_score=ocr["confidence"], ocr_raw_text=ocr["raw_text"],
        ocr_field_confidence=json.dumps(ocr["field_confidence"]), ocr_warnings=json.dumps(ocr["warnings"]),
        final_hsn_sac=ocr["hsn_sac"], expense_category=ocr["category"],
        status="auto_captured" if ocr["confidence"] >= current_app.config["OCR_HIGH_CONFIDENCE"] else "pending_review",
    )
    if email_meta:
        invoice.source_email_subject = (email_meta.get("subject") or "")[:300]
        invoice.source_email_from = (email_meta.get("from") or "")[:200]
        invoice.source_email_date = (email_meta.get("date") or "")[:60]

    invoice.vendor = match_vendor(client.id, ocr["gstin"])
    if invoice.vendor and invoice.due_date is None and invoice.invoice_date and invoice.vendor.msme_registered:
        invoice.due_date = invoice.invoice_date + timedelta(days=45)

    db.session.add(invoice)
    db.session.flush()

    same_file = find_same_file(client.id, digest, exclude_id=invoice.id)
    same_invoice = same_file or find_same_invoice(invoice)
    if same_invoice:
        invoice.is_duplicate_flag, invoice.duplicate_of_id = True, same_invoice.id

    for item in ocr["line_items"]:
        db.session.add(InvoiceLineItem(invoice_id=invoice.id, **item))
    return invoice
