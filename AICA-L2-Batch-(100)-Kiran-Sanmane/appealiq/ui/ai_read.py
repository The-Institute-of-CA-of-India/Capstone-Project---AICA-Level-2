"""Read with local AI (CR-010): the offline fallback offered in Review & Edit when the Standard
engine is unsure of the order type or finds no issue.

The read runs in a background thread (``pipeline.AIReadJob``) on a copy of the case; this panel
polls its progress every 2 seconds (model call n of m, seconds elapsed) and, when it finishes,
adds the suggestion and the issues to the current case. Nothing leaves this computer: only the
local server in Settings → Local AI is used.
"""

from __future__ import annotations

import streamlit as st

from appealiq import pipeline
from appealiq.models import CaseFile
from appealiq.ui import state, theme

JOB_KEY = "ai_read_job"


def busy() -> bool:
    """True while a local-AI read is running."""
    return st.session_state.get(JOB_KEY) is not None


def _start(case: CaseFile) -> None:
    engine = pipeline.local_reader(state.settings(), state.paths())
    st.session_state[JOB_KEY] = pipeline.AIReadJob(case.model_copy(deep=True), engine).start()


@st.fragment(run_every=2)
def _progress() -> None:
    job = st.session_state.get(JOB_KEY)
    if job is None:
        return
    snap = job.snapshot()
    if snap.finished and job.result is not None:
        st.session_state.pop(JOB_KEY, None)
        current = state.current_case()
        read = job.result
        if current is not None and read.ok:
            s = state.settings()
            merged = pipeline.apply_ai_read(current, read, state.kb(), today=state.today(),
                                            rag=s.rag, materiality=s.materiality)
            state.set_case(merged)
            pipeline.save_edits(merged, state.paths())
        st.session_state[state.NOTICE_KEY] = ("neutral" if read.ok else "amber", read.message)
        st.rerun()
    st.progress(snap.done / max(snap.total, 1),
                text=f"Local AI: {snap.done} of {snap.total} step(s) done"
                     + (f" — working on {snap.step}" if snap.step else "")
                     + f" · {snap.seconds:.0f} s elapsed. You can keep reviewing meanwhile.")
    if st.button("Cancel local AI", key="ai_read_cancel"):
        job.cancel()


def render_offer(case: CaseFile, *, title: str = "Read with local AI (offline)") -> None:
    """The offer: what the local model will do, the button, and the progress bar."""
    classify, find = pipeline.ai_read_needed(case)
    if not (classify or find) and not busy():
        return
    s = state.settings()
    what = " and ".join(x for x in (classify and "suggest the order type",
                                    find and "point at the grounds and decisions") if x)
    with st.expander(title, expanded=True, icon=":material/smart_toy:"):
        st.caption(f"{s.lmstudio.server_label} on this computer will {what}. Every quote is "
                   "checked against the order; sections, amounts and dates are read by the "
                   "program from the quotes; anything that cannot be found is marked UNVERIFIED "
                   "for you to confirm. Nothing is sent outside this computer.")
        if st.button("Read with local AI", key="ai_read_start", disabled=busy(),
                     type="primary"):
            _start(case)
            st.rerun()
        _progress()


def render_suggestion(case: CaseFile) -> None:
    """The local model's order-type suggestion with its verified quotes (never applied by
    itself: the reviewer confirms the order type)."""
    c = case.classification
    if c is None or not c.ai_label:
        return
    quotes = "; ".join(f"“{e.source_snippet}” (p.{e.page})" for e in c.ai_evidence[:3])
    theme.render_callout(
        f"Local AI suggests: {c.ai_label}." + (f" Quotes found in the order: {quotes}."
                                               if quotes else " Its quotes could not be found "
                                               "in the order, so the suggestion is not used."),
        tone="neutral", title="Local AI suggestion")
