"""New Analysis wizard: Upload & Details → Processing → Review → Approve & Download (SPEC §10.3).

The pipeline runs in a worker thread (``pipeline.PipelineJob``); Step 2 polls it with
``st.fragment(run_every=…)`` so the screen never freezes. State survives step navigation in
``st.session_state``; the CaseFile is autosaved after processing, after every edit and on
approval (SPEC §10.4).
"""

from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st

from appealiq import pipeline
from appealiq.fmt import fmt_date
from appealiq.models import SUPPORTING_KINDS, Act, CaseFile, StageResult
from appealiq.outputs import OutputError
from appealiq.ui import case_notes, review, state, theme

logger = logging.getLogger(__name__)

STEPS = ["Upload & Details", "Processing", "Review", "Approve & Download"]
FORM_KEYS = ["n_matter", "n_client", "n_service", "n_dept", "n_dept_date", "n_preset",
             "n_custom", "n_engine", "n_cloud_ack", "n_reviewer", "n_reviewer_other",
             "n_ack_unverified", "n_approve", "n_case_notes",
             *(f"n_sup_kind{n}" for n in range(1, pipeline.SUPPORTING_SLOTS + 1))]
SUP_SLOTS = [f"sup_file{n}" for n in range(1, pipeline.SUPPORTING_SLOTS + 1)]
JOB_KEY = "pipeline_job"
AUTO_ADVANCE_S = 3.0
MIME = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf"}
CLOUD_WARNING = ("Cloud mode sends the text of the order(s) for this case to the Anthropic API "
                 "outside this computer. Use it only where the client's engagement terms permit. "
                 "Standard and Local modes keep everything on this computer.")


def step() -> int:
    """Current wizard step (1–4)."""
    return st.session_state.get("wizard_step", 1)


def go(to: int) -> None:
    """Move to a step and rerun the whole page."""
    st.session_state["wizard_step"] = to
    st.session_state["wizard_max"] = max(st.session_state.get("wizard_max", 1), to)
    st.rerun()


def reset() -> None:
    """Start a fresh analysis (the previous matter stays saved in the register)."""
    for key in [*FORM_KEYS, "main_file", "ao_file", *SUP_SLOTS, state.CASE_KEY, JOB_KEY,
                "wizard_step",
                "wizard_max", "engine_checks", "finished_at", "pdf_message", "engine_label",
                review.TAB_KEY, review.TAB_STATE, review.OPEN_ISSUE]:
        st.session_state.pop(key, None)


def _act_banner(case: CaseFile | None) -> None:
    if case is not None and case.classification is not None \
            and case.classification.act != Act.IT_ACT_1961:
        theme.render_callout(pipeline.ACT_BANNER, tone="red",
                             title="Income-tax Act, 2025 / unknown Act")


# =========================================================================== step 1


def _uploader(label: str, slot: str, help_text: str) -> None:
    stored = st.session_state.get(slot)
    up = st.file_uploader(label, type=["pdf"], key=f"{slot}_up", help=help_text)
    if up is not None:
        st.session_state[slot] = (up.name, up.getvalue())
    elif stored is not None:
        name, data = stored
        c1, c2 = st.columns([4, 1])
        c1.caption(f"Uploaded: {name} ({len(data) / 1_048_576:.1f} MB)")
        if c2.button("Remove", key=f"{slot}_rm"):
            st.session_state.pop(slot, None)
            st.rerun()


def _supporting_uploads() -> None:
    """Up to three optional supporting documents, each with its type (CR-009 C)."""
    shown = sum(st.session_state.get(slot) is not None for slot in SUP_SLOTS)
    with st.expander(f"Supporting documents (optional){f' — {shown} added' if shown else ''}",
                     expanded=bool(shown), icon=":material/attach_file:"):
        st.caption("Form 35 / grounds of appeal help identify the issues; submissions supply "
                   "the assessee's own words for each issue ([Sub p.x] references). All are "
                   "listed in the paper book index.")
        kinds = list(SUPPORTING_KINDS)
        for n, slot in enumerate(SUP_SLOTS, start=1):
            st.selectbox(f"Document {n} — type", kinds, key=f"n_sup_kind{n}",
                         format_func=SUPPORTING_KINDS.get)
            _uploader(f"Document {n} (PDF)", slot, "Optional. PDF, up to 50 MB.")


