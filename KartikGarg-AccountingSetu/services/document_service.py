"""Document submission and processing pipeline.

UPLOAD → FILE VALIDATION → OCR/PDF EXTRACTION → AI/RULES UNDERSTANDING → STRUCTURED DATA →
VALIDATION → (CA REVIEW) → APPROVAL → INVOICE + DRAFT VOUCHER (accounting engine)

Original files are immutable. Extracted data is versioned: version 1 is the machine extraction,
later versions are human corrections; nothing is overwritten.
"""
from __future__ import annotations

import datetime as dt
import secrets
import zipfile
import io
from decimal import Decimal
from pathlib import Path

from config import settings
from services import admin_service, ai_service, invoice_parser, ocr_service
from services.audit_service import audit, log_error
from services.db import IntegrityError, get_db, new_id, now_iso, system_identity
from services.notification_service import notify_client_users, notify_firm
from services.period_service import assert_period_open
from services.storage_service import get_storage
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, month_bounds, normalize_invoice_no, sha256_bytes, to_date
from utils.permissions import PermissionDenied
from utils.validators import (gstin_state, is_interstate, validate_gstin, validate_invoice_date, validate_invoice_no,
                              validate_tax_amounts)

DOC_TYPES = {
    "sales_invoice": "Sales invoices", "purchase_invoice": "Purchase invoices", "expense_bill": "Expense bills",
    "credit_note": "Credit notes", "debit_note": "Debit notes", "bank_statement": "Bank statements",
    "salary_statement": "Salary statements", "payment_receipt": "Payment receipts", "other": "Other documents",
}
INVOICE_TYPES = {"sales_invoice", "purchase_invoice", "expense_bill", "credit_note", "debit_note"}
STATUSES = ["uploaded", "processing", "processed", "needs_review", "approved", "rejected", "finalized", "split"]
MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".csv": "text/csv", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
CRITICAL_FIELDS = ("invoice_no", "invoice_date", "party_gstin", "taxable_value", "total", "cgst", "sgst", "igst")
CONFIDENCE_THRESHOLD = 0.8


class UploadRejected(Exception):
    pass


class DocumentError(Exception):
    pass


# ------------------------------------------------------------------ file validation
def validate_file(filename: str, data: bytes) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in settings.allowed_extensions:
        raise UploadRejected(f"File type {ext or '(none)'} is not allowed. Allowed: {', '.join(settings.allowed_extensions)}")
    if not data:
        raise UploadRejected("File is empty")
    if len(data) > settings.max_upload_bytes:
        raise UploadRejected(f"File exceeds {settings.max_upload_mb} MB limit")
    head = data[:8]
    ok = {
        ".pdf": data[:1024].lstrip().startswith(b"%PDF"),
        ".png": head.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": head.startswith(b"\xff\xd8\xff"),
        ".jpeg": head.startswith(b"\xff\xd8\xff"),
        ".xlsx": head.startswith(b"PK"),
        ".csv": b"\x00" not in data[:4096],
    }[ext]
    if ext == ".xlsx" and ok:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                ok = "[Content_Types].xml" in z.namelist() and not any(n.lower().endswith(".bin") and "vba" in n.lower()
                                                                       for n in z.namelist())
        except zipfile.BadZipFile:
            ok = False
    if ext == ".csv" and ok:
        try:
            data[:65536].decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                data[:65536].decode("latin-1")
            except UnicodeDecodeError:
                ok = False
    if not ok:
        raise UploadRejected("File content does not match its extension (possibly corrupt or disguised file)")
    return ext, MIME[ext]


# ------------------------------------------------------------------ submissions
def get_or_create_submission(ctx: AuthContext, client_id: str, year: int, month: int) -> dict:
    client = require_client(ctx, client_id, "client_upload" if ctx.is_client else "upload_documents")
    db = get_db()
    row = db.fetchone("select * from document_submissions where client_id = ? and period_year = ? and period_month = ? "
                      "and status = 'draft' order by created_at desc", [client_id, year, month])
    if row:
        return row
    from services.firm_service import deadline_for

    sid = db.insert("document_submissions", {"firm_id": client["firm_id"], "client_id": client_id, "period_year": year,
                                             "period_month": month, "status": "draft",
                                             "due_date": deadline_for(client, year, month), "created_at": now_iso()})
    return db.get("document_submissions", sid)


