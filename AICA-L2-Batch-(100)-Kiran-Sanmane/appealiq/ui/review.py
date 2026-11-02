"""Step 3 — Review & Edit: summary strip and the tabs (SPEC §10.3 Step 3).

Every edit goes through ``state.apply_edit``: the field becomes USER_EDITED, the rules, tax
effect and decisions are recomputed at once (``pipeline.recompute``) and the CaseFile is
autosaved. Amounts are shown in the Indian format; editors that need numbers take whole rupees.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import reduce
from html import escape

import pandas as pd
import streamlit as st

from appealiq import pipeline, register
from appealiq.fmt import fmt_date, fmt_rate, inr
from appealiq.models import CaseFile, Evidence, Issue, OrderFamily, PaperBookEntry, doc_label
from appealiq.outputs.report_docx import ASSESSEE_SIDE, REVENUE_SIDE
from appealiq.ui import ai_notes, ai_read, case_notes, hearings, state, theme

OUTCOME_LABELS = {"ALLOWED": "Allowed", "PARTLY_ALLOWED": "Partly allowed",
                  "DISMISSED": "Dismissed", "RESTORED_TO_AO": "Restored to AO",
                  "NOT_ADJUDICATED": "Not adjudicated", "INFRUCTUOUS": "Infructuous",
                  "UNKNOWN": "Unknown"}
REC_LABELS = {"APPEAL": "Appeal", "APPEAL_BALANCE": "Appeal (balance)",
              "CROSS_OBJECT": "Cross-objection", "MONITOR": "Monitor",
              "PURSUE_SET_ASIDE": "Pursue set-aside", "ACCEPT": "Accept", "EVALUATE": "Evaluate"}
PRIORITIES = ["HIGH", "MEDIUM", "LOW"]
PRIORITY_TONE = {"HIGH": "RED", "MEDIUM": "AMBER", "LOW": "GREEN"}
SEVERITY_TONE = {"HIGH": "RED", "MEDIUM": "AMBER", "INFO": "neutral"}
LIKELIHOOD_TONE = {"UNLIKELY": "GREEN", "POSSIBLE": "AMBER", "LIKELY": "RED"}
FILED_LABELS = {"AO": "AO", "CIT(A)": "CIT(A)", "NEW_RULE_29": "New – Rule 29", None: "—"}
SIDE_LABELS = {"ASSESSEE": ASSESSEE_SIDE, "DEPARTMENT": REVENUE_SIDE}  # as in the report (U3)
TAB_NAMES = ["Order Details", "Issue Trail", "Tax Effect", "Decision Matrix",
             "Grounds & Paper Book", "Case Notes", "Case Laws in Orders", "Hearings",
             "Verification Log"]
TAB_KEY = "review_tabs"  # widget key of the tab bar
TAB_STATE = "review_tab"  # the open tab, by its stable name (survives reruns and label changes)
OPEN_ISSUE = "review_open_issue"  # the issue panel left open in the Issue Trail
ROLE_LABELS = [("ao_contention", "AO's contention"),
               ("assessee_submission", "Assessee's submission"),
               ("appellate_finding", "Appellate finding")]


def _cell(value: object) -> str:
    """A data_editor cell as text (blank for None / NaN)."""
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def _inv(mapping: dict) -> dict:
    return {v: k for k, v in mapping.items()}


def ref(ev: Evidence | None) -> str:
    """"p.3 ¶5.2", prefixed for another document ("AO p.1 ¶4", "Sub p.2 ¶3")."""
    if ev is None:
        return ""
    where = f"p.{ev.page}" + (f" ¶{ev.para_no}" if ev.para_no else "")
    prefix = doc_label(ev.doc_id)
    return f"{prefix} {where}" if prefix else where


def days_text(days: int, short: bool = False) -> str:
    """"61 days remaining" ("61 days" if ``short``) / "Expired 3 days ago"."""
    if days < 0:
        return f"Expired {-days} days ago"
    return f"{days} days" if short else f"{days} days remaining"


def _titles(case: CaseFile) -> dict[str, str]:
    titles = {i.issue_id: i.title for i in case.issues}
    titles["WHOLE_ORDER"] = "Whole order"
    return titles


# =========================================================================== summary strip


def render_strip(case: CaseFile) -> None:
    """Order, AY, Authority, DIN, Service date, Due date + RAG, Engine."""
    h, lim = case.header, case.limitation
    record = register.get_record(state.paths().db_file, case.matter_id, state.today())
    due_label = "Due date"
    if record is not None and not record.limitation_applies:  # filed: no countdown (CR-009 B)
        due_label = "Filed on"
        due = escape(fmt_date(record.filing_date, record.status))
        if record.next_hearing is not None:
            due += " " + theme.badge_html(f"Hearing {fmt_date(record.next_hearing)}", "teal")
    elif lim is not None:
        due = (f"{escape(fmt_date(lim.due_date))} "
               f"{theme.rag_badge_html(lim.rag, days_text(lim.days_remaining, short=True))}")
    else:
        due = "Not computed"
    engine = pipeline.ENGINE_NAMES.get(case.engine_used, case.engine_used)
    if case.engine_fallbacks:
        engine += f" ({len(case.engine_fallbacks)} fallback)"
    theme.render_html(theme.summary_strip_html([
        ("Order", escape(pipeline.short_order_label(case))),
        ("AY", escape(h.assessment_year.value or "Not found")),
        ("Authority", escape(h.authority.value or "Not found")),
        ("DIN", escape(h.din.value or "Not found")),
        ("Service date", escape(fmt_date(case.inputs.date_of_service))),
        (due_label, due),
        ("Engine", escape(engine)),
    ], grow=frozenset({"DIN"})))


# =========================================================================== tab 1: order details


def _order_type(case: CaseFile) -> None:
    c = case.classification
    if c is None or not (c.needs_user_choice or c.family == OrderFamily.UNKNOWN):
        return
    theme.render_callout("The type of order could not be identified with confidence. Confirm it "
                         "so that the right forum, limitation and decision rules apply.",
                         tone="amber", title="Confirm the order type")
    ai_read.render_suggestion(case)  # CR-010: shown, never applied without the reviewer
    families = [OrderFamily.CITA_250, OrderFamily.REVISION_263, OrderFamily.CITE_12AB_80G,
                OrderFamily.DRP_FINAL_144C13]
    suggested = families.index(c.ai_family) if c.ai_family in families else 0
    choice = st.selectbox("Order type", families, format_func=pipeline.REGISTER_ORDER_LABELS.get,
                          index=suggested, key="family_choice")
    if st.button("Confirm order type"):
        state.apply_edit(lambda x: pipeline.set_order_family(x, choice))


def _header_editor(case: CaseFile) -> None:
    rows = []
    for name, (label, kind) in pipeline.HEADER_FIELDS.items():
        f = getattr(case.header, name)
        rows.append({"Field": label, "Value": pipeline.header_display(f.value, kind),
                     "Reference": ref(f.evidence), "Status": theme.STATUS_LABELS[f.status],
                     "key": name})
    edited = st.data_editor(
        pd.DataFrame(rows), key=f"hdr_{state.edit_version()}", hide_index=True,
        use_container_width=True, disabled=["Field", "Reference", "Status"],
        column_config={"key": None, "Value": st.column_config.TextColumn(
            "Value", help="Dates DD-MM-YYYY; amounts in rupees (12,34,567); Yes / No.")})
    changes = [(r["key"], _cell(edited.iloc[n]["Value"]))
               for n, r in enumerate(rows) if _cell(edited.iloc[n]["Value"]) != r["Value"]]
    if changes:
        state.apply_edit(lambda c: reduce(lambda acc, ch: pipeline.edit_header(acc, *ch),
                                          changes, c))
    st.caption("Status: OK = verified against the order · Low confidence = close match · "
               "Unverified = not found in the order · Not found = blank · Edited = changed by "
               "you. A blank value means it was not found — it is never guessed.")


def _limitation_card(case: CaseFile) -> None:
    lim, fee = case.limitation, case.fee
    if lim is None:
        theme.render_callout("The due date could not be computed. Check the date of service and "
                             "the order type.", tone="red")
        return
    rows = [("Forum", lim.forum), ("Form", lim.form), ("Provision", lim.provision),
            ("Limitation runs from", f"{fmt_date(lim.start_date)} (date of service)"),
            ("Due date", fmt_date(lim.due_date))]
    if lim.cross_objection_due:
        rows.append(("Cross-objections due", fmt_date(lim.cross_objection_due)))
    rows.append(("Appeal fee", f"{inr(fee.amount)} — {fee.basis}" if fee else "Not computed"))
    body = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in rows)
    badge = theme.rag_badge_html(lim.rag, days_text(lim.days_remaining))
    notes = "".join(f"<li>{escape(n)}</li>" for n in lim.notes)
    theme.render_card("Limitation and fee", f'<p>{badge}</p><table class="aiq-kv">{body}</table>'
                      + (f'<ul class="aiq-muted">{notes}</ul>' if notes else ""))


def _revenue_appeal(case: CaseFile) -> None:
    with st.container(border=True):
        st.markdown("**Revenue's appeal**")
        received = st.toggle("Revenue's appeal received", value=case.inputs.dept_appeal_received,
                             key=f"rev_rx_{state.edit_version()}")
        when = case.inputs.dept_appeal_receipt_date
        if received:
            when = st.date_input("Date of receipt of the notice of appeal", value=when,
                                 format="DD-MM-YYYY", max_value=state.today(),
                                 key=f"rev_dt_{state.edit_version()}")
        changed = (received != case.inputs.dept_appeal_received
                   or (received and when != case.inputs.dept_appeal_receipt_date))
        if changed and (not received or when is not None):
            state.apply_edit(lambda c: pipeline.edit_inputs(
                c, dept_appeal_received=received, dept_appeal_receipt_date=when))


def _validity(case: CaseFile) -> None:
    st.markdown("**Validity and procedural observations**")
    if not case.validity:
        st.caption("No validity flags raised.")
        return
    theme.render_html(theme.table_html(
        ["Severity", "Observation", "Reference", "Basis"],
        [[theme.badge_html(f.severity.title(), SEVERITY_TONE[f.severity]),  # type: ignore[arg-type]
          f"{f.title}: {f.observation}", ref(f.evidence) or "—", f.basis] for f in case.validity],
        html_cols={0}))


def tab_order_details(case: CaseFile) -> None:
    """Editable key–value grid with status per field; limitation, Revenue's appeal, validity."""
    _order_type(case)
    left, right = st.columns([3, 2])
    with left:
        _header_editor(case)
    with right:
        _limitation_card(case)
        _revenue_appeal(case)
    _validity(case)


