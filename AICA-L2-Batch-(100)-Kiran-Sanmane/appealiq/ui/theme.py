"""Design system (SPEC §10.1): CSS injection and small HTML components.

The ``*_html`` functions are pure (string in, string out) so they can be unit-tested; the
``render_*`` wrappers write them to the page. All user text is HTML-escaped. No external
fonts, scripts or images are referenced.
"""

from __future__ import annotations

from html import escape
from typing import Literal

import streamlit as st

TOKENS: dict[str, str] = {
    "primary": "#0B2545",
    "accent": "#13807A",
    "ink": "#1F2933",
    "muted": "#616E7C",
    "bg": "#F5F7FA",
    "surface": "#FFFFFF",
    "border": "#E4E7EB",
    "red": "#B42318",
    "amber": "#B54708",
    "green": "#027A48",
    "red-tint": "#FEF3F2",
    "amber-tint": "#FFFAEB",
    "green-tint": "#ECFDF3",
}

FONT_STACK = '"Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif'

Rag = Literal["RED", "AMBER", "GREEN", "EXPIRED"]
Tone = Literal["neutral", "red", "amber", "green"]
FieldStatus = Literal["OK", "LOW_CONFIDENCE", "UNVERIFIED", "NOT_FOUND", "USER_EDITED"]
StepState = Literal["done", "current", "upcoming", "disabled"]

RAG_LABELS: dict[str, str] = {"RED": "Red", "AMBER": "Amber", "GREEN": "Green", "EXPIRED": "Expired"}
STATUS_LABELS: dict[str, str] = {
    "OK": "OK",
    "LOW_CONFIDENCE": "Low confidence",
    "UNVERIFIED": "Unverified",
    "NOT_FOUND": "Not found",
    "USER_EDITED": "Edited",
}


def _root_vars() -> str:
    return "\n".join(f"  --{name}: {value};" for name, value in TOKENS.items())