def upload_document(ctx: AuthContext, client_id: str, year: int, month: int, filename: str, data: bytes,
                    doc_type: str, submission_id: str | None = None) -> str:
    perm = "client_upload" if ctx.is_client else "upload_documents"
    client = require_client(ctx, client_id, perm)
    if doc_type not in DOC_TYPES:
        raise UploadRejected("Unknown document type")
    ext, mime = validate_file(filename, data)
    admin_service.check_plan_limit(client["firm_id"], "documents")
    db = get_db()
    digest = sha256_bytes(data)
    dup = db.fetchone("select id, original_filename, uploaded_at, status from documents where client_id = ? and sha256 = ? "
                      "and parent_document_id is null and status <> 'rejected'", [client_id, digest])
    if dup:
        raise UploadRejected(f"This exact file was already uploaded ({dup['original_filename']}, {str(dup['uploaded_at'])[:10]}).")
    if submission_id:
        sub = scoped_get(ctx, "document_submissions", submission_id, perm)
        if sub["client_id"] != client_id:
            raise PermissionDenied("Submission belongs to another client")
    else:
        sub = get_or_create_submission(ctx, client_id, year, month)
    # Store the file first, then write the record once with its final path (client users may insert, not update).
    doc_id = new_id()
    path = f"{client['firm_id']}/{client_id}/{year}/{month:02d}/{doc_id}{ext}"
    get_storage().put(path, data, mime)
    page_count = None
    if ext == ".pdf":
        try:
            page_count = ocr_service.pdf_page_count(data)
        except Exception:
            pass
    db.insert("documents", {
        "id": doc_id, "firm_id": client["firm_id"], "client_id": client_id, "submission_id": sub["id"], "period_year": year,
        "period_month": month, "doc_type": doc_type, "original_filename": Path(filename).name[:200],
        "storage_path": path, "mime_type": mime, "file_ext": ext, "file_size": len(data), "sha256": digest,
        "page_count": page_count, "status": "uploaded", "uploaded_by": ctx.user_id, "uploaded_at": now_iso(),
        "retention_until": dt.date(year + 8, 12, 31),
    })
    audit(ctx, "document.uploaded", "documents", doc_id, firm_id=client["firm_id"], client_id=client_id,
          after={"file": filename, "type": doc_type, "size": len(data)})
    return doc_id


def submit_documents(ctx: AuthContext, submission_id: str, notes: str = "") -> str:
    perm = "client_submit" if ctx.is_client else "upload_documents"
    sub = scoped_get(ctx, "document_submissions", submission_id, perm)
    if sub["status"] != "draft":
        raise DocumentError("This submission was already submitted")
    db = get_db()
    n = db.scalar("select count(*) from documents where submission_id = ?", [submission_id])
    if not n:
        raise DocumentError("Upload at least one document before submitting")
    ref = f"SUB-{sub['period_year']}{sub['period_month']:02d}-{secrets.token_hex(3).upper()}"
    db.update("document_submissions", submission_id, {"status": "submitted", "reference_no": ref, "submitted_by": ctx.user_id,
                                                      "submitted_at": now_iso(), "notes": notes or None})
    client = db.get("clients", sub["client_id"])
    notify_firm(sub["firm_id"], f"Documents submitted: {client['name']}",
                f"{n} document(s) for {sub['period_month']:02d}/{sub['period_year']} — ref {ref}", client_id=sub["client_id"])
    audit(ctx, "submission.submitted", "document_submissions", submission_id, firm_id=sub["firm_id"],
          client_id=sub["client_id"], after={"reference": ref, "documents": n})
    firm = db.get("firms", sub["firm_id"])
    if (firm.get("settings") or {}).get("auto_process_on_submit", True):
        # The client is authorized to submit; extraction itself is a server-side job that writes staff-only tables.
        with system_identity():
            process_submission(ctx, submission_id, _system=True)
    return ref