# =========================================================================== tab 2: issue trail


def _app_ref(issue: Issue) -> str:
    return f"p.{issue.para_refs[0].page} ¶{issue.para_refs[0].para_no}" if issue.para_refs else "—"


def _ao_ref(issue: Issue) -> str:
    if issue.ao_evidence_link is not None:
        return ref(issue.ao_evidence_link)
    return "Legal ground" if issue.nature == "LEGAL_JURISDICTIONAL" else "—"


def refs_text(issue: Issue) -> str:
    """One "Refs" cell (U2): the appellate para, then the AO's ("p.2 ¶7 · AO p.1 ¶4"). An
    issue added by the reviewer says so (CR-009)."""
    if issue.origin == "USER_ADDED":
        return "Added by reviewer"
    parts = [_app_ref(issue)] + ([] if _ao_ref(issue) == "—" else [_ao_ref(issue)])
    if issue.origin == "GROUNDS_LIST":
        parts.append("grounds list")
    elif issue.origin == "DECISION_SECTION":
        parts.append("matched to ground")
    elif issue.origin == "LOCAL_AI":
        parts.append("local AI")
    return " · ".join(p.replace(" ", " ") for p in parts)  # wraps only between refs


def _keep_sections_whole(text: str) -> str:
    """No line break inside "u/s 40(a)(ia)": a no-break space after "u/s" / "s." and a word
    joiner between ")(" when the title wraps."""
    text = re.sub(r"\b(u/s|s\.)\s+", "\\1\u00a0", text)
    return text.replace(")(", ")\u2060(")