CSS = f"""
:root {{
{_root_vars()}
  --font: {FONT_STACK};
}}
html, body, .stApp, .stMarkdown, p, li, td, th, label, input, textarea, select, button {{
  font-family: var(--font);
}}
/* Keep Streamlit's bundled icon font, or icon names render as text. */
[data-testid="stIconMaterial"], .material-symbols-rounded {{
  font-family: "Material Symbols Rounded" !important;
}}
.stApp {{ background: var(--bg); color: var(--ink); font-size: 14px; }}
.block-container {{ max-width: 1280px; padding-top: 16px; padding-bottom: 48px; }}
h1 {{ font-size: 24px !important; font-weight: 600 !important; color: var(--primary); }}
h2 {{ font-size: 18px !important; font-weight: 600 !important; color: var(--primary); }}
h3 {{ font-size: 16px !important; font-weight: 600 !important; color: var(--ink); }}
a {{ color: var(--accent); }}
*:focus-visible {{ outline: 2px solid var(--accent) !important; outline-offset: 2px; }}

/* Hide the default Streamlit chrome (SPEC §10.1). */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
[data-testid="stHeaderActionElements"] {{ display: none !important; }}

[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--border); }}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--primary); border-color: var(--primary); color: #FFFFFF;
  border-radius: 8px; font-weight: 600;
}}
.stButton > button {{ border-radius: 8px; }}

[data-testid="stDataFrame"], [data-testid="stTable"] {{ font-size: 13px; }}

/* Top bar */
.aiq-topbar {{
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--primary); color: #FFFFFF; border-radius: 8px;
  padding: 12px 24px; margin-bottom: 24px;
}}
.aiq-topbar .aiq-brand {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
.aiq-topbar .aiq-name {{ font-size: 20px; font-weight: 600; letter-spacing: 0.2px; }}
.aiq-topbar .aiq-sub {{ font-size: 13px; color: #C9D3E0; }}
.aiq-topbar .aiq-right {{ display: flex; align-items: center; gap: 16px; font-size: 13px; }}
.aiq-pill {{
  display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px;
  font-weight: 600; border: 1px solid rgba(255,255,255,0.45); color: #FFFFFF;
}}

/* Cards and KPI tiles */
.aiq-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06); padding: 16px 24px; margin-bottom: 16px;
}}
.aiq-card h3 {{ margin: 0 0 8px 0; }}
.aiq-card p, .aiq-card li {{ font-size: 14px; }}
.aiq-card .aiq-muted, .aiq-muted {{ color: var(--muted); }}
.aiq-kpi {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06); padding: 16px; border-top: 4px solid var(--primary);
}}
.aiq-kpi .aiq-kpi-label {{ color: var(--muted); font-size: 13px; }}
.aiq-kpi .aiq-kpi-value {{
  font-size: 28px; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums;
}}
.aiq-kpi.tone-red {{ border-top-color: var(--red); }}
.aiq-kpi.tone-amber {{ border-top-color: var(--amber); }}
.aiq-kpi.tone-green {{ border-top-color: var(--green); }}

/* RAG badges and status chips */
.aiq-badge {{
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
  border: 1px solid transparent; white-space: nowrap;
}}
.aiq-badge.rag-RED {{ color: var(--red); background: var(--red-tint); border-color: #FECDCA; }}
.aiq-badge.rag-AMBER {{ color: var(--amber); background: var(--amber-tint); border-color: #FEDF89; }}
.aiq-badge.rag-GREEN {{ color: var(--green); background: var(--green-tint); border-color: #ABEFC6; }}
.aiq-badge.rag-EXPIRED {{ color: #FFFFFF; background: var(--red); border-color: var(--red); }}
.aiq-chip {{
  display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px;
  border: 1px solid var(--border); color: var(--muted); background: var(--surface);
}}
.aiq-chip.st-OK {{ color: var(--green); background: var(--green-tint); border-color: #ABEFC6; }}
.aiq-chip.st-LOW_CONFIDENCE {{ color: var(--amber); background: var(--amber-tint); border-color: #FEDF89; }}
.aiq-chip.st-UNVERIFIED {{ color: var(--red); background: var(--red-tint); border-color: #FECDCA; }}
.aiq-chip.st-NOT_FOUND {{ color: var(--muted); background: var(--bg); }}
.aiq-chip.st-USER_EDITED {{ color: var(--accent); background: #E6F4F3; border-color: #A7D7D3; }}

/* Stepper */
.aiq-stepper {{ display: flex; gap: 8px; list-style: none; padding: 0; margin: 0 0 24px 0; }}
.aiq-stepper li {{
  flex: 1; display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--border); color: var(--muted); font-size: 13px;
}}
.aiq-stepper .aiq-num {{
  display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px;
  border-radius: 50%; border: 1px solid var(--border); font-weight: 600; font-size: 12px;
  font-variant-numeric: tabular-nums;
}}
.aiq-stepper li.step-current {{ border-color: var(--accent); color: var(--ink); font-weight: 600; }}
.aiq-stepper li.step-current .aiq-num {{ background: var(--accent); border-color: var(--accent); color: #FFFFFF; }}
.aiq-stepper li.step-done {{ color: var(--ink); }}
.aiq-stepper li.step-done .aiq-num {{ background: var(--primary); border-color: var(--primary); color: #FFFFFF; }}
.aiq-stepper li.step-disabled {{ opacity: 0.5; }}

/* Callouts */
.aiq-callout {{ border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; border: 1px solid; }}
.aiq-callout.tone-red {{ background: var(--red-tint); border-color: #FECDCA; color: var(--red); }}
.aiq-callout.tone-amber {{ background: var(--amber-tint); border-color: #FEDF89; color: var(--amber); }}
.aiq-callout.tone-green {{ background: var(--green-tint); border-color: #ABEFC6; color: var(--green); }}
.aiq-callout.tone-neutral {{ background: var(--surface); border-color: var(--border); color: var(--ink); }}

.aiq-num-cell {{ text-align: right; font-variant-numeric: tabular-nums; }}

/* Key-value tables inside cards */
.aiq-kv {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.aiq-kv td {{ padding: 4px 0; border: none; border-bottom: 1px solid var(--border); vertical-align: top; }}
.aiq-kv td:first-child {{ color: var(--muted); padding-right: 16px; width: 45%; }}
.aiq-kv td:last-child {{ overflow-wrap: anywhere; }}
.aiq-kv tr:last-child td {{ border-bottom: none; }}

/* Neutral / tone badges */
.aiq-badge.tone-neutral {{ color: var(--muted); background: var(--bg); border-color: var(--border); }}
.aiq-badge.tone-teal {{ color: var(--accent); background: #E6F4F3; border-color: #A7D7D3; }}

/* Summary strip (Review step): one row from 1366 px (U7); the DIN cell absorbs the squeeze. */
.aiq-strip {{
  display: flex; flex-wrap: nowrap; gap: 16px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 16px; margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06); align-items: flex-start;
}}
.aiq-strip .aiq-si {{ display: flex; flex-direction: column; gap: 4px; flex: 0 1 auto;
  min-width: 0; }}
.aiq-strip .aiq-si.grow {{ flex: 1 1 160px; }}
.aiq-strip .aiq-sl {{ color: var(--muted); font-size: 12px; white-space: nowrap; }}
.aiq-strip .aiq-sv {{ font-size: 13px; font-weight: 600; color: var(--ink);
  font-variant-numeric: tabular-nums; white-space: nowrap; }}
.aiq-strip .aiq-si.grow .aiq-sv {{ white-space: normal; overflow-wrap: anywhere; }}
@media (max-width: 1100px) {{ .aiq-strip {{ flex-wrap: wrap; }} }}

/* Data tables */
.aiq-table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 16px; }}
.aiq-table th {{ background: var(--primary); color: #FFFFFF; font-weight: 600; text-align: left;
  padding: 8px 12px; }}
.aiq-table td {{ padding: 8px 12px; border-top: 1px solid var(--border); vertical-align: top; }}
a.aiq-case-link {{ color: var(--accent); font-weight: 600; text-decoration: none; }}
.aiq-caselaw {{ table-layout: fixed; }}
.aiq-caselaw td, .aiq-caselaw th {{ overflow-wrap: anywhere; }}
.aiq-caselaw th:nth-child(1) {{ width: 19%; }} .aiq-caselaw th:nth-child(2) {{ width: 15%; }}
.aiq-caselaw th:nth-child(3) {{ width: 11%; }} .aiq-caselaw th:nth-child(4) {{ width: 9%; }}
.aiq-caselaw th:nth-child(5) {{ width: 9%; }} .aiq-caselaw th:nth-child(6) {{ width: 37%; }}
a.aiq-case-link:hover, a.aiq-case-link:focus {{ text-decoration: underline; }}
.aiq-table th.num {{ text-align: right; }}
/* Issue Trail (U2): the Title column takes the spare width and wraps; short columns stay on
   one line; the Refs column breaks only between its two references. */
.aiq-trail td:nth-child(1), .aiq-trail td:nth-child(2), .aiq-trail td:nth-child(4),
.aiq-trail td:nth-child(6), .aiq-trail td:nth-child(10) {{ white-space: nowrap; }}
.aiq-trail td:nth-child(3) {{ width: 32%; }}
.aiq-trail td:nth-child(9) {{ min-width: 72px; }}
.aiq-table tr:nth-child(even) td {{ background: var(--bg); }}
.aiq-table .num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.aiq-table tfoot td {{ font-weight: 600; border-top: 2px solid var(--primary); }}

/* AI-generated content: shaded and labelled */
.aiq-ai {{ background: #EEF2F6; border-left: 3px solid var(--accent); border-radius: 4px;
  padding: 8px 12px; margin: 8px 0; }}
.aiq-ai .aiq-ai-label {{ font-size: 12px; font-weight: 600; color: var(--accent);
  text-transform: none; margin-bottom: 4px; }}

/* Verbatim extracts */
.aiq-quote {{ font-style: italic; border-left: 2px solid var(--border); padding: 4px 12px;
  margin: 4px 0; color: var(--ink); }}
.aiq-ref {{ color: var(--muted); font-size: 12px; font-style: normal; white-space: nowrap; }}

/* Processing stage list */
.aiq-stages {{ list-style: none; padding: 0; margin: 0 0 16px 0; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; }}
.aiq-stages li {{ display: flex; align-items: center; gap: 12px; padding: 8px 16px;
  border-top: 1px solid var(--border); font-size: 13px; }}
.aiq-stages li:first-child {{ border-top: none; }}
.aiq-stages .aiq-sname {{ flex: 1; }}
.aiq-stages .aiq-smsg {{ color: var(--muted); font-size: 12px; flex: 2; }}
.aiq-stages .aiq-sdur {{ color: var(--muted); font-variant-numeric: tabular-nums; width: 72px;
  text-align: right; }}
.aiq-stages li.st-pending {{ color: var(--muted); }}
.aiq-stages li.st-running {{ font-weight: 600; }}
.aiq-icon {{ width: 16px; height: 16px; flex: none; }}
@keyframes aiq-spin {{ to {{ transform: rotate(360deg); }} }}
.aiq-spin {{ animation: aiq-spin 1s linear infinite; transform-origin: 50% 50%; }}

/* Output cards (U5): a bordered container keyed "outcard_*" holds the title, the format line
   and the Download button. */
[class*="st-key-outcard"] {{ background: var(--surface); border-left: 4px solid var(--primary)
  !important; border-radius: 8px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06); }}
.aiq-out-title {{ font-weight: 600; color: var(--ink); }}
.aiq-out-sub {{ color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }}
.aiq-check {{ display: flex; gap: 8px; align-items: flex-start; padding: 4px 0; }}

/* Sidebar (U6): wordmark at the top, privacy badge at the bottom */
[data-testid="stSidebarHeader"] {{ height: 8px; min-height: 8px; padding: 0; }}
[data-testid="stSidebarContent"] {{ position: relative; min-height: 100%; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 8px; padding-bottom: 72px; }}
.aiq-wordmark {{ display: flex; align-items: baseline; gap: 8px; padding: 0 0 16px 0;
  margin-bottom: 8px; border-bottom: 1px solid var(--border); }}
.aiq-wordmark .aiq-wm-name {{ font-size: 20px; font-weight: 700; color: var(--primary);
  letter-spacing: 0.2px; }}
.aiq-wordmark .aiq-wm-ver {{ font-size: 12px; color: var(--muted);
  font-variant-numeric: tabular-nums; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ border-radius: 8px; padding: 4px 8px; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
  background: #E6F4F3; }}
.aiq-side-foot {{ position: absolute; left: 24px; right: 24px; bottom: 24px; }}
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.aiq-side-foot) {{
  position: static; }}
.aiq-side-badge {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px;
  font-weight: 600; color: var(--green); background: var(--green-tint);
  border: 1px solid #ABEFC6; }}
.aiq-side-badge.cloud {{ color: var(--amber); background: var(--amber-tint);
  border-color: #FEDF89; }}

/* Inputs keep a visible edge on white panels (WCAG AA non-text contrast ≥ 3:1). */
.stTextInput [data-baseweb="input"], .stNumberInput [data-baseweb="input"],
.stDateInput [data-baseweb="input"], .stTextArea [data-baseweb="textarea"] {{
  border: 1px solid #7B8794 !important; border-radius: 8px; }}

/* Expanders and bordered containers on the 8 px grid */
[data-testid="stExpander"] details {{ border-radius: 8px; border-color: var(--border);
  background: var(--surface); }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 8px; }}
.aiq-empty {{ text-align: center; padding: 24px 16px; color: var(--muted); }}
.aiq-empty strong {{ display: block; color: var(--ink); font-size: 15px; margin-bottom: 4px; }}
"""

