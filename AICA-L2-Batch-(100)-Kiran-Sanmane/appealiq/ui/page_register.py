"""Case Register: search, filter, RAG, status, open a case (click its ID), edit or delete a case,
re-download outputs, export (SPEC §10.3 Case Register; CR-009 Session B)."""

from __future__ import annotations

import json
from html import escape

import streamlit as st

from appealiq import pipeline, register
from appealiq.fmt import fmt_date, inr
from appealiq.outputs.matters_xlsx import FILE_NAME, build_matter_list
from appealiq.ui import state, theme
from appealiq.ui.page_home import limitation_cell
from appealiq.ui.page_new import MIME
from appealiq.ui.review import OUTCOME_LABELS, REC_LABELS

RAG_OPTIONS = {"RED": "Red", "AMBER": "Amber", "GREEN": "Green", "EXPIRED": "Expired",
               "NONE": "No due date / filed"}
DELETE_RECORD = "Delete record only"
DELETE_FILES = "Delete record and files"
REGISTER_HEADERS = ["Case", "Client", "AY", "Order", "Form 36 due", "Days left / hearing",
                    "Status", "Filed on", "ITA No.", "Next hearing"]


def _filters() -> tuple[str, list[str], list[str]]:
    c1, c2, c3 = st.columns([3, 2, 2])
    text = c1.text_input("Search", key="reg_search",
                         placeholder="Case, client, AY, order or ITA No.")
    rag = c2.multiselect("RAG", list(RAG_OPTIONS), key="reg_rag", format_func=RAG_OPTIONS.get)
    status = c3.multiselect("Status", list(register.STATUSES), key="reg_status")
    return text, rag, status


def register_rows(records: list[register.MatterRecord]) -> list[list[str]]:
    """Case Register rows: the case ID is a link that opens the case; a filed case shows its
    next hearing instead of the Form 36 countdown."""
    s, today = state.settings(), state.today()
    return [[state.case_link_html(r.matter_id), r.client, r.assessment_year or "—",
             r.order_label or "—", fmt_date(r.due_date, "—"), limitation_cell(r, today, s.rag),
             r.status, fmt_date(r.filing_date, "—"), r.ita_no or "—",
             fmt_date(r.next_hearing, "—")] for r in records]


def _export(records: list[register.MatterRecord]) -> None:
    s, p, today = state.settings(), state.paths(), state.today()
    target = p.outputs_dir / FILE_NAME
    try:
        build_matter_list(records, target, today=today, rag=s.rag, firm=s.firm)
    except OSError as exc:
        theme.render_error("The register could not be exported.",
                           "Close the file if it is open in Excel and try again.", str(exc))
        return
    st.download_button("Export to Excel", target.read_bytes(), file_name=target.name,
                       mime=MIME[".xlsx"], disabled=not records)


@st.dialog("Edit case")
def _edit_dialog(record: register.MatterRecord) -> None:
    p = state.paths()
    st.caption(f"Case {record.matter_id}")
    client = st.text_input("Client", value=record.client)
    ay = st.text_input("Assessment year", value=record.assessment_year or "",
                       placeholder="e.g. 2022-23")
    status = st.selectbox("Status", register.STATUSES,
                          index=register.STATUSES.index(record.status))
    filed = st.date_input("Date of filing of appeal", value=record.filing_date,
                          format="DD/MM/YYYY", max_value=state.today())
    ita = st.text_input("ITA No.", value=record.ita_no or "",
                        placeholder="e.g. ITA No. 123/PUN/2026")
    if st.button("Save", type="primary"):
        try:
            register.update_case(p.db_file, record.matter_id, client=client,
                                 assessment_year=ay, status=status, filing_date=filed,
                                 ita_no=ita, today=state.today())
        except ValueError as exc:
            theme.render_error(str(exc), title="Not saved")
            return
        st.rerun()


@st.dialog("Delete case", width="large")
def _delete_dialog(record: register.MatterRecord) -> None:
    p = state.paths()
    st.markdown(f"Delete case **{escape(record.matter_id)}** ({escape(record.client)})?")
    st.caption(f"**{DELETE_RECORD}**: removes it from the Case Register with its hearing log; "
               "the saved analysis, uploads and outputs stay on this computer. "
               f"**{DELETE_FILES}**: also deletes the saved analysis, the uploaded orders and "
               "the generated reports. This cannot be undone.")
    c1, c2, c3 = st.columns(3)
    choice = None
    if c1.button(DELETE_RECORD, use_container_width=True):
        choice = False
    if c2.button(DELETE_FILES, type="primary", use_container_width=True):
        choice = True
    if c3.button("Cancel", use_container_width=True):
        st.rerun()
    if choice is not None:
        pipeline.delete_case(p, record.matter_id, with_files=choice)
        case = state.current_case()
        if case is not None and case.matter_id == record.matter_id:
            st.session_state["wizard_reset"] = True  # do not keep a deleted case in the wizard
        st.session_state["reg_deleted"] = (record.matter_id, choice)
        st.rerun()