TRAIL_HEADERS = ["Issue", "Ground", "Title", "Section", "AO amount", "Outcome", "Relief",
                 "Sustained", "Refs", "Status"]


def trail_rows(case: CaseFile) -> list[list[str]]:
    """Issue Trail rows (U2): the Title wraps, AO and appellate references share one column.
    The Status cell is trusted chip markup; every other cell is plain text."""
    return [[i.issue_id, ", ".join(i.ground_nos) or "—", _keep_sections_whole(i.title),
             i.section or "—",
             inr(i.amount_ao, "—"), OUTCOME_LABELS[i.outcome], inr(i.amount_relief, "—"),
             inr(i.amount_sustained, "—"), refs_text(i), theme.status_chip_html(i.status)]
            for i in case.issues]


def _trail_table(case: CaseFile) -> None:
    """The trail as a wrapping table: no truncated titles and no sideways scrolling at 1366 px
    (``st.data_editor`` cells cannot wrap). Edits are made in the issue panels below."""
    if not case.issues:
        theme.render_empty("No issues found",
                           "No grounds or issues could be read from this order. Add each ground "
                           "yourself, let the grounds be read from Form 35, or read the order "
                           "with local AI.")
        return
    theme.render_html(theme.table_html(TRAIL_HEADERS, trail_rows(case), numeric={4, 6, 7},
                                       html_cols={9}, css="aiq-trail"))
    st.caption("Open an issue below to change its title, section, outcome or amounts; the tax "
               "effect and decisions update at once. Refs: appellate order page and para, then "
               "the AO's order.")


def _extracts(issue: Issue) -> None:
    def show(ev: Evidence, label: str | None = None) -> None:
        mark = "" if ev.verified or ev.user_confirmed else " (unverified)"
        prefix = f"{label}{mark}: " if label else mark.strip()
        if prefix:
            st.caption(prefix)
        theme.render_html(theme.quote_html(ev.source_snippet, ref(ev)))

    if issue.title_evidence is not None:
        show(issue.title_evidence, "Heading in the order")
    for attr, label in ROLE_LABELS:
        items = getattr(issue, attr)
        if items:
            st.markdown(f"**{label}**")
            for ev in items:
                show(ev)
    if issue.ao_evidence_link is not None:
        show(issue.ao_evidence_link, "In the AO's order")
    if not (issue.title_evidence or issue.ao_contention or issue.assessee_submission
            or issue.appellate_finding):
        st.caption("Added by the reviewer: no extracts from the order."
                   if issue.origin == "USER_ADDED" else "No extracts were found for this issue.")


