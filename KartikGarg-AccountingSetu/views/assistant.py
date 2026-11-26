"""AI financial assistant chat."""
from __future__ import annotations

import streamlit as st

from config import settings
from services import admin_service, assistant_service
from ui.common import ctx, page_header, selected_client_id, table

EXAMPLES = ["What were my sales this month?", "How much GST liability is estimated?", "Which purchase invoices are missing from GSTR-2B?",
            "Which bank transactions are unmatched?", "What is my monthly profit?", "Compare this month with the previous month",
            "Which clients have not submitted documents?", "Which invoices contain duplicate numbers?",
            "What is my outstanding receivable balance?", "Show my top customers"]


def page():
    c = ctx()
    page_header("Ask Setu", "Answers come from your authorised, approved records. Figures are computed by the accounting engine, not by AI.")
    if not admin_service.feature_enabled("assistant"):
        st.info("The assistant is disabled by the platform administrator.")
        return
    st.caption(f"Question understanding: {'Claude (' + settings.anthropic_model + ')' if settings.anthropic_enabled else 'built-in keyword matching'}")
    hist = st.session_state.setdefault("chat", [])
    cols = st.columns(5)
    clicked = None
    for i, ex in enumerate(EXAMPLES if c.is_staff else [e for e in EXAMPLES if "clients" not in e]):
        if cols[i % 5].button(ex, key=f"ex_{i}"):
            clicked = ex
    for h in hist:
        with st.chat_message(h["role"]):
            st.markdown(h["text"])
            if h.get("records"):
                with st.expander(f"Underlying records ({len(h['records'])})"):
                    table(h["records"])
    q = st.chat_input("Ask about sales, GST, bank, profit…") or clicked
    if q:
        hist.append({"role": "user", "text": q})
        try:
            r = assistant_service.answer(c, q, selected_client_id())
            text = r["answer"] + (f"\n\n*Period: {r.get('period')}*" if r.get("period") else "")
            if r.get("notes"):
                text += "\n\n" + "\n".join(f"- {n}" for n in r["notes"])
            hist.append({"role": "assistant", "text": text, "records": r.get("records")})
        except Exception as exc:
            hist.append({"role": "assistant", "text": f"I couldn't answer that: {exc}"})
        st.rerun()