def _engine_checks(force: bool = False) -> dict[str, tuple[bool, str]]:
    checks = st.session_state.get("engine_checks")
    if checks is None or force or time.time() - checks[0] > 60:
        s, p = state.settings(), state.paths()
        with st.spinner("Checking engine availability…"):
            checks = (time.time(), {k: pipeline.engine_status(k, s, p)
                                    for k in ("standard", "lmstudio", "claude")})
        st.session_state["engine_checks"] = checks
    return checks[1]


def _engine_picker() -> tuple[str, bool]:
    checks = _engine_checks()
    s = state.settings()
    names = {"standard": "Standard",
             "lmstudio": f"Local AI ({s.lmstudio.server_label})",
             "claude": "Cloud AI"}
    kind = st.radio("Engine", list(names), key="n_engine", horizontal=True,
                    format_func=lambda k: names[k] + ("" if checks[k][0] else " — unavailable"),
                    help="Extraction is always done by the Standard engine on this computer. "
                         "Local or Cloud AI adds AI notes on demand in the Review step.")
    ok, message = checks[kind]
    theme.render_callout(message if ok else f"{message} The Standard engine will be used; you "
                         "can still generate AI notes later if the engine becomes available.",
                         tone="green" if ok else "amber")
    if st.button("Re-check availability", key="n_recheck"):
        _engine_checks(force=True)
        st.rerun()
    ack = False
    if kind == "claude":
        theme.render_callout(CLOUD_WARNING, tone="amber", title="Confidentiality warning")
        ack = st.checkbox("I confirm that cloud processing is permitted for this case.",
                          key="n_cloud_ack")
    return kind, ack


def _rate_picker() -> tuple[str, Decimal | None]:
    rates = state.kb().rates
    if rates is None:
        theme.render_error("rates.yaml could not be loaded.", "Check the rules folder in Settings.")
        return "", None
    st.markdown("**Tax rate**")
    code = case_notes.rate_cascade(rates, "n_rate", current=st.session_state.get("n_preset"),
                                   stacked=True)
    st.session_state["n_preset"] = code
    custom = None
    if code == rates.custom.code:
        value = st.number_input("Custom effective rate (%)", min_value=0.001, max_value=100.0,
                                value=30.0, step=0.5, format="%.3f", key="n_custom")
        custom = Decimal(str(value))
    st.caption(rates.ui_note + " Additions u/s 68 to 69D always use the s. 115BBE rate.")
    return code, custom


def _save_upload(matter_id: str, slot: str, filename: str) -> tuple[str, object] | None:
    stored = st.session_state.get(slot)
    if stored is None:
        return None
    name, data = stored
    folder = state.paths().uploads_dir / matter_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    target.write_bytes(data)
    return name, target


def _process(matter_id: str, client: str, service: date, dept: bool, dept_date: date | None,
             preset: str, custom: Decimal | None, kind: str, ack: bool) -> None:
    s, p = state.settings(), state.paths()
    try:
        matter_id = pipeline.validate_matter_id(matter_id)
        inputs = pipeline.make_inputs(state.kb(), date_of_service=service, rate_preset=preset,
                                      custom_rate_percent=custom, dept_appeal_received=dept,
                                      dept_appeal_receipt_date=dept_date, engine=kind)
        main = _save_upload(matter_id, "main_file", "main.pdf")
        ao = _save_upload(matter_id, "ao_file", "ao.pdf")
        supporting = []
        for n, slot in enumerate(SUP_SLOTS, start=1):
            # Saved by position, so supN.pdf matches the document ID that reprocessing reads.
            name = pipeline.supporting_upload_name(len(supporting) + 1)
            saved = _save_upload(matter_id, slot, name)
            if saved is not None:
                sup_kind = st.session_state.get(f"n_sup_kind{n}") or "OTHER"
                supporting.append((saved[1], saved[0], sup_kind))
        engine = pipeline.build_engine(kind, s, p, cloud_ack=ack)
    except (ValueError, OSError, pipeline.RulesError) as exc:
        message = getattr(exc, "message", None) or str(exc)
        st.session_state[state.NOTICE_KEY] = ("red", message)
        logger.warning("Could not start processing: %s", message)
        st.rerun()
    assert main is not None
    job = pipeline.PipelineJob(
        with_ao=ao is not None, matter_id=matter_id, client=client.strip(), inputs=inputs,
        main_pdf=main[1], main_filename=main[0], ao_pdf=ao[1] if ao else None,
        ao_filename=ao[0] if ao else None, paths=p, engine=engine, today=state.today(),
        rag=s.rag, kb=state.kb(), materiality=s.materiality, supporting=supporting,
        ai_fallback=s.lmstudio if s.lmstudio.ai_fallback else None).start()
    st.session_state[JOB_KEY] = job
    st.session_state.pop(state.CASE_KEY, None)
    st.session_state.pop("finished_at", None)
    st.session_state["engine_label"] = pipeline.engine_label(kind, s)
    st.session_state["wizard_max"] = 2
    go(2)