# Small inline SVG status icons (no external assets, no emojis).
_ICON_PATHS = {
    "pending": '<circle cx="8" cy="8" r="6.5" fill="none" stroke="#9AA5B1" stroke-width="1.5"/>',
    "running": '<circle cx="8" cy="8" r="6.5" fill="none" stroke="#E4E7EB" stroke-width="2"/>'
               '<path class="aiq-spin" d="M8 1.5 A6.5 6.5 0 0 1 14.5 8" fill="none" '
               'stroke="#13807A" stroke-width="2" stroke-linecap="round"/>',
    "ok": '<circle cx="8" cy="8" r="7.5" fill="#027A48"/><path d="M4.5 8.2l2.3 2.3 4.7-4.9" '
          'fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>',
    "warn": '<circle cx="8" cy="8" r="7.5" fill="#B54708"/><path d="M8 4v5" stroke="#FFFFFF" '
            'stroke-width="1.8" stroke-linecap="round"/><circle cx="8" cy="11.6" r="1" '
            'fill="#FFFFFF"/>',
    "failed": '<circle cx="8" cy="8" r="7.5" fill="#B42318"/><path d="M5.3 5.3l5.4 5.4M10.7 '
              '5.3l-5.4 5.4" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round"/>',
    "skipped": '<circle cx="8" cy="8" r="6.5" fill="none" stroke="#9AA5B1" stroke-width="1.5" '
               'stroke-dasharray="2 2"/>',
}
StageState = Literal["pending", "running", "ok", "warn", "failed", "skipped"]
STAGE_STATE_LABELS = {"pending": "Pending", "running": "Running", "ok": "Done",
                      "warn": "Warning", "failed": "Failed", "skipped": "Skipped"}
