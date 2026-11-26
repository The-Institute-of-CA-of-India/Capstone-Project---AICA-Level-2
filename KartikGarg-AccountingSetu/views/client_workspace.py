"""Client Workspace — everything for ONE client on one page: approval queue, GST, TDS, Tally, Excel.

This is the landing page once a client is selected. The separate Documents & Review / Accounting /
Bank / GST / Reports / Tally pages still exist for deeper, one-area-at-a-time work — this page is the
fast path: approve what's clean, see the numbers, download the files, without navigating around.
"""
from __future__ import annotations

import datetime as dt

import streamlit as st

from services import accounting_engine as ae, bank_service as bs, document_service as ds, gst_service as gs
from services import report_service as rs, tally_service as ts, tds_service as tds
from services.db import get_db
from ui.common import action, badge, ctx, kpi, page_header, require_client_selected, rupees, selected_period, table
from utils.helpers import D, ZERO, fy_bounds, fy_label_for, month_bounds

FIELDS = ["invoice_no", "invoice_date", "party_name", "party_gstin", "taxable_value", "cgst", "sgst", "igst", "total"]
FIELD_LABELS = {"invoice_no": "Invoice no.", "invoice_date": "Date", "party_name": "Party", "party_gstin": "GSTIN",
               "taxable_value": "Taxable value", "cgst": "CGST", "sgst": "SGST", "igst": "IGST", "total": "Total"}


def _flagged_row(c, d, ext):
    data = dict((ext or {}).get("data") or {})
    issues = ((ext or {}).get("validation") or {}).get("issues", [])
    sev = "error" if any(i["severity"] == "error" for i in issues) else "warning"
    icon = "🔴" if sev == "error" else "🟡"
    with st.container(border=True):
        top = st.columns([5, 1, 1, 1])
        top[0].markdown(f"{icon} **{d['original_filename']}**" + (f" · {data.get('invoice_no')}" if data.get("invoice_no") else ""))
        for i in issues[:3]:
            top[0].caption(("❗ " if i["severity"] == "error" else "⚠️ ") + i["message"])
        edit_key = f"editing_{d['id']}"
        editing = st.session_state.get(edit_key, False)
        if top[1].button("✏️ Edit", key=f"wsedit_{d['id']}"):
            st.session_state[edit_key] = not editing
            st.rerun()
        approve_disabled = sev == "error"
        if top[2].button("✅ Approve", key=f"wsappr_{d['id']}", disabled=approve_disabled,
                         help="Resolve the error first" if approve_disabled else "Approve with the warning(s) acknowledged"):
            with action():
                res = ds.approve_document(c, d["id"], acknowledge_warnings=True)
                st.success(f"Approved{' — voucher created' if res.get('voucher_id') else ''}")
                st.rerun()
        if top[3].button("✖ Decline", key=f"wsdecl_{d['id']}"):
            st.session_state[f"declining_{d['id']}"] = True
            st.rerun()
        if st.session_state.get(f"declining_{d['id']}"):
            reason = st.text_input("Reason for declining", key=f"wsreason_{d['id']}")
            if st.button("Confirm decline", key=f"wsdeclconfirm_{d['id']}") and reason.strip():
                with action("Declined"):
                    ds.reject_document(c, d["id"], reason)
                    st.session_state.pop(f"declining_{d['id']}", None)
                    st.rerun()
        if editing:
            cols = st.columns(3)
            corrected = {}
            for i, f in enumerate(FIELDS):
                cur = data.get(f)
                corrected[f] = cols[i % 3].text_input(FIELD_LABELS[f], "" if cur is None else str(cur), key=f"wsf_{d['id']}_{f}")
            if st.button("💾 Save", key=f"wssave_{d['id']}"):
                changes = {k: (v or None) for k, v in corrected.items() if (v or None) != data.get(k)}
                with action("Saved"):
                    status = ds.save_correction(c, d["id"], changes)
                    st.session_state[edit_key] = False
                    st.success(f"Saved — status: {status}")
                    st.rerun()


