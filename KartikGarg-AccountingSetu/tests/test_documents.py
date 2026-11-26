import datetime as dt

import pytest

from services import ai_service, document_service as ds, ocr_service
from services.db import get_db
from tests.conftest import CLIENT_A1_GSTIN, CUSTOMER_MH, SUPPLIER_KA, SUPPLIER_MH, invoice_text, make_pdf, make_png, purchase

TODAY = dt.date.today()
Y, M = TODAY.year, TODAY.month


def _upload(env, data, name="inv.pdf", dtype="purchase_invoice", ctx=None):
    return ds.upload_document(ctx or env.cu_a1, env.c_a1, Y, M, name, data, dtype)


def _current(env, doc_id):
    return ds.current_extraction(env.a_admin, doc_id)


def test_file_validation_rejects_bad_files(env):
    with pytest.raises(ds.UploadRejected, match="not allowed"):
        _upload(env, b"MZ....", "virus.exe")
    with pytest.raises(ds.UploadRejected, match="does not match"):
        _upload(env, b"not a pdf at all", "fake.pdf")
    with pytest.raises(ds.UploadRejected, match="empty"):
        _upload(env, b"", "empty.pdf")


def test_digital_pdf_extraction(env):
    doc_id = _upload(env, make_pdf([purchase("PI-2001", 10000)]))
    status = ds.process_document(env.a_admin, doc_id)
    ext = _current(env, doc_id)
    d = ext["data"]
    assert d["invoice_no"] == "PI-2001"
    assert d["category"] == "purchase" and d["party_gstin"] == SUPPLIER_MH
    assert d["taxable_value"] == "10000.00" and d["cgst"] == "900.00" and d["sgst"] == "900.00" and d["total"] == "11800.00"
    assert ext["field_confidence"]["total"] >= 0.9
    assert status in ("processed", "needs_review")
    errors = [i for i in ext["validation"]["issues"] if i["severity"] == "error"]
    assert not errors, errors


def test_sales_direction_detected_from_client_gstin(env):
    inv = {"invoice_no": "SI-01", "date": TODAY.replace(day=1).strftime("%d/%m/%Y"), "supplier_gstin": CLIENT_A1_GSTIN,
           "customer_gstin": CUSTOMER_MH, "supplier_name": "Client A1 Traders", "customer_name": "Mehta Retail",
           "taxable": 5000.0, "cgst": 450.0, "sgst": 450.0, "total": 5900.0}
    doc_id = _upload(env, make_pdf([inv]), dtype="sales_invoice")
    ds.process_document(env.a_admin, doc_id)
    d = _current(env, doc_id)["data"]
    assert d["category"] == "sales" and d["party_gstin"] == CUSTOMER_MH


def test_multiple_invoices_in_one_pdf_are_split(env):
    pdf = make_pdf([purchase("PI-3001", 1000), purchase("PI-3002", 2000), purchase("PI-3003", 3000)])
    doc_id = _upload(env, pdf)
    assert ds.process_document(env.a_admin, doc_id) == "split"
    children = get_db().fetchall("select * from documents where parent_document_id = ? order by page_from", [doc_id])
    assert len(children) == 3
    nos = [ds.current_extraction(env.a_admin, c["id"])["data"]["invoice_no"] for c in children]
    assert nos == ["PI-3001", "PI-3002", "PI-3003"]
    assert [c["page_from"] for c in children] == [1, 2, 3]


def test_scanned_pdf_without_ocr_goes_to_review(env):
    doc_id = _upload(env, make_pdf([], blank_pages=1), name="scan.pdf")
    assert ds.process_document(env.a_admin, doc_id) == "needs_review"
    doc = get_db().get("documents", doc_id)
    assert "could not be read" in doc["error_message"]


class FakeOCR(ocr_service.OCRProvider):
    name = "tesseract"

    def available(self):
        return True

    def image_to_text(self, image_bytes):
        return "\n".join(invoice_text(purchase("IMG-77", 4000)))


