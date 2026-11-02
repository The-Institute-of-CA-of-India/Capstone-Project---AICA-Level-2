"""Help & About: how it works, engines, privacy, disclaimer, version (SPEC §10.3)."""

from __future__ import annotations

from html import escape

import streamlit as st

from appealiq import APP_NAME, DISCLAIMER, __version__
from appealiq.ui import theme

HOW_IT_WORKS = [
    "Upload the order appealed against (and optionally the AO's order), and enter the date "
    "of service.",
    "AppealIQ reads the text, using OCR for scanned pages, and identifies the type of order.",
    "It extracts the order details and each issue, with page and para references.",
    "Every extract is checked word for word against the order; anything that does not match "
    "is flagged.",
    "Limitation, fee, validity checks, tax effect and recommendations are computed from the "
    "rules files.",
    "You review and edit the results, approve them, and download the report and filing kit.",
]

ENGINES = [
    ("Standard", "Rules and machine-learning models on this computer. Always available; it "
                 "does all extraction, and every date, fee, tax effect and recommendation is "
                 "computed by Python from the rules files — never by an AI model."),
    (
        "Local AI (LM Studio / Ollama)",
        "A language model running on this computer writes optional AI notes (summary and "
        "strategy note) for adverse issues. Nothing leaves the machine.",
    ),
    (
        "Cloud AI (Claude)",
        "Optional. The text of the order is sent to the Anthropic API only after a "
        "confidentiality warning you accept for each case; the report records its use.",
    ),
]


def render() -> None:
    """Render the Help & About page."""
    st.title("Help & About")
    steps = "".join(f"<li>{escape(s)}</li>" for s in HOW_IT_WORKS)
    theme.render_card("How it works", f"<ol>{steps}</ol>")
    engines = "".join(f"<li><strong>{escape(n)}</strong> — {escape(d)}</li>" for n, d in ENGINES)
    theme.render_card("Engines", f"<ul>{engines}</ul>")
    theme.render_card(
        "Data privacy",
        "<p>In Standard and Local mode, no document text or data leaves this computer. The app "
        "runs on 127.0.0.1 only, sends no usage statistics and loads no external fonts or "
        "scripts. Cloud mode is used only when you choose it for a case.</p>"
        "<p>Every extract is checked word for word against the order; anything that cannot be "
        "found is marked Unverified and left out of the outputs unless you confirm it. Outputs "
        "are generated only after a named reviewer approves the analysis. AppealIQ never "
        "suggests or invents case law.</p>",
    )
    theme.render_card(
        "Desktop shortcut",
        "<p>setup.bat creates an <strong>AppealIQ</strong> shortcut on the desktop. It starts "
        "the app in the background and opens it in a Microsoft Edge app window; closing that "
        "window stops the app. run.bat starts the app with a console window instead.</p>",
    )
    theme.render_card("Disclaimer", f"<p>{escape(DISCLAIMER)}</p>")
    theme.render_card(
        "About",
        f"<p>{escape(APP_NAME)} version {escape(__version__)}</p>",
    )