def _approval_section(c, cid, y, m):
    st.markdown("## 📋 Approval queue")
    docs = ds.list_documents(c, cid, year=y, month=m)
    # Bank statements are never "approved" like an invoice — they're imported on the Bank Reconciliation
    # page instead, so they're kept out of this approve/decline queue entirely.
    pending = [d for d in docs if d["status"] in ("processed", "needs_review") and d["doc_type"] != "bank_statement"]
    bank_ready = [d for d in docs if d["status"] in ("processed", "needs_review") and d["doc_type"] == "bank_statement"]
    if not pending and not docs:
        st.info("No documents uploaded for this period yet.")
        return
    extractions = ds.bulk_current_extractions(c, cid, [d["id"] for d in pending]) if pending else {}
    clean, flagged = [], []
    for d in pending:
        ext = extractions.get(d["id"])
        issues = (ext.get("validation") or {}).get("issues", []) if ext else [{"severity": "error", "message": "Not extracted"}]
        (flagged if issues else clean).append((d, ext))
    a, b, c3 = st.columns(3)
    kpi(a, "Ready to approve", len(clean))
    kpi(b, "Need your decision", len(flagged))
    approved_count = len([d for d in docs if d["status"] == "approved"])
    if bank_ready:
        st.caption(f"📄 {len(bank_ready)} bank statement document(s) are read and waiting — go to "
                  "**Bank Reconciliation → Import statement** to bring them in (they don't go through this approval queue).")
    kpi(c3, "Already approved", approved_count)
    if clean and c.can("approve_documents") and st.button(f"⚡ Approve all {len(clean)} clean document(s) now", type="primary",
                                                           key="ws_bulk_approve"):
        progress = st.progress(0.0, text=f"0 of {len(clean)}")
        ok, errs = 0, []
        with get_db().transaction():
            for i, (d, _) in enumerate(clean, 1):
                try:
                    ds.approve_document(c, d["id"])
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"{d['original_filename']}: {exc}")
                progress.progress(i / len(clean), text=f"{i} of {len(clean)}")
        progress.empty()
        st.session_state["ws_bulk_result"] = {"ok": ok, "total": len(clean), "errors": errs}
        st.rerun()
    result = st.session_state.pop("ws_bulk_result", None)
    if result:
        (st.success if not result["errors"] else st.warning)(f"Approved {result['ok']} of {result['total']} document(s).")
        for e in result["errors"][:10]:
            st.error(e)
    if flagged:
        st.markdown(f"#### {len(flagged)} document(s) need your decision")
        st.caption("Edit a value inline if it was misread, then Approve — or Decline if the document itself is wrong/unwanted.")
        for d, ext in flagged:
            _flagged_row(c, d, ext)


def _gst_section(c, cid, y, m):
    st.markdown("## 🧮 GST")
    s, e = month_bounds(y, m)
    try:
        p1 = gs.prepare_gstr1(c, cid, y, m)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"GSTR-1 could not be prepared: {exc}")
        return
    cols = st.columns(4)
    kpi(cols[0], "Taxable value", rupees(p1["totals"]["taxable_value"]))
    kpi(cols[1], "IGST", rupees(p1["totals"]["igst"]))
    kpi(cols[2], "CGST", rupees(p1["totals"]["cgst"]))
    kpi(cols[3], "SGST", rupees(p1["totals"]["sgst"]))
    for w in p1["warnings"][:5]:
        st.caption(f"⚠️ {w}")
    try:
        p3b = gs.prepare_gstr3b(c, cid, y, m)
        net = sum(p3b["cash_payable"].values(), ZERO)
        st.caption(f"Estimated net GST cash payable (after ITC set-off): **{rupees(net)}**")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"GSTR-3B could not be prepared: {exc}")
    a, b = st.columns(2)
    import json

    a.download_button("⬇ GSTR-1 JSON", json.dumps(gs.gstr1_portal_json(p1), indent=1),
                      file_name=f"GSTR1_{p1['period']}.json", mime="application/json", key="ws_gstr1_json")
    b.download_button("⬇ GSTR-1 Excel", gs.gstr1_excel(p1), file_name=f"GSTR1_{p1['period']}.xlsx", key="ws_gstr1_xlsx")
    st.caption("Preparation only — this is never filed by the app. Verify against the current GSTN schema before uploading.")