def _issue_form(issue: Issue) -> None:
    """Title, section, outcome and amounts for one issue (keyboard-friendly)."""
    legal = issue.nature == "LEGAL_JURISDICTIONAL"
    with st.form(f"iss_{issue.issue_id}_{state.edit_version()}", border=False):
        t1, t2 = st.columns([5, 2])
        title = t1.text_input("Title", value=issue.title, max_chars=80)
        section = t2.text_input("Section", value=issue.section or "", placeholder="e.g. 14A")
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
        labels = list(OUTCOME_LABELS.values())
        outcome = c1.selectbox("Outcome", labels, index=labels.index(OUTCOME_LABELS[issue.outcome]),
                               key=f"oc_{issue.issue_id}_{state.edit_version()}")
        ao = sustained = None
        if not legal:
            ao = c2.number_input("AO's addition (₹)", min_value=0, step=1000,
                                 value=issue.amount_ao, placeholder="Not found")
            sustained = c3.number_input("Sustained if partly allowed (₹)", min_value=0,
                                        step=1000, value=issue.amount_sustained,
                                        placeholder="Enter")
        if c4.form_submit_button("Save", use_container_width=True):
            st.session_state[OPEN_ISSUE] = issue.issue_id  # keep this panel open after the rerun
            kwargs: dict[str, object] = {}
            if title.strip() and title.strip() != issue.title:
                kwargs["title"] = title.strip()
            if section.strip() != (issue.section or ""):
                kwargs["section"] = section.strip()
            code = _inv(OUTCOME_LABELS)[outcome]
            if code != issue.outcome:
                kwargs["outcome"] = code
            if not legal and ao != issue.amount_ao:
                kwargs["amount_ao"] = None if ao is None else int(ao)
            if code == "PARTLY_ALLOWED" and sustained is not None \
                    and sustained != issue.amount_sustained:
                kwargs["amount_sustained"] = int(sustained)
            if kwargs:
                state.apply_edit(lambda c: pipeline.edit_issue(c, issue.issue_id, **kwargs))
    st.caption(f"AO {inr(issue.amount_ao, '—')} · relief {inr(issue.amount_relief, '—')} · "
               f"sustained {inr(issue.amount_sustained, '—')}")


def _add_issue_form(case: CaseFile, expanded: bool) -> None:
    """CR-009: add an issue the order's text did not yield (blank or weak detection)."""
    with st.expander("Add issue manually", expanded=expanded, icon=":material/add:"):
        with st.form(f"add_issue_{state.edit_version()}", border=False, clear_on_submit=True):
            t1, t2, t3 = st.columns([5, 2, 2])
            title = t1.text_input("Title", max_chars=80, placeholder="e.g. Addition u/s 68")
            section = t2.text_input("Section", placeholder="e.g. 68")
            grounds = t3.text_input("Ground No(s).", placeholder="e.g. 2, 3")
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
            labels = list(OUTCOME_LABELS.values())
            outcome = c1.selectbox("Outcome", labels, index=labels.index("Unknown"))
            ao = c2.number_input("AO's addition (₹)", min_value=0, step=1000, value=None,
                                 placeholder="Not stated")
            sustained = c3.number_input("Sustained if partly allowed (₹)", min_value=0,
                                        step=1000, value=None, placeholder="Enter")
            if c4.form_submit_button("Add", use_container_width=True):
                code = _inv(OUTCOME_LABELS)[outcome]
                state.apply_edit(lambda c: pipeline.add_issue(
                    c, title=title, section=section, ground_nos=grounds, outcome=code,
                    amount_ao=None if ao is None else int(ao),
                    amount_sustained=None if sustained is None else int(sustained)))
        st.caption("Added issues are marked as entered by the reviewer; nothing is quoted from "
                   "the order for them.")


def _form35_upload(case: CaseFile) -> None:
    """DF-001: read the issues from Form 35 when the order's text yields none."""
    with st.expander("Use grounds from Form 35", expanded=True, icon=":material/upload_file:"):
        if len(case.supporting) >= pipeline.SUPPORTING_SLOTS:
            st.caption(f"This case already has {pipeline.SUPPORTING_SLOTS} supporting "
                       "documents; add the grounds with Add issue manually.")
            return
        upload = st.file_uploader("Form 35 / grounds of appeal (PDF)", type=["pdf"],
                                  key=f"f35_{state.edit_version()}",
                                  help="Saved with the case and listed in the paper book index.")
        if st.button("Read grounds and reprocess", type="primary", disabled=upload is None,
                     use_container_width=True):
            s = state.settings()
            with st.spinner("Reading Form 35 and reprocessing… (scanned copies take longer)"):
                run = pipeline.reprocess_case(case, state.paths(), kb=state.kb(),
                                              today=state.today(), rag=s.rag,
                                              materiality=s.materiality,
                                              attach=(upload.getvalue(), upload.name, "FORM35"))
            if run.case is None:
                failed = next((r for r in reversed(run.results) if r.status == "failed"), None)
                theme.render_error(failed.message if failed else "Reprocessing stopped.",
                                   pipeline.corrective_action(failed) if failed else None,
                                   title="Form 35 could not be used")
                return
            state.set_case(run.case)
            found = len(run.case.issues)
            st.session_state[state.NOTICE_KEY] = (
                "green" if found else "amber",
                f"Form 35 added; {found} issue(s) listed from its grounds." if found else
                "Form 35 added, but no grounds could be read from it; use Add issue manually.")
            st.session_state["edit_version"] = state.edit_version() + 1
            st.rerun()
        st.caption("The case is processed again with Form 35; notes, comments and hearings are "
                   "kept.")