BadgeTone = Literal["neutral", "teal", "RED", "AMBER", "GREEN", "EXPIRED"]
AI_LABEL = "AI-generated — advisory, verify before use"


# --------------------------------------------------------------------------- pure HTML builders


def top_bar_html(app_name: str, subtitle: str, firm_name: str, engine_label: str) -> str:
    """Custom top bar: app name and subtitle on the left; firm name and engine pill on the right."""
    return (
        '<div class="aiq-topbar" role="banner">'
        f'<div class="aiq-brand"><span class="aiq-name">{escape(app_name)}</span>'
        f'<span class="aiq-sub">{escape(subtitle)}</span></div>'
        f'<div class="aiq-right"><span>{escape(firm_name)}</span>'
        f'<span class="aiq-pill" title="Extraction engine">{escape(engine_label)}</span></div>'
        "</div>"
    )


def card_html(title: str | None, body_html: str) -> str:
    """A surface card. ``body_html`` is trusted markup built by the caller (escape user text first)."""
    heading = f"<h3>{escape(title)}</h3>" if title else ""
    return f'<div class="aiq-card">{heading}{body_html}</div>'


def kpi_tile_html(label: str, value: str, tone: Tone = "neutral") -> str:
    """A KPI tile with a coloured top rule."""
    return (
        f'<div class="aiq-kpi tone-{tone}">'
        f'<div class="aiq-kpi-label">{escape(label)}</div>'
        f'<div class="aiq-kpi-value">{escape(value)}</div></div>'
    )