def step1() -> None:
    """Upload & Details (SPEC §3): Process stays disabled until the required fields are filled."""
    notice = state.pop_notice()
    if notice:
        theme.render_error(notice[1], title="Processing could not start")
    if state.current_case() is not None:
        theme.render_callout("A processed case is open. Processing again replaces it with a new "
                             "analysis (the saved case stays in the register).",
                             tone="neutral")
    today = state.today()
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Case details")
        matter_id = st.text_input("Case ID", key="n_matter", max_chars=40,
                                  placeholder="e.g. KT-2022-23",
                                  help="Letters, digits, hyphens and underscores only.")
        client = st.text_input("Client", key="n_client", max_chars=120)
        service = st.date_input("Date of service of the order", value=None, key="n_service",
                                format="DD-MM-YYYY", max_value=today,
                                min_value=date(2015, 4, 1))
        st.caption("Limitation runs from the date of communication/service, not the date of the "
                   "order.")
        dept = st.toggle("Revenue's appeal received", key="n_dept")
        dept_date = None
        if dept:
            dept_date = st.date_input("Date of receipt of the notice of appeal", value=None,
                                      key="n_dept_date", format="DD-MM-YYYY", max_value=today)
        preset, custom = _rate_picker()
    with right:
        st.subheader("Orders")
        _uploader("Order appealed against (required)", "main_file",
                  "CIT(A) / JCIT(A) order u/s 250, revision u/s 263, CIT(E) order u/s 12AB / "
                  "80G(5), or final order u/s 143(3) r.w.s. 144C(13). PDF, up to 50 MB.")
        _uploader("Assessment order of AO (optional — enables issue trail)", "ao_file",
                  "The AO's order, to trace each addition to its appellate outcome.")
        _supporting_uploads()
        kind, ack = _engine_picker()
    errors = pipeline.step1_errors(
        matter_id=matter_id, client=client, has_main=st.session_state.get("main_file") is not None,
        date_of_service=service, today=today, dept_appeal_received=dept,
        dept_appeal_receipt_date=dept_date, engine=kind, cloud_ack=ack)
    st.divider()
    c1, c2 = st.columns([1, 4])
    clicked = c1.button("Process", type="primary", disabled=bool(errors),
                        use_container_width=True)
    if errors:
        c2.caption("To enable Process: " + " ".join(errors))
    else:
        c2.caption("Processing runs on this computer and takes a few seconds for a typical "
                   "order.")
    if clicked and not errors and service is not None:
        _process(matter_id, client, service, dept, dept_date, preset, custom, kind, ack)


# =========================================================================== step 2


def _duration(ms: int) -> str:
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


