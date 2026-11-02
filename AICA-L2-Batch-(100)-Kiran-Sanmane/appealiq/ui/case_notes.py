"""Review tabs and controls added in CR-009 Session C: Case Notes, Case Laws in Orders, the
Category → Regime → Income band rate selector, and Reprocess case."""

from __future__ import annotations

from decimal import Decimal
from html import escape

import pandas as pd
import streamlit as st

from appealiq import pipeline
from appealiq.fmt import fmt_rate
from appealiq.models import CaseFile, CaseNotes, NoteCaseLaw, PendingPoint, doc_label
from appealiq.rules_engine import RatesFile
from appealiq.ui import state, theme

RELIED_ORDER = ["CIT(A)", "Assessee", "AO", "Not clear"]


# =========================================================================== rates


def rate_cascade(rates: RatesFile, key: str, current: str | None = None,
                 allow_custom: bool = True, stacked: bool = False) -> str:
    """Category → Regime / section → Income band selectors (side by side, or one below the
    other with ``stacked``); returns the preset code (or the custom code). ``current``
    preselects a preset."""
    preset = rates.preset(current) if current else None
    categories = rates.categories() + ([rates.custom.label] if allow_custom else [])
    c1, c2, c3 = (st, st, st) if stacked else st.columns([2, 3, 3])
    cat_now = (preset.category or "Other") if preset else (
        rates.custom.label if current == rates.custom.code else categories[0])
    category = c1.selectbox("Category", categories, key=f"{key}_cat",
                            index=categories.index(cat_now) if cat_now in categories else 0)
    if category == rates.custom.label:
        return rates.custom.code
    regimes = rates.regimes(category)
    reg_now = (preset.regime or "—") if preset and preset.category == category else regimes[0]
    regime = c2.selectbox("Regime / section", regimes, key=f"{key}_reg_{category}",
                          index=regimes.index(reg_now) if reg_now in regimes else 0)
    bands = rates.bands(category, regime)
    codes = [b.code for b in bands]
    labels = {b.code: f"{b.band or b.label} — {fmt_rate(b.rate)}"
                      + ("" if b.verified else " (unverified)") for b in bands}
    band = c3.selectbox("Income band (surcharge)", codes, key=f"{key}_band_{category}_{regime}",
                        index=codes.index(current) if current in codes else 0,
                        format_func=labels.get)
    return band


# =========================================================================== case notes


def _pending_frame(notes: CaseNotes) -> pd.DataFrame:
    return pd.DataFrame([{"Done": p.done, "Pending point": p.text} for p in notes.pending]
                        or [{"Done": False, "Pending point": ""}])


def _laws_frame(notes: CaseNotes) -> pd.DataFrame:
    return pd.DataFrame([{"Case name": c.case_name, "Citation": c.citation or "",
                          "Court": c.court or "", "Relied on for": c.proposition or ""}
                         for c in notes.case_laws]
                        or [{"Case name": "", "Citation": "", "Court": "", "Relied on for": ""}])


def _text(value: object) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def notes_from_form(points: str, remarks: str, arguments: str, pending: pd.DataFrame,
                    laws: pd.DataFrame) -> CaseNotes:
    """CaseNotes from the Case Notes form (blank rows dropped)."""
    return CaseNotes(
        points=points, remarks=remarks, arguments=arguments,
        pending=[PendingPoint(text=_text(r["Pending point"]).strip(), done=bool(r["Done"]))
                 for _, r in pending.iterrows() if _text(r["Pending point"]).strip()],
        case_laws=[NoteCaseLaw(case_name=_text(r["Case name"]).strip(),
                               citation=_text(r["Citation"]).strip() or None,
                               court=_text(r["Court"]).strip() or None,
                               proposition=_text(r["Relied on for"]).strip() or None)
                   for _, r in laws.iterrows()
                   if any(_text(r[c]).strip() for c in ("Case name", "Citation", "Court",
                                                        "Relied on for"))])