def rag_badge_html(rag: Rag, text: str | None = None) -> str:
    """A RAG badge; ``text`` overrides the label (e.g. "49 days")."""
    if rag not in RAG_LABELS:
        raise ValueError(f"Unknown RAG value: {rag!r}")
    return f'<span class="aiq-badge rag-{rag}">{escape(text or RAG_LABELS[rag])}</span>'


def status_chip_html(status: FieldStatus) -> str:
    """A field-status chip (OK / Low confidence / Unverified / Not found / Edited)."""
    if status not in STATUS_LABELS:
        raise ValueError(f"Unknown field status: {status!r}")
    return f'<span class="aiq-chip st-{status}">{STATUS_LABELS[status]}</span>'


def stepper_states(n_steps: int, current: int, max_enabled: int) -> list[StepState]:
    """State of each step (1-based ``current``); steps after ``max_enabled`` are disabled."""
    states: list[StepState] = []
    for i in range(1, n_steps + 1):
        if i < current:
            states.append("done")
        elif i == current:
            states.append("current")
        elif i <= max_enabled:
            states.append("upcoming")
        else:
            states.append("disabled")
    return states


def stepper_html(labels: list[str], current: int, max_enabled: int | None = None) -> str:
    """Horizontal stepper. ``max_enabled`` defaults to the current step."""
    states = stepper_states(len(labels), current, max_enabled or current)
    items = []
    for i, (label, state) in enumerate(zip(labels, states, strict=True), start=1):
        aria = ' aria-current="step"' if state == "current" else ""
        items.append(
            f'<li class="step-{state}"{aria}>'
            f'<span class="aiq-num">{i}</span><span>{escape(label)}</span></li>'
        )
    items_html = "".join(items)
    return f'<ol class="aiq-stepper" aria-label="Progress">{items_html}</ol>'


