"""Vouchers, approval workflow, manual journals, ledgers & mappings, opening balances, closing stock."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from services import accounting_engine as ae
from ui.common import action, badge, ctx, page_header, require_client_selected, rupees, selected_period, table
from utils.helpers import D, ZERO, fy_bounds, month_bounds


def _ledger_names(c, cid):
    leds = ae.list_ledgers(c, cid)
    return {l["id"]: f"{l['name']}  ·  {l['group_name']}" for l in leds}, leds


def _lines_editor(key, names, rows):
    df = pd.DataFrame(rows or [{"ledger": None, "dr_cr": "Dr", "amount": 0.0}, {"ledger": None, "dr_cr": "Cr", "amount": 0.0}])
    inv = {v: k for k, v in names.items()}
    df["ledger"] = df["ledger"].map(lambda x: names.get(x, x))
    edited = st.data_editor(df, num_rows="dynamic", width="stretch", key=key, column_config={
        "ledger": st.column_config.SelectboxColumn("Ledger", options=sorted(names.values()), required=True),
        "dr_cr": st.column_config.SelectboxColumn("Dr/Cr", options=["Dr", "Cr"], required=True),
        "amount": st.column_config.NumberColumn("Amount", min_value=0.0, format="%.2f")})
    lines = [ae.Line(inv[r["ledger"]], r["dr_cr"], D(str(r["amount"]))) for r in edited.to_dict("records")
             if r.get("ledger") in inv and r.get("amount")]
    dr, cr = ae.totals(lines)
    (st.success if dr == cr and dr > 0 else st.warning)(f"Debit {rupees(dr)} · Credit {rupees(cr)} · Difference {rupees(dr - cr)}")
    return lines


def _vouchers(c, cid, y, m):
    s, e = month_bounds(y, m)
    a, b, d = st.columns(3)
    status = a.selectbox("Status", [None, "draft", "approved", "rejected", "cancelled"], format_func=lambda x: x or "All")
    vtype = b.selectbox("Type", [None] + ae.VOUCHER_TYPES, format_func=lambda x: x or "All")
    only_review = d.checkbox("Only flagged for review")
    vs = ae.list_vouchers(c, cid, date_from=s, date_to=e, status=status, voucher_type=vtype)
    if only_review:
        vs = [v for v in vs if v["needs_review"]]
    table([{"date": str(v["voucher_date"]), "no": v["voucher_no"], "type": v["voucher_type"], "party": v.get("party_name"),
            "amount": D(v["total_amount"]), "status": v["status"], "review": v.get("review_reason") or "", "source": v["source_type"]}
           for v in vs])
    drafts = [v for v in vs if v["status"] == "draft" and not v["needs_review"]]
    if drafts and c.can("approve_vouchers") and st.button(f"Approve all {len(drafts)} unflagged draft voucher(s)"):
        with action("Approved"):
            for v in drafts:
                ae.approve_voucher(c, v["id"])
            st.rerun()
    if not vs:
        return
    vid = st.selectbox("Open voucher", [v["id"] for v in vs], format_func=lambda i: next(f"{v['voucher_no']} · {v['voucher_type']} · {v['status']}" for v in vs if v["id"] == i))
    v = next(x for x in vs if x["id"] == vid)
    st.markdown(f"#### {v['voucher_no']} {badge(v['status'])}", unsafe_allow_html=True)
    st.caption(f"{v['voucher_date']} · {v.get('narration') or ''}")
    if v["needs_review"]:
        st.warning(f"Flagged for review: {v.get('review_reason')}")
    lines = ae.get_voucher_lines(vid)
    table([{"ledger": l["ledger_name"], "group": l["group_name"], "debit": D(l["amount"]) if l["dr_cr"] == "Dr" else None,
            "credit": D(l["amount"]) if l["dr_cr"] == "Cr" else None} for l in lines])
    if v["status"] in ("draft", "rejected") and c.can("prepare_vouchers"):
        with st.expander("✏️ Edit lines (draft)"):
            names, _ = _ledger_names(c, cid)
            new = _lines_editor(f"ed_{vid}", names, [{"ledger": l["ledger_id"], "dr_cr": l["dr_cr"], "amount": float(D(l["amount"]))} for l in lines])
            narr = st.text_input("Narration", v.get("narration") or "", key=f"narr_{vid}")
            if st.button("Save voucher", key=f"sv_{vid}"):
                with action("Voucher updated"):
                    ae.update_voucher(c, vid, new, narration=narr)
                    st.rerun()
    if c.can("approve_vouchers") and v["status"] != "cancelled":
        a, b, d = st.columns(3)
        if v["status"] in ("draft", "rejected"):
            ack = a.checkbox("Classification reviewed", key=f"ack_{vid}") if v["needs_review"] else False
            if a.button("Approve", type="primary", key=f"ap_{vid}", disabled=v["needs_review"] and not ack):
                with action("Approved"):
                    ae.approve_voucher(c, vid, acknowledge_review=ack)
                    st.rerun()
        reason = b.text_input("Reason", key=f"rs_{vid}")
        if v["status"] == "draft" and b.button("Reject", key=f"rj_{vid}"):
            with action("Rejected"):
                ae.reject_voucher(c, vid, reason or "rejected")
                st.rerun()
        if d.button("Cancel voucher", key=f"cx_{vid}"):
            with action("Cancelled"):
                ae.cancel_voucher(c, vid, reason or "cancelled")
                st.rerun()


def _manual(c, cid, y, m):
    st.caption("Use for adjustments, depreciation, provisions, contra entries and anything not captured from documents.")
    names, _ = _ledger_names(c, cid)
    a, b = st.columns(2)
    vtype = a.selectbox("Voucher type", ae.VOUCHER_TYPES, index=ae.VOUCHER_TYPES.index("Journal"))
    date = b.date_input("Date", month_bounds(y, m)[1], format="DD/MM/YYYY")
    lines = _lines_editor("manual_lines", names, None)
    narr = st.text_input("Narration")
    if st.button("Save as draft voucher", type="primary", disabled=not c.can("prepare_vouchers")):
        with action("Draft voucher created — approve it in the Vouchers tab"):
            ae.create_voucher(c, cid, ae.VoucherDraft(vtype, date, lines, narration=narr), source_type="adjustment")


def _ledgers(c, cid):
    _, leds = _ledger_names(c, cid)
    table([{"name": l["name"], "group": l["group_name"], "nature": l["nature"], "gstin": l.get("party_gstin") or "",
            "system": "Yes" if l["is_system"] else ""} for l in leds])
    if c.can("manage_ledgers"):
        with st.form("new_ledger"):
            a, b, d = st.columns(3)
            nm = a.text_input("Ledger name")
            grp = b.selectbox("Group", sorted(ae.GROUP_NATURE))
            g = d.text_input("Party GSTIN (optional)")
            if st.form_submit_button("Create ledger"):
                with action("Ledger created"):
                    ae.create_ledger(c, cid, nm, grp, g.strip().upper() or None)
                    st.rerun()
    st.subheader("Ledger mapping (used by the automatic accounting rules)")
    maps = ae.list_mappings(c, cid)
    table(maps, drop_ids=True)
    if c.can("manage_ledgers") and maps:
        a, b, d = st.columns([2, 3, 1])
        key = a.selectbox("Mapping", [x["mapping_key"] for x in maps])
        lid = b.selectbox("Ledger", [l["id"] for l in leds], format_func=lambda i: next(l["name"] for l in leds if l["id"] == i))
        if d.button("Update"):
            with action("Mapping updated"):
                ae.set_mapping(c, cid, key, lid)
                st.rerun()


def _opening(c, cid):
    fy = st.session_state.get("fy")
    st.caption(f"Opening balances for FY {fy}. Required for a reliable Balance Sheet (capital, loans, fixed assets, debtors, "
               "creditors, bank, cash, stock).")
    _, leds = _ledger_names(c, cid)
    ob = ae.opening_balances(cid, fy)
    rows = [{"ledger": l["name"], "group": l["group_name"], "debit": float(ob.get(l["id"], ZERO)) if ob.get(l["id"], ZERO) > 0 else 0.0,
             "credit": float(-ob.get(l["id"], ZERO)) if ob.get(l["id"], ZERO) < 0 else 0.0, "_id": l["id"]}
            for l in leds if l["nature"] in ("asset", "liability", "equity")]
    df = pd.DataFrame(rows)
    edited = st.data_editor(df.drop(columns=["_id"]), width="stretch", disabled=["ledger", "group"], key="ob_editor",
                            column_config={"debit": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                                           "credit": st.column_config.NumberColumn(format="%.2f", min_value=0.0)})
    td, tc = D(str(edited["debit"].sum())), D(str(edited["credit"].sum()))
    (st.success if td == tc else st.warning)(f"Total Dr {rupees(td)} · Total Cr {rupees(tc)} · Difference {rupees(td - tc)}")
    if st.button("Save opening balances", type="primary", disabled=not c.can("prepare_vouchers")):
        with action("Opening balances saved"):
            for (_, r), lid in zip(edited.iterrows(), df["_id"]):
                dr, cr = D(str(r["debit"])), D(str(r["credit"]))
                if dr and cr:
                    raise ValueError(f"{r['ledger']}: enter either debit or credit, not both")
                cur = ob.get(lid, ZERO)
                new = dr - cr
                if new != cur:
                    ae.set_opening_balance(c, cid, fy, lid, abs(new), "Dr" if new >= 0 else "Cr")
    st.subheader("Closing stock")
    a, b, d = st.columns(3)
    as_of = a.date_input("As on", fy_bounds(fy)[1] if fy else dt.date.today(), format="DD/MM/YYYY")
    cur = ae.closing_stock_at(cid, as_of)
    amt = b.number_input("Value (₹)", 0.0, value=float(cur or 0), step=1000.0)
    basis = d.text_input("Valuation basis", "Cost or NRV, whichever lower")
    if st.button("Save closing stock", disabled=not c.can("prepare_vouchers")):
        with action("Closing stock saved"):
            ae.set_closing_stock(c, cid, as_of, D(str(amt)), basis)


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    page_header("Accounting", f"Double-entry vouchers · {m:02d}/{y}")
    t1, t2, t3, t4 = st.tabs(["Vouchers & approval", "Manual journal / adjustment", "Ledgers & mapping", "Opening balances & stock"])
    with t1:
        _vouchers(c, cid, y, m)
    with t2:
        _manual(c, cid, y, m)
    with t3:
        _ledgers(c, cid)
    with t4:
        _opening(c, cid)