def tab_case_notes(case: CaseFile) -> None:
    """Points, pending points (done tick), remarks, arguments and case laws (free text)."""
    notes = case.case_notes
    open_points = sum(not p.done for p in notes.pending)
    st.caption("Internal notes for the firm. They are saved with the case, exported to the "
               "Excel issue register, and added to the report only if you tick \"Include case "
               "notes\" when approving.")
    if open_points:
        theme.render_callout(f"{open_points} pending point(s) not yet done.", tone="amber")
    with st.form(f"notes_{state.edit_version()}", border=False):
        c1, c2 = st.columns(2, gap="large")
        points = c1.text_area("Points", value=notes.points, height=140,
                              placeholder="Key points for the appeal…")
        remarks = c2.text_area("Remarks", value=notes.remarks, height=140)
        arguments = st.text_area("Arguments", value=notes.arguments, height=160,
                                 placeholder="Arguments to be advanced before the Tribunal…")
        st.markdown("**Pending points**")
        pending = st.data_editor(_pending_frame(notes), num_rows="dynamic", hide_index=True,
                                 use_container_width=True, key=f"np_{state.edit_version()}",
                                 column_config={
                                     "Done": st.column_config.CheckboxColumn("Done", width=60),
                                     "Pending point": st.column_config.TextColumn(
                                         "Pending point", width="large")})
        st.markdown("**Case laws** (entered by you; AppealIQ never suggests judgments)")
        laws = st.data_editor(_laws_frame(notes), num_rows="dynamic", hide_index=True,
                              use_container_width=True, key=f"nl_{state.edit_version()}",
                              column_config={
                                  "Case name": st.column_config.TextColumn("Case name",
                                                                           width="medium"),
                                  "Citation": st.column_config.TextColumn(
                                      "Citation", help="e.g. [2015] 370 ITR 101 (Bom)"),
                                  "Court": st.column_config.TextColumn("Court"),
                                  "Relied on for": st.column_config.TextColumn(
                                      "Relied on for", width="large")})
        if st.form_submit_button("Save case notes", type="primary"):
            new = notes_from_form(points, remarks, arguments, pending, laws)
            state.apply_edit(lambda c: pipeline.set_case_notes(c, new))


# =========================================================================== case laws in orders


def case_law_rows(case: CaseFile, relied: list[str] | None = None) -> list[list[str]]:
    """Rows of the Case Laws in Orders table (filtered by who relied on it)."""
    rows = []
    for c in case.case_laws:
        if relied and c.relied_by not in relied:
            continue
        where = "; ".join(
            f"{doc_label(e.doc_id) or 'Order'} p.{e.page}" + (f" ¶{e.para_no}" if e.para_no
                                                              else "")
            for e in c.evidence[:1])
        brief = " ".join(f"“{e.source_snippet}”" for e in c.evidence)
        rows.append([c.case_name or "Not stated", c.citation, c.court or "Not stated",
                     c.relied_by, where, brief])
    return rows


def tab_case_laws(case: CaseFile) -> None:
    """Citations found in the AO order, the appellate order and the uploaded submissions."""
    st.caption("Read from the documents: case name, citation and court as written, who relied "
               "on it (from the document and the para), and the document's own sentence(s). "
               "No summaries are written and no judgments are suggested.")
    if not case.case_laws:
        theme.render_empty("No case laws cited",
                           "No citations (e.g. \"[2015] 370 ITR 101 (Bom)\", \"(2019) 101 "
                           "taxmann.com 99\") were found in the orders or the uploaded "
                           "submissions.")
        return
    present = [r for r in RELIED_ORDER if any(c.relied_by == r for c in case.case_laws)]
    relied = st.multiselect("Relied on by", present, default=present,
                            key=f"cl_rel_{case.matter_id}")
    rows = case_law_rows(case, relied)
    theme.render_html(theme.table_html(
        ["Case name", "Citation", "Court", "Relied on by", "Where", "In the document"],
        rows, css="aiq-caselaw"))
    st.caption(f"{len(rows)} of {len(case.case_laws)} citation(s) shown. Check each citation "
               "against the reporter before relying on it.")


# =========================================================================== reprocess


