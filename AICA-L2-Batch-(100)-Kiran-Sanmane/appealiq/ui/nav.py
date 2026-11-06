"""Pages, URL paths and the sidebar (SPEC §10.2; Phase 11 U1, U6).

Home is the default page and is served at the root URL ("/"). Streamlit ignores ``url_path`` for
the default page, so an old "/home" link used to raise "Page not found — Running the app's main
page". "/home" is now a hidden alias that opens Home. The sidebar is drawn here (Streamlit's
own page list is hidden): the AppealIQ wordmark and version at the top, the five pages in SPEC
order, and a privacy badge at the bottom.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import NamedTuple

import streamlit as st

from appealiq import APP_NAME, __version__
from appealiq.ui import page_help, page_home, page_new, page_register, page_settings

BADGE_OFFLINE = "Offline · Data stays on this computer"
BADGE_CLOUD = "Cloud mode on"


class PageSpec(NamedTuple):
    """One page: key in ``st.session_state["pages"]``, sidebar title and URL path."""

    key: str
    title: str
    url_path: str  # "" = the root URL (the default page)
    render: Callable[[], None]


PAGES: tuple[PageSpec, ...] = (
    PageSpec("home", "Home", "", page_home.render),
    PageSpec("new", "New Analysis", "new-analysis", page_new.render),
    PageSpec("register", "Case Register", "register", page_register.render),
    PageSpec("settings", "Settings", "settings", page_settings.render),
    PageSpec("help", "Help & About", "help", page_help.render),
)
# Old or hand-typed URL paths that open a page instead of "Page not found".
ALIASES: dict[str, str] = {"home": "home"}


def routable_paths() -> set[str]:
    """Every URL path the app answers ("" is the root)."""
    return {p.url_path for p in PAGES} | set(ALIASES)


def _alias(target: str) -> Callable[[], None]:
    def go() -> None:
        st.switch_page(st.session_state["pages"][target])
    go.__name__ = f"alias_to_{target}"
    return go


def build_pages() -> dict[str, st.Page]:
    """The ``st.Page`` objects: the five pages, then the hidden aliases."""
    pages = {spec.key: st.Page(spec.render, title=spec.title, url_path=spec.url_path or None,
                               default=spec.url_path == "") for spec in PAGES}
    for path, target in ALIASES.items():
        pages[f"alias:{path}"] = st.Page(_alias(target), title=f"{target} (alias)",
                                         url_path=path)
    return pages


def privacy_badge_html(cloud_on: bool) -> str:
    """Sidebar foot badge: offline (default) or cloud mode for the current case."""
    css, text = ("aiq-side-badge cloud", BADGE_CLOUD) if cloud_on else \
        ("aiq-side-badge", BADGE_OFFLINE)
    return f'<div class="aiq-side-foot"><span class="{css}">{escape(text)}</span></div>'


def wordmark_html() -> str:
    """Sidebar head: the AppealIQ wordmark and the version."""
    return (f'<div class="aiq-wordmark"><span class="aiq-wm-name">{escape(APP_NAME)}</span>'
            f'<span class="aiq-wm-ver">v{escape(__version__)}</span></div>')


def render_sidebar(pages: dict[str, st.Page], cloud_on: bool) -> None:
    """Wordmark, page links in SPEC §10.2 order, and the privacy badge."""
    with st.sidebar:
        st.markdown(wordmark_html(), unsafe_allow_html=True)
        for spec in PAGES:
            st.page_link(pages[spec.key], label=spec.title)
        st.markdown(privacy_badge_html(cloud_on), unsafe_allow_html=True)
