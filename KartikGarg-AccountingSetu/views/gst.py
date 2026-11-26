"""GST: GSTR-1 & GSTR-3B preparation, GSTR-2B reconciliation, ITC decisions, approval workflow."""
from __future__ import annotations

import json

import streamlit as st

from services import gst_service as gs, report_service
from services.db import get_db
from ui.common import action, badge, ctx, page_header, require_client_selected, rupees, selected_period, table
from utils.helpers import D, month_bounds

DISCLAIMER = ("Return-PREPARATION data from approved records. Accounting Setu does not file returns. Verify against the current "
              "GSTN offline-tool schema and file on the GST portal; record the ARN here afterwards.")


def _save_block(c, cid, prep):
    existing = get_db().fetchone("select * from gst_returns where client_id = ? and return_type = ? and period = ?",
                                 [cid, prep["return_type"], prep["period"]])
    a, b, d = st.columns(3)
    if existing:
        a.markdown(f"Saved status: {badge(existing['status'])}" + (f" · ARN {existing['external_arn']}" if existing.get("external_arn") else ""),
                   unsafe_allow_html=True)
    if b.button(f"Save {prep['return_type']} as prepared", disabled=not c.can("gst_prepare"), key=f"save_{prep['return_type']}"):
        with action("Saved"):
            gs.save_return(c, cid, prep)
            st.rerun()
    if existing and existing["status"] == "prepared" and d.button("Approve (CA)", disabled=not c.can("gst_approve"), key=f"appr_{prep['return_type']}"):
        with action("Approved"):
            gs.approve_return(c, existing["id"])
            st.rerun()
    if existing and existing["status"] == "approved":
        arn = st.text_input("ARN from GST portal (after you file there)", key=f"arn_{prep['return_type']}")
        if st.button("Record as filed on portal", key=f"filed_{prep['return_type']}", disabled=not c.can("gst_approve")):
            with action("Recorded (user-declared)"):
                gs.record_external_filing(c, existing["id"], arn)
                st.rerun()


