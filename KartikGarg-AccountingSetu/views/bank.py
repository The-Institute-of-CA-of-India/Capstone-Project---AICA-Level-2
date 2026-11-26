"""Bank statements: accounts, import, classification, automatic & manual matching, vouchers, BRS."""
from __future__ import annotations

import streamlit as st

from services import bank_service as bs, document_service as ds, ocr_service, report_service
from ui.common import action, ctx, page_header, require_client_selected, rupees, selected_period, table
from utils.helpers import D, month_bounds


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    s, e = month_bounds(y, m)
    page_header("Bank reconciliation", f"{m:02d}/{y}")
    accounts = bs.list_bank_accounts(c, cid)
    with st.expander("➕ Add bank account", expanded=not accounts):
        with st.form("bank_acct"):
            a, b, d = st.columns(3)
            bank = a.text_input("Bank name")
            no = b.text_input("Account number (only last 4 digits are stored)")
            ifsc = d.text_input("IFSC")
            if st.form_submit_button("Create", disabled=not c.can("bank_reconcile")):
                with action("Bank account and ledger created"):
                    bs.create_bank_account(c, cid, bank, no, ifsc)
                    st.rerun()
    if not accounts:
        return
    acct = st.selectbox("Bank account", [a["id"] for a in accounts], format_func=lambda i: next(a["ledger_name"] for a in accounts if a["id"] == i))
    t1, t2, t3, t4 = st.tabs(["Import statement", "Transactions & matching", "Generate vouchers", "Reconciliation statement"])
    with t1:
        pending = [d for d in ds.list_documents(c, cid, doc_type="bank_statement") if d["status"] in ("processed", "needs_review")]
        if pending:
            st.markdown("**Statements submitted by the client**")
            for d in pending:
                ext = ds.current_extraction(c, d["id"])
                data = (ext or {}).get("data") or {}
                n = len(data.get("transactions") or [])
                a, b = st.columns([3, 1])
                a.write(f"{d['original_filename']} — {n} transaction(s); warnings: {len(data.get('warnings') or [])}")
                if n and b.button("Import", key=f"imp_{d['id']}", disabled=not c.can("bank_reconcile")):
                    with action():
                        st.success(str(bs.import_statement(c, cid, acct, data, document_id=d["id"])))
                        st.rerun()
        st.markdown("**Upload a statement directly** (CSV / Excel export from net banking is most reliable; digital PDF supported)")
        f = st.file_uploader("Statement file", type=["csv", "xlsx", "pdf"])
        if f:
            ext = "." + f.name.rsplit(".", 1)[-1].lower()
            parsed = bs.parse_statement_file(f.getvalue(), ext)
            for w in parsed["warnings"]:
                st.warning(w)
            table(parsed["transactions"][:300])
            if parsed["transactions"] and st.button("Import these transactions", type="primary", disabled=not c.can("bank_reconcile")):
                with action():
                    st.success(str(bs.import_statement(c, cid, acct, parsed)))
    with t2:
        status = st.selectbox("Match status", [None] + bs.MATCH_STATUSES, format_func=lambda x: x or "All")
        txns = bs.list_transactions(c, cid, acct, s, e, status)
        a, b = st.columns([1, 3])
        if a.button("⚡ Run automatic matching", disabled=not c.can("bank_reconcile")):
            with action():
                st.success(str(bs.auto_match(c, cid, acct)))
                st.rerun()
        b.caption("Only exact, unambiguous matches (score ≥ 85, full amount) are matched automatically; everything else is suggested for review.")
        table([{"date": str(t["txn_date"]), "narration": t["narration"][:60], "ref": t.get("reference"), "debit": D(t["debit"]),
                "credit": D(t["credit"]), "balance": D(t["balance"], None), "category": t["category"], "status": t["match_status"],
                "score": t.get("match_score"), "voucher": "yes" if t.get("voucher_id") else ""} for t in txns])
        if txns:
            tid = st.selectbox("Work on transaction", [t["id"] for t in txns],
                               format_func=lambda i: next(f"{t['txn_date']} · {t['narration'][:50]} · {D(t['debit']) or D(t['credit'])}" for t in txns if t["id"] == i))
            t = next(x for x in txns if x["id"] == tid)
            a, b = st.columns(2)
            cat = a.selectbox("Category", list(bs.CATEGORIES), index=list(bs.CATEGORIES).index(t["category"]), format_func=lambda k: bs.CATEGORIES[k])
            if a.button("Set category"):
                with action("Category updated"):
                    bs.set_category(c, tid, cat, t.get("party_ledger_id"))
                    st.rerun()
            sugg = bs.suggestions(c, tid)
            if sugg:
                b.markdown("**Suggestions**")
                for sg in sugg:
                    b.write(f"{sg.get('label', sg['target_type'])} · ₹{sg['amount']} · score {sg['score']} · {sg['status']} · {', '.join(sg.get('reasons') or [])}")
            side = "cr" if D(t["credit"]) > 0 else "dr"
            invs = bs.open_invoices(cid, side)
            st.markdown("**Manual match against open invoices**")
            chosen = st.multiselect("Invoices", [i["id"] for i in invs],
                                    format_func=lambda i: next(f"{x['invoice_no']} · {x['party_name']} · outstanding {x['outstanding']}" for x in invs if x["id"] == i))
            amounts = {i: st.number_input(f"Amount for {next(x['invoice_no'] for x in invs if x['id'] == i)}", 0.0,
                                          value=float(next(x["outstanding"] for x in invs if x["id"] == i)), key=f"amt_{tid}_{i}") for i in chosen}
            a, b, d = st.columns(3)
            if a.button("Confirm match", type="primary", disabled=not chosen):
                with action():
                    st.success(bs.confirm_match(c, tid, [{"target_type": "invoice", "target_id": i, "amount": str(v)} for i, v in amounts.items()]))
                    st.rerun()
            if b.button("Remove match"):
                with action("Match removed"):
                    bs.unmatch(c, tid)
                    st.rerun()
            if d.button("Mark duplicate" if t["match_status"] != "duplicate" else "Not a duplicate"):
                with action("Updated"):
                    bs.mark_duplicate(c, tid, t["match_status"] != "duplicate")
                    st.rerun()
    with t3:
        txns = [t for t in bs.list_transactions(c, cid, acct, s, e) if not t.get("voucher_id") and t["match_status"] != "duplicate"]
        st.caption("Creates DRAFT Receipt / Payment / Contra vouchers. Uncertain classifications go to Suspense and are flagged for review.")
        table([{"date": str(t["txn_date"]), "narration": t["narration"][:60], "debit": D(t["debit"]), "credit": D(t["credit"]),
                "category": t["category"], "status": t["match_status"]} for t in txns])
        if txns and st.button(f"Generate draft vouchers for {len(txns)} transaction(s)", type="primary", disabled=not c.can("prepare_vouchers")):
            with action():
                r = bs.generate_vouchers(c, cid, [t["id"] for t in txns])
                st.success(f"Created {r['created']}, skipped {r['skipped']}")
                for err in r["errors"]:
                    st.error(err)
    with t4:
        as_of = st.date_input("As on", e, format="DD/MM/YYYY")
        rec = bs.reconciliation(c, cid, acct, as_of)
        cols = st.columns(4)
        cols[0].metric("Balance as per books", rupees(rec["book_balance"]))
        cols[1].metric("Balance as per bank", rupees(rec["statement_balance"]) if rec["statement_available"] else "No statement")
        cols[2].metric("Matched transactions", rec["matched_count"])
        cols[3].metric("Difference", rupees(rec["difference"]))
        if rec["difference"]:
            st.warning("Unexplained difference — check opening balance of the bank ledger and unimported statement periods.")
        st.markdown(f"**Add: deposits recorded in books, not yet credited by bank** — {rupees(rec['pending_deposits_total'])}")
        table([{"date": str(x["voucher_date"]), "voucher": x["voucher_no"], "narration": x["narration"], "amount": D(x["amount"])} for x in rec["pending_deposits"]])
        st.markdown(f"**Less: payments recorded in books, not yet debited by bank** — {rupees(rec['pending_payments_total'])}")
        table([{"date": str(x["voucher_date"]), "voucher": x["voucher_no"], "narration": x["narration"], "amount": D(x["amount"])} for x in rec["pending_payments"]])
        st.markdown(f"**Bank entries not yet in books** — credits {rupees(rec['bank_credits_not_in_books'])}, debits {rupees(rec['bank_debits_not_in_books'])}")
        table([{"date": str(t["txn_date"]), "narration": t["narration"][:60], "debit": D(t["debit"]), "credit": D(t["credit"])} for t in rec["not_in_books"]])
        rows = [{"particulars": "Balance as per bank statement", "amount": rec["statement_balance"] or D(0)},
                {"particulars": "Add: deposits not yet credited", "amount": rec["pending_deposits_total"]},
                {"particulars": "Less: payments not yet debited", "amount": rec["pending_payments_total"]},
                {"particulars": "Adjusted bank balance", "amount": rec["adjusted_bank_balance"]},
                {"particulars": "Balance as per books", "amount": rec["book_balance"]},
                {"particulars": "Add: bank credits not in books", "amount": rec["bank_credits_not_in_books"]},
                {"particulars": "Less: bank debits not in books", "amount": rec["bank_debits_not_in_books"]},
                {"particulars": "Adjusted book balance", "amount": rec["adjusted_book_balance"]},
                {"particulars": "Difference", "amount": rec["difference"]}]
        pdf = report_service.to_pdf("Bank Reconciliation Statement", f"{rec['bank_ledger']} · as on {as_of:%d-%b-%Y}", [("Summary", rows)])
        st.download_button("⬇ BRS (PDF)", pdf, file_name=f"BRS_{as_of}.pdf", mime="application/pdf")
