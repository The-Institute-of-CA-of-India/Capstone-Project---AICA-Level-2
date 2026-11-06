"""Hearings tab of a case (CR-009 Session B): appeal status, date of filing, ITA No. and the
hearing log (date, bench, purpose, outcome, next date, remarks).

The log lives in the case register (``register.hearings``), so the next hearing date reaches
Home and the Case Register without opening the case.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from appealiq import register
from appealiq.fmt import fmt_date
from appealiq.ui import state, theme

OUTCOME_SCHEDULED = "Scheduled (not yet held)"
PURPOSES = ["First hearing", "Arguments", "Stay application", "Filing of paper book",
            "Adjournment application", "Pronouncement", "Rectification (MA)", "Other"]


def status_form(record: register.MatterRecord, key: str) -> None:
    """Status, date of filing and ITA No. (required from "Appeal filed" on)."""
    p = state.paths()
    with st.form(f"{key}_{record.matter_id}", border=False):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1], vertical_alignment="bottom")
        status = c1.selectbox("Status", register.STATUSES,
                              index=register.STATUSES.index(record.status))
        filed = c2.date_input("Date of filing of appeal", value=record.filing_date,
                              format="DD/MM/YYYY", max_value=state.today())
        ita = c3.text_input("ITA No.", value=record.ita_no or "",
                            placeholder="e.g. ITA No. 123/PUN/2026")
        if c4.form_submit_button("Save", type="primary", use_container_width=True):
            try:
                register.set_status(p.db_file, record.matter_id, status, filing_date=filed,
                                    ita_no=ita, today=state.today())
            except ValueError as exc:
                theme.render_error(str(exc), title="Status not saved")
                return
            st.rerun()
    st.caption("From \"Appeal filed\" on, the date of filing is required and the Form 36 "
               "countdown gives way to the next hearing date.")


def _log_rows(hearings: list[register.Hearing]) -> list[list[str]]:
    return [[fmt_date(h.date), h.bench or "—", h.purpose or "—",
             h.outcome or "Scheduled", fmt_date(h.next_date, "—"), h.remarks or ""]
            for h in hearings]


def _hearing_form(matter_id: str, hearing: register.Hearing | None, key: str) -> None:
    p = state.paths()
    outcomes = [OUTCOME_SCHEDULED, *register.HEARING_OUTCOMES]
    with st.form(key, clear_on_submit=hearing is None, border=False):
        c1, c2, c3 = st.columns([2, 3, 3])
        when = c1.date_input("Hearing date", value=hearing.date if hearing else state.today(),
                             format="DD/MM/YYYY")
        bench = c2.text_input("Bench", value=hearing.bench or "" if hearing else "",
                              placeholder="e.g. 'A' Bench, Pune")
        purpose = c3.selectbox("Purpose", PURPOSES, accept_new_options=True,
                               index=PURPOSES.index(hearing.purpose)
                               if hearing and hearing.purpose in PURPOSES else 0)
        c4, c5, c6 = st.columns([3, 2, 3])
        outcome = c4.selectbox("Outcome", outcomes,
                               index=outcomes.index(hearing.outcome)
                               if hearing and hearing.outcome else 0)
        next_date = c5.date_input("Next date", value=hearing.next_date if hearing else None,
                                  format="DD/MM/YYYY")
        remarks = c6.text_input("Remarks", value=hearing.remarks or "" if hearing else "")
        if st.form_submit_button("Save hearing" if hearing else "Add hearing", type="primary"):
            entry = register.Hearing(
                hearing_id=hearing.hearing_id if hearing else None, matter_id=matter_id,
                date=when or date.today(), bench=bench, purpose=purpose,
                outcome=None if outcome == OUTCOME_SCHEDULED else outcome,
                next_date=next_date, remarks=remarks)
            try:
                register.save_hearing(p.db_file, entry)
            except ValueError as exc:
                theme.render_error(str(exc), title="Hearing not saved")
                return
            st.rerun()


def render(matter_id: str) -> None:
    """The Hearings tab for one case."""
    p, today = state.paths(), state.today()
    record = register.get_record(p.db_file, matter_id, today)
    if record is None:
        theme.render_empty("Case not in the register",
                           "Hearings are kept in the Case Register; process or save the case "
                           "first.")
        return
    st.markdown("**Appeal status**")
    status_form(record, "hstatus")
    hearings = register.list_hearings(p.db_file, matter_id)
    nxt = register.next_hearing(hearings, today)
    st.markdown("**Hearing log**")
    if nxt is not None:
        days = (nxt - today).days
        theme.render_callout(f"Next hearing on {fmt_date(nxt)} "
                             f"({'today' if days == 0 else f'in {days} day(s)'}).",
                             tone="amber" if days <= register.HEARING_WINDOW_DAYS else "neutral")
    if hearings:
        theme.render_html(theme.table_html(
            ["Date", "Bench", "Purpose", "Outcome", "Next date", "Remarks"],
            _log_rows(hearings), numeric={0, 4}))
    else:
        theme.render_empty("No hearings yet", "Add the first hearing date below once the "
                                              "Tribunal fixes it.")
    with st.expander("Add hearing", expanded=not hearings, icon=":material/add:"):
        _hearing_form(matter_id, None, f"hadd_{matter_id}")
    if hearings:
        labels = {h.hearing_id: f"{fmt_date(h.date)} · {h.purpose or 'Hearing'} · "
                                f"{h.outcome or 'Scheduled'}" for h in hearings}
        with st.expander("Edit or delete a hearing", icon=":material/edit:"):
            chosen = st.selectbox("Hearing", list(labels), format_func=labels.get,
                                  key=f"hsel_{matter_id}")
            hearing = next(h for h in hearings if h.hearing_id == chosen)
            _hearing_form(matter_id, hearing, f"hedit_{matter_id}_{chosen}")
            if st.button("Delete this hearing", key=f"hdel_{matter_id}_{chosen}"):
                register.delete_hearing(p.db_file, matter_id, int(chosen or 0))
                st.rerun()