def test_image_ocr_and_scanned_pdf_with_ocr_engine(env):
    ocr_service.set_ocr(FakeOCR())
    doc_id = _upload(env, make_png(), name="photo.png")
    ds.process_document(env.a_admin, doc_id)
    d = _current(env, doc_id)["data"]
    assert d["invoice_no"] == "IMG-77" and d["total"] == "4720.00"
    assert _current(env, doc_id)["source"] == "ocr"
    doc2 = _upload(env, make_pdf([], blank_pages=1), name="scan2.pdf")
    ds.process_document(env.a_admin, doc2)
    assert _current(env, doc2)["data"]["invoice_no"] == "IMG-77"


def test_duplicate_file_rejected(env):
    pdf = make_pdf([purchase("PI-4001")])
    _upload(env, pdf)
    with pytest.raises(ds.UploadRejected, match="already uploaded"):
        _upload(env, pdf, name="again.pdf")


def test_duplicate_invoice_detection(env):
    d1 = _upload(env, make_pdf([purchase("PI-5001", 1000)]))
    ds.process_document(env.a_admin, d1)
    ds.save_correction(env.a_admin, d1, {"itc_eligibility": "eligible"})
    ds.approve_document(env.a_admin, d1, acknowledge_warnings=True)
    d2 = _upload(env, make_pdf([dict(purchase("PI-5001", 1000), item="Different scan")]), name="dup.pdf")
    ds.process_document(env.a_admin, d2)
    issues = _current(env, d2)["validation"]["issues"]
    assert any(i.get("duplicate") and i["severity"] == "error" for i in issues)
    with pytest.raises(ds.DocumentError, match="Duplicate"):
        ds.approve_document(env.a_admin, d2, acknowledge_warnings=True)


def test_missing_fields_flagged(env):
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, ln in enumerate(["Some Vendor", "TAX INVOICE", "Thanks for your business", "Total amount payable soon",
                            "This page intentionally has no numbers"]):
        c.drawString(50, 800 - 18 * i, ln)
    c.save()
    doc_id = _upload(env, buf.getvalue())
    assert ds.process_document(env.a_admin, doc_id) == "needs_review"
    fields = {i["field"] for i in _current(env, doc_id)["validation"]["issues"] if i["severity"] == "error"}
    assert {"invoice_no", "invoice_date"} <= fields


def test_low_confidence_fields_flagged_and_not_guessed(env):
    class LowConf(ai_service.AIProvider):
        name, is_ai = "fake-ai", True

        def extract_documents(self, file_bytes, mime, text, hints):
            return [{"page_from": 1, "page_to": 1, "notes": "stamp over total",
                     "data": {"doc_kind": "invoice", "supplier_name": "X", "supplier_gstin": SUPPLIER_MH, "customer_gstin": CLIENT_A1_GSTIN,
                              "invoice_no": "LC-1", "invoice_date": TODAY.replace(day=1).isoformat(), "taxable_value": "1000.00",
                              "cgst": "90.00", "sgst": "90.00", "igst": None, "cess": None, "total": None, "items": []},
                     "confidence": {"invoice_no": 0.95, "invoice_date": 0.95, "taxable_value": 0.55, "cgst": 0.9, "sgst": 0.9,
                                    "total": 0.0, "supplier_gstin": 0.95}}]

    ai_service.set_provider(LowConf())
    doc_id = _upload(env, make_pdf([purchase("LC-1")]))
    assert ds.process_document(env.a_admin, doc_id) == "needs_review"
    ext = _current(env, doc_id)
    assert ext["data"]["total"] is None  # never guessed
    msgs = " ".join(i["message"] for i in ext["validation"]["issues"])
    assert "Low confidence" in msgs and "total missing" in msgs.lower()