@st.dialog("Reprocess case", width="large")
def reprocess_dialog(case: CaseFile) -> None:
    """Run the analysis again on the saved uploads (CR-009 C)."""
    edits = pipeline.outcome_edits(case)
    kept = ["case notes", "reviewer comments", "hearings",
            f"{sum(i.origin == 'USER_ADDED' for i in case.issues)} issue(s) you added"]
    st.markdown("The orders and supporting documents saved for this case are read again with "
                "the current rules. **Kept:** " + ", ".join(kept) + ".")
    if edits:
        theme.render_callout(f"Your edits to {', '.join(edits)} (outcome, amounts, title or "
                             "section) will be discarded: the values are read again from the "
                             "order.", tone="amber", title="Outcome edits will be discarded")
    if case.approved_by:
        st.caption("The approval is withdrawn; approve again to regenerate the outputs.")
    c1, c2 = st.columns(2)
    label = "Discard edits and reprocess" if edits else "Reprocess"
    if c1.button(label, type="primary", use_container_width=True):
        s = state.settings()
        with st.spinner("Reprocessing… (scanned orders take longer: OCR)"):
            run = pipeline.reprocess_case(case, state.paths(), kb=state.kb(),
                                          today=state.today(), rag=s.rag,
                                          materiality=s.materiality)
        if run.case is None:
            failed = next((r for r in reversed(run.results) if r.status == "failed"), None)
            theme.render_error(failed.message if failed else "Reprocessing stopped.",
                               pipeline.corrective_action(failed) if failed else None,
                               title="Reprocessing stopped")
            return
        state.set_case(run.case)
        warns = [r for r in run.results if r.status == "warn"]
        st.session_state[state.NOTICE_KEY] = (
            "green" if not warns else "amber",
            "Reprocessed." + (f" {len(warns)} stage(s) finished with a warning: "
                              + "; ".join(pipeline.stage_label(r.stage) for r in warns) + "."
                              if warns else ""))
        st.session_state["edit_version"] = st.session_state.get("edit_version", 0) + 1
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def override_rows(case: CaseFile) -> list[list[str]]:
    """Issues with a per-issue rate override (Tax Effect tab)."""
    return [[i.issue_id, i.title, fmt_rate(i.rate_override), escape(i.rate_override_basis or "")]
            for i in case.issues if i.rate_override is not None]


def issue_rate_editor(case: CaseFile) -> None:
    """Per-issue rate override: a preset from the table or a rate typed in (CR-009 C)."""
    rates = state.kb().rates
    issues = [i for i in case.issues if i.nature != "PENALTY"]
    if rates is None or not issues:
        return
    with st.expander("Per-issue rate override", icon=":material/percent:"):
        st.caption("Use when one issue is taxed at a different rate (e.g. a special-rate "
                   "income or another regime). The issue's tax effect, decision and the report "
                   "use the override.")
        labels = {i.issue_id: f"{i.issue_id} · {i.title}" for i in issues}
        issue_id = st.selectbox("Issue", list(labels), format_func=labels.get,
                                key="ovr_issue")
        issue = next(i for i in issues if i.issue_id == issue_id)
        if issue.rate_override is not None:
            st.caption(f"Current override: {issue.rate_override_basis}")
        code = rate_cascade(rates, f"ovr_{issue_id}", allow_custom=True)
        custom = None
        if code == rates.custom.code:
            custom = st.number_input("Rate (%)", min_value=0.001, max_value=100.0, value=30.0,
                                     step=0.5, format="%.3f", key=f"ovr_custom_{issue_id}")
        b1, b2 = st.columns(2)
        if b1.button("Apply to this issue", type="primary", key=f"ovr_apply_{issue_id}"):
            preset = rates.preset(code)
            percent = Decimal(str(custom)) if preset is None else preset.rate * 100
            basis = preset.label if preset is not None else "Rate entered by the reviewer"
            state.apply_edit(lambda c: pipeline.set_issue_rate(c, issue_id, percent, basis))
        if issue.rate_override is not None and b2.button("Remove override",
                                                         key=f"ovr_rm_{issue_id}"):
            state.apply_edit(lambda c: pipeline.set_issue_rate(c, issue_id, None))
