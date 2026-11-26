"""Business client portal — deliberately simple: pick month → upload → submit → confirmation."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from services import document_service as ds, firm_service, report_service as rs
from services.db import get_db
from ui.common import action, badge, ctx, kpi, month_options, page_header, rupees, table
from utils.helpers import fy_label_for, month_bounds

UPLOAD_CATEGORIES = ["sales_invoice", "purchase_invoice", "expense_bill", "bank_statement", "credit_note", "debit_note",
                     "salary_statement", "payment_receipt", "other"]


def _client():
    c = ctx()
    return c, get_db().get("clients", c.client_id)


def dashboard():
    c, client = _client()
    today = dt.date.today()
    page_header(client["name"], f"Financial year {fy_label_for(today, client.get('fy_start_month') or 4)} · managed by {c.firm_name}")
    py, pm = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    due = firm_service.deadline_for(client, py, pm)
    subs = [s for s in ds.list_submissions(c, client["id"]) if (s["period_year"], s["period_month"]) == (py, pm) and s["status"] != "draft"]
    cols = st.columns(4)
    kpi(cols[0], f"Documents for {dt.date(py, pm, 1):%b %Y}", "Submitted ✔" if subs else "Pending")
    kpi(cols[1], "Deadline", f"{due:%d %b %Y}")
    s, e = month_bounds(py, pm)
    p = rs.profit_and_loss_data(client, s, e)
    has_data = p["net_sales"] or p["net_purchases"] or p["indirect_expenses"]
    kpi(cols[2], f"Revenue ({dt.date(py, pm, 1):%b})", rupees(p["net_sales"]) if has_data else "—")
    kpi(cols[3], f"Expenses ({dt.date(py, pm, 1):%b})", rupees(p["net_purchases"] + p["direct_expenses"] + p["indirect_expenses"]) if has_data else "—")
    if has_data:
        st.info(f"Provisional {'profit' if p['net_profit'] >= 0 else 'loss'} for {dt.date(py, pm, 1):%B}: {rupees(abs(p['net_profit']))} "
                "(based on records approved by your CA so far).")
    if not subs:
        st.warning(f"Please upload and submit your {dt.date(py, pm, 1):%B %Y} documents by {due:%d %b %Y}.")
        st.session_state["portal_month"] = (py, pm)
        st.caption("Open **Submit Documents** from the menu to upload.")
    open_q = ds.list_clarifications(c, client["id"], "open")
    if open_q:
        st.subheader(f"Your CA has {len(open_q)} question(s)")
        for q in open_q:
            st.markdown(f"- {q['question']}")
    st.subheader("Reports shared by your CA")
    reps = rs.list_reports(c, client["id"])
    if not reps:
        st.caption("No reports yet.")
    for r in reps[:5]:
        data, _ = rs.report_bytes(c, r["id"])
        st.download_button(f"⬇ {r['title']}", data, file_name=f"{r['report_type']}.{r['file_format']}", key=f"cr_{r['id']}")


def submit_page():
    c, client = _client()
    page_header("Submit documents", "Upload your invoices, bills and bank statements. No typing of amounts needed.")
    opts = month_options(18)
    default = st.session_state.get("portal_month", opts[1] if len(opts) > 1 else opts[0])
    ym = st.selectbox("1️⃣ Which month are these documents for?", opts, index=opts.index(default) if default in opts else 1,
                      format_func=lambda t: dt.date(t[0], t[1], 1).strftime("%B %Y"))
    y, m = ym
    st.caption(f"Due by {firm_service.deadline_for(client, y, m):%d %B %Y}")
    sub = ds.get_or_create_submission(c, client["id"], y, m)
    st.markdown("2️⃣ **Upload documents** — PDF, photos (JPG/PNG), Excel or CSV. One PDF may contain many invoices.")
    cat = st.radio("What are you uploading?", UPLOAD_CATEGORIES, horizontal=True, format_func=lambda k: ds.DOC_TYPES[k])
    files = st.file_uploader("Choose files or take a photo", type=["pdf", "jpg", "jpeg", "png", "xlsx", "csv"], accept_multiple_files=True,
                             key=f"up_{sub['id']}_{cat}")
    if files and st.button("Upload selected files"):
        for f in files:
            with action(f"✔ {f.name}"):
                ds.upload_document(c, client["id"], y, m, f.name, f.getvalue(), cat, submission_id=sub["id"])
    docs = [d for d in ds.list_documents(c, client["id"], year=y, month=m, include_children=False) if d["submission_id"] == sub["id"]]
    st.markdown(f"**Files in this submission: {len(docs)}**")
    for d in docs:
        st.markdown(f"- {d['original_filename']} · {ds.DOC_TYPES.get(d['doc_type'])}")
    notes = st.text_area("Anything your CA should know? (optional)")
    st.markdown("3️⃣ **Submit**")
    if st.button("✅ SUBMIT DOCUMENTS", type="primary", disabled=not docs):
        with action():
            ref = ds.submit_documents(c, sub["id"], notes)
            st.balloons()
            st.success(f"Submitted! Your reference number is **{ref}** ({dt.datetime.now():%d %b %Y %H:%M}). Your CA has been notified.")


def my_documents():
    c, client = _client()
    page_header("My documents", "Everything you have submitted and its processing status.")
    subs = [s for s in ds.list_submissions(c, client["id"]) if s["status"] != "draft"]
    st.subheader("Submission history")
    table([{"reference": s["reference_no"], "month": f"{s['period_month']:02d}/{s['period_year']}", "files": s["doc_count"],
            "submitted": str(s["submitted_at"])[:16], "status": s["status"]} for s in subs])
    st.subheader("Documents")
    docs = ds.list_documents(c, client["id"], include_children=False)
    friendly = {"uploaded": "Received", "processing": "Processing", "processed": "Read — awaiting CA review", "needs_review": "With CA for review",
                "approved": "Accepted", "rejected": "Rejected", "finalized": "Accounted & closed", "split": "Read (multiple invoices)"}
    for d in docs:
        a, b, e = st.columns([4, 2, 1])
        a.write(f"{d['original_filename']} · {d['period_month']:02d}/{d['period_year']}")
        b.markdown(f"{badge(d['status'])} {friendly.get(d['status'], '')}", unsafe_allow_html=True)
        if d["status"] == "rejected" and d.get("error_message"):
            a.caption(f"Reason: {d['error_message']}")
        data, _ = ds.read_document_bytes(c, d["id"])
        e.download_button("⬇", data, file_name=d["original_filename"], key=f"cd_{d['id']}")


def reports_page():
    c, client = _client()
    page_header("Reports from your CA")
    reps = rs.list_reports(c, client["id"])
    if not reps:
        st.info("Your CA has not shared any reports yet.")
    for r in reps:
        data, _ = rs.report_bytes(c, r["id"])
        a, b = st.columns([4, 1])
        a.markdown(f"**{r['title']}**" + (" · provisional" if r["is_provisional"] else "") + f"  \nShared {str(r['shared_at'])[:10]}")
        b.download_button("Download", data, file_name=f"{r['report_type']}.{r['file_format']}", key=f"rp_{r['id']}")


def clarifications_page():
    c, client = _client()
    page_header("Questions from your CA")
    items = ds.list_clarifications(c, client["id"])
    if not items:
        st.info("No questions. 🎉")
    for q in items:
        with st.container(border=True):
            st.markdown(f"{badge(q['status'])} **{q['question']}**" + (f"  \nDocument: {q['original_filename']}" if q.get("original_filename") else ""),
                        unsafe_allow_html=True)
            if q.get("response"):
                st.write(f"Your answer: {q['response']}")
            if q["status"] == "open":
                ans = st.text_area("Your answer", key=f"ans_{q['id']}")
                if st.button("Send answer", key=f"sa_{q['id']}"):
                    with action("Sent"):
                        ds.respond_clarification(c, q["id"], ans)
                        st.rerun()


def profile_page():
    c, client = _client()
    page_header("Business profile")
    st.write(f"**Name:** {client['name']}  \n**GSTIN:** {client.get('gstin') or '—'}  \n**PAN:** {client.get('pan') or '—'}  \n"
             f"**Constitution:** {client.get('business_type') or '—'}  \n**Email:** {client.get('email') or '—'}  \n"
             f"**Phone:** {client.get('phone') or '—'}  \n**CA firm:** {c.firm_name}")
    st.caption("To change these details, please contact your CA firm.")
