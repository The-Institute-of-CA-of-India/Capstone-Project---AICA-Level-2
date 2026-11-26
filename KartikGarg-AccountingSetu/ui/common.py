"""Shared UI helpers: theme CSS, status badges, tables, session context, safe action wrapper."""
from __future__ import annotations

import datetime as dt
import html
from contextlib import contextmanager
from decimal import Decimal

import pandas as pd
import streamlit as st

from services.admin_service import PlanLimitExceeded
from services.audit_service import log_error
from services.tenancy import AuthContext
from utils.helpers import money
from utils.permissions import NotFound, PermissionDenied

NAVY, GOLD, GREY = "#0B2545", "#C9A227", "#F4F6F9"

STATUS_COLORS = {
    "uploaded": ("#E2E8F0", "#334155"), "processing": ("#DBEAFE", "#1E40AF"), "processed": ("#E0F2FE", "#075985"),
    "needs_review": ("#FEF3C7", "#92400E"), "approved": ("#DCFCE7", "#166534"), "rejected": ("#FEE2E2", "#991B1B"),
    "finalized": ("#E0E7FF", "#3730A3"), "split": ("#F1F5F9", "#475569"), "draft": ("#F1F5F9", "#475569"),
    "submitted": ("#DBEAFE", "#1E40AF"), "completed": ("#DCFCE7", "#166534"), "matched": ("#DCFCE7", "#166534"),
    "unmatched": ("#FEE2E2", "#991B1B"), "partially_matched": ("#FEF3C7", "#92400E"), "duplicate": ("#F1F5F9", "#475569"),
    "suspense": ("#FFEDD5", "#9A3412"), "needs_review_b": ("#FEF3C7", "#92400E"), "open": ("#F1F5F9", "#475569"),
    "reopened": ("#FEF3C7", "#92400E"), "active": ("#DCFCE7", "#166534"), "pending": ("#FEF3C7", "#92400E"),
    "suspended": ("#FEE2E2", "#991B1B"), "deactivated": ("#E2E8F0", "#334155"), "prepared": ("#E0F2FE", "#075985"),
    "filed_externally": ("#E0E7FF", "#3730A3"), "shared": ("#DCFCE7", "#166534"), "answered": ("#DCFCE7", "#166534"),
    "closed": ("#E2E8F0", "#334155"),
}

CSS = f"""
<style>
:root {{ --navy: {NAVY}; --gold: {GOLD}; --grey: {GREY}; }}
.block-container {{ padding-top: 1.6rem; max-width: 1400px; }}
h1, h2, h3 {{ color: var(--navy); letter-spacing: -0.01em; }}
h1 {{ font-size: 1.65rem !important; border-bottom: 2px solid var(--gold); padding-bottom: .35rem; }}
section[data-testid="stSidebar"] {{ background: var(--navy); }}
section[data-testid="stSidebar"] * {{ color: #E2E8F0; }}
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {{ color: #0F172A; }}
section[data-testid="stSidebar"] a[aria-current="page"] {{ background: rgba(201,162,39,.18); border-left: 3px solid var(--gold); }}
.as-brand {{ font-weight: 700; font-size: 1.15rem; color: #fff !important; }}
.as-brand span {{ color: var(--gold) !important; }}
.as-tag {{ font-size: .72rem; opacity: .75; margin-top: -4px; }}
.as-badge {{ display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: .74rem; font-weight: 600; }}
.as-card {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px 16px; }}
.as-kpi-label {{ font-size: .76rem; color: #64748B; text-transform: uppercase; letter-spacing: .04em; }}
.as-kpi-value {{ font-size: 1.45rem; font-weight: 700; color: var(--navy); }}
.as-warn {{ background:#FFF7ED; border-left: 4px solid #EA580C; padding: 10px 14px; border-radius: 6px; color:#7C2D12; }}
.as-provisional {{ background:#FEF3C7; border: 1px solid #F59E0B; padding: 8px 12px; border-radius: 6px; color:#78350F; font-weight:600; }}
div[data-testid="stMetricValue"] {{ color: var(--navy); }}
.stButton>button[kind="primary"] {{ background: var(--navy); border-color: var(--navy); }}
.stButton>button[kind="primary"]:hover {{ background: #13315C; border-color: var(--gold); }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def badge(status: str | None) -> str:
    s = (status or "").lower()
    bg, fg = STATUS_COLORS.get(s, ("#F1F5F9", "#334155"))
    return f"<span class='as-badge' style='background:{bg};color:{fg}'>{html.escape(s.replace('_', ' ').title())}</span>"


def kpi(col, label: str, value, help_text: str | None = None) -> None:
    col.markdown(f"<div class='as-card'><div class='as-kpi-label'>{html.escape(label)}</div>"
                 f"<div class='as-kpi-value'>{html.escape(str(value))}</div></div>", unsafe_allow_html=True)


def rupees(v) -> str:
    return "—" if v is None else f"₹{money(v)}"


def to_df(rows: list[dict], drop_ids: bool = True, money_cols: tuple = ()) -> pd.DataFrame:
    clean = []
    for r in rows:
        row = {}
        for k, v in r.items():
            if drop_ids and (k == "id" or k.endswith("_id")):
                continue
            if isinstance(v, Decimal):
                v = float(v)
            elif isinstance(v, (dict, list)):
                v = str(v)
            row[k] = v
        clean.append(row)
    df = pd.DataFrame(clean)
    df.columns = [str(c).replace("_", " ").title() for c in df.columns]
    return df


def table(rows: list[dict], **kw) -> None:
    if not rows:
        st.info("No records.")
        return
    df = to_df(rows, **kw)
    num_cols = {c: st.column_config.NumberColumn(c, format="%.2f") for c in df.columns if df[c].dtype.kind == "f"}
    st.dataframe(df, width="stretch", hide_index=True, column_config=num_cols)


def ctx() -> AuthContext:
    return st.session_state["ctx"]


def selected_client_id() -> str | None:
    c = ctx()
    if c.is_client:
        return c.client_id
    return st.session_state.get("client_id")


def selected_period() -> tuple[int, int]:
    today = dt.date.today()
    return int(st.session_state.get("year", today.year)), int(st.session_state.get("month", today.month))


def require_client_selected() -> str:
    cid = selected_client_id()
    if not cid:
        st.info("Select a client in the sidebar to continue.")
        st.stop()
    return cid


KNOWN_ERRORS = (PermissionDenied, NotFound, ValueError, PlanLimitExceeded)


@contextmanager
def action(success: str | None = None):
    """Run a user action; show domain errors as messages, log unexpected ones."""
    try:
        yield
        if success:
            st.success(success)
    except KNOWN_ERRORS as exc:
        st.error(str(exc))
    except Exception as exc:  # domain exceptions from services + unexpected errors
        name = type(exc).__name__
        if name in {"AccountingError", "UnbalancedVoucher", "DuplicateVoucher", "PeriodLocked", "DocumentError", "UploadRejected",
                    "AuthError", "TallyExportError", "StorageError", "IntegrityError"}:
            st.error(str(exc))
        else:
            c = st.session_state.get("ctx")
            log_error("ui.action", exc, firm_id=getattr(c, "firm_id", None), user_id=getattr(c, "user_id", None))
            st.error(f"Unexpected error ({name}). It has been logged for the administrator.")


def page_header(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def month_options(n: int = 24) -> list[tuple[int, int]]:
    today = dt.date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


def download(label: str, data: bytes, filename: str, mime: str, key: str | None = None) -> None:
    st.download_button(label, data=data, file_name=filename, mime=mime, key=key or f"dl_{filename}")