def _comments(issue: Issue) -> None:
    """Reviewer comments on the issue (internal, CR-009 C)."""
    with st.form(f"cmt_{issue.issue_id}_{state.edit_version()}", border=False):
        text = st.text_area("Reviewer comments", value=issue.reviewer_comments or "",
                            height=80, placeholder="Internal comments on this issue…",
                            help="Kept with the case and in the Excel register; in the report "
                                 "only in the optional internal annexure.")
        if st.form_submit_button("Save comments") and text.strip() != (
                issue.reviewer_comments or ""):
            st.session_state[OPEN_ISSUE] = issue.issue_id
            state.apply_edit(lambda c: pipeline.set_reviewer_comment(c, issue.issue_id, text))


def _layout_inspector(case: CaseFile) -> None:
    """CR-010: how each page was read and why no issue was found — built on this computer from
    the saved case, shown here only (never in a report, a log or the register)."""
    with st.expander("Layout inspector — how each page was read (this computer only)",
                     expanded=False, icon=":material/plagiarism:"):
        inspection = pipeline.layout_inspection(case, state.kb())
        st.caption("For your eyes only: the order's own text is shown here and nowhere else. "
                   "Nothing on this panel is saved in the outputs or sent anywhere.")
        theme.render_html("<ul>" + "".join(f"<li>{escape(f)}</li>"
                                           for f in inspection.findings) + "</ul>")
        for page in inspection.pages:
            note = f" — {page.note}" if page.note else ""
            st.markdown(f"**Page {page.page}** · {escape(page.method)} · {page.chars:,} "
                        f"characters{escape(note)}")
            rows = [[p.marker, p.preview, ", ".join(p.tags) or "—"] for p in page.paras]
            if rows:
                theme.render_html(theme.table_html(["Para", "Starts with", "Detected"], rows))


def tab_issue_trail(case: CaseFile) -> None:
    """The issue trail table, AI notes controls and one expander per issue."""
    notice = pipeline.issue_detection_notice(case)
    if notice is not None:
        theme.render_callout(notice.message, tone=notice.tone, title=notice.title)
    _trail_table(case)
    if case.issues:
        _add_issue_form(case, expanded=False)
    else:  # DF-001: the ways forward, side by side
        left, right = st.columns(2)
        with left:
            _add_issue_form(case, expanded=True)
        with right:
            _form35_upload(case)
    ai_read.render_offer(case)  # CR-010: no issue found, or the order type is unsure
    if case.unmatched_ao:
        lines = "; ".join(f"{i.title} ({inr(i.amount_ao, 'amount not found')})"
                          for i in case.unmatched_ao)
        theme.render_callout(f"Addition(s) not found in the appellate order — check whether a "
                             f"ground was raised: {lines}.", tone="amber",
                             title="Issue trail check")
    _layout_inspector(case)
    st.markdown("**Issue details, extracts and AI notes**")
    ai_notes.render_controls(case)
    open_issue = st.session_state.get(OPEN_ISSUE)
    for issue in case.issues:
        # The panel's open state is kept by issue, so it stays open across the reruns of an
        # edit or a finished AI note, even when its label (the outcome) changes.
        key = f"issue_panel_{issue.issue_id}"
        with st.expander(f"{issue.issue_id} · {issue.title} — {OUTCOME_LABELS[issue.outcome]}",
                         expanded=open_issue == issue.issue_id, key=key,
                         on_change=_remember_panel, args=(issue.issue_id, key)):
            _issue_form(issue)
            _comments(issue)
            _extracts(issue)
            ai_notes.render_issue_note(case, issue)


def _remember_panel(issue_id: str, key: str) -> None:
    """Expander callback: remember the open issue panel (one at a time)."""
    if st.session_state.get(key):
        st.session_state[OPEN_ISSUE] = issue_id
    elif st.session_state.get(OPEN_ISSUE) == issue_id:
        st.session_state.pop(OPEN_ISSUE, None)


# =========================================================================== tab 3: tax effect


