"""Home dashboard: KPI tiles, upcoming deadlines, upcoming hearings and the start button
(SPEC §10.3 Home; CR-009 Session B: hearings, case links)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from appealiq import register
from appealiq.config import RagSettings
from appealiq.fmt import fmt_date
from appealiq.ui import state, theme

HOME_ROWS = 15


def days_badge(days: int | None, rag: str | None) -> str:
    """"12 days" / "Expired 3 days ago" as a RAG badge (or a dash without a due date)."""
    if days is None or rag is None:
        return "—"
    text = f"{days} day{'s' if days != 1 else ''}" if days >= 0 else \
        f"Expired {-days} day{'s' if days != -1 else ''} ago"
    return theme.rag_badge_html(rag, text)  # type: ignore[arg-type]


def hearing_badge(when: str | None, days: int | None) -> str:
    """"Hearing 12-11-2026" (in place of the limitation badge once the appeal is filed)."""
    if when is None or days is None:
        return theme.badge_html("Filed")
    tone = "AMBER" if days <= register.HEARING_WINDOW_DAYS else "teal"
    return theme.badge_html(f"Hearing {when}", tone)  # type: ignore[arg-type]


def limitation_cell(record: register.MatterRecord, today: date, rag: RagSettings) -> str:
    """Days left while the appeal is to be filed; the next hearing once it is filed."""
    if record.limitation_applies:
        return days_badge(record.days_remaining(today), record.rag(today, rag))
    if record.status == "Closed":
        return "—"
    nxt = record.next_hearing
    return hearing_badge(fmt_date(nxt) if nxt else None,
                         (nxt - today).days if nxt else None)


def render() -> None:
    """Render the Home page from the case register."""
    st.title("Home")
    settings, paths, today = state.settings(), state.paths(), state.today()
    records = register.list_records(paths.db_file, today)
    kpi = register.dashboard(records, today, settings.rag)
    red = settings.rag.red_max_days
    theme.render_kpi_row([
        ("Open cases", str(kpi.open_matters), "neutral"),
        (f"Due in {red} days or less", str(kpi.due_red), "red"),
        (f"Due in {red + 1}–{settings.rag.amber_max_days} days", str(kpi.due_amber), "amber"),
        (f"Hearings in next {register.HEARING_WINDOW_DAYS} days", str(kpi.hearings_next_7_days),
         "amber" if kpi.hearings_next_7_days else "neutral"),
        ("Analyses this month", str(kpi.analyses_this_month), "neutral"),
    ])
    if kpi.expired:
        theme.render_callout(f"{kpi.expired} case(s) not yet filed are past the Form 36 due "
                             "date — consider a condonation application u/s 253(5).", tone="red",
                             title="Limitation expired")
    st.write("")
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    left.subheader("Upcoming deadlines")
    if right.button("Start new analysis", type="primary", use_container_width=True):
        st.session_state["wizard_reset"] = True
        st.switch_page(st.session_state["pages"]["new"])
    rows = register.upcoming(records, today, limit=HOME_ROWS)
    if not records:
        theme.render_empty("No cases yet",
                           "Start a new analysis: upload an appellate order and its date of "
                           "service, and the Form 36 due date appears here.")
        return
    if rows:
        theme.render_html(theme.table_html(
            ["Case", "Client", "AY", "Order", "Form 36 due", "Days left", "Status"],
            [[state.case_link_html(r.matter_id), r.client, r.assessment_year or "—",
              r.order_label or "—", fmt_date(r.due_date, "—"),
              days_badge(r.days_remaining(today), r.rag(today, settings.rag)),
              r.status] for r in rows],
            numeric={4}, html_cols={0, 5}))
        st.caption("Click a case to open it. Days are counted from today's date; limitation is "
                   "computed from the date of service entered for each case.")
    else:
        theme.render_empty("No upcoming deadlines",
                           "Every case is filed, closed or has no due date.")

    st.subheader("Upcoming hearings")
    hearings = register.upcoming_hearings(paths.db_file, records, today)[:HOME_ROWS]
    if not hearings:
        theme.render_empty("No hearings fixed",
                           "Add hearing dates in a case's Hearings tab once the appeal is "
                           "filed.")
        return
    theme.render_html(theme.table_html(
        ["Case", "Client", "ITA No.", "Hearing date", "In", "Bench", "Purpose", "Status"],
        [[state.case_link_html(u.record.matter_id), u.record.client, u.record.ita_no or "—",
          fmt_date(u.date), _in_days((u.date - today).days),
          (u.hearing.bench if u.hearing else None) or "—",
          _purpose(u), u.record.status] for u in hearings],
        numeric={3}, html_cols={0}))


def _in_days(days: int) -> str:
    return "Today" if days == 0 else f"{days} day{'s' if days != 1 else ''}"


def _purpose(u: register.UpcomingHearing) -> str:
    """The purpose of a scheduled hearing; for a next date fixed at a hearing, "Next date"."""
    if u.hearing is None:
        return "—"
    if u.hearing.outcome is None:
        return u.hearing.purpose or "—"
    return f"Next date ({u.hearing.outcome.lower()} on {fmt_date(u.hearing.date)})"
