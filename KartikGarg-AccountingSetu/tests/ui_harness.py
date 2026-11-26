"""Renders one view function for a given user inside Streamlit's AppTest runner (used by test_ui_pages.py)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from services import auth_service  # noqa: E402

c = auth_service.build_context(st.session_state["user_id"])
auth_service.activate_request_identity(c)
st.session_state["ctx"] = c
module, func = st.session_state["page"].split(":")
getattr(importlib.import_module(module), func)()