def _rate_selector(case: CaseFile) -> None:
    rates = state.kb().rates
    if rates is None:
        theme.render_error("rates.yaml could not be loaded, so the rate cannot be changed.")
        return
    st.markdown(f"**Effective tax rate** — {escape(case.inputs.rate_basis)} "
                f"({fmt_rate(case.inputs.rate)})")
    code = case_notes.rate_cascade(rates, f"rate_{state.edit_version()}",
                                   current=case.inputs.rate_preset)
    custom = None
    if code == rates.custom.code:
        custom = st.number_input("Custom rate (%)", min_value=0.001, max_value=100.0,
                                 value=float(case.inputs.rate * 100), step=0.5, format="%.3f",
                                 key=f"rate_c_{state.edit_version()}")
    changed = code != case.inputs.rate_preset or (
        custom is not None and Decimal(str(custom)) / 100 != case.inputs.rate)
    if changed:
        try:
            new = pipeline.make_inputs(state.kb(), date_of_service=case.inputs.date_of_service,
                                       rate_preset=code, custom_rate_percent=None if custom is None
                                       else Decimal(str(custom)))
        except pipeline.EditError as exc:
            theme.render_error(exc.message)
            return
        state.apply_edit(lambda c: pipeline.edit_inputs(c, rate_preset=new.rate_preset,
                                                        rate=new.rate, rate_basis=new.rate_basis))
    st.caption(rates.ui_note)


def _side_table(case: CaseFile, side: str, total: int) -> None:
    titles = _titles(case)
    lines = [x for x in case.tax_effect.lines if x.side == side]  # type: ignore[union-attr]
    st.markdown(f"**{SIDE_LABELS[side]}**")
    if not lines:
        st.caption("No amounts on this side.")
        return
    rows = [[f"{x.issue_id} · {titles.get(x.issue_id, '')}", inr(x.income_in_dispute),
             fmt_rate(x.rate),
             (theme.badge_html("s. 115BBE", "teal") + " " if "115BBE" in x.rate_basis else "")
             + escape(x.rate_basis), inr(x.tax_effect)] for x in lines]
    theme.render_html(theme.table_html(
        ["Issue", "Income in dispute", "Rate", "Rate basis", "Tax effect"], rows,
        numeric={1, 2, 4}, html_cols={3}, footer=["Total", "", "", "", inr(total)]))


def _likelihood(case: CaseFile) -> None:
    tax = case.tax_effect
    limits = state.kb().monetary_limits
    assert tax is not None
    note = limits.likelihood.display_note if limits else ""
    if tax.dept_appeal_likelihood == "NOT_APPLICABLE":
        theme.render_callout("Not applicable — the Revenue does not appeal this type of order to "
                             "the ITAT, so the monetary limits do not arise.", tone="neutral",
                             title="Revenue appeal likelihood")
        return
    share = Decimal(tax.dept_total) / Decimal(tax.itat_limit) * 100 if tax.itat_limit else 0
    circular = limits.circular if limits else "CBDT circular"
    badge = theme.rag_badge_html(LIKELIHOOD_TONE[tax.dept_appeal_likelihood],  # type: ignore[arg-type]
                                 tax.dept_appeal_likelihood.title())
    theme.render_card("Revenue appeal likelihood", (
        f"<p>{badge}</p><p>Tax effect of the relief granted {escape(inr(tax.dept_total))} = "
        f"{share:.1f}% of the ITAT monetary limit of {escape(inr(tax.itat_limit))} "
        f"({escape(circular)}).</p><p class=\"aiq-muted\">{escape(note)}</p>"))


def _exception_flags(case: CaseFile) -> None:
    tax = case.tax_effect
    if tax is None or not tax.exception_flags:
        return
    st.markdown("**Exception flags (circular para 3.1 / 3.2) — for review**")
    for flag in tax.exception_flags:
        c1, c2 = st.columns([5, 1])
        with c1:
            status = " — cleared by the reviewer" if flag.cleared else ""
            st.markdown(f"“{escape(flag.phrase)}”{status}")
            theme.render_html(theme.quote_html(flag.evidence.source_snippet, ref(flag.evidence)))
        with c2:
            label = "Restore" if flag.cleared else "Clear"
            if st.button(label, key=f"flag_{flag.phrase}_{state.edit_version()}"):
                state.apply_edit(lambda c, p=flag.phrase, v=not flag.cleared:
                                 pipeline.set_exception_flag(c, p, v))


def tab_tax_effect(case: CaseFile) -> None:
    """Rate selector, issue-wise tax effect for both sides, likelihood and exception flags."""
    _rate_selector(case)
    tax = case.tax_effect
    if tax is None:
        theme.render_error("The tax effect could not be computed.",
                           "Check the rate and the issue amounts.")
        return
    family = pipeline.family_of(case)
    _side_table(case, "ASSESSEE", tax.assessee_total)
    if tax.dept_appeal_likelihood == "NOT_APPLICABLE" and family != OrderFamily.CITA_250:
        st.markdown(f"**{SIDE_LABELS['DEPARTMENT']}**")
        st.caption("Not applicable for this type of order.")
    else:
        _side_table(case, "DEPARTMENT", tax.dept_total)
    _likelihood(case)
    _exception_flags(case)
    overrides = case_notes.override_rows(case)
    if overrides:
        st.markdown("**Per-issue rate overrides**")
        theme.render_html(theme.table_html(["Issue", "Title", "Rate", "Basis"], overrides,
                                           numeric={2}, html_cols={3}))
    case_notes.issue_rate_editor(case)
    for n in tax.notes:
        st.caption(n)


