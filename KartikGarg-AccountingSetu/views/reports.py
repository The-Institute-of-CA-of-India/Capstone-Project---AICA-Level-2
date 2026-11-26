"""Financial reports with charts, comparisons, PDF/Excel export and CA approval before sharing."""
from __future__ import annotations

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from services import accounting_engine as ae, bank_service as bs, gst_service as gs, report_service as rs
from services.db import get_db
from ui.common import action, badge, ctx, page_header, require_client_selected, rupees, selected_period, table
from utils.helpers import D, fy_bounds, month_bounds


def _export(c, cid, key, title, sheets, sections, start, end, provisional, notes=None):
    client = get_db().get("clients", cid)
    subtitle = f"{client['name']} · {start:%d-%b-%Y} to {end:%d-%b-%Y}"
    banner = "PROVISIONAL / INCOMPLETE — NOT A FINAL STATEMENT" if provisional else None
    pdf = rs.to_pdf(title, subtitle, sections, notes, banner)
    xls = rs.to_excel(sheets, f"{title} — {subtitle}")
    a, b, d = st.columns(3)
    a.download_button("⬇ PDF", pdf, file_name=f"{key}_{end}.pdf", mime="application/pdf", key=f"pdf_{key}")
    b.download_button("⬇ Excel", xls, file_name=f"{key}_{end}.xlsx", key=f"xls_{key}")
    if c.can("generate_reports") and d.button("Save for approval/sharing", key=f"save_{key}"):
        with action("Saved — approve and share it in the 'Saved & shared' tab"):
            rs.save_report(c, cid, key, f"{title} ({start:%d-%b-%y} to {end:%d-%b-%y})", pdf, "pdf", start, end, provisional)


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    fy = st.session_state.get("fy")
    page_header("Reports", "Generated from approved vouchers only.")
    scope = st.radio("Period", ["Selected month", "Financial year to date", "Custom"], horizontal=True)
    if scope == "Selected month":
        start, end = month_bounds(y, m)
    elif scope == "Financial year to date":
        start, end = fy_bounds(fy)
        end = min(end, dt.date.today())
    else:
        a, b = st.columns(2)
        start, end = a.date_input("From", month_bounds(y, m)[0], format="DD/MM/YYYY"), b.date_input("To", month_bounds(y, m)[1], format="DD/MM/YYYY")
    tabs = st.tabs(["Overview", "P&L", "Balance Sheet", "Trial Balance", "Registers", "Books & Ledgers", "Debtors/Creditors",
                    "GST summary", "Voucher register", "Saved & shared"])
    with tabs[0]:
        series = rs.monthly_series(c, cid, fy)
        if series:
            fig = go.Figure()
            fig.add_bar(x=[s["month"] for s in series], y=[float(s["sales"]) for s in series], name="Sales", marker_color="#0B2545")
            fig.add_bar(x=[s["month"] for s in series], y=[float(s["purchases"] + s["expenses"]) for s in series], name="Purchases + expenses",
                        marker_color="#94A3B8")
            fig.add_scatter(x=[s["month"] for s in series], y=[float(s["net_profit"]) for s in series], name="Net profit",
                            line=dict(color="#C9A227", width=3))
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), barmode="group", title=f"FY {fy} monthly trend")
            st.plotly_chart(fig, width="stretch")
        comp = rs.comparison(c, cid, y, m)
        st.subheader(f"{m:02d}/{y} compared")
        table(comp["rows"])
        if not comp["last_year_available"]:
            st.caption("Previous-year comparison shown only where approved data exists.")
    with tabs[1]:
        p = rs.profit_and_loss(c, cid, start, end)
        if p["is_provisional"]:
            st.markdown("<div class='as-provisional'>Provisional — " + "; ".join(p["completeness"][:4]) + "</div>", unsafe_allow_html=True)
        for n in p["notes"]:
            st.warning(n)
        rows = rs.pnl_rows(p)
        table(rows)
        for grp, items in p["detail"].items():
            with st.expander(grp):
                table(items)
        _export(c, cid, "pnl", "Profit and Loss Account", {"P&L": rows}, [("Profit and Loss", rows)], start, end, p["is_provisional"], p["notes"])
    with tabs[2]:
        bsd = rs.balance_sheet(c, cid, end)
        st.markdown(f"<div class='as-provisional'>{bsd['label']}</div>" if bsd["is_provisional"] else f"**{bsd['label']}**", unsafe_allow_html=True)
        for r in bsd["provisional_reasons"]:
            st.warning(r)
        a, b = st.columns(2)
        with a:
            st.markdown("**Liabilities & capital**")
            table(rs.bs_rows(bsd, "liabilities"))
            st.metric("Total", rupees(bsd["total_liabilities"]))
        with b:
            st.markdown("**Assets**")
            table(rs.bs_rows(bsd, "assets"))
            st.metric("Total", rupees(bsd["total_assets"]))
        st.caption("A complete Balance Sheet needs opening balances, fixed assets & depreciation, closing stock, loans and provisions "
                   "(Accounting → Opening balances & stock / Manual journal).")
        _export(c, cid, "bs", "Balance Sheet", {"Liabilities": rs.bs_rows(bsd, "liabilities"), "Assets": rs.bs_rows(bsd, "assets")},
                [("Liabilities & Capital", rs.bs_rows(bsd, "liabilities")), ("Assets", rs.bs_rows(bsd, "assets"))],
                fy_bounds(fy)[0], end, bsd["is_provisional"], bsd["provisional_reasons"])
    with tabs[3]:
        tb = rs.trial_balance(c, cid, start, end)
        rows = [{k: r[k] for k in ("ledger", "group", "opening", "period_debit", "period_credit", "debit", "credit")} for r in tb["rows"]]
        table(rows)
        st.write(f"Totals: Dr {rupees(tb['total_debit'])} · Cr {rupees(tb['total_credit'])} · Difference {rupees(tb['difference'])}")
        _export(c, cid, "tb", "Trial Balance", {"Trial Balance": rows}, [("Trial Balance", rows)], start, end, bool(tb["difference"]))
    with tabs[4]:
        kind = st.selectbox("Register", ["sales", "purchase", "expense"], format_func=lambda k: f"{k.title()} register")
        rows = rs.register(c, cid, kind, start, end)
        table(rows)
        _export(c, cid, f"{kind}_register", f"{kind.title()} Register", {kind: rows}, [(f"{kind.title()} Register", rows)], start, end, False)
    with tabs[5]:
        mode = st.selectbox("Book", ["Bank Book", "Cash Book", "General Ledger"])
        if mode == "General Ledger":
            leds = ae.list_ledgers(c, cid)
            lid = st.selectbox("Ledger", [l["id"] for l in leds], format_func=lambda i: next(l["name"] for l in leds if l["id"] == i))
            books = [rs.general_ledger(c, cid, lid, start, end)]
        else:
            books = rs.book(c, cid, "Bank Accounts" if mode == "Bank Book" else "Cash-in-Hand", start, end)
        for bk in books:
            st.markdown(f"**{bk['ledger']}** — opening {rupees(bk['opening'])}, closing {rupees(bk['closing'])}")
            table(bk["rows"])
        if books:
            sheets = {bk["ledger"][:28]: bk["rows"] for bk in books}
            _export(c, cid, mode.lower().replace(" ", "_"), mode, sheets, [(bk["ledger"], bk["rows"]) for bk in books], start, end, False)
    with tabs[6]:
        grp = st.radio("Report", ["Sundry Debtors", "Sundry Creditors"], horizontal=True)
        rows = rs.party_balances(c, cid, end, grp)
        table(rows)
        st.write(f"Total: {rupees(sum((r['balance'] for r in rows), D(0)))}")
        key = "debtors" if grp == "Sundry Debtors" else "creditors"
        _export(c, cid, key, "Debtors Report" if key == "debtors" else "Creditors Report", {key: rows}, [(grp, rows)], start, end, False)
    with tabs[7]:
        g = gs.gst_summary(c, cid, start, end)
        rows = [{"head": h.upper(), "output_tax": g["output"][h], "eligible_itc": g["input_eligible"][h], "rcm": g["rcm"][h],
                 "other_input_tax": g["input_other"][h], "estimated_net": g["estimated_net_liability"][h]} for h in ("igst", "cgst", "sgst", "cess")]
        table(rows)
        _export(c, cid, "gst_summary", "GST Summary", {"GST": rows}, [("GST Summary", rows)], start, end, True,
                ["Estimate before Rule 88A set-off and GSTR-2B reconciliation"])
    with tabs[8]:
        rows = rs.voucher_register(c, cid, start, end)
        table(rows)
        _export(c, cid, "voucher_register", "Voucher Register", {"Vouchers": rows}, [("Voucher Register", rows)], start, end, False)
    with tabs[9]:
        reps = rs.list_reports(c, cid)
        for r in reps:
            a, b, d, e = st.columns([4, 1, 1, 1])
            a.markdown(f"{r['title']} {badge(r['status'])} {'· provisional' if r['is_provisional'] else ''}", unsafe_allow_html=True)
            data, _ = rs.report_bytes(c, r["id"])
            b.download_button("⬇", data, file_name=f"{r['report_type']}.{r['file_format']}", key=f"dlr_{r['id']}")
            if r["status"] in ("draft", "approved") and c.can("approve_reports") and d.button("Approve & share", key=f"sh_{r['id']}"):
                with action("Shared with client"):
                    rs.approve_and_share(c, r["id"])
                    st.rerun()
            if r["status"] == "shared" and c.can("approve_reports") and e.button("Withdraw", key=f"wd_{r['id']}"):
                with action("Withdrawn"):
                    rs.withdraw_report(c, r["id"])
                    st.rerun()
        if not reps:
            st.info("No saved reports yet.")
