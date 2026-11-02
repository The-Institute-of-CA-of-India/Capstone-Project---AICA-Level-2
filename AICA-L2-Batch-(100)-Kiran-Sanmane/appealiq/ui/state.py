"""Session-state helpers shared by the pages (SPEC §10.4: state survives step navigation).

The CaseFile under review lives in ``st.session_state["case"]``. Every reviewer edit goes through
``apply_edit``: the change is applied, the rules / tax effect / decisions are recomputed, the
CaseFile is autosaved and the page reruns.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from appealiq import pipeline
from appealiq.config import Paths, Settings
from appealiq.models import CaseFile
from appealiq.pipeline import KBLoadResult, KnowledgeBase

logger = logging.getLogger(__name__)

CASE_KEY = "case"
NOTICE_KEY = "review_notice"


def settings() -> Settings:
    """Current settings (loaded by app.py on every run)."""
    return st.session_state["settings"]


def paths() -> Paths:
    """Project paths (set by app.py)."""
    return st.session_state["paths"]


def today() -> date:
    """The system date; every date-dependent rule receives it explicitly (SPEC §8.7)."""
    return date.today()


@st.cache_resource(show_spinner=False)
def _rules(rules_dir: str, stamp: tuple[float, ...]) -> KBLoadResult:  # noqa: ARG001 - cache key
    return pipeline.load_knowledge_base(Path(rules_dir))


def rules() -> KBLoadResult:
    """The knowledge base, reloaded when a rules file changes."""
    folder = paths().rules_dir
    stamp = tuple(sorted(p.stat().st_mtime for p in folder.glob("*.yaml")))
    return _rules(str(folder), stamp)


def kb() -> KnowledgeBase:
    """Shortcut for ``rules().kb``."""
    return rules().kb


def keep(keys: Iterable[str]) -> None:
    """Keep widget values alive while their page is not shown (Streamlit drops them)."""
    for key in keys:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def current_case() -> CaseFile | None:
    """The CaseFile in the wizard, if any."""
    return st.session_state.get(CASE_KEY)


def set_case(case: CaseFile) -> None:
    """Replace the CaseFile in the wizard."""
    st.session_state[CASE_KEY] = case


def apply_edit(change: Callable[[CaseFile], CaseFile], *, rerun: bool = True) -> bool:
    """Apply a reviewer edit, recompute §8.7–§8.9, autosave and rerun.

    Returns:
        False if the edit was rejected (the message is stored for the next run).
    """
    case = current_case()
    if case is None:
        return False
    try:
        edited = change(case)
    except pipeline.EditError as exc:
        st.session_state[NOTICE_KEY] = ("red", exc.message)
        if rerun:
            st.rerun()
        return False
    s = settings()
    result = pipeline.recompute(edited, kb(), today=today(), rag=s.rag,
                                materiality=s.materiality)
    set_case(result.case)
    try:
        pipeline.save_edits(result.case, paths())
    except OSError:
        logger.exception("Autosave failed for %s", result.case.matter_id)
        st.session_state[NOTICE_KEY] = ("amber", "The change was applied but could not be saved "
                                                  "to disk. Check that the data folder is "
                                                  "writable.")
    if result.problems:
        st.session_state[NOTICE_KEY] = ("amber", " ".join(result.problems))
    st.session_state["edit_version"] = st.session_state.get("edit_version", 0) + 1
    if rerun:
        st.rerun()
    return True


def edit_version() -> int:
    """Bumped after every edit, so editor widgets start from the recomputed data."""
    return st.session_state.get("edit_version", 0)


def pop_notice() -> tuple[str, str] | None:
    """A message left by the previous edit (tone, text)."""
    return st.session_state.pop(NOTICE_KEY, None)


OPEN_PARAM = "case"  # "?case=<id>": a case link in the Case Register or on Home


def case_link_html(matter_id: str, label: str | None = None) -> str:
    """A link that opens the case in Review (CR-009 Session B: click a case to open it)."""
    return (f'<a class="aiq-case-link" href="?{OPEN_PARAM}={quote(matter_id)}" target="_self" '
            f'title="Open case {escape(matter_id)}">{escape(label or matter_id)}</a>')


def open_case(matter_id: str) -> str | None:
    """Load a saved case into the wizard at Step 3 (Review).

    Returns:
        ``None`` when opened, else a user-facing reason.
    """
    s = settings()
    try:
        case = pipeline.load_case(paths(), matter_id)
    except (OSError, ValueError) as exc:
        logger.warning("Case %s could not be opened: %s", matter_id, exc)
        return (f"Case {matter_id} could not be opened: its saved analysis is missing or was "
                "saved by an older version. Process the order again from New Analysis.")
    set_case(pipeline.recompute(case, kb(), today=today(), rag=s.rag,
                                materiality=s.materiality).case)
    st.session_state["wizard_step"], st.session_state["wizard_max"] = 3, 4
    st.session_state["engine_label"] = pipeline.engine_label(case.inputs.engine, s)
    return None