def test_ai_failure_falls_back_to_rules(env):
    class Broken(ai_service.AIProvider):
        name, is_ai = "broken", True

        def extract_documents(self, *a, **k):
            raise RuntimeError("network down")

    ai_service.set_provider(Broken())
    doc_id = _upload(env, make_pdf([purchase("FB-1")]))
    ds.process_document(env.a_admin, doc_id)
    ext = _current(env, doc_id)
    assert ext["data"]["invoice_no"] == "FB-1" and ext["provider"] == "rules"
    assert get_db().scalar("select count(*) from system_logs where source = 'ai.extract'") == 1


def test_interstate_tax_mismatch_is_error(env):
    inv = purchase("PI-6001", 1000, supplier=SUPPLIER_KA)  # KA supplier charging CGST/SGST to MH client
    doc_id = _upload(env, make_pdf([inv]))
    ds.process_document(env.a_admin, doc_id)
    assert any("Inter-state" in i["message"] for i in _current(env, doc_id)["validation"]["issues"])


def test_correction_keeps_original_and_approval_creates_voucher(env):
    doc_id = _upload(env, make_pdf([purchase("PI-7001", 2000)]))
    ds.process_document(env.a_admin, doc_id)
    ds.save_correction(env.a_admin, doc_id, {"supplier_name": "Sharma Steel Suppliers", "party_name": "Sharma Steel Suppliers",
                                             "itc_eligibility": "eligible"})
    hist = ds.extraction_history(env.a_admin, doc_id)
    assert [h["source"] for h in hist] == ["rules", "manual"]
    assert hist[0]["data"]["party_name"] != hist[1]["data"]["party_name"]
    res = ds.approve_document(env.a_admin, doc_id, acknowledge_warnings=True)
    assert res["invoice_id"] and res["voucher_id"]
    assert get_db().get("documents", doc_id)["status"] == "approved"


def test_client_submission_workflow(env):
    doc_id = _upload(env, make_pdf([purchase("PI-8001")]))
    sub = get_db().get("documents", doc_id)["submission_id"]
    ref = ds.submit_documents(env.cu_a1, sub)
    s = get_db().get("document_submissions", sub)
    assert ref.startswith("SUB-") and s["status"] == "completed" and s["submitted_at"]
    assert get_db().get("documents", doc_id)["status"] in ("processed", "needs_review")
    notes = get_db().fetchall("select * from notifications where firm_id = ?", [env.firm_a])
    assert any("Documents submitted" in n["title"] for n in notes)
    with pytest.raises(ds.DocumentError):
        ds.submit_documents(env.cu_a1, sub)


def test_clarification_round_trip(env):
    cid = ds.raise_clarification(env.a_admin, env.c_a1, "Please send the March rent agreement")
    ds.respond_clarification(env.cu_a1, cid, "Uploaded today")
    assert ds.list_clarifications(env.cu_a1, env.c_a1)[0]["status"] == "answered"
    from utils.permissions import NotFound

    with pytest.raises(NotFound):
        ds.respond_clarification(env.cu_a2, cid, "not mine")


def test_register_spreadsheet_import(env):
    csv = ("Invoice No,Invoice Date,Party Name,GSTIN,Taxable Value,CGST,SGST,IGST,Invoice Value\n"
           f"S-1,{TODAY.replace(day=1):%d/%m/%Y},Mehta Retail,{CUSTOMER_MH},1000,90,90,0,1180\n"
           f"S-2,{TODAY.replace(day=1):%d/%m/%Y},Walk-in,,500,45,45,0,590\n").encode()
    doc_id = _upload(env, csv, name="sales.csv", dtype="sales_invoice")
    assert ds.process_document(env.a_admin, doc_id) == "split"
    kids = get_db().fetchall("select id from documents where parent_document_id = ?", [doc_id])
    assert len(kids) == 2
    d = ds.current_extraction(env.a_admin, kids[0]["id"])["data"]
    assert d["category"] == "sales" and d["total"] in ("1180.00", "590.00")