# =========================================================================== tab 4: decisions


def tab_decisions(case: CaseFile) -> None:
    """Decision matrix (recommendation and priority overridable) and the action plan."""
    titles = _titles(case)
    rows = [{"Issue": d.issue_id, "Title": titles.get(d.issue_id, ""),
             "Recommendation": REC_LABELS[d.recommendation], "Priority": d.priority,
             "Status": theme.STATUS_LABELS[d.status]}
            for d in case.decisions]
    if rows:
        edited = st.data_editor(
            pd.DataFrame(rows), key=f"dec_{state.edit_version()}", hide_index=True,
            use_container_width=True, disabled=["Issue", "Title", "Status"],
            column_config={
                "Issue": st.column_config.TextColumn("Issue", width=60),
                "Title": st.column_config.TextColumn("Title", width="large"),
                "Recommendation": st.column_config.SelectboxColumn(
                    "Recommendation", options=list(REC_LABELS.values()), required=True),
                "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES,
                                                             required=True)})
        code = _inv(REC_LABELS)
        edits = [(r["Issue"], code[edited.iloc[n]["Recommendation"]],
                  edited.iloc[n]["Priority"] if edited.iloc[n]["Priority"] != r["Priority"]
                  else None)
                 for n, r in enumerate(rows)
                 if edited.iloc[n]["Recommendation"] != r["Recommendation"]
                 or edited.iloc[n]["Priority"] != r["Priority"]]
        if edits:
            state.apply_edit(lambda c: reduce(
                lambda acc, e: pipeline.set_recommendation(acc, e[0], e[1], e[2]), edits, c))
        st.caption("Recommendations follow the decision rules (SPEC §8.9). An override is kept "
                   "when the rules re-run and is noted in the rationale.")
        theme.render_html(theme.table_html(
            ["Issue", "Recommendation", "Priority", "Rationale"],
            [[d.issue_id, REC_LABELS[d.recommendation],
              theme.badge_html(d.priority.title(), PRIORITY_TONE[d.priority]),  # type: ignore[arg-type]
              d.rationale] for d in case.decisions], html_cols={2}))
    else:
        st.caption("No decisions — no verified issues.")
    st.markdown("**Action plan**")
    theme.render_html(theme.table_html(
        ["Priority", "Action", "Form", "Due"],
        [[theme.badge_html(a.priority.title(), PRIORITY_TONE.get(a.priority, "neutral")),  # type: ignore[arg-type]
          a.action + (f" Documents: {'; '.join(a.documents)}." if a.documents else ""),
          a.form or "—", fmt_date(a.due_date, "—")] for a in case.actions],
        html_cols={0}, numeric={3}))


# ================================================================ tab 5: grounds and paper book


def _grounds(case: CaseFile) -> None:
    st.markdown("**Draft grounds of appeal**" + (" — edited" if case.grounds_edited else ""))
    text = st.text_area("Grounds (one per paragraph, numbered)", "\n\n".join(case.grounds),
                        height=360, key=f"grounds_{state.edit_version()}",
                        label_visibility="collapsed")
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Save grounds", disabled=text.strip() == "\n\n".join(case.grounds).strip()):
        paras = [p for p in text.replace("\r", "").split("\n\n")]
        state.apply_edit(lambda c: pipeline.set_grounds(c, paras))
    if c2.button("Restore template", disabled=not case.grounds_edited):
        state.apply_edit(lambda c: pipeline.set_grounds(c, None))
    st.caption("Rule 8, ITAT Rules: concise grounds under distinct heads, without argument or "
               "narrative. Edited grounds are kept when the rules re-run.")


def _paper_book(case: CaseFile) -> None:
    st.markdown("**Paper book index**" + (" — edited" if case.paper_book_edited else ""))
    rows = [{"Particulars": e.particulars, "Filed before": FILED_LABELS[e.filed_before],
             "Pages": e.pages or ""} for e in case.paper_book]
    edited = st.data_editor(
        pd.DataFrame(rows, columns=["Particulars", "Filed before", "Pages"]),
        key=f"pb_{state.edit_version()}", hide_index=True, num_rows="dynamic",
        use_container_width=True, height=min(36 * (len(rows) + 2) + 3, 1000),
        column_config={"Particulars": st.column_config.TextColumn("Particulars", width="large",
                                                                  required=True),
                       "Filed before": st.column_config.SelectboxColumn(
                           "Filed before", options=list(FILED_LABELS.values())),
                       "Pages": st.column_config.TextColumn("Pages", width="small")})
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Save index"):
        code = _inv(FILED_LABELS)
        detected = {e.particulars: e.detected_from for e in case.paper_book}
        entries = [PaperBookEntry(s_no=n, particulars=str(r["Particulars"]).strip(),
                                  filed_before=code.get(r["Filed before"]),
                                  pages=(str(r["Pages"]).strip() or None)
                                  if pd.notna(r["Pages"]) else None,
                                  detected_from=detected.get(str(r["Particulars"]).strip()))
                   for n, (_, r) in enumerate(edited.iterrows(), start=1)
                   if pd.notna(r["Particulars"]) and str(r["Particulars"]).strip()]
        state.apply_edit(lambda c: pipeline.set_paper_book(c, entries))
    if c2.button("Restore generated index", disabled=not case.paper_book_edited):
        state.apply_edit(lambda c: pipeline.set_paper_book(c, None, state.kb()))
    st.caption("The Pages column refers to the page numbers of the paginated paper book PDF "
               "uploaded on the ITAT e-filing portal.")


