"""Streamlit entry point: page config, theme, top bar and sidebar navigation (SPEC §10)."""

from __future__ import annotations

import logging
import traceback

import streamlit as st

from appealiq import APP_NAME, APP_SUBTITLE, pipeline
from appealiq.config import ensure_data_dirs, get_paths, load_settings, setup_logging
from appealiq.ui import nav, state, theme

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

paths = get_paths()
ensure_data_dirs(paths)
setup_logging(paths)
logger = logging.getLogger("appealiq.app")

loaded = load_settings(paths.settings_file)
st.session_state["settings"] = loaded.settings
st.session_state["paths"] = paths

theme.inject_css()
theme.render_top_bar(
    APP_NAME,
    APP_SUBTITLE,
    loaded.settings.firm.name,
    st.session_state.get("engine_label", "Standard"),
)
for problem in loaded.problems:
    theme.render_callout(problem, tone="amber", title="Settings")

# Health check once per session (SPEC §12.1); the full panel is in Settings.
if "startup_health" not in st.session_state:
    items = pipeline.health_check(paths, loaded.settings, check_llm=False)
    st.session_state["startup_health"] = [i for i in items if not i.ok and not i.optional]
for item in st.session_state["startup_health"]:
    theme.render_callout(f"{item.name}: {item.detail}", tone="red", title="Health check")

# SPEC §10.2: Home · New Analysis · Case Register · Settings · Help & About (own sidebar, U6)
pages = nav.build_pages()
st.session_state["pages"] = pages
current = st.navigation(list(pages.values()), position="hidden")
# A case link ("?case=<id>" in the Case Register or on Home) opens the case in Review.
opened = st.query_params.get(state.OPEN_PARAM)
if opened:
    del st.query_params[state.OPEN_PARAM]
    problem = state.open_case(opened)
    if problem is None:
        st.switch_page(pages["new"])
    theme.render_callout(problem, tone="red", title="Case not opened")
case = st.session_state.get(state.CASE_KEY)
nav.render_sidebar(pages, cloud_on=case is not None and (case.cloud_used
                                                         or case.inputs.engine == "claude"))

try:
    current.run()
except Exception:  # noqa: BLE001 - last line of defence: no traceback reaches the user (§12.3)
    logger.exception("Unhandled error in the UI")
    theme.render_error("Something went wrong on this page. Your work is autosaved.",
                       "Go back to Home and reopen the case from the Case Register. If it "
                       "happens again, download the diagnostic log from the processing screen "
                       "or Settings and share it with support.",
                       details=traceback.format_exc(limit=6))
