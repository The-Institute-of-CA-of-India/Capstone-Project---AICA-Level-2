"""On-demand AI notes (summary + strategy note) for the Review step (SPEC §8.9, §10.3).

The analysis itself is Standard and finishes in seconds; the reviewer then asks for AI notes per
adverse issue ("Generate AI note") or for all adverse issues. The work runs in a background thread
(``pipeline.AINotesJob``) on a copy of the CaseFile; this panel polls its progress every 2 seconds
and merges the notes into the current CaseFile when it finishes.
"""

from __future__ import annotations

import streamlit as st

from appealiq import pipeline
from appealiq.models import CaseFile, Issue
from appealiq.ui import state, theme

JOB_KEY = "ai_notes_job"
KIND_KEY = "ai_notes_engine"
MSG_WITHHELD = "AI note withheld — failed validation"


def engine_options(case: CaseFile) -> list[str]:
    """AI engines the reviewer may use for notes: local always; cloud only if acknowledged."""
    return ["lmstudio", "claude"] if case.cloud_ack else ["lmstudio"]


def _kind(case: CaseFile) -> str:
    options = engine_options(case)
    current = st.session_state.get(KIND_KEY)
    if current not in options:
        current = case.inputs.engine if case.inputs.engine in options else options[0]
        st.session_state[KIND_KEY] = current
    return current


def _start(case: CaseFile, issue_ids: list[str], grounds: bool) -> None:
    kind = _kind(case)
    engine = pipeline.build_engine(kind, state.settings(), state.paths(),
                                   cloud_ack=case.cloud_ack)
    if not isinstance(engine, pipeline.LLMEngine):
        st.session_state[state.NOTICE_KEY] = ("amber", "AI notes need the local or cloud engine.")
        return
    job = pipeline.AINotesJob(case.model_copy(deep=True), engine, issue_ids,
                              rephrase_grounds=grounds).start()
    st.session_state[JOB_KEY] = (job, issue_ids)


def busy() -> bool:
    """True while a notes job is running."""
    return st.session_state.get(JOB_KEY) is not None


@st.fragment(run_every=2)
def _progress() -> None:
    entry = st.session_state.get(JOB_KEY)
    if entry is None:
        return
    job, issue_ids = entry
    snap = job.snapshot()
    if snap.finished:
        st.session_state.pop(JOB_KEY, None)
        current = state.current_case()
        if current is not None:
            merged = pipeline.merge_ai_notes(current, job.case, issue_ids)
            state.set_case(merged)
            pipeline.save_edits(merged, state.paths())
            done = sum(1 for r in snap.results if r.status == "OK")
            message = f"AI notes: {done} of {len(issue_ids)} generated."
            if snap.grounds_message:
                message += f" {snap.grounds_message}"
            if snap.cancelled:
                message += " Cancelled before the end."
            st.session_state[state.NOTICE_KEY] = ("neutral", message)
        st.rerun()
    label = "ground titles" if snap.current == "grounds" else f"issue {snap.current or '…'}"
    st.progress(snap.done / max(snap.total, 1),
                text=f"AI notes: {snap.done} of {snap.total} done — working on {label}. You can "
                     "keep reviewing meanwhile.")
    if st.button("Cancel AI notes", key="ai_cancel"):
        job.cancel()


def render_controls(case: CaseFile) -> None:
    """Engine choice, the "Generate for all adverse issues" button and the progress bar."""
    adverse = pipeline.adverse_issue_ids(case)
    s = state.settings()
    left, right = st.columns([2, 3])
    with left:
        options = engine_options(case)
        _kind(case)  # seeds the widget value
        st.radio("AI notes engine", options, key=KIND_KEY, horizontal=True,
                 format_func=lambda k: (f"Local AI ({s.lmstudio.model or s.lmstudio.server_label})"
                                        if k == "lmstudio" else "Cloud AI"),
                 help="AI notes are advisory and clearly labelled. Local AI runs on this "
                      "computer; Cloud AI is offered only if you accepted the confidentiality "
                      "warning in Step 1.")
    with right:
        st.write("")
        if st.button(f"Generate for all adverse issues ({len(adverse)})", disabled=busy()
                     or not adverse, key="ai_all"):
            _start(case, adverse, grounds=True)
            st.rerun()
    _progress()


def render_issue_note(case: CaseFile, issue: Issue) -> None:
    """The AI block for one issue: the note (shaded, labelled) and its button (adverse only)."""
    if issue.ai_status == "OK":
        theme.render_html(theme.ai_note_html(issue.summary, issue.strategy_note))
    elif issue.ai_status == "WITHHELD":
        theme.render_callout(issue.ai_message or MSG_WITHHELD, tone="amber")
    elif issue.ai_status == "UNAVAILABLE":
        theme.render_callout(issue.ai_message or "AI not available.", tone="neutral",
                             title="AI note not generated")
    if issue.issue_id in pipeline.adverse_issue_ids(case):
        label = "Regenerate AI note" if issue.ai_status == "OK" else "Generate AI note"
        if st.button(label, key=f"ai_{issue.issue_id}", disabled=busy()):
            st.session_state["review_open_issue"] = issue.issue_id  # reopened when the note lands
            _start(case, [issue.issue_id], grounds=False)
            st.rerun()
