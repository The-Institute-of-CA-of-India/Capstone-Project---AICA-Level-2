"""Helpers to create approved invoices directly (bypassing OCR) for accounting/GST/bank tests."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from services import accounting_engine as ae
from services.db import get_db, now_iso
from utils.helpers import D


def add_invoice(env, client_id, *, category="purchase", no="X-1", date=None, party="Sharma Steel", gstin=None, taxable="10000",
                cgst="900", sgst="900", igst="0", cess="0", total=None, note_type="invoice", supply_type="taxable", rcm=False,
                itc="eligible", pos=None, items=None, post=True, approve=True, ctx=None, expense_head=None):
    from services import tds_service as _tds
    from utils.helpers import fy_label_for as _fy_label_for

    ctx = ctx or env.a_admin
    client = get_db().get("clients", client_id)
    date = date or dt.date.today().replace(day=1)
    total = total if total is not None else str(D(taxable) + D(cgst) + D(sgst) + D(igst) + D(cess))
    tds_fields = {"tds_status": "not_applicable", "tds_section": None, "tds_rate": D(0)}
    if category in ("purchase", "expense"):
        fy_label = _fy_label_for(date, client.get("fy_start_month") or 4)
        prior = _tds.vendor_payments_this_fy(client_id, gstin, party, fy_label, date)
        data = {"category": category, "party_name": party, "expense_head": expense_head, "taxable_value": taxable}
        sugg = _tds.suggest_tds_for_invoice(client, data, prior)
        tds_fields = {"tds_status": sugg["tds_status"], "tds_section": sugg["tds_section"], "tds_rate": D(sugg["tds_rate"])}
    inv_id = get_db().insert("invoices", {
        "firm_id": client["firm_id"], "client_id": client_id, "category": category, "note_type": note_type, "invoice_no": no,
        "invoice_date": date, "party_name": party, "party_gstin": gstin, "party_state_code": gstin[:2] if gstin else None,
        "place_of_supply": pos, "supply_type": supply_type, "reverse_charge": rcm, "taxable_value": D(taxable), "cgst": D(cgst),
        "sgst": D(sgst), "igst": D(igst), "cess": D(cess), "total": D(total), "discount": D(0), "round_off": D(0),
        "itc_eligibility": "not_applicable" if category == "sales" else itc, "status": "approved", "expense_head": expense_head,
        "created_at": now_iso(), **tds_fields})
    for n, it in enumerate(items or [], 1):
        get_db().insert("invoice_items", {"firm_id": client["firm_id"], "client_id": client_id, "invoice_id": inv_id, "line_no": n,
                                          "description": it.get("description"), "hsn_sac": it.get("hsn"), "quantity": D(it.get("qty", 1)),
                                          "taxable_value": D(it["taxable"]), "gst_rate": D(it["rate"])})
    vid = None
    if post:
        vid = ae.post_invoice(ctx, inv_id)
        if approve:
            ae.approve_voucher(ctx, vid, acknowledge_review=True)
    return inv_id, vid


def lines_by_ledger(voucher_id):
    out = {}
    for ln in ae.get_voucher_lines(voucher_id):
        out[ln["ledger_name"]] = (ln["dr_cr"], D(ln["amount"]))
    return out


Decimal = Decimal