def _stage_rows(snap: pipeline.JobSnapshot) -> list[tuple[str, str, str, str]]:
    by_stage = {r.stage: r for r in snap.results}
    rows: list[tuple[str, str, str, str]] = []
    for name in snap.planned:
        label = pipeline.stage_label(name)
        r = by_stage.get(name)
        if r is not None:
            message = "" if r.status == "ok" else r.message
            rows.append((r.status, label, message, _duration(r.duration_ms)))
        elif name == snap.running:
            rows.append(("running", label, "", ""))
        else:
            rows.append(("skipped" if snap.finished else "pending", label,
                         "Not run" if snap.finished else "", ""))
    for r in snap.results:  # cancellation / unexpected failure
        if r.stage not in snap.planned:
            rows.append(("failed", pipeline.stage_label(r.stage), r.message, ""))
    return rows


def _log_lines(snap: pipeline.JobSnapshot) -> str:
    return "\n".join(f"[{r.status.upper():6}] {pipeline.stage_label(r.stage)} "
                     f"({_duration(r.duration_ms)}): {r.message}" for r in snap.results) \
        or "Starting…"


@st.fragment(run_every=0.5)
def _processing_panel() -> None:
    job: pipeline.PipelineJob | None = st.session_state.get(JOB_KEY)
    if job is None:
        theme.render_callout("Nothing is being processed.", tone="neutral")
        return
    snap = job.snapshot()
    done = len([r for r in snap.results if r.stage in snap.planned])
    status = "Finished" if snap.finished else ("Cancelling after the current stage…"
                                                if job.cancelling else "Processing…")
    st.progress(min(done / max(len(snap.planned), 1), 1.0),
                text=f"{status} {_duration(snap.elapsed_ms)}")
    theme.render_html(theme.stage_list_html(_stage_rows(snap)))  # type: ignore[arg-type]
    with st.expander("Processing log"):
        st.code(_log_lines(snap), language=None)
    if not snap.finished:
        if st.button("Cancel", disabled=job.cancelling, key="cancel_job"):
            job.cancel()
        return
    run = snap.run
    if run is None or run.case is None:
        _failed(snap)
        return
    finished_at = st.session_state.setdefault("finished_at", time.time())
    if state.current_case() is None or state.current_case().matter_id != run.case.matter_id:
        state.set_case(run.case)
    warns = [r for r in run.results if r.status == "warn"]
    advice = pipeline.run_advice(run.results, has_ao=job.has_ao)
    theme.render_card("Analysis complete", (
        f"<p><strong>{escape(pipeline.run_summary(run.case))}</strong></p>"
        + (f'<p class="aiq-muted">{len(warns)} stage(s) finished with a warning — see what to '
           "do below.</p>" if warns else "")
        + ('<p class="aiq-muted">Opening the Review step…</p>' if not (warns or advice)
           else "")))
    _stage_actions(job, warns, advice)
    if st.button("Continue to Review", type="primary", key="to_review") or (
            not (warns or advice) and time.time() - finished_at >= AUTO_ADVANCE_S):
        st.session_state.pop(JOB_KEY, None)
        st.session_state["wizard_max"] = 4
        st.session_state["wizard_step"] = 3
        st.rerun(scope="app")


def _retry(job: pipeline.PipelineJob, key: str) -> None:
    """"Retry this step": the run starts again with the same inputs (CR-009 C)."""
    if st.button("Retry this step", key=key,
                 help="Processing runs again with the same files and inputs; the stages build "
                      "on each other, so it starts from the first stage (a few seconds)."):
        st.session_state[JOB_KEY] = job.retry()
        st.session_state.pop("finished_at", None)
        st.session_state.pop(state.CASE_KEY, None)
        st.rerun()


def _stage_actions(job: pipeline.PipelineJob, results: list[StageResult],
                   advice: list[str]) -> None:
    """Each warned / failed stage with its corrective action and a Retry button."""
    tess = _tesseract_available()
    for n, r in enumerate(results):
        action = pipeline.corrective_action(r, tesseract_available=tess, has_ao=job.has_ao)
        with st.container(border=True):
            st.markdown(f"**{escape(pipeline.stage_label(r.stage))}** — {escape(r.message)}")
            if action:
                st.caption(f"What to do: {action}")
            _retry(job, f"retry_{r.stage}_{n}")
    for line in advice:
        theme.render_callout(line, tone="neutral", title="Tip")


def _tesseract_available() -> bool:
    cached = st.session_state.get("tess_ok")
    if cached is None:
        cached = st.session_state["tess_ok"] = pipeline.detect_tesseract().available
    return bool(cached)