def _detail(record: register.MatterRecord) -> None:
    s, p, today = state.settings(), state.paths(), state.today()
    head, b1, b2, b3 = st.columns([4, 1, 1, 1], vertical_alignment="bottom")
    head.subheader(f"Case {record.matter_id}")
    if b1.button("Open", type="primary", key=f"open_{record.matter_id}",
                 use_container_width=True):
        problem = state.open_case(record.matter_id)
        if problem is None:
            st.switch_page(st.session_state["pages"]["new"])
        theme.render_error(problem)
    if b2.button("Edit", key=f"edit_{record.matter_id}", use_container_width=True):
        _edit_dialog(record)
    if b3.button("Delete", key=f"del_{record.matter_id}", use_container_width=True):
        _delete_dialog(record)
    left, right = st.columns([3, 2], gap="large")
    with left:
        rows = [("Client", record.client), ("AY", record.assessment_year or "—"),
                ("Order", record.order_label or "—"), ("Form", record.form or "—"),
                ("Due date", fmt_date(record.due_date, "—")), ("Status", record.status),
                ("Date of filing", fmt_date(record.filing_date, "—")),
                ("ITA No.", record.ita_no or "—"),
                ("Next hearing", fmt_date(record.next_hearing, "—")),
                ("Engine", pipeline.ENGINE_NAMES.get(record.engine or "", record.engine or "—")),
                ("Issues", str(record.issues) if record.issues is not None else "—"),
                ("Approved by", record.approved_by or "Not approved yet"),
                ("Created", record.created.strftime("%d-%m-%Y %H:%M"))]
        body = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in rows)
        badge = limitation_cell(record, today, s.rag)
        theme.render_card(None, f"<p>{badge}</p><table class=\"aiq-kv\">{body}</table>")
    with right:
        files = pipeline.output_files(p, record.matter_id)
        st.markdown("**Outputs**")
        if not files:
            st.caption("No outputs yet — approve the case in Step 4 to generate them.")
        for kind, path in files.items():
            st.download_button(pipeline.OUTPUT_KINDS[kind][0], path.read_bytes(),
                               file_name=path.name, key=f"rdl_{record.matter_id}_{kind}",
                               mime=MIME.get(path.suffix, "application/octet-stream"),
                               use_container_width=True)
    try:
        case = pipeline.load_case(p, record.matter_id)
    except (OSError, ValueError) as exc:
        theme.render_error("The saved analysis for this case could not be read.",
                           "It may have been moved or deleted, or saved by an older version.",
                           str(exc))
        return
    decisions = {d.issue_id: d for d in case.decisions}
    theme.render_html(theme.table_html(
        ["Issue", "Section", "Outcome", "AO amount", "Relief", "Sustained", "Recommendation"],
        [[f"{i.issue_id} · {i.title}", i.section or "—", OUTCOME_LABELS[i.outcome],
          inr(i.amount_ao, "—"), inr(i.amount_relief, "—"), inr(i.amount_sustained, "—"),
          REC_LABELS[decisions[i.issue_id].recommendation] if i.issue_id in decisions else "—"]
         for i in case.issues], numeric={3, 4, 5}))
    with st.expander("Saved CaseFile (read-only)"):
        data = json.loads(case.model_dump_json(exclude={"main", "ao"}))
        st.json(data, expanded=False)


def render() -> None:
    """Render the Case Register."""
    st.title("Case Register")
    s, p, today = state.settings(), state.paths(), state.today()
    deleted = st.session_state.pop("reg_deleted", None)
    if deleted:
        mid, files = deleted
        theme.render_callout(f"Case {mid} was deleted" + (" with its files." if files else
                             " from the register; its files were kept."), tone="green")
    records = register.list_records(p.db_file, today)
    if not records:
        theme.render_empty("No cases yet", "Cases are added here automatically when an "
                                           "analysis finishes. Start one from New Analysis.")
        return
    text, rag, status = _filters()
    shown = register.search(records, text, today=today, rag=s.rag, rag_filter=rag,
                            status_filter=status)
    theme.render_html(theme.table_html(REGISTER_HEADERS, register_rows(shown),
                                       numeric={4, 7, 9}, html_cols={0, 5}))
    c1, c2 = st.columns([1, 4])
    with c1:
        _export(shown)
    c2.caption(f"{len(shown)} of {len(records)} case(s) shown. Click a case ID to open it.")
    if not shown:
        return
    st.divider()
    ids = [r.matter_id for r in shown]
    clients = {r.matter_id: r.client for r in shown}
    chosen = st.selectbox("Select a case to view, edit or delete", ids, key="reg_open",
                          format_func=lambda m: f"{m} — {clients[m]}")
    _detail(next(r for r in shown if r.matter_id == chosen))