def _tds_section(c, cid, y, m, client):
    st.markdown("## 🧾 TDS")
    if not client.get("is_tds_deductor"):
        st.info("This client is not marked as a TDS deductor. Turn it on in **Clients → (this client) → Profile** "
                "if they are required to deduct TDS on vendor payments.")
        return
    q, fy = tds.quarter_for(y, m)
    s, e = month_bounds(y, m)
    summary = tds.tds_summary(c, cid, s, e)
    cols = st.columns(3)
    kpi(cols[0], "TDS deducted this month", rupees(summary["total"]))
    kpi(cols[1], "Pending TDS decisions", summary["pending_decisions"])
    kpi(cols[2], "Quarter", f"{q} {fy}")
    if summary["pending_decisions"]:
        st.caption("Some approved purchase/expense invoices still need a TDS decision — open them from the Approval queue "
                   "above (already-approved ones can be decided from Documents & Review).")
    try:
        prep = tds.prepare_26q(c, cid, q, fy)
        st.caption(f"Quarter {q} {fy} ({prep['period_from']} to {prep['period_to']}): {prep['total_invoices']} deduction(s), "
                   f"{len(prep['deductees'])} deductee(s), total TDS {rupees(prep['total_tds'])}")
        for w in prep["warnings"]:
            st.caption(f"⚠️ {w}")
        st.download_button("⬇ 26Q data (Excel)", tds.to_excel(prep), file_name=f"26Q_{q}_{fy}.xlsx", key="ws_26q_xlsx")
        st.caption("Preparation only — file Form 26Q on TRACES/the e-filing portal yourself, then record the acknowledgement "
                   "number on the Clients page.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"26Q could not be prepared: {exc}")


def _tally_section(c, cid, y, m):
    st.markdown("## 📤 Tally export")
    s, e = month_bounds(y, m)
    pv = ts.preview(c, cid, s, e)
    if not pv["vouchers"]:
        drafts = ae.list_vouchers(c, cid, date_from=s, date_to=e, status="draft") if c.can("approve_vouchers") else []
        unflagged = [v for v in drafts if not v["needs_review"]]
        if unflagged:
            st.warning(f"{len(unflagged)} voucher(s) for this month are still drafts — approving a document "
                      "creates its voucher as a draft, and it only reaches Tally once approved.")
            if st.button(f"✅ Approve all {len(unflagged)} draft voucher(s) now", key="ws_tally_approve_drafts"):
                with action():
                    ok, flagged = _approve_draft_vouchers(c, cid, s, e)
                    st.success(f"Approved {ok} voucher(s)." + (f" {flagged} still need review." if flagged else ""))
        else:
            st.info("No approved vouchers yet this month — approve documents above first.")
        return
    st.caption(f"{len(pv['vouchers'])} approved voucher(s) ready for this month.")
    for i in pv["issues"][:5]:
        st.warning(i)
    if st.button("Generate Tally files", key="ws_tally_gen", disabled=pv["blocking"]):
        with action():
            xml, info = ts.export(c, cid, s, e)
            st.session_state["ws_tally_files"] = (xml, info)
            st.success(f"Generated — {info['count']} voucher(s)")
    if "ws_tally_files" in st.session_state:
        xml, info = st.session_state["ws_tally_files"]
        a, b = st.columns(2)
        if info.get("masters_xml"):
            a.download_button("⬇ 1. Ledger masters XML", info["masters_xml"], file_name="tally_masters.xml", key="ws_tally_m")
        b.download_button("⬇ 2. Vouchers XML", xml, file_name="tally_vouchers.xml", key="ws_tally_v")


def _reports_section(c, cid, y, m):
    st.markdown("## 📊 Reports (Excel)")
    s, e = month_bounds(y, m)
    client = get_db().get("clients", cid)
    p = rs.profit_and_loss_data(client, s, e)
    cols = st.columns(4)
    kpi(cols[0], "Net sales", rupees(p["net_sales"]))
    kpi(cols[1], "Net purchases", rupees(p["net_purchases"]))
    kpi(cols[2], "Gross profit", rupees(p["gross_profit"]))
    kpi(cols[3], "Net profit", rupees(p["net_profit"]))
    tb = rs.trial_balance_rows(cid, s, e)
    sales_reg = rs.register(c, cid, "sales", s, e)
    purch_reg = rs.register(c, cid, "purchase", s, e)
    xls = rs.to_excel({"Trial Balance": [{k: v for k, v in r.items() if k != "ledger_id"} for r in tb],
                       "P&L": rs.pnl_rows(p), "Sales Register": sales_reg, "Purchase Register": purch_reg},
                      f"{client['name']} — {s:%b %Y}")
    st.download_button("⬇ Monthly workbook (Trial Balance + P&L + Registers)", xls, file_name=f"Reports_{s:%Y%m}.xlsx",
                       key="ws_reports_xlsx")
    st.caption("For the Balance Sheet and more report types, open the full **Reports** page from the sidebar.")


def _bank_section(c, cid, y, m):
    """Full bank reconciliation, inline — no separate page to visit: add the account, import a submitted
    statement, auto-match, generate the draft vouchers, all on this same tab."""
    st.markdown("## 🏦 Bank reconciliation")
    s, e = month_bounds(y, m)
    accounts = bs.list_bank_accounts(c, cid)
    with st.expander("➕ Add bank account", expanded=not accounts):
        a, b, d = st.columns(3)
        bank = a.text_input("Bank name", key="ws_bank_name")
        no = b.text_input("Account number (only last 4 digits are stored)", key="ws_bank_no")
        ifsc = d.text_input("IFSC", key="ws_bank_ifsc")
        if st.button("Create", key="ws_bank_create", disabled=not c.can("bank_reconcile")):
            with action("Bank account and ledger created"):
                bs.create_bank_account(c, cid, bank, no, ifsc)
                st.rerun()
    if not accounts:
        return
    acct = st.selectbox("Bank account", [a["id"] for a in accounts],
                        format_func=lambda i: next(a["ledger_name"] for a in accounts if a["id"] == i), key="ws_bank_acct")

    pending_stmts = [d for d in ds.list_documents(c, cid, year=y, month=m, doc_type="bank_statement")
                     if d["status"] in ("processed", "needs_review")]
    if pending_stmts:
        st.markdown("**Statements submitted by the client — ready to import**")
        for d in pending_stmts:
            ext = ds.current_extraction(c, d["id"])
            data = (ext or {}).get("data") or {}
            n = len(data.get("transactions") or [])
            a, b = st.columns([3, 1])
            a.write(f"📄 {d['original_filename']} — {n} transaction(s); warnings: {len(data.get('warnings') or [])}")
            if n and b.button("Import", key=f"ws_imp_{d['id']}", disabled=not c.can("bank_reconcile")):
                with action():
                    st.success(str(bs.import_statement(c, cid, acct, data, document_id=d["id"])))
                    st.rerun()

    txns = bs.list_transactions(c, cid, acct, s, e)
    unmatched = len([t for t in txns if t["match_status"] in ("unmatched", "needs_review", "suspense")])
    a, b, d = st.columns(3)
    kpi(a, "Transactions this month", len(txns))
    kpi(b, "Unmatched / need review", unmatched)
    kpi(d, "Matched", len(txns) - unmatched)
    if txns and unmatched and c.can("bank_reconcile") and st.button("⚡ Run automatic matching", key="ws_bank_automatch"):
        with action():
            st.success(str(bs.auto_match(c, cid, acct)))
            st.rerun()
    if txns:
        table([{"date": str(t["txn_date"]), "narration": t["narration"][:60], "debit": D(t["debit"]), "credit": D(t["credit"]),
                "category": t["category"], "status": t["match_status"], "voucher": "yes" if t.get("voucher_id") else ""}
               for t in txns])
        unposted = [t for t in txns if not t.get("voucher_id") and t["match_status"] not in ("duplicate", "matched", "partially_matched")]
        if unposted and c.can("prepare_vouchers") and st.button(f"Generate draft vouchers for {len(unposted)} unmatched transaction(s)",
                                                                 key="ws_bank_genvouchers"):
            with action():
                r = bs.generate_vouchers(c, cid, [t["id"] for t in unposted])
                st.success(f"Created {r['created']}, skipped {r['skipped']}")
                for err in r["errors"]:
                    st.error(err)
    st.caption("For manual match-to-invoice, categorisation and the BRS statement, open the full "
              "**Bank Reconciliation** page from the sidebar.")


def _approve_draft_vouchers(c, cid, s, e, *, acknowledge_flagged: bool = False) -> tuple[int, int]:
    """Approving a document only creates its voucher as a DRAFT — a second, deliberate checkpoint before it
    counts as posted (Tally export and the Trial Balance/P&L only include status='approved' vouchers). Without
    this step 'Generate everything' silently produced an empty Tally file and an incomplete report even though
    every document was approved. Vouchers the engine flagged `needs_review` (e.g. ITC eligibility, RCM) still
    represent a real compliance judgement — they're only approved here when the CA has explicitly ticked
    "also approve flagged vouchers" for this run; otherwise they're left for the Accounting page."""
    if not c.can("approve_vouchers"):
        return 0, 0
    drafts = ae.list_vouchers(c, cid, date_from=s, date_to=e, status="draft")
    ok, flagged = 0, 0
    for v in drafts:
        if v["needs_review"] and not acknowledge_flagged:
            flagged += 1
            continue
        try:
            ae.approve_voucher(c, v["id"], acknowledge_review=acknowledge_flagged)
            ok += 1
        except Exception:  # noqa: BLE001
            flagged += 1
    return ok, flagged


def _generate_everything(c, cid, y, m, client, *, acknowledge_flagged: bool = False) -> dict:
    """Runs bank import + auto-match, voucher posting, Tally export, Excel reports, GST prep (+ TDS prep if
    applicable) in one go and collects every resulting file so they all appear as download buttons together,
    instead of one tab at a time."""
    s, e = month_bounds(y, m)
    files, notes = [], []
    accounts = bs.list_bank_accounts(c, cid)
    if accounts:
        acct = accounts[0]["id"]
        pending_stmts = [d for d in ds.list_documents(c, cid, year=y, month=m, doc_type="bank_statement")
                         if d["status"] in ("processed", "needs_review")]
        imported = 0
        for d in pending_stmts:
            ext = ds.current_extraction(c, d["id"])
            data = (ext or {}).get("data") or {}
            if data.get("transactions"):
                try:
                    bs.import_statement(c, cid, acct, data, document_id=d["id"])
                    imported += 1
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"⚠️ Bank statement {d['original_filename']} could not be imported: {exc}")
        if imported:
            notes.append(f"Bank: {imported} statement(s) imported into {accounts[0]['ledger_name']}.")
        try:
            match_stats = bs.auto_match(c, cid, acct)
            matched = match_stats.get("matched", 0)
            if matched:
                notes.append(f"Bank: {matched} transaction(s) auto-matched.")
            unmatched_txns = [t for t in bs.list_transactions(c, cid, acct, s, e)
                              if not t.get("voucher_id") and t["match_status"] not in ("duplicate", "matched", "partially_matched")]
            if unmatched_txns and c.can("prepare_vouchers"):
                gv = bs.generate_vouchers(c, cid, [t["id"] for t in unmatched_txns])
                if gv["created"]:
                    notes.append(f"Bank: {gv['created']} draft voucher(s) generated for unmatched transactions.")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ Bank auto-matching failed: {exc}")
    approved_vouchers, flagged_vouchers = _approve_draft_vouchers(c, cid, s, e, acknowledge_flagged=acknowledge_flagged)
    if approved_vouchers:
        notes.append(f"Accounting: {approved_vouchers} draft voucher(s) approved and posted.")
    if flagged_vouchers:
        notes.append(f"⚠️ {flagged_vouchers} voucher(s) still need your review on the **Accounting** page — "
                     "Tally and reports exclude them until approved.")
    try:
        p1 = gs.prepare_gstr1(c, cid, y, m)
        import json

        files.append({"label": "⬇ GSTR-1 JSON", "filename": f"GSTR1_{p1['period']}.json",
                     "data": json.dumps(gs.gstr1_portal_json(p1), indent=1), "mime": "application/json"})
        files.append({"label": "⬇ GSTR-1 Excel", "filename": f"GSTR1_{p1['period']}.xlsx", "data": gs.gstr1_excel(p1)})
        notes.append(f"GST: {p1['invoice_count']} sales invoice(s) prepared for GSTR-1.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"⚠️ GST could not be prepared: {exc}")
    try:
        pv = ts.preview(c, cid, s, e)
        if pv["vouchers"] and not pv["blocking"]:
            xml, info = ts.export(c, cid, s, e)
            if info.get("masters_xml"):
                files.append({"label": "⬇ Tally masters XML", "filename": "tally_masters.xml", "data": info["masters_xml"]})
            files.append({"label": "⬇ Tally vouchers XML", "filename": "tally_vouchers.xml", "data": xml})
            notes.append(f"Tally: {info['count']} voucher(s) exported.")
        elif pv["blocking"]:
            notes.append("⚠️ Tally export skipped: " + "; ".join(pv["issues"][:3]))
        else:
            notes.append("Tally: no approved vouchers this month yet.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"⚠️ Tally export failed: {exc}")
    try:
        p = rs.profit_and_loss_data(client, s, e)
        tb = rs.trial_balance_rows(cid, s, e)
        xls = rs.to_excel({"Trial Balance": [{k: v for k, v in r.items() if k != "ledger_id"} for r in tb],
                           "P&L": rs.pnl_rows(p), "Sales Register": rs.register(c, cid, "sales", s, e),
                           "Purchase Register": rs.register(c, cid, "purchase", s, e)}, f"{client['name']} — {s:%b %Y}")
        files.append({"label": "⬇ Reports workbook", "filename": f"Reports_{s:%Y%m}.xlsx", "data": xls})
        notes.append("Reports: Trial Balance, P&L and registers compiled.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"⚠️ Reports could not be compiled: {exc}")
    if client.get("is_tds_deductor"):
        try:
            q, fy = tds.quarter_for(y, m)
            prep = tds.prepare_26q(c, cid, q, fy)
            files.append({"label": "⬇ 26Q (TDS) Excel", "filename": f"26Q_{q}_{fy}.xlsx", "data": tds.to_excel(prep)})
            notes.append(f"TDS: {prep['total_invoices']} deduction(s) for {q} {fy}.")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ TDS 26Q could not be prepared: {exc}")
    return {"files": files, "notes": notes}


def page():
    c = ctx()
    cid = require_client_selected()
    client = get_db().get("clients", cid)
    y, m = selected_period()
    page_header(f"🏢 {client['name']}", f"Everything for this client · {m:02d}/{y}")
    if client.get("gstin"):
        st.caption(f"GSTIN: {client['gstin']} · PAN: {client.get('pan') or '—'}"
                   + (f" · TAN: {client['tan']}" if client.get("tan") else ""))

    _approval_section(c, cid, y, m)
    st.divider()

    _ws_s, _ws_e = month_bounds(y, m)
    draft_vouchers = ae.list_vouchers(c, cid, date_from=_ws_s, date_to=_ws_e, status="draft") if c.can("approve_vouchers") else []
    flagged_count = sum(1 for v in draft_vouchers if v["needs_review"])
    acknowledge_flagged = False
    if flagged_count:
        acknowledge_flagged = st.checkbox(f"Also approve the {flagged_count} voucher(s) flagged for review "
                                          "(ITC eligibility, RCM, etc. — I've checked these)", key="ws_ack_flagged")

    if st.button("🚀 Generate everything (Bank + Tally + Excel + GST" + (" + TDS" if client.get("is_tds_deductor") else "") + ")",
                type="primary", key="ws_generate_all"):
        # Bank-statement documents are excluded here too — they're imported via the Bank tab above, never
        # "approved" like an invoice, so they must never block this button.
        pending_clean = [d for d in ds.list_documents(c, cid, year=y, month=m)
                         if d["status"] in ("processed", "needs_review") and d["doc_type"] != "bank_statement"]
        if pending_clean:
            st.warning(f"{len(pending_clean)} document(s) in the Approval queue above are not approved yet — "
                      "approve or decline them first, then click Generate again.")
        else:
            st.session_state["ws_generated"] = _generate_everything(c, cid, y, m, client, acknowledge_flagged=acknowledge_flagged)
            st.rerun()

    generated = st.session_state.get("ws_generated")
    if generated:
        st.markdown("#### Ready to download")
        for note in generated["notes"]:
            st.caption(note)
        cols = st.columns(len(generated["files"]) or 1)
        for i, f in enumerate(generated["files"]):
            cols[i % len(cols)].download_button(f["label"], f["data"], file_name=f["filename"], mime=f.get("mime"),
                                                key=f"ws_gen_{i}")

    tabs = st.tabs(["GST", "TDS", "Tally", "Reports", "Bank"])
    with tabs[0]:
        _gst_section(c, cid, y, m)
    with tabs[1]:
        _tds_section(c, cid, y, m, client)
    with tabs[2]:
        _tally_section(c, cid, y, m)
    with tabs[3]:
        _reports_section(c, cid, y, m)
    with tabs[4]:
        _bank_section(c, cid, y, m)