def tab_grounds(case: CaseFile) -> None:
    """Editable grounds and paper book index."""
    _grounds(case)
    st.divider()
    _paper_book(case)


# ================================================================ tab 6: verification log


def verification_count(case: CaseFile) -> int:
    """Badge on the tab title: log entries plus unverified items."""
    return len(case.verification_log) + len(pipeline.unverified_items(case))


def tab_verification(case: CaseFile) -> None:
    """Unverified items (confirm and keep) and the filterable verification log."""
    items = pipeline.unverified_items(case)
    if items:
        theme.render_callout(f"{len(items)} item(s) could not be found word for word in the "
                             "order. They are left out of the outputs unless you confirm them.",
                             tone="amber", title="Unverified items")
        for item in items:
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{escape(item.label)}**")
                    for ev in item.evidence:
                        theme.render_html(theme.quote_html(ev.source_snippet, ref(ev)))
                with c2:
                    if st.button("Confirm and keep", key=f"conf_{item.kind}_{item.key}"):
                        state.apply_edit(lambda c, k=item.kind, key=item.key:
                                         pipeline.confirm_item(c, k, key))
    else:
        theme.render_callout("Every extract used in the outputs was found in the order.",
                             tone="green", title="All extracts verified or confirmed")
    needle = st.text_input("Filter the log", key="vlog_filter", placeholder="e.g. I3, page, rate")
    entries = [e for e in case.verification_log if needle.lower() in e.lower()]
    if entries:
        theme.render_html("<ul>" + "".join(f"<li>{escape(e)}</li>" for e in entries) + "</ul>")
    else:
        st.caption("No log entries." if not needle else "No entries match the filter.")
    no_text = case.main.no_text_pages + (case.ao.no_text_pages if case.ao else [])
    if no_text:
        st.caption(f"Pages with no readable text (NO_TEXT): {', '.join(map(str, no_text))}.")


# =========================================================================== page


def tab_labels(case: CaseFile) -> list[str]:
    """Tab titles; the Verification Log carries its count as a badge (SPEC §10.3)."""
    return [*TAB_NAMES[:-1], f"{TAB_NAMES[-1]} ({verification_count(case)})"]


def selected_tab(labels: list[str]) -> str:
    """The label of the tab to show: the one the reviewer opened last (by stable name), so a
    rerun after an edit or a finished AI note never jumps back to the first tab."""
    name = st.session_state.get(TAB_STATE, TAB_NAMES[0])
    index = TAB_NAMES.index(name) if name in TAB_NAMES else 0
    return labels[index]


def _remember_tab(labels: list[str]) -> None:
    """Tab-bar callback: store the open tab by its stable name (labels carry counts)."""
    label = st.session_state.get(TAB_KEY)
    if label in labels:
        st.session_state[TAB_STATE] = TAB_NAMES[labels.index(label)]


def render(case: CaseFile) -> None:
    """Step 3: strip, notices and the tabs."""
    render_strip(case)
    left, right = st.columns([5, 1])
    if case.supporting:
        left.caption("Supporting documents: " + "; ".join(
            f"{s.label} ({s.doc.filename})" for s in case.supporting))
    if right.button("Reprocess case", key="reprocess", use_container_width=True,
                    help="Read the saved orders again with the current rules; keeps case notes, "
                         "comments, hearings and issues you added."):
        case_notes.reprocess_dialog(case)
    notice = state.pop_notice()
    if notice:
        tone, text = notice
        if tone == "red":
            theme.render_error(text, title="The change was not applied")
        else:
            theme.render_callout(text, tone=tone)  # type: ignore[arg-type]
    for err in case.blocking_errors:
        theme.render_error(err, "Edit the date in the Order Details tab; approval stays "
                                "disabled until this is fixed.",
                           title="Blocking error")
    labels = tab_labels(case)
    tabs = st.tabs(labels, key=TAB_KEY, default=selected_tab(labels), on_change=_remember_tab,
                   args=(labels,))
    with tabs[0]:
        tab_order_details(case)
    with tabs[1]:
        tab_issue_trail(case)
    with tabs[2]:
        tab_tax_effect(case)
    with tabs[3]:
        tab_decisions(case)
    with tabs[4]:
        tab_grounds(case)
    with tabs[5]:
        case_notes.tab_case_notes(case)
    with tabs[6]:
        case_notes.tab_case_laws(case)
    with tabs[7]:
        hearings.render(case.matter_id)
    with tabs[8]:
        tab_verification(case)