def callout_html(text: str, tone: Tone = "neutral", title: str | None = None) -> str:
    """A tinted callout box for notices, warnings and errors."""
    heading = f"<strong>{escape(title)}</strong><br>" if title else ""
    return f'<div class="aiq-callout tone-{tone}" role="note">{heading}{escape(text)}</div>'


def badge_html(text: str, tone: BadgeTone = "neutral") -> str:
    """A small badge: RAG tones or neutral / teal."""
    css = f"rag-{tone}" if tone in RAG_LABELS else f"tone-{tone}"
    return f'<span class="aiq-badge {css}">{escape(text)}</span>'


def summary_strip_html(items: list[tuple[str, str]], grow: frozenset[str] = frozenset()) -> str:
    """Review summary strip on one row. Each item is (label, value_html); escape text values
    first. Items labelled in ``grow`` take the spare width and may wrap (e.g. the DIN)."""
    cells = "".join(f'<div class="aiq-si{" grow" if label in grow else ""}">'
                    f'<span class="aiq-sl">{escape(label)}</span>'
                    f'<span class="aiq-sv">{value}</span></div>' for label, value in items)
    return f'<div class="aiq-strip" role="region" aria-label="Case summary">{cells}</div>'


def empty_state_html(title: str, hint: str) -> str:
    """An empty state ("No cases yet") with a one-line hint on what to do next."""
    return (f'<div class="aiq-card aiq-empty" role="status"><strong>{escape(title)}</strong>'
            f"{escape(hint)}</div>")


def table_html(headers: list[str], rows: list[list[str]], *, numeric: set[int] | None = None,
               html_cols: set[int] | None = None, footer: list[str] | None = None,
               css: str = "") -> str:
    """A styled table. Cells are escaped unless their column is in ``html_cols`` (trusted
    markup such as badges); columns in ``numeric`` are right-aligned with tabular figures.
    ``css`` adds a class for table-specific column rules (e.g. ``aiq-trail``)."""
    numeric, html_cols = numeric or set(), html_cols or set()

    def cell(i: int, value: str, tag: str = "td") -> str:
        css = ' class="num"' if i in numeric else ""
        return f"<{tag}{css}>{value if i in html_cols else escape(value)}</{tag}>"

    head = "".join(cell(i, h, "th") for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(cell(i, v) for i, v in enumerate(r)) + "</tr>" for r in rows)
    foot = ("<tfoot><tr>" + "".join(cell(i, v) for i, v in enumerate(footer)) + "</tr></tfoot>"
            if footer else "")
    classes = f"aiq-table {css}".strip()
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody>{foot}' \
           "</table>"


def stage_icon_html(state: StageState) -> str:
    """Inline SVG icon for a processing stage state."""
    return (f'<svg class="aiq-icon" viewBox="0 0 16 16" role="img" '
            f'aria-label="{STAGE_STATE_LABELS[state]}">{_ICON_PATHS[state]}</svg>')