def _failed(snap: pipeline.JobSnapshot) -> None:
    run = snap.run
    failed = next((r for r in reversed(run.results) if r.status == "failed"), None) \
        if run else None
    job: pipeline.PipelineJob | None = st.session_state.get(JOB_KEY)
    if failed is not None and failed.stage == "cancelled":
        theme.render_callout(pipeline.MSG_CANCELLED, tone="neutral", title="Cancelled")
    else:
        message = failed.message if failed else "Processing stopped."
        action = pipeline.corrective_action(failed, tesseract_available=_tesseract_available()) \
            if failed else None
        theme.render_error(message, action or "Check the upload and the inputs in Step 1, then "
                                              "try again.",
                           details=_log_lines(snap), title="Processing stopped")
        if job is not None:
            _retry(job, "retry_failed")
        st.download_button("Download diagnostic log", pipeline.diagnostic_log(state.paths()),
                           file_name="appealiq_diagnostic.log", mime="text/plain")
    if st.button("Back to Upload & Details", key="back_step1"):
        st.session_state.pop(JOB_KEY, None)
        st.session_state["wizard_step"] = 1
        st.rerun(scope="app")


def step2() -> None:
    """Processing: stage list with status and duration, progress bar, log, Cancel."""
    _processing_panel()


# =========================================================================== step 4


def _reviewer() -> str:
    reviewers = state.settings().reviewers
    if not reviewers:
        return st.text_input("Reviewer name", key="n_reviewer_other",
                             help="Add reviewers in Settings to pick them from a list.")
    other = "Someone else…"
    pick = st.selectbox("Reviewer", [*reviewers, other], key="n_reviewer")
    if pick == other:
        return st.text_input("Reviewer name", key="n_reviewer_other")
    return pick


def _checklist_html(items: list[pipeline.ChecklistItem]) -> str:
    rows = "".join(
        f'<div class="aiq-check">{theme.stage_icon_html("ok" if i.ok else "pending")}'
        f"<div><strong>{escape(i.label)}</strong>"
        + (f'<br><span class="aiq-muted">{escape(i.detail)}</span>' if i.detail else "")
        + "</div></div>" for i in items)
    return rows


def card_text(kind: str, size_bytes: int | None, pdf_note: str | None = None) -> tuple[str, str]:
    """Output card title and format line (U5): "ITAT Appeal Readiness Report" /
    "PDF · 212 KB" — the document type and format, not the long file name."""
    title, suffix = pipeline.OUTPUT_KINDS[kind]
    title = title.removesuffix(" (PDF)")
    if size_bytes is not None:
        return title, theme.file_meta(Path(suffix).suffix, size_bytes)
    if kind == "report_pdf":
        return title, pdf_note or "PDF unavailable — DOCX provided"
    return title, f"{theme.file_meta(Path(suffix).suffix, None)} · not generated"


def _outputs(case: CaseFile) -> None:
    files = pipeline.output_files(state.paths(), case.matter_id)
    pdf_note = st.session_state.get("pdf_message")
    cols = st.columns(3, gap="medium")
    for n, kind in enumerate(pipeline.OUTPUT_KINDS):
        path = files.get(kind)
        title, sub = card_text(kind, path.stat().st_size if path else None, pdf_note)
        with cols[n % 3], st.container(border=True, key=f"outcard_{kind}"):
            theme.render_html(theme.output_card_html(title, sub))
            if path is not None:
                st.download_button("Download", path.read_bytes(), file_name=path.name,
                                   mime=MIME.get(path.suffix, "application/octet-stream"),
                                   key=f"dl_{kind}", use_container_width=True)
            else:
                st.button("Download", disabled=True, key=f"dl_{kind}", use_container_width=True)