def _gstr1(c, cid, y, m):
    p = gs.prepare_gstr1(c, cid, y, m)
    for w in p["warnings"]:
        st.warning(w)
    cols = st.columns(5)
    cols[0].metric("Invoices", p["invoice_count"])
    cols[1].metric("Taxable", rupees(p["totals"]["taxable_value"]))
    cols[2].metric("IGST", rupees(p["totals"]["igst"]))
    cols[3].metric("CGST", rupees(p["totals"]["cgst"]))
    cols[4].metric("SGST", rupees(p["totals"]["sgst"]))
    labels = {"b2b": "4A/4B/6B/6C – B2B", "b2cl": "5 – B2C Large", "b2cs": "7 – B2C Others", "cdnr": "9B – Credit/Debit notes (registered)",
              "cdnur": "9B – Credit/Debit notes (unregistered)", "exp": "6A – Exports", "nil": "8 – Nil/Exempt/Non-GST", "hsn": "12 – HSN summary"}
    for k, label in labels.items():
        with st.expander(f"{label} ({len(p['sections'][k])})"):
            table(p["sections"][k])
    with st.expander(f"13 – Documents issued ({len(p['documents_issued'])})"):
        table(p["documents_issued"])
    a, b = st.columns(2)
    a.download_button("⬇ GSTR-1 JSON (offline-tool layout)", json.dumps(gs.gstr1_portal_json(p), indent=1),
                      file_name=f"GSTR1_{p['period']}_{p.get('gstin') or 'NA'}.json", mime="application/json")
    b.download_button("⬇ GSTR-1 workbook (Excel)", gs.gstr1_excel(p), file_name=f"GSTR1_{p['period']}.xlsx",
                      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    _save_block(c, cid, p)


def _gstr3b(c, cid, y, m):
    basis = st.radio("ITC basis", ["books", "gstr2b_matched"], horizontal=True,
                     format_func=lambda x: "Purchase register (eligible)" if x == "books" else "Only invoices matched with GSTR-2B")
    with st.expander("Table 5.1 – interest & late fee (enter if applicable)"):
        a, b, d, e = st.columns(4)
        interest = {"igst": a.number_input("Interest IGST", 0.0), "cgst": b.number_input("Interest CGST", 0.0),
                    "sgst": d.number_input("Interest SGST", 0.0), "cess": e.number_input("Interest cess", 0.0)}
        late = {"cgst": a.number_input("Late fee CGST", 0.0), "sgst": b.number_input("Late fee SGST", 0.0)}
    r = gs.prepare_gstr3b(c, cid, y, m, itc_basis=basis, interest={k: str(v) for k, v in interest.items()},
                          late_fee={k: str(v) for k, v in late.items()})
    for w in r["warnings"]:
        st.warning(w)
    names = {"a": "(a) Outward taxable (other than zero/nil/exempt)", "b": "(b) Outward zero-rated", "c": "(c) Other outward (nil, exempt)",
             "d": "(d) Inward supplies liable to reverse charge", "e": "(e) Non-GST outward"}
    st.subheader("3.1 Outward and inward supplies liable to reverse charge")
    table([{"nature": names[k], **v} for k, v in r["table_3_1"].items()])
    st.subheader("3.2 Inter-state supplies to unregistered persons")
    table(r["table_3_2"])
    st.subheader("4 Eligible ITC")
    t4n = {"A1": "(A)(1) Import of goods", "A2": "(A)(2) Import of services", "A3": "(A)(3) Inward liable to RCM", "A4": "(A)(4) ISD",
           "A5": "(A)(5) All other ITC", "B1": "(B)(1) Reversed – Rules 38/42/43 & Sec 17(5)", "B2": "(B)(2) Reversed – others",
           "C": "(C) Net ITC available", "D1": "(D)(1) Reclaimed (earlier 4B2)", "D2": "(D)(2) Ineligible – Sec 16(4) & POS"}
    table([{"details": t4n[k], **r["table_4"][k]} for k in t4n])
    st.subheader("5 Exempt, nil-rated and non-GST inward supplies")
    table([{"nature": k.replace("_", " "), "value": v} for k, v in r["table_5"].items()])
    st.subheader("6.1 Payment of tax (Rule 88A set-off)")
    table([{"head": h.upper(), "liability": r["liability"][h], "rcm_cash": r["rcm_liability_cash"][h],
            "paid_by_itc": r["liability"][h] - r["setoff"]["cash_payable"][h], "cash_payable": r["cash_payable"][h],
            "itc_carried_forward": r["setoff"]["itc_balance_carried_forward"][h]} for h in ("igst", "cgst", "sgst", "cess")])
    st.caption("ITC utilisation: " + ", ".join(f"{k}: ₹{v}" for k, v in r["setoff"]["utilisation"].items()))
    _save_block(c, cid, r)


def _gstr2b(c, cid, y, m):
    period = f"{m:02d}{y}"
    st.caption("Upload the GSTR-2B JSON downloaded from the GST portal (preferred) or the portal Excel/CSV.")
    f = st.file_uploader("GSTR-2B file", type=["json", "xlsx", "csv"])
    if f and st.button("Import & reconcile", type="primary", disabled=not c.can("gst_prepare")):
        with action():
            up = gs.import_gstr2b(c, cid, period, f.name, f.getvalue())
            res = gs.reconcile_2b(c, cid, up)
            st.success(f"Reconciled: {res['summary']['counts']}")
    rec = gs.latest_reconciliation(c, cid, period)
    if not rec:
        st.info("No reconciliation for this period yet.")
        return
    sm = rec["summary"]
    cols = st.columns(4)
    cols[0].metric("ITC as per books", rupees(sm["itc_as_per_books"]))
    cols[1].metric("ITC as per 2B", rupees(sm["itc_as_per_2b"]))
    cols[2].metric("Matched ITC", rupees(sm["itc_matched"]))
    cols[3].metric("Difference", rupees(sm["difference"]))
    status = st.selectbox("Show", [None] + sorted(sm["counts"]), format_func=lambda s: "All" if s is None else f"{s} ({sm['counts'][s]})")
    items = [i for i in rec["items"] if status is None or i["status"] == status]
    table([{"status": i["status"], **{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in (i["details"] or {}).items()}} for i in items])
    xls = report_service.to_excel({"reconciliation": [{"status": i["status"], **{k: str(v) for k, v in (i["details"] or {}).items()}} for i in rec["items"]]},
                                  f"GSTR-2B reconciliation {period}")
    st.download_button("⬇ Reconciliation (Excel)", xls, file_name=f"GSTR2B_recon_{period}.xlsx")


def _itc(c, cid, y, m):
    s, e = month_bounds(y, m)
    invs = get_db().fetchall("select * from invoices where client_id = ? and category in ('purchase','expense') and status = 'approved' "
                             "and invoice_date between ? and ? order by invoice_date", [cid, s, e])
    st.caption("ITC is never assumed. Decide eligibility per Sections 16 and 17(5); blocked credit is reported in 4(A) and reversed in 4(B)(1).")
    table([{"invoice": i["invoice_no"], "party": i["party_name"], "gstin": i.get("party_gstin"), "tax": D(i["igst"]) + D(i["cgst"]) + D(i["sgst"]),
            "itc": i["itc_eligibility"], "reason": i.get("itc_reason")} for i in invs])
    if invs:
        a, b, d, e2 = st.columns([3, 2, 3, 1])
        iid = a.selectbox("Invoice", [i["id"] for i in invs], format_func=lambda x: next(f"{i['invoice_no']} · {i['party_name']}" for i in invs if i["id"] == x))
        el = b.selectbox("Eligibility", ["eligible", "ineligible", "blocked", "pending"])
        rs = d.text_input("Reason")
        if e2.button("Set"):
            with action("Updated"):
                gs.set_itc_eligibility(c, iid, el, rs)
                st.rerun()


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    page_header("GST", f"Period {m:02d}/{y}")
    st.markdown(f"<div class='as-warn'>{DISCLAIMER}</div>", unsafe_allow_html=True)
    st.write("")
    t1, t2, t3, t4, t5 = st.tabs(["GSTR-1", "GSTR-3B", "GSTR-2B reconciliation", "ITC eligibility", "Saved returns"])
    with t1:
        _gstr1(c, cid, y, m)
    with t2:
        _gstr3b(c, cid, y, m)
    with t3:
        _gstr2b(c, cid, y, m)
    with t4:
        _itc(c, cid, y, m)
    with t5:
        table(gs.list_returns(c, cid))
