"""CA document review dashboard: queue, original alongside extracted values, corrections, approval."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from services import accounting_engine as ae, document_service as ds, ocr_service
from ui.common import action, badge, ctx, page_header, require_client_selected, selected_period, table

FIELDS = [("invoice_no", "Invoice number"), ("invoice_date", "Invoice date (YYYY-MM-DD)"), ("party_name", "Party name"),
          ("party_gstin", "Party GSTIN"), ("place_of_supply", "Place of supply (state code)"), ("taxable_value", "Taxable value"),
          ("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"), ("cess", "Cess"), ("discount", "Discount"),
          ("round_off", "Round off"), ("total", "Invoice total"), ("original_invoice_no", "Original invoice no. (notes)")]
SUPPLY_TYPES = ["taxable", "nil", "exempt", "non_gst", "export_wpay", "export_wopay", "sez_wpay", "sez_wopay", "deemed_export"]
ITC = ["pending", "eligible", "ineligible", "blocked"]


def _conf_icon(c):
    if c is None:
        return ""
    return "🟢" if c >= 0.9 else "🟡" if c >= 0.8 else "🔴"


def _preview(c, doc):
    try:
        data, _ = ds.read_document_bytes(c, doc["id"])
    except Exception as exc:
        st.error(f"Cannot load original: {exc}")
        return
    ext = doc["file_ext"]
    st.download_button("⬇ Download original", data, file_name=doc["original_filename"].split(" [part")[0],
                       key=f"dlo_{doc['id']}")
    if ext == ".pdf":
        start = doc.get("page_from") or 1
        end = doc.get("page_to") or min(doc.get("page_count") or 1, start + 2)
        for p in range(start, min(end, start + 2) + 1):
            png = ocr_service.render_pdf_page(data, p)
            if png:
                st.image(png, caption=f"Page {p}", width="stretch")
    elif ext in (".png", ".jpg", ".jpeg"):
        st.image(data, width="stretch")
    else:
        try:
            df = ocr_service.read_table(data, ext)
            if doc.get("parent_document_id"):
                st.caption("Spreadsheet row imported as this document")
            st.dataframe(df.head(50), width="stretch", hide_index=True)
        except Exception as exc:
            st.error(f"Preview failed: {exc}")


def _detail(c, doc):
    st.markdown(f"### {doc['original_filename']} {badge(doc['status'])}", unsafe_allow_html=True)
    st.caption(f"Type: {ds.DOC_TYPES.get(doc['doc_type'], doc['doc_type'])} · uploaded {str(doc['uploaded_at'])[:16]}"
               + (f" · pages {doc['page_from']}–{doc['page_to']}" if doc.get("page_from") else ""))
    if doc.get("error_message"):
        st.error(doc["error_message"])
    ext = ds.current_extraction(c, doc["id"])
    left, right = st.columns([1, 1.15])
    with left:
        _preview(c, doc)
    with right:
        if not ext:
            st.info("Not processed yet.")
            if doc["status"] == "uploaded" and st.button("Process now", type="primary", key=f"proc_{doc['id']}"):
                with action():
                    st.success(f"Status: {ds.process_document(c, doc['id'])}")
                    st.rerun()
            return
        data, conf = dict(ext["data"]), ext.get("field_confidence") or {}
        issues = (ext.get("validation") or {}).get("issues", [])
        st.caption(f"Source: {ext['source']} ({ext.get('provider')}) · version {ext['version']} · overall confidence "
                   f"{ext.get('overall_confidence') or 0}%")
        for i in issues:
            (st.error if i["severity"] == "error" else st.warning)(f"**{i['field']}**: {i['message']}")
        if data.get("doc_kind") == "bank_statement":
            st.info("Bank statement — import it into a bank account on the Bank Reconciliation page.")
            table(data.get("transactions", [])[:200])
            return
        editable = doc["status"] in ("processed", "needs_review") and c.can("review_documents")
        with st.form(f"fix_{doc['id']}"):
            a, b = st.columns(2)
            cats = ["", "sales", "purchase", "expense"]
            corrected = {
                "category": a.selectbox("Category", cats, index=cats.index(data.get("category") or ""), disabled=not editable) or None,
                "note_type": b.selectbox("Document", ["invoice", "credit_note", "debit_note"],
                                         index=["invoice", "credit_note", "debit_note"].index(data.get("note_type") or "invoice"),
                                         disabled=not editable),
            }
            cols = st.columns(2)
            for n, (f, label) in enumerate(FIELDS):
                cur = data.get(f)
                icon = "⚪" if f in ("cess", "discount", "round_off") and str(cur) in ("0", "0.00", "None") else _conf_icon(conf.get(f))
                corrected[f] = cols[n % 2].text_input(f"{icon} {label}", "" if cur is None else str(cur),
                                                      disabled=not editable, key=f"{doc['id']}_{f}") or None
            a, b, d = st.columns(3)
            corrected["supply_type"] = a.selectbox("Supply type", SUPPLY_TYPES, index=SUPPLY_TYPES.index(data.get("supply_type") or "taxable"),
                                                   disabled=not editable)
            corrected["reverse_charge"] = b.checkbox("Reverse charge", bool(data.get("reverse_charge")), disabled=not editable)
            if (corrected["category"] or data.get("category")) in ("purchase", "expense"):
                corrected["itc_eligibility"] = d.selectbox("ITC eligibility", ITC, index=ITC.index(data.get("itc_eligibility") or "pending"),
                                                           disabled=not editable, help="Never assumed — decide per Sec 16/17(5)")
            if (corrected["category"] or data.get("category")) == "expense":
                heads = [k for _, _, k in ae.DEFAULT_LEDGERS if k and k.startswith("exp:")]
                corrected["expense_head"] = st.selectbox("Expense head", heads, index=heads.index(data["expense_head"])
                                                         if data.get("expense_head") in heads else heads.index("exp:general"),
                                                         disabled=not editable)
            items = pd.DataFrame(data.get("items") or [], columns=["description", "hsn_sac", "quantity", "unit_price", "taxable_value", "gst_rate"])
            st.caption("Line items (HSN-wise)")
            edited = st.data_editor(items, num_rows="dynamic", width="stretch", disabled=not editable, key=f"items_{doc['id']}")
            saved = st.form_submit_button("💾 Save corrections", disabled=not editable)
        if saved:
            corrected["items"] = [{k: (None if pd.isna(v) else str(v)) for k, v in r.items()} for r in edited.to_dict("records")]
            changes = {k: v for k, v in corrected.items() if v != data.get(k) and not (v is None and data.get(k) in (None, ""))}
            with action():
                st.success(f"Saved as new version — status: {ds.save_correction(c, doc['id'], changes)}")
                st.rerun()
        if doc["status"] in ("processed", "needs_review") and c.can("approve_documents"):
            st.divider()
            has_warn = any(i["severity"] == "warning" for i in issues)
            ack = st.checkbox("I have reviewed the warnings above against the original", key=f"ack_{doc['id']}") if has_warn else True
            a, b = st.columns(2)
            if a.button("✅ Approve for accounting", type="primary", key=f"appr_{doc['id']}", disabled=not ack):
                with action():
                    res = ds.approve_document(c, doc["id"], acknowledge_warnings=bool(ack))
                    st.success("Approved" + (" — draft voucher created" if res.get("voucher_id") else ""))
                    st.rerun()
            reason = b.text_input("Rejection reason", key=f"rr_{doc['id']}")
            if b.button("✖ Reject", key=f"rej_{doc['id']}"):
                with action("Rejected"):
                    ds.reject_document(c, doc["id"], reason)
                    st.rerun()
        if doc["status"] in ("needs_review", "processed") and c.can("review_documents") and st.button("↻ Re-run extraction", key=f"re_{doc['id']}"):
            with action():
                st.success(f"Status: {ds.process_document(c, doc['id'])}")
                st.rerun()
    t1, t2, t3, t4 = st.tabs(["Internal notes", "Ask client", "Extraction versions", "Processing history"])
    with t1:
        for n in ds.list_notes(c, doc["id"]):
            st.markdown(f"**{n.get('full_name') or 'User'}** · {str(n['created_at'])[:16]}  \n{n['note']}")
        note = st.text_area("Add internal note (not visible to client)", key=f"note_{doc['id']}")
        if st.button("Add note", key=f"noteb_{doc['id']}") and note.strip():
            with action("Note added"):
                ds.add_note(c, doc["id"], note)
                st.rerun()
    with t2:
        q = st.text_area("Question for the client", key=f"q_{doc['id']}")
        if st.button("Send clarification request", key=f"qb_{doc['id']}") and q.strip():
            with action("Sent to client"):
                ds.raise_clarification(c, doc["client_id"], q, doc["id"])
    with t3:
        for h in ds.extraction_history(c, doc["id"]):
            with st.expander(f"v{h['version']} · {h['source']} · {str(h['created_at'])[:16]}"):
                st.json(h["data"])
    with t4:
        table([{"job": j["job_type"], "status": j["status"], "started": str(j["started_at"])[:19], "error": j.get("error"),
                "log": "; ".join(j.get("log") or [])} for j in ds.processing_history(c, doc["id"])])


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    page_header("Documents & review", f"Period {m:02d}/{y}")
    result = st.session_state.pop("bulk_approve_result", None)
    if result:
        (st.success if not result["errors"] else st.warning)(
            f"Bulk approval finished: {result['ok']} of {result['total']} document(s) approved."
            + (f" {len(result['errors'])} could not be approved." if result["errors"] else ""))
        for e in result["errors"][:10]:
            st.error(e)
    if c.can("upload_documents"):
        with st.expander("📤 Upload documents on behalf of the client"):
            dtype = st.selectbox("Document type", list(ds.DOC_TYPES), format_func=lambda k: ds.DOC_TYPES[k])
            files = st.file_uploader("Files", type=["pdf", "jpg", "jpeg", "png", "xlsx", "csv"], accept_multiple_files=True)
            if files and st.button("Upload", type="primary"):
                for f in files:
                    with action(f"Uploaded {f.name}"):
                        ds.upload_document(c, cid, y, m, f.name, f.getvalue(), dtype)
    subs = [s for s in ds.list_submissions(c, cid) if s["period_year"] == y and s["period_month"] == m]
    if subs:
        st.subheader("Submissions")
        for s in subs:
            a, b, d = st.columns([3, 2, 1])
            a.markdown(f"**{s.get('reference_no') or 'Draft (not submitted)'}** · {s['doc_count']} file(s) · "
                       f"submitted {str(s.get('submitted_at') or '—')[:16]}")
            b.markdown(badge(s["status"]), unsafe_allow_html=True)
            if s["status"] in ("submitted", "draft") and c.can("review_documents") and d.button("Process", key=f"ps_{s['id']}"):
                with action():
                    st.success(str(ds.process_submission(c, s["id"])))
                    st.rerun()
    st.subheader("Document queue")
    f1, f2, f3 = st.columns(3)
    t = f1.selectbox("Type", [None] + list(ds.DOC_TYPES), format_func=lambda k: "All types" if k is None else ds.DOC_TYPES[k])
    stt = f2.selectbox("Status", [None] + ds.STATUSES, format_func=lambda k: "All statuses" if k is None else k.replace("_", " ").title())
    all_months = f3.checkbox("All months")
    docs = ds.list_documents(c, cid, year=None if all_months else y, month=None if all_months else m, doc_type=t, status=stt)
    if not docs:
        st.info("No documents for this filter.")
        return

    reviewable = [d for d in docs if d["status"] != "split"]
    # Bank statements are imported on the Bank Reconciliation page, not approved here — keep them out of the
    # approve/decline queue so the "ready to approve" bulk action never tries (and fails) to approve one.
    pending = [d for d in reviewable if d["status"] in ("processed", "needs_review") and d["doc_type"] != "bank_statement"]
    # One bulk query for every pending document's extraction, instead of one query each — this page can easily
    # list dozens of documents, and a query per row would make it noticeably slower.
    extractions = ds.bulk_current_extractions(c, cid, [d["id"] for d in pending]) if pending else {}
    clean, flagged = [], []
    for d in pending:
        ext = extractions.get(d["id"])
        issues = (ext.get("validation") or {}).get("issues", []) if ext else [{"severity": "error", "message": "Extraction result not found"}]
        if any(i["severity"] == "error" for i in issues):
            flagged.append((d, issues, "error"))
        elif issues:
            flagged.append((d, issues, "warning"))
        else:
            clean.append(d)

    if c.can("approve_documents") and pending:
        st.markdown("#### Approval status")
        a, b = st.columns(2)
        with a.container(border=True):
            st.markdown(f"**✅ {len(clean)} ready to approve**")
            st.caption("Every field was read with no issues found — nothing here was guessed or assumed.")
            if clean and st.button(f"Approve all {len(clean)} clean document(s)", type="primary", key="bulk_approve_docs"):
                progress = st.progress(0.0, text=f"Approving 0 of {len(clean)}…")
                ok, errs = 0, []
                from services.db import get_db as _get_db

                with _get_db().transaction():  # one commit for the whole batch instead of one per document
                    for i, d in enumerate(clean, 1):
                        try:
                            ds.approve_document(c, d["id"])
                            ok += 1
                        except Exception as exc:  # noqa: BLE001
                            errs.append(f"{d['original_filename']}: {exc}")
                        progress.progress(i / len(clean), text=f"Approving {i} of {len(clean)}…")
                progress.empty()
                # Stored and shown after the rerun (a message shown right before st.rerun() is cleared before
                # anyone can read it) — this is what made the earlier bulk-approve look like it did nothing.
                st.session_state["bulk_approve_result"] = {"ok": ok, "total": len(clean), "errors": errs}
                st.rerun()
        with b.container(border=True):
            st.markdown(f"**⚠️ {len(flagged)} need your review**")
            st.caption("At least one value could not be confirmed automatically — compare it against the original "
                       "before deciding; nothing here is approved without you looking at it.")
        if flagged:
            st.markdown("**Open for review:**")
            for d, issues, sev in sorted(flagged, key=lambda x: x[2] != "error"):
                icon = "🔴" if sev == "error" else "🟡"
                top = issues[0]["message"] if issues else ""
                r1, r2 = st.columns([5, 1])
                r1.markdown(f"{icon} **{d['original_filename']}** — {top}" + (f" (+{len(issues) - 1} more)" if len(issues) > 1 else ""))
                if r2.button("Open →", key=f"openrow_{d['id']}"):
                    st.session_state["open_doc_id"] = d["id"]
                    st.rerun()
        st.divider()

    with st.expander(f"Full document list ({len(docs)})", expanded=not pending):
        table([{"file": d["original_filename"], "type": d["doc_type"], "status": d["status"],
                "period": f"{d['period_month']:02d}/{d['period_year']}", "flags": len(d.get("review_flags") or []),
                "uploaded": str(d["uploaded_at"])[:16]} for d in docs])

    if not reviewable:
        return
    order = {"needs_review": 0, "processed": 1, "uploaded": 2}
    reviewable.sort(key=lambda d: order.get(d["status"], 3))
    ids = [d["id"] for d in reviewable]
    wanted = st.session_state.get("open_doc_id")
    default_idx = ids.index(wanted) if wanted in ids else 0
    sel = st.selectbox("Open a specific document", ids, index=default_idx,
                       format_func=lambda i: next(f"{d['original_filename']} — {d['status']}" for d in reviewable if d["id"] == i))
    st.session_state["open_doc_id"] = sel
    st.divider()
    _detail(c, next(d for d in reviewable if d["id"] == sel))