def step4(case: CaseFile) -> None:
    """Approve & Download: checklist, reviewer, approval box, output cards."""
    review.render_strip(case)
    if case.approved_by:
        when = case.approved_at.strftime("%d-%m-%Y %H:%M") if case.approved_at else ""
        theme.render_callout(f"Approved by {case.approved_by} on {when}. The case is saved in "
                             "the Case Register; outputs are below.", tone="green",
                             title="Approved")
        _outputs(case)
        st.caption("Editing the review after approval withdraws the approval; approve again to "
                   "regenerate the outputs.")
        return
    pending = pipeline.unverified_items(case)
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Approval")
        reviewer = _reviewer()
        acknowledged = True
        if pending:
            acknowledged = st.checkbox(
                f"I acknowledge that {len(pending)} unverified item(s) will be left out of the "
                "outputs (or I will confirm them in the Verification Log tab).",
                key="n_ack_unverified")
        approved = st.checkbox("I have reviewed this analysis and approve it for the report and "
                               "filing kit.", key="n_approve")
        with_notes = st.checkbox("Include case notes and reviewer comments in the report as an "
                                 "internal annexure (not for the client)", value=False,
                                 key="n_case_notes", disabled=case.case_notes.empty and not any(
                                     i.reviewer_comments for i in case.issues))
    items = pipeline.approval_checklist(case, acknowledged=acknowledged, reviewer=reviewer or "",
                                        approved=approved)
    with right:
        theme.render_card("Checklist", _checklist_html(items))
    ready = all(i.ok for i in items)
    if st.button("Approve and generate outputs", type="primary", disabled=not ready):
        try:
            with st.spinner("Generating the report, grounds, paper book index and issue "
                            "register… (PDF conversion can take a minute)"):
                result = pipeline.finalise_matter(case, reviewer, settings=state.settings(),
                                                  paths=state.paths(), today=state.today(),
                                                  include_case_notes=with_notes)
        except pipeline.EditError as exc:
            theme.render_error(exc.message)
            return
        except (OutputError, pipeline.RulesError) as exc:
            theme.render_error(exc.message, "Check the approval and the rules files in Settings, "
                                            "then try again.")
            return
        except OSError as exc:
            logger.exception("Output generation failed")
            theme.render_error("The outputs could not be written.",
                               "Close any open copy of the files in Word or Excel and try again.",
                               details=str(exc))
            return
        state.set_case(result.case)
        pdf = result.bundle.report_pdf
        st.session_state["pdf_message"] = pdf.message if pdf else None
        st.rerun()
    if not ready:
        st.caption("Outputs unlock when every checklist item is complete.")


# =========================================================================== page


def _nav(case: CaseFile | None, current: int) -> None:
    """One aligned row (U5): Back on the left, the next step beside it, New analysis on the
    right; every button the same height and width class."""
    max_step = st.session_state.get("wizard_max", 1)
    if case is None or current == 2:
        return
    st.divider()
    back, main, _, new = st.columns([2, 4, 3, 2], vertical_alignment="center")
    if current != 1 and back.button("Back", key=f"nav_back_{current}",
                                    use_container_width=True):
        go(1 if current == 3 else current - 1)
    if current == 1 and max_step >= 3 and main.button("Return to Review",
                                                      use_container_width=True):
        go(3)
    if current == 3 and main.button("Continue to Approve & Download", type="primary",
                                    use_container_width=True):
        go(4)
    if current == 4 and case.approved_by and main.button("Open Case Register",
                                                         use_container_width=True):
        st.switch_page(st.session_state["pages"]["register"])
    if new.button("New analysis", key=f"nav_new_{current}", use_container_width=True):
        reset()
        st.rerun()


def render() -> None:
    """Render the wizard."""
    st.title("New Analysis")
    if st.session_state.pop("wizard_reset", False):
        reset()
    state.keep(FORM_KEYS)
    case = state.current_case()
    current = step()
    if current >= 3 and case is None:
        current = 1
    _act_banner(case)
    theme.render_stepper(STEPS, current, st.session_state.get("wizard_max", current))
    if current == 1:
        step1()
    elif current == 2:
        step2()
    elif current == 3:
        assert case is not None
        review.render(case)
    else:
        assert case is not None
        step4(case)
    _nav(case, current)
    if case is not None and case.limitation is not None:
        st.caption(f"Case {case.matter_id} · autosaved · Form due "
                   f"{fmt_date(case.limitation.due_date)}")