def list_submissions(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall(
        "select s.*, (select count(*) from documents d where d.submission_id = s.id and d.parent_document_id is null) as doc_count "
        "from document_submissions s where s.client_id = ? order by s.period_year desc, s.period_month desc, s.created_at desc",
        [client_id])


def list_documents(ctx: AuthContext, client_id: str, *, year: int | None = None, month: int | None = None,
                   doc_type: str | None = None, status: str | None = None, include_children: bool = True) -> list[dict]:
    require_client(ctx, client_id, "view")
    sql = "select * from documents where client_id = ?"
    p: list = [client_id]
    for col, val in (("period_year", year), ("period_month", month), ("doc_type", doc_type), ("status", status)):
        if val:
            sql += f" and {col} = ?"
            p.append(val)
    if not include_children:
        sql += " and parent_document_id is null"
    return get_db().fetchall(sql + " order by uploaded_at desc, page_from", p)


def read_document_bytes(ctx: AuthContext, doc_id: str) -> tuple[bytes, dict]:
    """The ONLY way file bytes leave storage: after tenant authorization."""
    doc = scoped_get(ctx, "documents", doc_id, "view")
    data = get_storage().get(doc["storage_path"])
    audit(ctx, "document.downloaded", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"])
    return data, doc


# ------------------------------------------------------------------ processing
def _job(doc: dict, ctx: AuthContext, job_type: str) -> str:
    return get_db().insert("processing_jobs", {"firm_id": doc["firm_id"], "client_id": doc["client_id"], "document_id": doc["id"],
                                               "job_type": job_type, "status": "running", "attempts": 1,
                                               "started_at": now_iso(), "created_by": ctx.user_id, "created_at": now_iso(),
                                               "log": []})


def _finish_job(job_id: str, status: str, log: list, error: str | None = None) -> None:
    get_db().update("processing_jobs", job_id, {"status": status, "log": log, "error": error, "finished_at": now_iso()})


def process_submission(ctx: AuthContext, submission_id: str, _system: bool = False) -> dict:
    sub = scoped_get(ctx, "document_submissions", submission_id, "client_submit" if (_system and ctx.is_client) else "review_documents")
    db = get_db()
    db.update("document_submissions", submission_id, {"status": "processing"})
    docs = db.fetchall("select id from documents where submission_id = ? and status = 'uploaded' and parent_document_id is null",
                       [submission_id])
    results = {"processed": 0, "needs_review": 0, "failed": 0}
    for d in docs:
        status = process_document(ctx, d["id"], _system=_system)
        key = "processed" if status in ("processed", "split") else "needs_review" if status == "needs_review" else "failed"
        results[key] += 1
    db.update("document_submissions", submission_id, {"status": "completed"})
    return results


def _client_party_fields(data: dict, client: dict, declared: str) -> tuple[dict, list[dict], float]:
    """Decide sales/purchase/expense and the counter-party, relative to the client's own GSTIN."""
    issues: list[dict] = []
    cg = (client.get("gstin") or "").upper()
    kind = data.get("doc_kind") or "invoice"
    category = None
    conf = 0.0
    if data.get("party_name") is not None or data.get("party_gstin") is not None:  # register import
        category = {"sales_invoice": "sales", "purchase_invoice": "purchase", "expense_bill": "expense"}.get(declared)
        if declared in ("credit_note", "debit_note"):
            category = data.get("category") or None
        conf = 0.9 if category else 0.0
        party_name, party_gstin = data.get("party_name"), data.get("party_gstin")
    else:
        sup, cus = (data.get("supplier_gstin") or "").upper(), (data.get("customer_gstin") or "").upper()
        if cg and sup == cg:
            category, conf = "sales", 0.95
        elif cg and cus == cg:
            category, conf = ("expense" if declared == "expense_bill" else "purchase"), 0.95
        else:
            category = {"sales_invoice": "sales", "purchase_invoice": "purchase", "expense_bill": "expense"}.get(declared)
            conf = 0.7 if category else 0.0
            if category and cg and cus and category != "sales" and cus != cg:
                issues.append({"field": "customer_gstin", "severity": "error",
                               "message": f"Invoice is addressed to GSTIN {cus}, not the client's GSTIN {cg}"})
            if category == "sales" and cg and sup and sup != cg:
                issues.append({"field": "supplier_gstin", "severity": "error",
                               "message": f"Sales invoice issued by {sup}, not the client's GSTIN {cg}"})
        if category == "sales":
            party_name, party_gstin = data.get("customer_name"), data.get("customer_gstin")
        else:
            party_name, party_gstin = data.get("supplier_name"), data.get("supplier_gstin")
    if category is None:
        issues.append({"field": "category", "severity": "error",
                       "message": "Could not determine whether this is a sales, purchase or expense document"})
    note_type = kind if kind in ("credit_note", "debit_note") else (declared if declared in ("credit_note", "debit_note") else "invoice")
    out = {"category": category, "note_type": note_type, "party_name": party_name, "party_gstin": party_gstin or None}
    return out, issues, conf


def validate_extraction(client: dict, data: dict, conf: dict, year: int, month: int, doc_id: str | None) -> list[dict]:
    issues: list[dict] = []
    db = get_db()
    ok, msg = validate_invoice_no(data.get("invoice_no"))
    if not data.get("invoice_no"):
        issues.append({"field": "invoice_no", "severity": "error", "message": msg})
    elif not ok:
        issues.append({"field": "invoice_no", "severity": "warning", "message": msg})
    start, end = month_bounds(year, month)
    ok, msg = validate_invoice_date(data.get("invoice_date"), start, end)
    if not ok:
        issues.append({"field": "invoice_date", "severity": "error", "message": msg})
    elif msg != "ok":
        issues.append({"field": "invoice_date", "severity": "warning", "message": msg})
    if not data.get("party_name"):
        issues.append({"field": "party_name", "severity": "error", "message": "Party name missing"})
    pg = data.get("party_gstin")
    taxes = D(data.get("cgst")) + D(data.get("sgst")) + D(data.get("igst"))
    if pg:
        ok, msg = validate_gstin(pg)
        if not ok:
            issues.append({"field": "party_gstin", "severity": "error", "message": msg})
    elif data.get("category") in ("purchase", "expense") and taxes > 0:
        issues.append({"field": "party_gstin", "severity": "warning",
                       "message": "Supplier GSTIN missing — ITC cannot be claimed without it"})
    issues += validate_tax_amounts(data)
    # inter/intra-state consistency
    cstate = (client.get("gstin") or "")[:2] or client.get("state_code")
    if data.get("category") == "sales":
        supplier_state = cstate
        pos = data.get("place_of_supply") or gstin_state(pg) or cstate
    else:
        supplier_state = gstin_state(pg)
        pos = data.get("place_of_supply") or cstate
    inter = is_interstate(supplier_state, pos)
    if inter is True and (D(data.get("cgst")) or D(data.get("sgst"))):
        issues.append({"field": "igst", "severity": "error",
                       "message": f"Inter-state supply ({supplier_state}→{pos}) but CGST/SGST charged instead of IGST"})
    if inter is False and D(data.get("igst")):
        issues.append({"field": "cgst", "severity": "error",
                       "message": f"Intra-state supply ({supplier_state}) but IGST charged instead of CGST/SGST"})
    if D(data.get("taxable_value")) > 0 and taxes == 0 and (data.get("supply_type") or "taxable") == "taxable" \
            and not data.get("reverse_charge"):
        issues.append({"field": "supply_type", "severity": "warning",
                       "message": "No GST charged — set supply type (nil/exempt/export/non-GST) or verify"})
    # duplicates
    no = normalize_invoice_no(data.get("invoice_no"))
    if no and data.get("category"):
        for inv in db.fetchall("select id, invoice_no, party_gstin, party_name, invoice_date, document_id from invoices "
                               "where client_id = ? and category = ? and note_type = ? and status <> 'cancelled'",
                               [client["id"], data["category"], data.get("note_type") or "invoice"]):
            same_party = (pg and inv["party_gstin"] == pg) or (not pg and (inv["party_name"] or "").lower() == (data.get("party_name") or "").lower())
            if normalize_invoice_no(inv["invoice_no"]) == no and same_party and inv["document_id"] != doc_id:
                issues.append({"field": "invoice_no", "severity": "error", "duplicate": True,
                               "message": f"Duplicate: invoice {inv['invoice_no']} from this party is already recorded"})
                break
        others = db.fetchall("select e.document_id, e.data from extracted_document_data e join documents d on d.id = e.document_id "
                             "where e.client_id = ? and e.is_current = ? and d.status in ('processed','needs_review','approved') "
                             "and e.document_id <> ?", [client["id"], True, doc_id or ""])
        for o in others:
            od = o["data"] if isinstance(o["data"], dict) else {}
            if normalize_invoice_no(od.get("invoice_no")) == no and (od.get("party_gstin") or od.get("party_name")) == (pg or data.get("party_name")):
                issues.append({"field": "invoice_no", "severity": "warning", "duplicate": True,
                               "message": "Another uploaded document has the same invoice number and party"})
                break
    # confidence
    for f in CRITICAL_FIELDS:
        c = conf.get(f)
        if f == "party_gstin" and not pg:
            continue
        if c is not None and c < CONFIDENCE_THRESHOLD and data.get(f) not in (None, ""):
            issues.append({"field": f, "severity": "warning", "low_confidence": True,
                           "message": f"Low confidence ({c:.0%}) — verify against the original"})
    return issues


def _decide_status(issues: list[dict]) -> str:
    return "needs_review" if issues else "processed"


def _save_extraction(doc: dict, *, source: str, provider: str, raw_text: str, data: dict, conf: dict, issues: list,
                     user_id: str | None) -> None:
    # Two overlapping requests for the same document (e.g. a rerun that overlaps the previous one, or two browser
    # tabs) can both read the same "next version" number before either saves it. Retry on that specific collision
    # instead of letting it surface as a raw database error.
    db = get_db()
    vals = [v for k, v in conf.items() if isinstance(v, (int, float)) and k in CRITICAL_FIELDS and data.get(k) not in (None, "")]
    overall = round(sum(vals) / len(vals) * 100, 2) if vals else 0
    for attempt in range(5):
        version = (db.scalar("select max(version) from extracted_document_data where document_id = ?", [doc["id"]]) or 0) + 1
        try:
            with db.transaction():
                db.execute("update extracted_document_data set is_current = ? where document_id = ?", [False, doc["id"]])
                db.insert("extracted_document_data", {
                    "firm_id": doc["firm_id"], "client_id": doc["client_id"], "document_id": doc["id"], "version": version,
                    "source": source, "provider": provider, "raw_text": (raw_text or "")[:200000], "data": data,
                    "field_confidence": conf, "overall_confidence": Decimal(str(overall)), "validation": {"issues": issues},
                    "is_current": True, "created_by": user_id, "created_at": now_iso(),
                })
            return
        except IntegrityError:
            if attempt == 4:
                raise


def _create_children(ctx: AuthContext, parent: dict, parts: list[dict]) -> list[str]:
    db = get_db()
    ids = []
    for i, p in enumerate(parts, start=1):
        cid = db.insert("documents", {
            "firm_id": parent["firm_id"], "client_id": parent["client_id"], "submission_id": parent["submission_id"],
            "parent_document_id": parent["id"], "period_year": parent["period_year"], "period_month": parent["period_month"],
            "doc_type": parent["doc_type"], "original_filename": f"{parent['original_filename']} [part {i}]",
            "storage_path": parent["storage_path"], "mime_type": parent["mime_type"], "file_ext": parent["file_ext"],
            "file_size": 0, "sha256": f"{parent['sha256']}:{i}", "page_from": p.get("page_from"), "page_to": p.get("page_to"),
            "status": "processing", "uploaded_by": parent["uploaded_by"], "uploaded_at": now_iso(),
            "retention_until": parent.get("retention_until"),
        })
        ids.append(cid)
    db.update("documents", parent["id"], {"status": "split", "error_message": None})
    audit(ctx, "document.split", "documents", parent["id"], firm_id=parent["firm_id"], client_id=parent["client_id"],
          after={"parts": len(parts)})
    return ids


def _finalize_invoice_part(ctx, doc, client, part, provider_name, source, raw_text, declared) -> str:
    data, conf = dict(part["data"]), dict(part["confidence"])
    party, party_issues, cat_conf = _client_party_fields(data, client, declared)
    data.update(party)
    conf["category"] = cat_conf
    if "party_gstin" not in conf:
        conf["party_gstin"] = conf.get("customer_gstin" if party["category"] == "sales" else "supplier_gstin", 0.0)
    conf["party_name"] = conf.get("party_name", conf.get("customer_name" if party["category"] == "sales" else "supplier_name", 0.0))
    data.setdefault("supply_type", "taxable")
    if party["category"] == "expense":
        from services.accounting_engine import classify_expense_head

        head, confident = classify_expense_head(f"{data.get('party_name') or ''} " +
                                                " ".join(i.get("description") or "" for i in data.get("items", [])))
        data["expense_head"] = head
        conf["expense_head"] = 0.85 if confident else 0.3
    issues = party_issues + validate_extraction(client, data, conf, doc["period_year"], doc["period_month"], doc["id"])
    if part.get("notes"):
        issues.append({"field": "notes", "severity": "warning", "message": f"Reader note: {part['notes']}"})
    _save_extraction(doc, source=source, provider=provider_name, raw_text=raw_text, data=data, conf=conf, issues=issues,
                     user_id=ctx.user_id)
    status = _decide_status(issues)
    get_db().update("documents", doc["id"], {"status": status, "classification_confidence": Decimal(str(round(cat_conf * 100, 2))),
                                             "review_flags": [i["message"] for i in issues][:30], "error_message": None})
    return status


def process_document(ctx: AuthContext, doc_id: str, _system: bool = False) -> str:
    """Run the extraction pipeline. Returns the resulting document status."""
    perm = "client_submit" if (_system and ctx.is_client) else "review_documents"
    doc = scoped_get(ctx, "documents", doc_id, perm)
    if doc["status"] in ("approved", "finalized", "split"):
        raise DocumentError(f"Document is {doc['status']}; it cannot be reprocessed")
    if doc.get("parent_document_id") and doc["file_ext"] in (".csv", ".xlsx"):
        raise DocumentError("Rows imported from a spreadsheet cannot be re-extracted; correct values in the review form.")
    client = get_db().get("clients", doc["client_id"])
    db = get_db()
    db.update("documents", doc_id, {"status": "processing"})
    job = _job(doc, ctx, "extract")
    log: list[str] = []
    try:
        data = get_storage().get(doc["storage_path"])
        ext, mime, declared = doc["file_ext"], doc["mime_type"], doc["doc_type"]
        if doc.get("page_from") and ext == ".pdf":
            data = ocr_service.pdf_subset(data, doc["page_from"], doc["page_to"])
        hints = {"client_gstin": client.get("gstin"), "declared_type": declared}

        # ---------- bank statements ----------
        if declared == "bank_statement":
            from services import bank_service

            parsed = bank_service.parse_statement_file(data, ext)
            log.append(f"bank statement parsed: {len(parsed['transactions'])} rows")
            issues = [{"field": "transactions", "severity": "warning" if parsed["transactions"] else "error", "message": m}
                      for m in parsed["warnings"]]
            if not parsed["transactions"]:
                issues.append({"field": "transactions", "severity": "error", "message": "No transactions could be read"})
            _save_extraction(doc, source="import" if ext in (".csv", ".xlsx") else "ocr", provider="bank_parser",
                             raw_text=parsed.get("raw_text", ""), data={"doc_kind": "bank_statement", **parsed},
                             conf={}, issues=issues, user_id=ctx.user_id)
            status = "needs_review" if issues else "processed"
            db.update("documents", doc_id, {"status": status, "review_flags": [i["message"] for i in issues][:30]})
            _finish_job(job, "succeeded", log)
            return status

        # ---------- spreadsheets: invoice registers ----------
        if ext in (".csv", ".xlsx"):
            df = ocr_service.read_table(data, ext)
            if invoice_parser.looks_like_bank_table(list(df.columns)):
                db.update("documents", doc_id, {"doc_type": "bank_statement", "status": "uploaded"})
                _finish_job(job, "succeeded", ["re-classified as bank statement"])
                return process_document(ctx, doc_id, _system)
            rows = invoice_parser.parse_register_rows(df)
            log.append(f"register rows: {len(rows)}")
            if not rows:
                msg = "Spreadsheet columns not recognised as an invoice register (need invoice no, date, party, amounts)"
                _save_extraction(doc, source="import", provider="register", raw_text=df.head(50).to_csv(index=False),
                                 data={"doc_kind": "other"}, conf={}, issues=[{"field": "file", "severity": "error", "message": msg}],
                                 user_id=ctx.user_id)
                db.update("documents", doc_id, {"status": "needs_review", "review_flags": [msg]})
                _finish_job(job, "succeeded", log)
                return "needs_review"
            for r in rows:
                r["page_from"] = r["page_to"] = None
            if len(rows) == 1:
                status = _finalize_invoice_part(ctx, doc, client, rows[0], "register", "import", "", declared)
            else:
                child_ids = _create_children(ctx, doc, rows)
                for cid, r in zip(child_ids, rows):
                    _finalize_invoice_part(ctx, db.get("documents", cid), client, r, "register", "import", "", declared)
                status = "split"
            _finish_job(job, "succeeded", log)
            return status

        # ---------- PDFs and images ----------
        if ext == ".pdf":
            tr = ocr_service.extract_pdf(data)
        else:
            tr = ocr_service.extract_image(data)
        log += tr.errors
        pages_text = [p.text for p in tr.pages]
        unreadable = tr.unreadable_pages
        provider = ai_service.get_provider()
        source = "ai" if provider.is_ai else ("ocr" if any(p.source == "tesseract" for p in tr.pages) else "rules")
        parts = None
        if provider.is_ai:
            try:
                parts = provider.extract_documents(data, mime, tr.text, {**hints, "pages_text": pages_text})
                log.append(f"AI extraction ({provider.name}): {len(parts)} document(s)")
            except Exception as exc:
                log_error("ai.extract", exc, context={"document_id": doc_id}, firm_id=doc["firm_id"])
                log.append(f"AI extraction failed, using local rules: {exc}")
                provider, source = ai_service.fallback_provider(), "rules"
        if parts is None:
            if unreadable and len(unreadable) == len(tr.pages):
                msg = ("Scanned image/PDF could not be read: no OCR engine or AI provider configured. "
                       "Enter the values manually from the original, or configure Tesseract / ANTHROPIC_API_KEY.")
                if tr.errors and "No OCR engine" not in tr.errors[0]:
                    msg = "; ".join(tr.errors)
                _save_extraction(doc, source="ocr", provider="none", raw_text="", data={"doc_kind": "invoice", "items": []},
                                 conf={}, issues=[{"field": "file", "severity": "error", "message": msg}], user_id=ctx.user_id)
                db.update("documents", doc_id, {"status": "needs_review", "review_flags": [msg], "error_message": msg})
                _finish_job(job, "succeeded", log + [msg])
                return "needs_review"
            parts = provider.extract_documents(data, mime, tr.text, {**hints, "pages_text": pages_text,
                                                                     "allow_split": declared in INVOICE_TYPES})
        if declared not in INVOICE_TYPES:
            kind, c = invoice_parser.classify_text(tr.text, doc["original_filename"], declared)
            if kind in ("invoice", "credit_note", "debit_note") and parts and parts[0]["data"].get("invoice_no"):
                declared = "purchase_invoice"  # classified as an invoice although uploaded as 'other'
                db.update("documents", doc_id, {"doc_type": "credit_note" if kind == "credit_note" else declared})
            else:
                issues = [{"field": "doc_type", "severity": "warning",
                           "message": f"Classified as '{kind}' ({c:.0%}). Record manually via Accounting if required."}]
                _save_extraction(doc, source=source, provider=provider.name, raw_text=tr.text, data={"doc_kind": kind},
                                 conf={}, issues=issues, user_id=ctx.user_id)
                db.update("documents", doc_id, {"status": "needs_review", "review_flags": [issues[0]["message"]]})
                _finish_job(job, "succeeded", log)
                return "needs_review"
        if unreadable:
            for p in parts:
                p.setdefault("notes", "")
                p["notes"] = (p["notes"] + f" Pages {unreadable} had no readable text.").strip()
        if len(parts) > 1 and not doc.get("parent_document_id"):
            child_ids = _create_children(ctx, doc, parts)
            for cid, part in zip(child_ids, parts):
                raw = "\n".join(pages_text[(part["page_from"] or 1) - 1:(part["page_to"] or len(pages_text))])
                _finalize_invoice_part(ctx, db.get("documents", cid), client, part, provider.name, source, raw, declared)
            log.append(f"split into {len(parts)} documents")
            status = "split"
        else:
            status = _finalize_invoice_part(ctx, doc, client, parts[0], provider.name, source, tr.text, declared)
        _finish_job(job, "succeeded", log)
        audit(ctx, "document.processed", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"],
              after={"status": status, "provider": provider.name})
        return status
    except Exception as exc:
        log_error("document.process", exc, context={"document_id": doc_id}, firm_id=doc["firm_id"], user_id=ctx.user_id)
        db.update("documents", doc_id, {"status": "needs_review", "error_message": f"Processing error: {exc}"[:500],
                                        "review_flags": [f"Processing error: {exc}"[:300]]})
        _finish_job(job, "failed", log, str(exc)[:1000])
        return "needs_review"


# ------------------------------------------------------------------ review
def current_extraction(ctx: AuthContext, doc_id: str) -> dict | None:
    scoped_get(ctx, "documents", doc_id, "view")
    return get_db().fetchone("select * from extracted_document_data where document_id = ? and is_current = ?", [doc_id, True])


def bulk_current_extractions(ctx: AuthContext, client_id: str, document_ids: list[str]) -> dict[str, dict]:
    """The current extraction for many documents in ONE query, instead of one query per document — needed so a
    review-queue summary over dozens of documents doesn't cost a network round trip per document."""
    require_client(ctx, client_id, "view")
    if not document_ids:
        return {}
    db = get_db()
    marks = ",".join("?" for _ in document_ids)
    rows = db.fetchall(
        f"select document_id, data, validation, overall_confidence from extracted_document_data "
        f"where client_id = ? and document_id in ({marks}) and is_current = ?", [client_id, *document_ids, True])
    return {r["document_id"]: r for r in rows}


def extraction_history(ctx: AuthContext, doc_id: str) -> list[dict]:
    scoped_get(ctx, "documents", doc_id, "review_documents")
    return get_db().fetchall("select * from extracted_document_data where document_id = ? order by version", [doc_id])


def save_correction(ctx: AuthContext, doc_id: str, corrected: dict) -> str:
    """Store a human-corrected version (original extraction is preserved) and re-validate."""
    doc = scoped_get(ctx, "documents", doc_id, "review_documents")
    if doc["status"] in ("approved", "finalized"):
        raise DocumentError("Approved documents cannot be edited")
    assert_period_open(doc["client_id"], dt.date(doc["period_year"], doc["period_month"], 1))
    client = get_db().get("clients", doc["client_id"])
    cur = current_extraction(ctx, doc_id)
    base = dict(cur["data"]) if cur else {}
    old_conf = dict(cur["field_confidence"]) if cur else {}
    changed = {k: v for k, v in corrected.items() if base.get(k) != v}
    data = {**base, **corrected}
    for k in ("taxable_value", "cgst", "sgst", "igst", "cess", "discount", "round_off", "total"):
        if data.get(k) not in (None, ""):
            data[k] = str(D(data[k]))
    # Human-entered or human-confirmed values carry full confidence
    conf = {**old_conf, **{k: 1.0 for k in corrected}}
    issues = validate_extraction(client, data, conf, doc["period_year"], doc["period_month"], doc_id)
    if not data.get("category"):
        issues.append({"field": "category", "severity": "error", "message": "Select sales / purchase / expense"})
    _save_extraction(doc, source="manual", provider="user", raw_text=cur["raw_text"] if cur else "", data=data, conf=conf,
                     issues=issues, user_id=ctx.user_id)
    get_db().update("documents", doc_id, {"status": _decide_status(issues), "review_flags": [i["message"] for i in issues][:30],
                                          "error_message": None})
    audit(ctx, "document.corrected", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"],
          before={k: base.get(k) for k in changed}, after=changed)
    return _decide_status(issues)


def approve_document(ctx: AuthContext, doc_id: str, *, acknowledge_warnings: bool = False) -> dict:
    """Approve: create the invoice record and its draft voucher. Errors always block; warnings need acknowledgement."""
    from services import accounting_engine

    doc = scoped_get(ctx, "documents", doc_id, "approve_documents")
    if doc["status"] not in ("processed", "needs_review"):
        raise DocumentError(f"Document in status '{doc['status']}' cannot be approved")
    assert_period_open(doc["client_id"], dt.date(doc["period_year"], doc["period_month"], 1))
    ext = current_extraction(ctx, doc_id)
    if not ext:
        raise DocumentError("Document has no extracted data yet — process it first")
    data = ext["data"]
    issues = (ext.get("validation") or {}).get("issues", [])
    errors = [i for i in issues if i["severity"] == "error"]
    if errors:
        raise DocumentError("Resolve errors before approval: " + "; ".join(e["message"] for e in errors))
    warnings = [i for i in issues if i["severity"] == "warning"]
    if warnings and not acknowledge_warnings:
        raise DocumentError("Review and acknowledge warnings: " + "; ".join(w["message"] for w in warnings))
    db = get_db()
    result: dict = {"invoice_id": None, "voucher_id": None}
    kind = data.get("doc_kind")
    if kind == "bank_statement" or doc["doc_type"] == "bank_statement":
        raise DocumentError("Bank statements are imported from the Bank Reconciliation page (choose the bank account).")
    if kind not in ("invoice", "credit_note", "debit_note") or not data.get("category"):
        db.update("documents", doc_id, {"status": "approved", "reviewed_by": ctx.user_id, "reviewed_at": now_iso()})
        audit(ctx, "document.approved", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"],
              after={"note": "non-invoice document; no voucher generated"})
        return result
    client = db.get("clients", doc["client_id"])
    pg = data.get("party_gstin")
    party_state = gstin_state(pg)
    pos = data.get("place_of_supply") or (party_state if data["category"] == "sales" else None) or client.get("state_code")
    itc = "not_applicable" if data["category"] == "sales" else data.get("itc_eligibility") or ("pending" if pg else "ineligible")
    tds_fields = {"tds_status": "not_applicable", "tds_section": None, "tds_rate": ZERO}
    if data["category"] in ("purchase", "expense"):
        from services import tds_service
        from utils.helpers import fy_label_for

        inv_date = to_date(data["invoice_date"])
        fy_label = fy_label_for(inv_date, client.get("fy_start_month") or 4)
        prior = tds_service.vendor_payments_this_fy(doc["client_id"], pg, data.get("party_name") or "", fy_label, inv_date)
        suggestion = tds_service.suggest_tds_for_invoice(client, data, prior)
        tds_fields = {"tds_status": suggestion["tds_status"], "tds_section": suggestion["tds_section"],
                     "tds_rate": D(suggestion["tds_rate"])}
    with db.transaction():
        inv_id = db.insert("invoices", {
            "firm_id": doc["firm_id"], "client_id": doc["client_id"], "document_id": doc_id, "category": data["category"],
            "note_type": data.get("note_type") or "invoice", "invoice_no": str(data["invoice_no"]).strip(),
            "invoice_date": to_date(data["invoice_date"]), "party_name": data.get("party_name") or "Unknown",
            "party_gstin": pg, "party_state_code": party_state, "place_of_supply": pos,
            "supply_type": data.get("supply_type") or "taxable", "reverse_charge": bool(data.get("reverse_charge")),
            "original_invoice_no": data.get("original_invoice_no"),
            "taxable_value": D(data.get("taxable_value")), "cgst": D(data.get("cgst")), "sgst": D(data.get("sgst")),
            "igst": D(data.get("igst")), "cess": D(data.get("cess")), "discount": D(data.get("discount")),
            "round_off": D(data.get("round_off")), "total": D(data.get("total")), "expense_head": data.get("expense_head"),
            "itc_eligibility": itc, "itc_reason": None if pg or data["category"] == "sales" else "Supplier GSTIN missing",
            "status": "approved", "created_by": ctx.user_id, "approved_by": ctx.user_id, "approved_at": now_iso(),
            "created_at": now_iso(), **tds_fields,
        })
        for n, item in enumerate(data.get("items") or [], start=1):
            db.insert("invoice_items", {"firm_id": doc["firm_id"], "client_id": doc["client_id"], "invoice_id": inv_id,
                                        "line_no": n, "description": item.get("description"), "hsn_sac": item.get("hsn_sac"),
                                        "quantity": D(item.get("quantity"), None), "unit_price": D(item.get("unit_price"), None),
                                        "taxable_value": D(item.get("taxable_value")), "gst_rate": D(item.get("gst_rate"))})
        db.update("documents", doc_id, {"status": "approved", "reviewed_by": ctx.user_id, "reviewed_at": now_iso()})
        audit(ctx, "document.approved", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"],
              after={"invoice_id": inv_id, "warnings_acknowledged": [w["message"] for w in warnings]})
        result["invoice_id"] = inv_id
        if ctx.can("prepare_vouchers"):
            result["voucher_id"] = accounting_engine.post_invoice(ctx, inv_id)
    return result


def reject_document(ctx: AuthContext, doc_id: str, reason: str) -> None:
    doc = scoped_get(ctx, "documents", doc_id, "approve_documents")
    if doc["status"] in ("approved", "finalized"):
        raise DocumentError("Approved documents cannot be rejected")
    if not reason.strip():
        raise DocumentError("Give a reason for rejection")
    get_db().update("documents", doc_id, {"status": "rejected", "error_message": reason, "reviewed_by": ctx.user_id,
                                          "reviewed_at": now_iso()})
    audit(ctx, "document.rejected", "documents", doc_id, firm_id=doc["firm_id"], client_id=doc["client_id"],
          after={"reason": reason})
    notify_client_users(doc["client_id"], "A document was rejected", f"{doc['original_filename']}: {reason}")


def add_note(ctx: AuthContext, doc_id: str, note: str) -> None:
    doc = scoped_get(ctx, "documents", doc_id, "review_documents")
    get_db().insert("document_notes", {"firm_id": doc["firm_id"], "client_id": doc["client_id"], "document_id": doc_id,
                                       "user_id": ctx.user_id, "note": note.strip(), "created_at": now_iso()})


def list_notes(ctx: AuthContext, doc_id: str) -> list[dict]:
    scoped_get(ctx, "documents", doc_id, "review_documents")
    return get_db().fetchall("select n.*, u.full_name from document_notes n left join user_profiles u on u.id = n.user_id "
                             "where n.document_id = ? order by n.created_at", [doc_id])


# ------------------------------------------------------------------ clarifications
def raise_clarification(ctx: AuthContext, client_id: str, question: str, doc_id: str | None = None) -> str:
    client = require_client(ctx, client_id, "review_documents")
    if doc_id:
        d = scoped_get(ctx, "documents", doc_id, "review_documents")
        if d["client_id"] != client_id:
            raise PermissionDenied("Document belongs to another client")
    cid = get_db().insert("clarification_requests", {"firm_id": client["firm_id"], "client_id": client_id, "document_id": doc_id,
                                                     "raised_by": ctx.user_id, "question": question.strip(),
                                                     "created_at": now_iso()})
    notify_client_users(client_id, "Your CA has a question", question.strip()[:200])
    audit(ctx, "clarification.raised", "clarification_requests", cid, client_id=client_id)
    return cid


def respond_clarification(ctx: AuthContext, clarification_id: str, response: str) -> None:
    c = scoped_get(ctx, "clarification_requests", clarification_id, "client_respond" if ctx.is_client else "review_documents")
    if c["status"] == "closed":
        raise DocumentError("This clarification is closed")
    get_db().update("clarification_requests", clarification_id, {"response": response.strip(), "status": "answered",
                                                                 "responded_by": ctx.user_id, "responded_at": now_iso()})
    if ctx.is_client and c.get("raised_by"):
        from services.notification_service import notify_user

        notify_user(c["raised_by"], "Client answered your clarification", response.strip()[:200], firm_id=c["firm_id"],
                    client_id=c["client_id"])
    audit(ctx, "clarification.answered", "clarification_requests", clarification_id, firm_id=c["firm_id"],
          client_id=c["client_id"])


def close_clarification(ctx: AuthContext, clarification_id: str) -> None:
    c = scoped_get(ctx, "clarification_requests", clarification_id, "review_documents")
    get_db().update("clarification_requests", clarification_id, {"status": "closed"})
    audit(ctx, "clarification.closed", "clarification_requests", clarification_id, client_id=c["client_id"])


def list_clarifications(ctx: AuthContext, client_id: str, status: str | None = None) -> list[dict]:
    require_client(ctx, client_id, "view")
    sql = ("select c.*, d.original_filename from clarification_requests c left join documents d on d.id = c.document_id "
           "where c.client_id = ?")
    p: list = [client_id]
    if status:
        sql += " and c.status = ?"
        p.append(status)
    return get_db().fetchall(sql + " order by c.created_at desc", p)


def processing_history(ctx: AuthContext, doc_id: str) -> list[dict]:
    scoped_get(ctx, "documents", doc_id, "view")
    return get_db().fetchall("select * from processing_jobs where document_id = ? order by created_at", [doc_id])


ZERO_D = ZERO