def stage_list_html(rows: list[tuple[StageState, str, str, str]]) -> str:
    """Processing stage list; each row is (state, stage label, message, duration text)."""
    items = "".join(
        f'<li class="st-{state}">{stage_icon_html(state)}'
        f'<span class="aiq-sname">{escape(label)}</span>'
        f'<span class="aiq-smsg">{escape(message)}</span>'
        f'<span class="aiq-sdur">{escape(duration)}</span></li>'
        for state, label, message, duration in rows)
    return f'<ul class="aiq-stages" aria-live="polite">{items}</ul>'


def ai_note_html(summary: str | None, note: str | None) -> str:
    """AI summary and strategy note, shaded and labelled (SPEC §8.9, §10.3)."""
    parts = []
    if summary:
        parts.append(f"<p><strong>Summary.</strong> {escape(summary)}</p>")
    if note:
        parts.append(f"<p><strong>Strategy note.</strong> {escape(note)}</p>")
    return (f'<div class="aiq-ai" role="note"><div class="aiq-ai-label">{AI_LABEL}</div>'
            f'{"".join(parts)}</div>')


def quote_html(snippet: str, ref: str) -> str:
    """A verbatim extract in italics with its [p/¶] reference."""
    return (f'<div class="aiq-quote">“{escape(snippet)}” '
            f'<span class="aiq-ref">[{escape(ref)}]</span></div>')


def output_card_html(title: str, subtitle: str) -> str:
    """The title and format line of an output card (the Download button sits in the same
    bordered container, below this)."""
    return (f'<div class="aiq-out-title">{escape(title)}</div>'
            f'<div class="aiq-out-sub">{escape(subtitle)}</div>')


_FORMATS = {".docx": "Word document", ".pdf": "PDF", ".xlsx": "Excel workbook"}


def file_meta(suffix: str, size_bytes: int | None) -> str:
    """"Word document · 84 KB" for an output card (no file name: it is long and repetitive)."""
    kind = _FORMATS.get(suffix.lower(), suffix.lstrip(".").upper() or "File")
    if size_bytes is None:
        return kind
    size = (f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576
            else f"{max(1, round(size_bytes / 1024))} KB")
    return f"{kind} · {size}"


# --------------------------------------------------------------------------- streamlit wrappers


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css() -> None:
    """Inject the design-system CSS. Call once per page run, before other components."""
    _html(f"<style>{CSS}</style>")


def render_top_bar(app_name: str, subtitle: str, firm_name: str, engine_label: str) -> None:
    _html(top_bar_html(app_name, subtitle, firm_name, engine_label))


def render_card(title: str | None, body_html: str) -> None:
    _html(card_html(title, body_html))


def render_kpi_row(tiles: list[tuple[str, str, Tone]]) -> None:
    """Render KPI tiles side by side: each tuple is (label, value, tone)."""
    for column, (label, value, tone) in zip(st.columns(len(tiles)), tiles, strict=True):
        with column:
            _html(kpi_tile_html(label, value, tone))


def render_stepper(labels: list[str], current: int, max_enabled: int | None = None) -> None:
    _html(stepper_html(labels, current, max_enabled))


def render_callout(text: str, tone: Tone = "neutral", title: str | None = None) -> None:
    _html(callout_html(text, tone, title))


def render_empty(title: str, hint: str) -> None:
    _html(empty_state_html(title, hint))


def render_html(markup: str) -> None:
    """Write trusted markup built by the ``*_html`` helpers."""
    _html(markup)


def render_error(message: str, fix: str | None = None, details: str | None = None,
                 title: str = "Something needs attention") -> None:
    """Red callout in plain English with a suggested fix; technical detail in an expander
    (SPEC §10.4)."""
    text = f"{message} {fix}" if fix else message
    _html(callout_html(text, "red", title))
    if details:
        with st.expander("Technical details"):
            st.code(details, language=None)
