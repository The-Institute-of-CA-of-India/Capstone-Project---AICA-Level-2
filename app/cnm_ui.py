"""Investor Manager: screens (NiceGUI, pure Python).

Runs a local server on 127.0.0.1 only; nothing leaves the computer.
"""
from __future__ import annotations

import asyncio
import os
import queue
import re
import string
import webbrowser
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from nicegui import app, run, ui

from cn_app import (assumed, brokers, deletion, grandfather, prices, registration, tally_export, tally_match, cost_recon, fifo, holdings_recon, maintenance, master, masters, opening, passwords,
                    periods, persons, portal, reference, report, tally, tally_link)
from cn_app import paths as dpaths
from cn_app.models import CHARGE_KEYS, CHARGE_LABELS
from cn_app.pdf_report import build_pdf
from cn_app.pipeline import import_paths, remedy
from cn_app.store import Store
from cn_app.xml_export import build_xml

VERSION = os.environ.get("CNM_VERSION", "v1.13") + " (Phase 1)"
MASTER_DAYS = 7          # masters older than this prompt an update
DATA = Path(os.environ.get("CNM_DATA", Path.cwd() / "Data")).resolve()
PROJECT = Path(os.environ.get("CNM_PROJECT", DATA.parent)).resolve()
DATA.mkdir(parents=True, exist_ok=True)
L = dpaths.Layout(DATA)
MIGRATED = dpaths.migrate(DATA)          # v1.0 - v1.6 folders moved into the v1.7 layout (once)
REPORTS = L.reports
PW_FILE = L.client / "passwords.txt"

_lock = threading.Lock()


def store() -> Store:
    s = Store(L.db)
    opening.ensure(s)
    masters.ensure(s)
    passwords.ensure(s, PW_FILE)
    brokers.ensure(s)
    portal.ensure(s)
    cost_recon.ensure(s)
    return s


# --------------------------------------------------------------------------- look and feel

NAVY, TEAL, GOLD = "#1F3A5F", "#2A7F8F", "#E0A526"
CSS = """
body { background:#F4F7FB; font-family: 'Segoe UI', Roboto, sans-serif; }
.kpi { border-radius:14px; padding:14px 18px; min-width:190px; box-shadow:0 1px 3px rgba(16,42,67,.08); background:white; }
.kpi .lbl { font-size:12px; color:#5B6B7F; text-transform:uppercase; letter-spacing:.04em; }
.kpi .val { font-size:22px; font-weight:700; color:#1F3A5F; margin-top:2px; }
.kpi .sub { font-size:11px; color:#8094A9; }
.card { border-radius:14px; box-shadow:0 1px 3px rgba(16,42,67,.08); background:white; }
.navbtn { width:100%; text-transform:none; font-size:13.5px; border-radius:10px; }
.navbtn .q-btn__content { justify-content:flex-start; flex-wrap:nowrap; }
.page-title { font-size:22px; font-weight:700; color:#1F3A5F; }
.hint { color:#5B6B7F; font-size:13px; }
.dropzone { width:100%; }
.dropzone .q-uploader { width:100%; max-height:none; border:2px dashed #2A7F8F; border-radius:14px; box-shadow:none; background:#F7FBFC; }
.dropzone .q-uploader__header { background:#2A7F8F; }
.dropzone .q-uploader__title { font-size:15px; font-weight:600; }
.dropzone .q-uploader__list { min-height:130px; position:relative; }
.dropzone .q-uploader__list::after { content:"Drag and drop files here"; position:absolute; left:0; right:0; top:42px;
  text-align:center; color:#7FA7B0; font-size:20px; font-weight:600; pointer-events:none; }
.dropzone .q-uploader--dnd { background:#E3F3F5; border-color:#1F3A5F; }
.cnm-error .q-notification__actions .q-btn { color:white !important; font-weight:700; border:1px solid white; }
.navgroup .q-item { border-radius:10px; font-size:13.5px; padding-left:16px; }
.navgroup .q-item__section--avatar { min-width:36px; }
.navbtn.pl-4 { font-size:12.5px; padding-left:10px; }
#cnm-wait { position:fixed; inset:0; background:rgba(15,30,50,.35); z-index:9000; display:none;
  align-items:center; justify-content:center; }
#cnm-wait .box { background:white; border-radius:14px; padding:22px 30px; font-size:17px; font-weight:600;
  color:#1F3A5F; box-shadow:0 8px 30px rgba(0,0,0,.25); display:flex; gap:14px; align-items:center; }
#cnm-wait .spin { width:26px; height:26px; border:4px solid #CFE3E8; border-top-color:#2A7F8F; border-radius:50%;
  animation:cnmspin .8s linear infinite; }
@keyframes cnmspin { to { transform:rotate(360deg); } }
@keyframes cnmblink { 0%,100% { opacity:1; } 50% { opacity:.25; } }
.cnm-blink { animation:cnmblink 1s step-start infinite; color:#C62828; font-weight:800; }
.navbtn.danger { color:#C62828 !important; font-weight:700; }
.navbtn.danger.active-danger { background:#C62828 !important; color:white !important; }
.kpi.click { cursor:pointer; transition:box-shadow .15s, transform .15s; }
.kpi.click:hover { box-shadow:0 4px 14px rgba(16,42,67,.18); transform:translateY(-1px); }
.ag-theme-quartz { --ag-cell-horizontal-padding:10px; --ag-header-background-color:#1F3A5F; --ag-header-foreground-color:white; --ag-font-size:12px; --ag-row-height:30px; }
"""

NAV = [
    ("Dashboard", "dashboard", "/"),
    ("Investment", "account_balance_wallet", "/investment"),
    ("Contract Notes", "receipt_long", [("Import Contract Notes", "upload_file", "/import"),
                                        ("List of Contract Notes", "list_alt", "/notes"),
                                        ("Script Register", "table_view", "/register"),
                                        ("Daily Summary", "calendar_month", "/daily"),
                                        ("Scrip Master", "business", "/master"),
                                        ("Opening Holdings", "inventory_2", "/opening")]),
    ("Reconciliation", "fact_check", [("Contract Note Reconciliation", "receipt_long", "/recon"),
                                      ("Holding Reconciliation", "account_balance_wallet", "/recon/holdings"),
                                      ("Cost Reconciliation (Tally)", "balance", "/recon/cost")]),
    ("Imports", "cloud_download", [("Import Market Masters", "cloud_download", "/masters"),
                                   ("Import Tally Masters", "account_tree", "/tally/masters"),
                                   ("Import Market Rates", "trending_up", "/rates"),
                                   ("Grandfathering FMV", "history_edu", "/fmv"),
                                   ("Broker Portal Download", "travel_explore", "/portal")]),
    ("Reports & Export", "download", "/reports"),
    ("Persons and PAN", "people", "/persons"),
    ("Export to Tally", "send", "/tally"),
    ("Import Log", "history", "/log"),
    ("Data Maintenance", "cleaning_services", "/maintenance"),
    ("Delete Data", "delete_forever", "/delete"),
    ("Settings", "settings", "/settings"),
]


def inr(v, dec=0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    neg, v = v < 0, abs(v)
    whole, _, frac = f"{v:.{dec}f}".partition(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + parts) + "," + tail
    return ("-" if neg else "") + "₹ " + whole + ("." + frac if dec else "")


def person_options() -> dict:
    return {"": "All persons", **{p["key"]: p["label"] for p in persons.all_people(store())}}


def current_pan() -> str:
    """Selected person key: a PAN, 'NAME:<name>' for a person without PAN, or '' for all."""
    return app.storage.general.get("client", "")


def current_period() -> str:
    return app.storage.general.get("period", "all")


def scope_pan(key: str):
    if not key:
        return None
    return "__NO_CONTRACT_NOTES__" if key.startswith("NAME:") else key


def scope():
    """(pan, from, to) for report.frames from the selectors at the top."""
    a, b = periods.bounds(current_period())
    return scope_pan(current_pan()), a, b


def person_label() -> str:
    return person_options().get(current_pan(), "All persons")


def period_options() -> dict:
    first = store().query("SELECT MIN(trade_date) d FROM notes")[0]["d"]
    return periods.options(first)


def custom_period_dialog():
    a, b = periods.bounds(current_period())
    with ui.dialog() as d, ui.card():
        ui.label("Custom period").classes("text-lg font-semibold")
        f_in = ui.input("From", value=a or "").props("type=date outlined dense")
        t_in = ui.input("To", value=b or "").props("type=date outlined dense")

        def ok():
            app.storage.general["period"] = f"C:{f_in.value or ''}:{t_in.value or ''}"
            d.close()
            ui.navigate.reload()
        with ui.row():
            ui.button("Cancel", on_click=lambda: (d.close(), ui.navigate.reload())).props("flat")
            ui.button("Apply", on_click=ok)
    d.open()


_prompt = {"done": False}     # ask once each time the app is started


def master_prompt(age):
    with ui.dialog().props("persistent") as d, ui.card().classes("w-[560px] p-5"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.icon("cloud_download").classes("text-4xl").style(f"color:{TEAL}")
            ui.label("Update the security masters now?").classes("text-xl font-semibold")
        ui.label(("The masters have never been downloaded." if age is None else
                  f"The masters were last updated {age} day(s) ago.") +
                 " New IPOs, bonus issues, splits, rights and mergers happen every week, so a weekly update keeps "
                 "company names, ISINs and industries correct. It takes about a minute and needs internet.") \
            .classes("text-sm text-gray-700")
        with ui.row().classes("w-full justify-end gap-3 pt-2"):
            ui.button("Not now", icon="close", on_click=d.close).props("unelevated color=negative no-caps")
            ui.button("Update now", icon="check", on_click=lambda: (d.close(), ui.navigate.to("/masters?auto=1"))) \
                .props("unelevated color=positive no-caps autofocus size=lg")
    d.open()


WAIT_JS = """
<div id="cnm-wait"><div class="box"><div class="spin"></div><span id="cnm-wait-msg">Opening, please wait...</span></div></div>
<script>
window.cnmWait = function(msg) {
  var w = document.getElementById('cnm-wait'); if (!w) return;
  document.getElementById('cnm-wait-msg').textContent = msg || 'Opening, please wait...';
  w.style.display = 'flex';
};
window.addEventListener('beforeunload', function() { window.cnmWait('Opening, please wait...'); });
window.addEventListener('pageshow', function() { var w = document.getElementById('cnm-wait'); if (w) w.style.display = 'none'; });
</script>
"""


def frame(title: str, active: str, show_scope: bool = True):
    """Common header, navigation and client selector. Returns the content column."""
    ui.add_css(CSS)
    ui.add_body_html(WAIT_JS)
    ui.colors(primary=NAVY, secondary=TEAL, accent=GOLD)
    reg_ok = registration.registered(store())
    if not reg_ok:
        ui.navigate.to("/registration")
    lic, valid = registration.licensee(store())
    with ui.header().classes("items-center px-4 py-2").style(f"background:{NAVY}"):
        ui.icon("account_balance").classes("text-2xl text-white")
        ui.label("Investor Manager").classes("text-lg font-semibold text-white")
        if lic:
            ui.label("|").classes("text-white opacity-50")
            ui.label(lic).classes("text-base text-white").tooltip("Licensee")
            ui.label(f"Valid Upto: {valid}").classes("text-sm text-white opacity-80 ml-2")
        ui.space()
        popts = period_options()
        cur = current_period()
        if cur not in popts:
            popts[cur] = periods.label(cur)

        def on_period(e):
            if e.value == "custom":
                custom_period_dialog()
            else:
                app.storage.general["period"] = e.value or "all"
                ui.navigate.reload()
        ui.select({**popts, "custom": "Custom range..."}, value=cur, on_change=on_period) \
            .props("dense outlined dark options-dense prefix-icon=event").classes("w-56") \
            .style("background:rgba(255,255,255,.08)").tooltip("Period: financial year or custom range")
        opts = person_options()
        ui.select(opts, value=current_pan() if current_pan() in opts else "",
                  on_change=lambda e: (app.storage.general.__setitem__("client", e.value or ""),
                                       ui.navigate.reload())) \
            .props("dense outlined dark options-dense").classes("w-80").style("background:rgba(255,255,255,.08)") \
            .tooltip("Show one person / PAN or all")
    with ui.left_drawer(value=True).classes("p-2").style("background:white; border-right:1px solid #E3E8EF") \
            .props("width=262 bordered"):
        for label, icon, path in NAV:
            if isinstance(path, list):                      # a group with sub-menus
                with ui.expansion(label, icon=icon, value=any(active == p for _, _, p in path)) \
                        .classes("w-full navgroup").props("dense header-class=text-primary"):
                    for sub, sicon, spath in path:
                        props = ("unelevated color=primary text-color=white" if active == spath
                                 else "flat text-color=primary")
                        ui.button(sub, icon=sicon, on_click=lambda p=spath: ui.navigate.to(p)) \
                            .props(f"{props} no-caps no-wrap align=left dense").classes("navbtn pl-4")
                continue
            danger = path == "/delete"
            if danger:
                props = "unelevated color=negative text-color=white" if active == path else "flat text-color=negative"
            else:
                props = ("unelevated color=primary text-color=white" if active == path else "flat text-color=primary")
            ui.button(label, icon=icon, on_click=lambda p=path: ui.navigate.to(p)) \
                .props(f"{props} no-caps no-wrap align=left").classes("navbtn" + (" danger" if danger else ""))
        ui.space()
        ui.label(f"Version {VERSION}").classes("text-xs text-gray-400 px-3 pt-6")
    footer_bar()
    if reg_ok and active != "/masters" and not _prompt["done"]:
        _prompt["done"] = True
        age = masters.age_days(store())
        if age is None or age > MASTER_DAYS:
            master_prompt(age)
    col = ui.column().classes("w-full p-6 gap-4")
    with col:
        with ui.row().classes("items-center gap-3 w-full no-wrap"):
            ui.label(title).classes("page-title")
            if show_scope:
                ui.label(f"{person_label()}  |  {periods.label(current_period())}").classes("hint")
            ui.space()
            if active != "/":
                ui.button("Close", icon="close", on_click=lambda: ui.run_javascript(
                    "if (document.referrer && document.referrer.indexOf(location.host) >= 0 && history.length > 1)"
                    " { history.back(); } else { location.href = '/'; }")) \
                    .props("unelevated color=accent text-color=white no-caps").classes("font-semibold") \
                    .tooltip("Back to where you came from")
    return col


class busy:
    """`async with busy("Prices are being updated...")`: a message that stays on screen (and blocks other
    clicks) until the work is finished."""

    def __init__(self, message: str):
        self.message = message
        self.dialog = None

    async def __aenter__(self):
        with ui.dialog().props("persistent") as d, ui.card().classes("p-6 items-center"):
            with ui.row().classes("items-center gap-4 no-wrap"):
                ui.spinner(size="lg", color="secondary")
                ui.label(self.message).classes("text-lg font-semibold").style(f"color:{NAVY}")
            ui.label("Please wait. The other buttons will work again when this is finished.").classes("hint")
        self.dialog = d
        d.open()
        await asyncio.sleep(0.15)          # let the message reach the screen first
        return self

    async def __aexit__(self, *exc):
        try:
            self.dialog.close()
        except Exception:  # noqa: BLE001 - the page may have been closed meanwhile
            pass
        return False


DEVELOPER = {
    "Created by": "CA Atul Mathuria",
    "Address": "A 701, Winsway Complex Bldg. No. 2 A Wing CHSL, Old Police Lane, Andheri East, Mumbai 400 069, "
               "Maharashtra, India",
    "Email Address": "atul@atulmathuria.com",
    "Mobile No.": "(91) 98923 23031",
    "LinkedIn": "",
    "Instagram": "",
}
DEV_LINKS = {"Email Address": "mailto:atul@atulmathuria.com", "Mobile No.": "tel:+919892323031"}


def footer_bar():
    with ui.footer().classes("items-center px-4 py-1").style(f"background:{NAVY}"):
        ui.button("CA Atul Mathuria", icon="verified_user", on_click=lambda: ui.navigate.to("/developer")) \
            .props("flat no-caps dense text-color=white").classes("text-sm").tooltip("About the developer")
        ui.space()
        ui.label(f"Investor Manager {VERSION}").classes("text-xs text-white opacity-70")


@ui.page("/developer")
def developer_page():
    col = frame("About the Developer", "/developer", show_scope=False)
    with col:
        with ui.card().classes("card p-6 w-full max-w-3xl"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("account_circle").classes("text-6xl").style(f"color:{NAVY}")
                with ui.column().classes("gap-0"):
                    ui.label("CA Atul Mathuria").classes("text-2xl font-bold").style(f"color:{NAVY}")
                    ui.label("Chartered Accountant | Developer of Investor Manager").classes("hint")
            ui.separator()
            for k, v in DEVELOPER.items():
                with ui.row().classes("items-start gap-3 no-wrap w-full"):
                    ui.label(k).classes("w-36 shrink-0 text-gray-600 font-medium")
                    url = DEV_LINKS.get(k) or (v if v.startswith("http") else "")
                    if not v:
                        ui.label("(to be added)").classes("flex-1 text-gray-400")
                    elif url:
                        ui.link(v, url, new_tab=not url.startswith(("mailto:", "tel:"))).classes("flex-1 text-primary")
                    else:
                        ui.label(v).classes("flex-1")


@ui.page("/registration")
def registration_page(edit: str = ""):
    ui.add_css(CSS)
    ui.colors(primary=NAVY, secondary=TEAL, accent=GOLD)
    st = store()
    old = registration.load(st)
    new = not old
    with ui.header().classes("items-center px-4 py-2").style(f"background:{NAVY}"):
        ui.icon("account_balance").classes("text-2xl text-white")
        ui.label("Investor Manager").classes("text-lg font-semibold text-white")
    footer_bar()
    with ui.column().classes("w-full items-center p-6"):
        with ui.card().classes("card p-6 w-full max-w-4xl"):
            ui.label("Registration" if new else "Registration details").classes("page-title")
            ui.label("Please fill in these details once. Fields marked * are required. The Licence No. will be "
                     "used to activate the app later; leave it blank if you do not have one yet.").classes("hint")
            if not new and not edit:
                for k, label, _ in registration.FIELDS:
                    with ui.row().classes("gap-3"):
                        ui.label(label).classes("w-56 text-gray-600")
                        ui.label(old.get(k) or "-")
                lic, valid = registration.licensee(st)
                with ui.row().classes("gap-3"):
                    ui.label("Valid Upto").classes("w-56 text-gray-600")
                    ui.label(valid)
                with ui.row():
                    ui.button("Edit details", icon="edit", on_click=lambda: ui.navigate.to("/registration?edit=1"))
                    ui.button("Back", on_click=lambda: ui.navigate.to("/")).props("flat")
                return
            boxes = {}
            with ui.grid(columns=2).classes("w-full gap-3"):
                for k, label, req in registration.FIELDS:
                    boxes[k] = ui.input(label + (" *" if req else ""), value=old.get(k, "")) \
                        .props("outlined dense")
                if new:
                    boxes["country"].value = boxes["country"].value or "India"
            ui.label("Password of the Administrator" + (" *" if new else " (leave blank to keep)")) \
                .classes("font-semibold text-gray-700 mt-2")
            with ui.row().classes("gap-3"):
                pw = ui.input("Password", password=True, password_toggle_button=True).props("autocomplete=new-password outlined dense")
                pw2 = ui.input("Confirm password", password=True).props("autocomplete=new-password outlined dense")
                cur = None
                if not new:
                    cur = ui.input("Present password (to save changes)", password=True).props("autocomplete=new-password outlined dense")

            def save():
                data = {k: b.value for k, b in boxes.items()}
                errs = registration.validate(data, pw.value or None, pw2.value or None, new)
                if not new and not registration.check_password(store(), cur.value or ""):
                    errs.append("The present password of the Administrator is not correct")
                if errs:
                    failure("Registration not saved", [{"what": e.split(" is ")[0].split(" should")[0], "why": e,
                                                        "fix": "Correct it and press Save again."} for e in errs])
                    return
                registration.save(store(), data, pw.value or None)
                success("Registration saved. Welcome to Investor Manager!" if new else "Registration updated")
                ui.navigate.to("/")
            ui.button("Save and continue" if new else "Save changes", icon="how_to_reg", on_click=save) \
                .props("unelevated color=positive size=lg")


def grid(df, money=(), rupee=(), qty=(), height="calc(100vh - 230px)", pinned=1, on_row=None, editable=(),
         selectable=False, colour=(), totals=None, fit=False, row_style=""):
    cols = []
    for i, c in enumerate(df.columns):
        cd = {"field": c, "headerName": c, "filter": True, "sortable": True, "resizable": True, "minWidth": 90}
        if str(c).startswith("_"):
            cd["hide"] = True
        if c in money:
            cd.update({"type": "rightAligned", "filter": "agNumberColumnFilter",
                       ":valueFormatter": "p => p.value == null ? '' : Number(p.value).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})"})
        elif c in rupee:
            cd.update({"type": "rightAligned", "filter": "agNumberColumnFilter",
                       ":valueFormatter": "p => p.value == null ? '' : Number(p.value).toLocaleString('en-IN', {maximumFractionDigits: 0})"})
        elif c in qty:
            cd.update({"type": "rightAligned", "filter": "agNumberColumnFilter",
                       ":valueFormatter": "p => p.value == null ? '' : Number(p.value).toLocaleString('en-IN')"})
        elif "Date" in c or c == "Holding Since":
            cd[":valueFormatter"] = "p => p.value && p.value.length == 10 ? p.value.slice(8) + '-' + p.value.slice(5, 7) + '-' + p.value.slice(0, 4) : p.value"
        if fit:                               # fill the width; headings wrap instead of truncating
            wide = c in ("Name", "Name of Company")
            cd.update({"flex": 2 if wide else 1,
                       "minWidth": 170 if wide else 118 if c in list(money) + list(rupee) or c == "Holding Since" else 92,
                       "wrapHeaderText": True,
                       "autoHeaderHeight": True, "filter": False, "suppressHeaderMenuButton": True})
        if c in colour:                       # gains green, losses red
            cd[":cellStyle"] = ("p => p.value == null ? null : {color: p.value < 0 ? '#C62828' : '#2E7D32', "
                                "fontWeight: 600}")
        if i < pinned:
            cd["pinned"] = "left"
        if c in editable:
            cd.update({"editable": True, "cellStyle": {"background": "#FFF9E6"}})
        cols.append(cd)
    data = df.where(df.notna(), None).to_dict("records") if len(df) else []
    opts = {"columnDefs": cols, "rowData": data, "pagination": True, "paginationPageSize": 100,
            "paginationPageSizeSelector": [50, 100, 500, 1000], "enableCellTextSelection": True}
    if row_style:
        opts[":getRowStyle"] = row_style
    if totals:
        opts["pinnedBottomRowData"] = [totals]
        opts[":getRowStyle"] = "p => p.node.rowPinned ? {fontWeight: 700, background: '#EEF3F8'} : null"
    if selectable:
        opts["rowSelection"] = {"mode": "multiRow", "checkboxes": True, "headerCheckbox": True,
                                "enableClickSelection": False}
        opts["selectionColumnDef"] = {"pinned": "left", "width": 48, "maxWidth": 48, "suppressHeaderMenuButton": True}
    elif on_row:
        opts["rowSelection"] = {"mode": "singleRow", "checkboxes": False, "enableClickSelection": True}
    g = ui.aggrid(opts, theme="quartz", auto_size_columns=False) \
        .classes("w-full").style(f"height:{height}")
    if not fit:
        g.on("firstDataRendered", lambda: g.run_grid_method("autoSizeAllColumns"))
    if on_row:
        def clicked(e):
            colid = e.args.get("colId")
            if colid == "ag-Grid-SelectionColumn" or colid in editable:
                return                        # ticking a row or editing a cell is not "open"
            on_row(e.args.get("data", {}))
        g.on("cellClicked", clicked)
    return g


def first(df, cols):
    """Put the most used columns first; keep the rest in their original order."""
    lead = [c for c in cols if c in df.columns]
    return df[lead + [c for c in df.columns if c not in lead]]


NOTE_LEAD = ["Trade Date", "Contract Note No", "Broker", "Client / Account", "Gross Purchase Value", "Gross Sale Value",
             "Total Charges", "Net Amount (Rs, rounded)", "Direction", "Status"]
SCRIP_LEAD = ["Trade Date", "Script", "Side", "Quantity", "Avg Gross Rate", "Gross Value", "Total Charges",
              "Net Cost / Proceeds (Rs)", "Net Rate per Unit (Rs)", "Client / Account", "Broker", "Contract Note No"]


def drop_zone(title: str, accept: str, on_files, button: str = "Choose file(s) to upload"):
    """Large drag-and-drop area. Files are saved to a fresh batch folder, then on_files(batch, paths) runs."""
    async def got(e):
        batch = L.uploads / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        batch.mkdir(parents=True, exist_ok=True)
        paths = []
        for f in e.files:
            p = batch / Path(f.name).name
            await f.save(p)
            paths.append(p)
        up.reset()
        await on_files(batch, paths)

    with ui.row().classes("items-center gap-3"):
        ui.button(button, icon="upload_file", on_click=lambda: up.run_method("pickFiles")) \
            .props("unelevated color=secondary size=lg no-caps")
        ui.label("or drag and drop the file(s) onto the box below").classes("hint")
    with ui.element("div").classes("dropzone"):
        up = ui.upload(multiple=True, auto_upload=True, on_multi_upload=got, label=title) \
            .props(f"accept={accept} flat")
    return up


def keep_copy(p: Path, folder: Path):
    """Keep an uploaded source file in Transaction Data (uploads themselves are temporary)."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        dst = folder / f"{datetime.now():%Y%m%d_%H%M%S}_{p.name}"
        dst.write_bytes(Path(p).read_bytes())
    except OSError:
        pass


def confirm(title: str, lines: list[str], on_yes, yes_label="Delete"):
    with ui.dialog() as d, ui.card().classes("w-[620px] max-w-[95vw]"):
        ui.label(title).classes("text-lg font-semibold")
        with ui.column().classes("max-h-72 overflow-auto gap-0"):
            for ln in lines[:200]:
                ui.label(ln).classes("text-sm")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=d.close).props("flat")

            async def yes():
                d.close()
                res = on_yes()
                if asyncio.iscoroutine(res):
                    await res
            ui.button(yes_label, icon="delete", on_click=yes).props("color=negative")
    d.open()


def folder_dialog(start: Path, on_pick):
    """Server-side folder picker (works for any drive on this computer)."""
    cur = {"p": start if start.exists() else PROJECT}
    with ui.dialog() as dlg, ui.card().classes("w-[640px]"):
        ui.label("Select folder").classes("text-lg font-semibold")
        here = ui.label().classes("hint")
        box = ui.column().classes("w-full h-96 overflow-auto gap-0")

        def show(p: Path):
            cur["p"] = p
            here.text = str(p)
            box.clear()
            with box:
                with ui.row().classes("gap-1"):
                    for d in drives():
                        ui.button(str(d), on_click=lambda d=d: show(d)).props("dense flat no-caps size=sm")
                if p.parent != p:
                    ui.button(".. (up)", icon="arrow_upward", on_click=lambda: show(p.parent)) \
                        .props("flat no-caps align=left").classes("w-full")
                try:
                    subs = sorted([d for d in p.iterdir() if d.is_dir() and not d.name.startswith((".", "$"))],
                                  key=lambda d: d.name.lower())
                except OSError:
                    subs = []
                for d in subs:
                    ui.button(d.name, icon="folder", on_click=lambda d=d: show(d)) \
                        .props("flat no-caps align=left").classes("w-full").style(f"color:{NAVY}")

        show(cur["p"])
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("Use this folder", icon="check", on_click=lambda: (dlg.close(), on_pick(cur["p"])))
    dlg.open()


def drives():
    if sys.platform.startswith("win"):
        return [Path(f"{d}:\\") for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    return [Path("/")]


def empty_state(msg="No contract notes imported yet."):
    with ui.card().classes("card p-8 items-center w-full"):
        ui.icon("inbox").classes("text-6xl text-gray-300")
        ui.label(msg).classes("text-gray-500")
        ui.button("Import contract notes", icon="upload_file", on_click=lambda: ui.navigate.to("/import"))


def open_url(url: str):
    webbrowser.open(url)


def deliver(paths):
    """Show exported files: open a single file directly (Excel, PDF...), or the folder for several."""
    paths = [Path(p) for p in paths]
    if not paths:
        return
    target = paths[0] if len(paths) == 1 else paths[0].parent
    if sys.platform.startswith("win"):
        _front()
        try:
            os.startfile(str(target))  # noqa: S606 - the user's own export
        except OSError:
            subprocess.Popen(["explorer", "/select,", str(paths[0])])
    try:                                   # the page may have been closed while the export ran
        if not sys.platform.startswith("win") and len(paths) == 1:
            ui.download.file(paths[0])
        success(f"Exported successfully: {target}")
    except RuntimeError:
        pass


def _front():
    """Let the window we open next come in front of the (maximised) app window."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)     # ASFW_ANY
        except Exception:  # noqa: BLE001
            pass


def open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            _front()
            subprocess.Popen(["explorer.exe", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        ui.notify(f"Folder opened in a separate window: {path}  (if you do not see it, look for File Explorer "
                  f"on the taskbar)", type="info", position="top", timeout=6000, multi_line=True)
    except Exception as exc:  # noqa: BLE001
        failure("The folder could not be opened", [{"what": str(path), "why": str(exc),
                                                     "fix": "Open it from File Explorer: it is inside the Data "
                                                            "folder next to the exe."}])


# --------------------------------------------------------------------------- dashboard

def advice(text: str) -> str:
    """What the user can do about a problem message."""
    t = str(text).lower()
    if "header row" in t or "missing column" in t:
        return ("The sheet needs a header row with columns such as Name, Script, Date of Purchase, Qty and Purchase "
                "Value. Correct the headings and upload again.")
    if "date" in t and ("understood" in t or "empty" in t):
        return "Write the date as DD/MM/YYYY (or an Excel date) and upload again."
    if "pan" in t and "valid" in t:
        return ("PAN must be 10 characters, for example ABCDE1234F. Correct it, or leave it empty and set it on "
                "Persons and PAN.")
    if "isin" in t and "valid" in t:
        return "ISIN must be 12 characters starting with IN. Correct it, or leave it empty: it is found from the masters."
    if "quantity" in t:
        return "Enter a quantity greater than zero."
    if "purchase value" in t:
        return "Enter the purchase value (total cost) or the purchase rate."
    if "name / holder" in t:
        return "Enter the holder's name (or PAN) on that row."
    if any(k in t for k in ("urlerror", "timed out", "tunnel", "connection", "getaddrinfo", "network")):
        return ("The website could not be reached. Check the internet connection and press Update again; or open the "
                "source page with the buttons below, download the file and upload it here.")
    if "expected list" in t:
        return "The website was busy and sent a different page. Try again in a few minutes, or download the file by hand."
    if "no isin column" in t or "not recognised" in t:
        return ("This file is not a known master list. Use the official BSE / NSE / Nifty / AMFI files, or any CSV / "
                "Excel file with an ISIN column.")
    if "could not read the file" in t or "badzipfile" in t or "not a zip" in t:
        return "The file could not be opened. Make sure it is a real .xlsx file (save it again from Excel) and retry."
    return remedy(text)


def success(msg: str):
    """Green message at the top for a few seconds."""
    ui.notify(msg, type="positive", position="top", timeout=5000, icon="check_circle", multi_line=True,
              classes="text-base")


def failure(title: str, problems: list[dict], box=None):
    """Red message with the reason and what to do; the full list also goes into `box` on the page."""
    from html import escape
    first = problems[0] if problems else {"why": "", "fix": ""}
    more = f"<br><i>+{len(problems) - 1} more listed on the page</i>" if len(problems) > 1 else ""
    ui.notify(f"<b>{escape(title)}</b><br><b>Why:</b> {escape(str(first['why']))}<br>"
              f"<b>What to do:</b> {escape(str(first['fix']))}{more}", type="negative", position="top",
              timeout=20000, close_button="Close", multi_line=True, icon="error", html=True,
              classes="text-base cnm-error")
    if box is not None:
        box.clear()
        with box:
            problem_card(title, problems)


def problem_card(title: str, problems: list[dict]):
    with ui.card().classes("card p-4 w-full").style("border:2px solid #C62828; background:#FFF5F5"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("error").classes("text-2xl text-red-700")
            ui.label(title).classes("text-lg font-semibold text-red-800")
        with ui.column().classes("gap-2 max-h-80 overflow-auto w-full"):
            for p in problems[:200]:
                with ui.column().classes("gap-0"):
                    ui.label(p.get("what", "")).classes("font-semibold text-sm")
                    ui.label("Why: " + p.get("why", "")).classes("text-sm text-red-700")
                    ui.label("What to do: " + p.get("fix", "")).classes("text-sm text-gray-800")


def kpi(label, value, sub="", color=NAVY, on_click=None, tip=""):
    box = ui.element("div").classes("kpi" + (" click" if on_click else ""))
    if on_click:
        box.on("click", lambda: on_click())
    if tip:
        box.tooltip(tip)
    with box:
        if "Loss" in label or "loss" in label:          # the word Loss always in red
            ui.html(re.sub(r"(?i)\b(loss)\b", r'<span style="color:#C62828">\1</span>', label)).classes("lbl")
        else:
            ui.label(label).classes("lbl")
        ui.label(value).classes("val").style(f"color:{color}")
        if sub:
            ui.label(sub).classes("sub")


@ui.page("/")
def dashboard():
    col = frame("Dashboard", "/")
    fr = report.frames(store(), *scope())
    nf, sf = fr["notes"], fr["scrips"]
    with col:
        age = masters.age_days(store())
        if age is None or age > MASTER_DAYS:
            master_banner("Security masters (company names, ISIN, industry) " +
                          ("have not been downloaded yet." if age is None else f"are {age} days old.") +
                          " Update them on Import Market Masters.")
        with ui.row().classes("items-center gap-3 w-full"):
            ui.label("Investment").classes("text-lg font-bold").style(f"color:{NAVY}")
            ui.space()
            price_buttons()
            ui.button("Investment statement", icon="account_balance_wallet",
                      on_click=lambda: ui.navigate.to("/investment")).props("outline no-caps")
        investment_block(datetime.now().strftime("%Y-%m-%d"))
        ui.separator()
        ui.label("Contract notes").classes("text-lg font-bold").style(f"color:{NAVY}")
        if not len(nf):
            empty_state()
            return
        buys, sells = sf[sf["Side"] == "BUY"], sf[sf["Side"] == "SELL"]
        with ui.row().classes("gap-4 flex-wrap"):
            kpi("Contract notes", f"{len(nf):,}", f"{nf['Broker'].nunique()} broker(s), {nf['PAN'].nunique()} client(s)")
            kpi("Purchases (net cost)", inr(buys["Net Cost / Proceeds (Rs)"].sum()), f"{len(buys)} script rows", TEAL)
            kpi("Sales (net proceeds)", inr(sells["Net Cost / Proceeds (Rs)"].sum()), f"{len(sells)} script rows", "#B4572E")
            kpi("Brokerage + levies", inr(sf["Total Charges"].sum()), "all charges allocated", GOLD)
            rec = (nf["Status"] == "Reconciled").sum()
            kpi("Reconciled", f"{rec} / {len(nf)}", "notes matching printed net", "#2E7D32" if rec == len(nf) else "#C62828")

        sf = sf.copy()
        sf["Month"] = sf["Trade Date"].str[:7]
        months = sorted(sf["Month"].unique())
        mb = sf[sf["Side"] == "BUY"].groupby("Month")["Net Cost / Proceeds (Rs)"].sum()
        ms = sf[sf["Side"] == "SELL"].groupby("Month")["Net Cost / Proceeds (Rs)"].sum()
        with ui.row().classes("w-full gap-4 no-wrap"):
            with ui.card().classes("card p-3").style("flex:2"):
                ui.label("Monthly purchases and sales (₹): click a bar for details").classes("font-semibold text-gray-700")
                ui.echart({
                    "tooltip": {"trigger": "axis"}, "legend": {"data": ["Purchases", "Sales"], "top": 0, "right": 10},
                    "grid": {"left": 80, "right": 20, "top": 40, "bottom": 30},
                    "xAxis": {"type": "category", "data": months},
                    "yAxis": {"type": "value"},
                    "series": [{"name": "Purchases", "type": "bar", "data": [round(mb.get(m, 0)) for m in months],
                                "itemStyle": {"color": TEAL}},
                               {"name": "Sales", "type": "bar", "data": [round(ms.get(m, 0)) for m in months],
                                "itemStyle": {"color": "#D9825B"}}]},
                    on_point_click=lambda e: drill_dialog(
                        f"Month {e.name}: " + ("purchases" if e.series_name == "Purchases" else "sales"),
                        sf[(sf["Month"] == e.name) & (sf["Side"] == ("BUY" if e.series_name == "Purchases" else "SELL"))],
                        f"/register?month={e.name}")).classes("w-full h-80")
            with ui.card().classes("card p-3").style("flex:1"):
                ui.label("Turnover by broker (click a slice)").classes("font-semibold text-gray-700")
                tb = sf.groupby("Broker")["Gross Value"].sum().round()
                ui.echart({"tooltip": {"trigger": "item"},
                           "legend": {"bottom": 0, "type": "scroll"},
                           "series": [{"type": "pie", "radius": ["40%", "65%"], "center": ["50%", "45%"],
                                       "data": [{"name": k, "value": v} for k, v in tb.items()],
                                       "label": {"show": False}}],
                           "color": [NAVY, TEAL, GOLD, "#D9825B", "#7B8FA6"]},
                          on_point_click=lambda e: drill_dialog(f"Broker: {e.name}", sf[sf["Broker"] == e.name])) \
                    .classes("w-full h-80")
        with ui.row().classes("w-full gap-4 no-wrap"):
            with ui.card().classes("card p-3").style("flex:2"):
                ui.label("Top 12 scripts by purchase value (click a bar for details)").classes("font-semibold text-gray-700")
                top = buys.groupby("Script")["Net Cost / Proceeds (Rs)"].sum().sort_values().tail(12)
                ui.echart({"tooltip": {"trigger": "axis"}, "grid": {"left": 110, "right": 30, "top": 10, "bottom": 30},
                           "xAxis": {"type": "value"}, "yAxis": {"type": "category", "data": list(top.index)},
                           "series": [{"type": "bar", "data": [round(v) for v in top.values], "itemStyle": {"color": NAVY}}]},
                          on_point_click=lambda e: drill_dialog(f"{e.name}: purchases and sales",
                                                                sf[sf["Script"] == e.name],
                                                                f"/register?script={e.name}")).classes("w-full h-96")
            with ui.card().classes("card p-3").style("flex:1"):
                ui.label("Asset class (gross turnover, click a slice)").classes("font-semibold text-gray-700")
                ac = sf.groupby("Asset Class")["Gross Value"].sum().round()
                ui.echart({"tooltip": {"trigger": "item"},
                           "legend": {"bottom": 0, "type": "scroll"},
                           "series": [{"type": "pie", "radius": ["40%", "65%"], "center": ["50%", "45%"],
                                       "label": {"show": False},
                                       "data": [{"name": k or "Unclassified", "value": v} for k, v in ac.items()]}],
                           "color": [TEAL, GOLD, NAVY, "#D9825B", "#7B8FA6"]},
                          on_point_click=lambda e: drill_dialog(
                              f"Asset class: {e.name}",
                              sf[sf["Asset Class"].replace("", "Unclassified").fillna("Unclassified") == e.name],
                              f"/register?asset={e.name}")).classes("w-full h-96")
                ui.label("Industry split appears once the Scrip Master has industries.").classes("hint")


# --------------------------------------------------------------------------- import

@ui.page("/import")
def import_page():
    col = frame("Import Contract Notes", "/import")
    state = {"path": PROJECT / "Resources" if (PROJECT / "Resources").exists() else PROJECT}
    q: queue.Queue = queue.Queue()

    with col:
        upto_box = ui.column().classes("w-full")

        def draw_upto():
            upto_box.clear()
            df = report.last_imported(store(), scope_pan(current_pan()))
            with upto_box:
                with ui.card().classes("card p-4 w-full").style(f"border-left:5px solid {TEAL}"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("event_available").classes("text-2xl").style(f"color:{TEAL}")
                        ui.label(f"Already imported: {person_label()}").classes("font-semibold text-gray-700")
                    if len(df):
                        ui.label("Import contract notes dated after the date shown for each broker. Notes already "
                                 "imported are skipped anyway, so overlapping files are safe.").classes("hint")
                        grid(df, qty=["Notes"], pinned=1, height=f"{min(90 + 42 * len(df), 300)}px")
                    else:
                        ui.label("No contract notes imported yet for this selection.").classes("hint")
        draw_upto()
        ui.label("Drag and drop contract notes (PDF, ZIP, HTML, images, broker tradebooks) into the box; the import "
                 "starts by itself. Already imported notes are skipped automatically.").classes("hint")

        async def dropped(batch, paths):
            await start([str(batch)])

        drop_zone("Contract notes: drop files here",
                  ".pdf,.htm,.html,.zip,.xlsx,.xls,.csv,.jpg,.jpeg,.png", dropped, "Upload contract note file(s)")
        with ui.card().classes("card p-4 w-full"):
            ui.label("Or import a whole folder (including sub-folders)").classes("font-semibold text-gray-700")
            with ui.row().classes("items-center w-full gap-2"):
                ui.icon("folder").classes("text-2xl").style(f"color:{GOLD}")
                path_in = ui.input("Folder", value=str(state["path"])).classes("flex-grow").props("outlined dense")
                ui.button("Browse", icon="folder_open", on_click=lambda: browse()).props("outline")
                go = ui.button("Import folder", icon="play_arrow", on_click=lambda: start([path_in.value]))
        progress = ui.linear_progress(show_value=False).props("indeterminate color=secondary").classes("w-full")
        progress.visible = False
        summary_row = ui.row().classes("gap-4 flex-wrap")
        problems_box = ui.column().classes("w-full")
        log = ui.log(max_lines=2000).classes("w-full h-96 card").style("font-size:12px")

    def browse():
        folder_dialog(Path(path_in.value), lambda p: setattr(path_in, "value", str(p)))

    async def start(paths):
        paths = [p for p in paths if p and Path(p).exists()]
        if not paths:
            ui.notify("Folder not found", type="warning")
            return
        go.disable()
        progress.visible = True
        log.clear()
        log.push(f"Importing from {', '.join(paths)} ...")
        pw = passwords.all_passwords(store())

        def work():
            with _lock:
                st = store()
                res = import_paths(paths, st, DATA, pw, echo=q.put)
                reference.fill_master(st)
                assumed.refresh(st)
                maintenance.write_csv(st, L)
                return res

        timer = ui.timer(0.3, lambda: [log.push(q.get_nowait()) for _ in range(q.qsize())])
        try:
            summary, review = await run.io_bound(work)
        finally:
            await asyncio.sleep(0.4)
            timer.cancel()
            while not q.empty():
                log.push(q.get_nowait())
            progress.visible = False
            go.enable()
        summary_row.clear()
        with summary_row:
            kpi("Files read", str(summary["files"]))
            kpi("Notes saved", str(summary["notes_saved"]), color="#2E7D32")
            kpi("Duplicates skipped", str(summary["duplicates"]), color=GOLD)
            kpi("Not reconciled", str(summary["unreconciled"]), color="#C62828" if summary["unreconciled"] else NAVY)
            kpi("Errors", str(summary["errors"]), color="#C62828" if summary["errors"] else NAVY)
        for cn in review:
            log.push(f"NOT SAVED {cn.broker} {cn.cn_no}: difference {cn.recon_diff:,.2f}")
        draw_upto()
        problems_box.clear()
        probs = [{"what": f"{p['status']}: {Path(p['source'].split(' > ')[-1].split(' [')[0]).name}",
                  "why": p["message"] or p["status"], "fix": p["remedy"]} for p in summary["problems"]]
        if summary["notes_saved"]:
            success(f"{summary['notes_saved']} contract note(s) imported successfully"
                    + (f", {summary['duplicates']} already imported were skipped" if summary["duplicates"] else ""))
        elif not probs:
            ui.notify("Nothing new to import: these contract notes were already imported.", type="info",
                      position="top", timeout=5000, multi_line=True)
        if probs:
            failure(f"{len(probs)} file(s) could not be imported", probs, problems_box)


# --------------------------------------------------------------------------- tables

MONEY_COLS = ["Gross Purchase Value", "Gross Sale Value", *CHARGE_LABELS.values(), "Total Charges",
              "Net Amount (as printed)", "Reconciliation Diff", "Avg Gross Rate", "Gross Value", "Net Value (exact)",
              "Rounding (Rs)", "Net Rate per Unit (Rs)", "Gross Rate", "Computed Net (Buy - Sell + Charges)",
              "Printed Net (+ payable / - receivable)", "Difference", "Price"]
RUPEE_COLS = ["Net Amount (Rs, rounded)", "Net Cost / Proceeds (Rs)", "Total Cost (Rs)"]
QTY_COLS = ["Quantity", "Buy Quantity", "Sell Quantity", "Script Rows"]


@ui.page("/notes")
def notes_page():
    col = frame("Contract Notes", "/notes")
    fr = report.frames(store(), *scope())
    nf = fr["notes"]
    with col:
        if not len(nf):
            empty_state()
            return
        with ui.row().classes("items-center gap-3"):
            ui.label("Tick notes to delete them; click a row to open it, edit or delete its items.").classes("hint")
            ui.space()
            dbtn = ui.button("Delete selected notes", icon="delete").props("color=negative outline")
        g = grid(first(nf, NOTE_LEAD), MONEY_COLS, RUPEE_COLS, QTY_COLS, pinned=2,
                 on_row=lambda r: note_dialog(int(r["_nid"])), selectable=True, height="calc(100vh - 270px)")

        async def delete_selected():
            rows = await g.get_selected_rows()
            if not rows:
                ui.notify("Tick one or more notes first", type="warning")
                return
            ids = [int(r["_nid"]) for r in rows]

            def yes():
                done = store().delete_notes(ids)
                ui.notify(f"{len(done)} contract note(s) deleted. Their files can be imported again.", type="positive")
                ui.navigate.reload()
            confirm(f"Delete {len(rows)} contract note(s)?",
                    [f"{r['Trade Date']}  {r['Broker']}  {r['Contract Note No']}  {r['Client / Account']}" for r in rows]
                    + ["", "Their trades and script rows are deleted too. This is written to the Import Log."], yes)
        dbtn.on_click(delete_selected)


def note_dialog(note_id: int):
    s = store()
    fr = report.frames(s)
    nrow = fr["notes"][fr["notes"]["_nid"] == note_id]
    if not len(nrow):
        return
    row = nrow.iloc[0].to_dict()
    sf = fr["scrips"][fr["scrips"]["_nid"] == note_id]
    with ui.dialog() as dlg, ui.card().classes("w-[1250px] max-w-[96vw]"):
        with ui.row().classes("w-full items-center"):
            ui.label(f"{row.get('Broker')}  |  {row.get('Contract Note No')}  |  {row.get('Client / Account')}") \
                .classes("text-lg font-semibold")
            ui.space()
            ok = row.get("Status") == "Reconciled"
            ui.badge(row.get("Status") if ok else f"Check: differs by {row.get('Reconciliation Diff'):,.2f}",
                     color="green" if ok else "red")
        with ui.row().classes("gap-3 items-end"):
            kpi("Net amount (printed)", inr(row.get("Net Amount (as printed)"), 2), row.get("Direction"))
            kpi("Total charges", inr(row.get("Total Charges"), 2))
            td = ui.input("Trade date", value=row.get("Trade Date")).props("type=date outlined dense")
            sd = ui.input("Settlement date", value=row.get("Settlement Date") or "").props("type=date outlined dense")

            def save_dates():
                try:
                    st = store()
                    if td.value != row.get("Trade Date"):
                        st.update_note(note_id, "trade_date", td.value)
                    if sd.value and sd.value != row.get("Settlement Date"):
                        st.update_note(note_id, "settlement_date", sd.value)
                    ui.notify("Dates saved", type="positive")
                except ValueError as exc:
                    ui.notify(str(exc), type="negative")
            ui.button("Save dates", icon="save", on_click=save_dates).props("outline")
        ui.label("Yellow cells can be edited (quantity, value, charges, ISIN, script). Totals, net cost and the check "
                 "against the printed amount are recalculated, and every change is logged.").classes("hint")
        cols = ["Script", "ISIN", "Side", "Quantity", "Avg Gross Rate", "Gross Value",
                *[CHARGE_LABELS[k] for k in CHARGE_KEYS], "Total Charges", "Net Cost / Proceeds (Rs)",
                "Rounding (Rs)", "STT / Stamp Basis", "_sid"]
        editable = ["Script", "ISIN", "Quantity", "Gross Value", *[CHARGE_LABELS[k] for k in CHARGE_KEYS]]
        g = grid(sf[cols], MONEY_COLS, RUPEE_COLS, QTY_COLS, height="380px", editable=editable, selectable=True)

        def changed(e):
            r, colid = e.args.get("data", {}), e.args.get("colId")
            try:
                store().update_scrip(int(r["_sid"]), colid, r.get(colid))
                ui.notify(f"Saved {colid}", type="positive", timeout=1200)
            except (ValueError, TypeError) as exc:
                ui.notify(f"Not saved: {exc}", type="negative")
        g.on("cellValueChanged", changed)

        async def delete_items():
            rows = await g.get_selected_rows()
            if not rows:
                ui.notify("Tick one or more items first", type="warning")
                return

            def yes():
                store().delete_scrip_rows([int(r["_sid"]) for r in rows])
                ui.notify(f"{len(rows)} item(s) deleted", type="positive")
                dlg.close()
                note_dialog(note_id)
            confirm(f"Delete {len(rows)} item(s) from this note?",
                    [f"{r['Script']} {r['Side']} {r['Quantity']:g}" for r in rows], yes)
        ui.label(f"Source: {row.get('Source File')}").classes("hint")
        with ui.row().classes("w-full"):
            ui.button("Delete selected items", icon="delete", on_click=delete_items).props("color=negative outline")
            ui.space()
            ui.button("Close and refresh", on_click=lambda: (dlg.close(), ui.navigate.reload()))
    dlg.open()


@ui.page("/register")
def register_page(month: str = "", script: str = "", asset: str = ""):
    col = frame("Script Register (per contract note, script and side)", "/register")
    sf = report.frames(store(), *scope())["scrips"]
    with col:
        if not len(sf):
            empty_state()
            return
        flt = []
        if month:
            sf, _ = sf[sf["Trade Date"].str.startswith(month)], flt.append(f"month {month}")
        if script:
            sf, _ = sf[sf["Script"] == script], flt.append(f"script {script}")
        if asset:
            sf, _ = sf[sf["Asset Class"].replace("", "Unclassified") == asset], flt.append(f"asset class {asset}")
        if flt:
            with ui.row().classes("items-center"):
                ui.label("Filtered: " + ", ".join(flt)).classes("hint")
                ui.button("Clear filter", on_click=lambda: ui.navigate.to("/register")).props("flat dense")
        grid(first(sf, SCRIP_LEAD), MONEY_COLS, RUPEE_COLS, QTY_COLS, pinned=3)


@ui.page("/daily")
def daily_page():
    col = frame("Daily Summary (client, date, script and side; BUY and SELL never netted)", "/daily")
    df = report.frames(store(), *scope())["daily"]
    with col:
        if not len(df):
            empty_state()
            return
        grid(first(df, SCRIP_LEAD), MONEY_COLS, RUPEE_COLS, QTY_COLS, pinned=3)


@ui.page("/recon")
def recon_page():
    col = frame("Contract Note Reconciliation", "/recon")
    rf = report.frames(store(), *scope())["recon"]
    with col:
        if not len(rf):
            empty_state()
            return
        ok = (rf["Status"] == "Reconciled").sum()
        ui.label(f"{ok} of {len(rf)} notes reconcile to the printed net amount (tolerance 5 paise). "
                 "Notes that do not reconcile are never saved; see the Import Log.").classes("hint")
        grid(rf, MONEY_COLS, RUPEE_COLS, QTY_COLS, pinned=1)


@ui.page("/recon/holdings")
def holding_recon_page():
    col = frame("Holding Reconciliation", "/recon/holdings")
    state = {"df": None, "file": "", "how": ""}
    with col:
        ui.label("Compare the holding as per the app (opening holdings + purchases - sales up to the statement date) "
                 "with a holding statement from your DP, broker or CAS, script by script.").classes("hint")
        people = {k: v for k, v in person_options().items() if k}
        with ui.card().classes("card p-4 w-full"):
            ui.label("1. Whose statement, and as on which date").classes("font-semibold text-gray-700")
            with ui.row().classes("items-end gap-4 flex-wrap"):
                psel = ui.select(people, value=current_pan() if current_pan() in people else None,
                                 label="Person / PAN").props("outlined dense options-dense").classes("w-80")
                asof = ui.input("Statement date (as on)", value=datetime.now().strftime("%Y-%m-%d")) \
                    .props("type=date outlined dense")
                blist = ["All brokers"] + brokers.names(store())
                bsel = ui.select(blist, value="All brokers", label="Broker / DP of the statement") \
                    .props("outlined dense options-dense").classes("w-72") \
                    .tooltip("Choose the broker if the statement covers only that demat account")
            with ui.expansion("Where to get a holding statement", icon="help_outline").classes("w-full"):
                ui.label("Log in on the site, download the holding statement (PDF, Excel or CSV), then upload it "
                         "below. Your broker's back-office / console (Holdings > Download) works too.").classes("hint")
                with ui.row().classes("gap-2 flex-wrap"):
                    for title, url in holdings_recon.SOURCES:
                        ui.button(title, icon="open_in_new", on_click=lambda u=url: open_url(u)) \
                            .props("outline no-caps dense").classes("text-xs")

        ui.label("2. Upload the holding statement").classes("font-semibold text-gray-700")

        async def got(batch, paths):
            p = paths[0]
            try:
                df, how = await run.io_bound(lambda: holdings_recon.read_statement(p))
            except Exception as exc:  # noqa: BLE001
                store().log(p.name, "Holding statement not read", str(exc))
                failure("The holding statement could not be read",
                        [{"what": p.name, "why": str(exc),
                          "fix": advice(str(exc)) if "password" in str(exc).lower() else
                          "Use the statement's Excel or CSV download if there is one, or a PDF with the holdings in a "
                          "table (ISIN, name, quantity)."}], map_box)
                return
            state.update(df=df, file=p.name, how=how)
            keep_copy(p, L.statements)
            success(f"Statement read: {len(df)} row(s) from {how}. Check the columns and press Reconcile.")
            draw_mapping()
        drop_zone("Holding statement: drop a PDF, Excel or CSV file here", ".pdf,.xlsx,.xls,.csv", got,
                  "Upload holding statement")
        map_box = ui.column().classes("w-full")
        result_box = ui.column().classes("w-full")

        def draw_mapping():
            map_box.clear()
            df = state["df"]
            guess = holdings_recon.guess_columns(df)
            opts = {"": "(none)", **{c: c for c in df.columns}}
            with map_box:
                with ui.card().classes("card p-4 w-full"):
                    ui.label(f"3. Columns found in {state['file']} ({state['how']})").classes("font-semibold text-gray-700")
                    ui.label("The app has picked these columns. Change any that are wrong, then press Reconcile.") \
                        .classes("hint")
                    sels = {}
                    with ui.row().classes("items-end gap-3 flex-wrap"):
                        for key, label in (("isin", "ISIN"), ("symbol", "Symbol / scrip code"), ("name", "Security name"),
                                           ("qty", "Quantity (holding)"), ("value", "Value (optional)")):
                            sels[key] = ui.select(opts, value=guess.get(key, ""), label=label) \
                                .props("outlined dense options-dense").classes("w-56")
                    grid(df.head(25).astype(str), pinned=0, height="260px")

                    async def do_reconcile():
                        if not psel.value:
                            failure("Choose the person first", [{"what": "Person / PAN", "why": "no person selected",
                                                                 "fix": "Choose whose statement this is in step 1."}])
                            return
                        mapping = {k: v.value for k, v in sels.items() if v.value}
                        if "qty" not in mapping or not ({"isin", "symbol", "name"} & set(mapping)):
                            failure("Columns missing", [{"what": "Column choice",
                                                         "why": "a quantity column and an ISIN, symbol or name column "
                                                                "are needed",
                                                         "fix": "Choose them in the drop-downs above."}])
                            return
                        broker = "" if bsel.value == "All brokers" else bsel.value

                        def work():
                            with _lock:
                                st = store()
                                stmt = holdings_recon.statement_rows(st, state["df"], mapping)
                                res = holdings_recon.reconcile(st, psel.value, asof.value, stmt, broker)
                                rid = holdings_recon.save_run(st, psel.value, people.get(psel.value, psel.value),
                                                              asof.value, broker, state["file"], res)
                                return res, rid, len(stmt)
                        res, rid, nstmt = await run.io_bound(work)
                        if not nstmt:
                            failure("No holdings found in the statement",
                                    [{"what": state["file"], "why": "no rows with a quantity were found in the chosen "
                                                                    "columns",
                                      "fix": "Check the column choice, especially Quantity."}])
                            return
                        show_result(res, rid)
                        bad = (res["Status"] != "Matched").sum()
                        if bad:
                            failure(f"{bad} script(s) do not match",
                                    [{"what": f"{r['Script'] or r['ISIN']}", "why": f"{r['Status']}: app "
                                      f"{r['Qty as per App']:g}, statement {r['Qty as per Statement']:g}",
                                      "fix": fix_for(r["Status"])} for _, r in res[res["Status"] != "Matched"].iterrows()])
                        else:
                            success(f"All {len(res)} script(s) match the statement")
                    ui.button("Reconcile", icon="compare_arrows", on_click=do_reconcile) \
                        .props("unelevated color=positive size=lg no-caps")

        def show_result(res, rid):
            result_box.clear()
            with result_box:
                with ui.card().classes("card p-4 w-full"):
                    ui.label(f"4. Result: {people.get(psel.value, '')} as on {asof.value}"
                             + ("" if bsel.value == "All brokers" else f" ({bsel.value})")) \
                        .classes("font-semibold text-gray-700")
                    c = res["Status"].value_counts()
                    with ui.row().classes("gap-3 flex-wrap"):
                        kpi("Matched", str(c.get("Matched", 0)), color="#2E7D32")
                        kpi("Difference", str(c.get("Difference", 0)), color="#C62828" if c.get("Difference") else NAVY)
                        kpi("Opening holding missing", str(c.get("Opening holding missing", 0)),
                            "sold more than bought in the app", color="#C62828" if c.get("Opening holding missing") else NAVY)
                        kpi("Only in app", str(c.get("Only in app", 0)), color=GOLD if c.get("Only in app") else NAVY)
                        kpi("Only in statement", str(c.get("Only in statement", 0)),
                            color=GOLD if c.get("Only in statement") else NAVY)
                    grid(res, money=["Value as per Statement"],
                         qty=["Qty as per App", "Qty as per Statement", "Difference (Statement - App)"],
                         pinned=2, height="420px")

                    def export():
                        p = REPORTS / f"Holding_Reconciliation_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
                        res.to_excel(p, index=False, sheet_name="Holding Reconciliation")
                        deliver([p])
                    ui.button("Open in Excel", icon="grid_on", on_click=export).props("outline")

        ui.separator()
        ui.label("Earlier reconciliations (click one to see it again)").classes("font-semibold text-gray-700")
        hist = holdings_recon.runs(store())
        if len(hist):
            def open_run(r):
                res = holdings_recon.run_result(store(), int(r["_id"]))
                with ui.dialog() as d, ui.card().classes("w-[1200px] max-w-[96vw]"):
                    ui.label(f"{r['Person']} as on {r['As on Date']} ({r['Broker / DP']}), {r['Statement file']}") \
                        .classes("text-lg font-semibold")
                    grid(res, money=["Value as per Statement"],
                         qty=["Qty as per App", "Qty as per Statement", "Difference (Statement - App)"], pinned=2,
                         height="480px")
                    ui.button("Close", on_click=d.close)
                d.open()
            grid(hist, qty=["Scripts", "Matched", "Difference", "Only in App", "Only in Statement"], pinned=1,
                 height="240px", on_row=open_run)
        else:
            ui.label("None yet.").classes("hint")


def fix_for(status: str) -> str:
    return {
        "Difference": "Check for a missing or wrong contract note, a bonus / split / rights not yet entered, or an "
                      "opening holding with the wrong quantity.",
        "Opening holding missing": "The app has sales from shares bought before the first contract note. Add those "
                                   "purchases on Opening Holdings.",
        "Only in app": "The statement shows none: check for a sale contract note not imported, a transfer out, or "
                       "choose the right broker / DP above.",
        "Only in statement": "The app has none: import the purchase contract note or add it on Opening Holdings "
                             "(also IPO allotments, transfers in, bonus shares).",
    }.get(status, "")


@ui.page("/recon/cost")
def cost_recon_page():
    col = frame("Cost Reconciliation (Tally)", "/recon/cost")
    st = store()
    cfg = tally.load(st)
    state = {"ledgers": None, "source": "", "res": None}
    with col:
        ui.label("Compare the cost of each script held as per the app (FIFO: opening holdings + purchases, less the "
                 "cost of shares sold, in whole rupees) with the balance of its investment ledger in Tally as on the "
                 "same date. Quantities are matched on Holding Reconciliation.").classes("hint")
        people = {k: v for k, v in person_options().items() if k}
        with ui.card().classes("card p-4 w-full"):
            ui.label("1. Whose books, and as on which date").classes("font-semibold text-gray-700")
            with ui.row().classes("items-end gap-4 flex-wrap"):
                psel = ui.select(people, value=current_pan() if current_pan() in people else None,
                                 label="Person / PAN").props("outlined dense options-dense").classes("w-80")
                default_date = periods.bounds(current_period())[1] or datetime.now().strftime("%Y-%m-%d")
                asof = ui.input("As on date", value=default_date).props("type=date outlined dense")
                bsel = ui.select(["All brokers"] + brokers.names(st), value="All brokers", label="Broker") \
                    .props("outlined dense options-dense").classes("w-64") \
                    .tooltip("Choose a broker only if Tally keeps separate investment ledgers per broker")

        with ui.card().classes("card p-4 w-full"):
            ui.label("2. Ledger balances from Tally").classes("font-semibold text-gray-700")
            with ui.tabs().classes("text-primary") as tabs:
                t_live = ui.tab("Read from Tally now", icon="cable")
                t_file = ui.tab("Upload Tally export", icon="upload_file")
            with ui.tab_panels(tabs, value=t_live).classes("w-full"):
                with ui.tab_panel(t_live):
                    ui.label("Tally Prime must be open with the company loaded, and set to act as a server on port "
                             "9000 (F1 Help > Settings > Connectivity > Client/Server configuration: TallyPrime is "
                             "acting as Both, Port 9000).").classes("hint")
                    with ui.row().classes("items-end gap-3 flex-wrap"):
                        comp = ui.input("Tally company (blank = the one open)", value=cfg["company"]) \
                            .props("outlined dense").classes("w-80")
                        grp = ui.input("Group of investment ledgers", value=cfg["investment_group"]) \
                            .props("outlined dense").classes("w-60")
                        port = ui.input("Tally address", value=tally_link.URL).props("outlined dense").classes("w-56")

                        async def read_live():
                            try:
                                async with busy("Ledger balances are being read from Tally..."):
                                    df = await run.io_bound(lambda: tally_link.ledgers(comp.value.strip(), asof.value,
                                                                                        port.value.strip()))
                            except Exception as exc:  # noqa: BLE001
                                store().log("Tally", "Tally not read", str(exc))
                                failure("Could not read from Tally", [{
                                    "what": port.value, "why": str(exc),
                                    "fix": "Open Tally Prime and the company, set Connectivity to act as Both on port "
                                           "9000, then try again. Or use 'Upload Tally export'."}])
                                return
                            if not len(df):
                                failure("Tally returned no ledgers", [{
                                    "what": comp.value or "open company", "why": "no ledgers in the reply",
                                    "fix": "Check the company name exactly as in Tally (or leave it blank)."}])
                                return
                            loaded(df, f"Tally ({comp.value or 'open company'})")
                        ui.button("Read balances from Tally", icon="sync", on_click=read_live) \
                            .props("unelevated color=primary no-caps")
                with ui.tab_panel(t_file):
                    ui.label("In Tally: Display More Reports > Trial Balance (or Group Summary of Investments), set the "
                             "period to end on the as-on date, show ledgers (Alt+F5 Detailed), then Export (Alt+E) to "
                             "Excel. Upload that file here.").classes("hint")

                    async def got(batch, paths):
                        p = paths[0]
                        try:
                            df = await run.io_bound(lambda: tally_link.ledgers_from_file(p))
                        except Exception as exc:  # noqa: BLE001
                            store().log(p.name, "Tally export not read", str(exc))
                            failure("The Tally export could not be read", [{
                                "what": p.name, "why": str(exc),
                                "fix": "Export the Trial Balance with ledger names and closing balances to Excel."}])
                            return
                        keep_copy(p, L.tally)
                        loaded(df, p.name)
                    drop_zone("Tally export: drop the Trial Balance / Group Summary (Excel, CSV or XML)",
                              ".xlsx,.xls,.csv,.xml", got, "Upload Tally export")
            led_info = ui.label("").classes("hint")

        result_box = ui.column().classes("w-full")

        def loaded(df, source):
            state.update(ledgers=df, source=source)
            led_info.text = f"{len(df)} ledger balances loaded from {source}."
            success(f"{len(df)} ledger balances read from {source}")
            do_reconcile()

        def do_reconcile():
            if state["ledgers"] is None:
                failure("Ledger balances needed", [{"what": "Step 2", "why": "no Tally balances loaded yet",
                                                    "fix": "Read them from Tally or upload a Tally export."}])
                return
            if not psel.value:
                failure("Choose the person first", [{"what": "Person / PAN", "why": "no person selected",
                                                     "fix": "Choose whose books these are in step 1."}])
                return
            broker = "" if bsel.value == "All brokers" else bsel.value
            with _lock:
                s2 = store()
                res = cost_recon.reconcile(s2, psel.value, asof.value, state["ledgers"], tally.load(s2), broker,
                                           grp.value)
                cost_recon.save_run(s2, psel.value, people.get(psel.value, psel.value), asof.value, broker,
                                    state["source"], res)
            state["res"] = res
            show(res)
            bad = res[res["Status"] != "Matched"]
            if len(bad):
                c = bad["Status"].value_counts()
                failure(f"{len(bad)} line(s) do not match", [{"what": k, "why": f"{v} script(s)", "fix": cost_fix(k)}
                                                             for k, v in c.items()])
            elif len(res):
                success(f"All {len(res)} script(s) match Tally")

        def show(res):
            result_box.clear()
            with result_box:
                with ui.card().classes("card p-4 w-full"):
                    ui.label(f"3. Result: {people.get(psel.value, '')} as on {asof.value}"
                             + ("" if bsel.value == "All brokers" else f" ({bsel.value})")).classes(
                        "font-semibold text-gray-700")
                    c = res["Status"].value_counts()
                    with ui.row().classes("gap-3 flex-wrap"):
                        kpi("Cost as per App", inr(res["Cost as per App"].sum()))
                        kpi("Balance as per Tally", inr(res["Balance as per Tally"].fillna(0).sum()))
                        kpi("Matched", str(c.get("Matched", 0)), color="#2E7D32")
                        for k in ("Difference", "Ledger not found", "Opening holding missing", "Only in Tally"):
                            kpi(k, str(c.get(k, 0)), color="#C62828" if c.get(k) else NAVY)
                    grid(res, rupee=["Cost as per App", "Balance as per Tally", "Difference (Tally - App)"],
                         qty=["Qty as per App", "Shortage qty"], pinned=2, height="420px")
                    with ui.row().classes("gap-3"):
                        def export():
                            p = REPORTS / f"Cost_Reconciliation_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
                            res.to_excel(p, index=False, sheet_name="Cost Reconciliation")
                            deliver([p])
                        ui.button("Open in Excel", icon="grid_on", on_click=export).props("outline")
                        ui.button("Match ledgers to scripts", icon="link", on_click=match_dialog).props("outline")

        def match_dialog():
            res = state["res"]
            if res is None:
                return
            names = sorted(state["ledgers"]["Ledger"].tolist(), key=str.lower)
            todo = res[(res["Status"] != "Matched") & (res["Script"] != "")]
            sels = {}
            hold = {r["isin"] or r["symbol"]: r["key"] for _, r in
                    fifo.holdings(store(), psel.value, asof.value).iterrows()}
            with ui.dialog() as d, ui.card().classes("w-[900px] max-w-[96vw]"):
                ui.label("Match Tally ledgers to scripts").classes("text-lg font-semibold")
                ui.label("Choose the Tally ledger for each script not matched. The choice is remembered for this "
                         "person.").classes("hint")
                with ui.scroll_area().style("height:60vh"):
                    for _, r in todo.iterrows():
                        with ui.row().classes("items-center gap-3 no-wrap"):
                            ui.label(f"{r['Script']}").classes("w-40 font-medium")
                            ui.label(r["Name of Company"] or "").classes("w-64 text-sm text-gray-600")
                            sels[hold.get(r["ISIN"] or r["Script"], r["ISIN"])] = ui.select(
                                {"": "(none)", **{n: n for n in names}}, value=r["Tally Ledger"] or "",
                                with_input=True).props("outlined dense options-dense").classes("w-80")

                def save():
                    for key, sel in sels.items():
                        tally_link.set_map(store(), psel.value, key, sel.value)
                    d.close()
                    success("Ledger matching saved")
                    do_reconcile()
                with ui.row():
                    ui.button("Save and reconcile again", icon="save", on_click=save).props("unelevated color=positive")
                    ui.button("Cancel", on_click=d.close).props("flat")
            d.open()

        ui.separator()
        ui.label("Earlier cost reconciliations (click one to see it again)").classes("font-semibold text-gray-700")
        hist = cost_recon.runs(st)
        if len(hist):
            def open_run(r):
                res = cost_recon.run_result(store(), int(r["_id"]))
                with ui.dialog() as d, ui.card().classes("w-[1200px] max-w-[96vw]"):
                    ui.label(f"{r['Person']} as on {r['As on Date']} ({r['Broker']}), {r['Source']}") \
                        .classes("text-lg font-semibold")
                    grid(res, rupee=["Cost as per App", "Balance as per Tally", "Difference (Tally - App)"],
                         qty=["Qty as per App", "Shortage qty"], pinned=2, height="480px")
                    ui.button("Close", on_click=d.close)
                d.open()
            grid(hist, rupee=["Cost as per App", "Balance as per Tally"], qty=["Scripts", "Matched"], pinned=1,
                 height="240px", on_row=open_run)
        else:
            ui.label("None yet.").classes("hint")


def cost_fix(status: str) -> str:
    return {
        "Difference": "Check the purchase / sale entries in Tally against the contract notes (charges capitalised or "
                      "not, a missing entry, cost of shares sold taken differently from FIFO).",
        "Ledger not found": "Use 'Match ledgers to scripts' to pick the Tally ledger, or create the ledger in Tally.",
        "Opening holding missing": "The app has sales from shares bought before the first contract note, so its cost "
                                   "is incomplete. Add those purchases on Opening Holdings.",
        "Only in Tally": "Tally has a balance but the app holds none: a sale not booked in Tally, or the purchase "
                         "contract note / opening holding is missing in the app.",
    }.get(status, "")


@ui.page("/portal")
def portal_page():
    col = frame("Broker Portal Download", "/portal")
    st = store()
    saved = {r["broker"]: r for r in portal.logins(st)}
    sess = {"s": None, "timer": None, "dead": 0, "fill_until": 0, "busy": False}
    with col:
        ui.label("Download contract notes, ledger, P&L and holding statements from the broker's website. The app "
                 "opens the site in a separate browser window and fills your user id and password; you type the "
                 "OTP / CAPTCHA, log in, and click the downloads you need. Every file downloaded in that window is "
                 "picked up: contract notes are imported at once, the rest are filed by type.").classes("hint")
        if not saved:
            with ui.card().classes("card p-4 w-full").style("border-left:5px solid #E0A526"):
                ui.label("No portal logins saved yet").classes("font-semibold")
                ui.label("Add the broker, user id and password in Settings > Broker web portal logins.").classes("hint")
                ui.button("Open Settings", icon="settings", on_click=lambda: ui.navigate.to("/settings")) \
                    .props("unelevated color=primary")
            return
        with ui.card().classes("card p-4 w-full"):
            with ui.row().classes("items-end gap-4 flex-wrap"):
                bsel = ui.select(sorted(saved), value=sorted(saved)[0], label="Broker").props("outlined dense") \
                    .classes("w-72")
                ui.label().bind_text_from(bsel, "value", lambda b: f"User id: {saved[b]['user_id']}   |   "
                                                                   f"{saved[b]['url']}" if b else "") \
                    .classes("hint")
            with ui.row().classes("gap-3"):
                start_btn = ui.button("Open portal and log in", icon="login", on_click=lambda: start()) \
                    .props("unelevated color=positive size=lg no-caps")
                stop_btn = ui.button("Finish session", icon="stop_circle", on_click=lambda: stop("Session finished")) \
                    .props("outline color=negative size=lg no-caps")
                stop_btn.disable()
            status = ui.label("").classes("text-base font-semibold")
            with ui.expansion("What to download on the portal", icon="help_outline").classes("w-full"):
                ui.label("Contract notes for the period (PDF / ZIP / HTML), Ledger or Fund statement, Profit & Loss "
                         "(tax P&L / realised gains), and the Holdings statement as on date. Choose the period on the "
                         "broker's site, then press its Download buttons. Close nothing: the app watches the "
                         "download folder until you press Finish session.").classes("hint")
        summary = ui.row().classes("gap-3 flex-wrap")
        log = ui.log(max_lines=500).classes("w-full h-72 card").style("font-size:12px")
        files_box = ui.column().classes("w-full")
        counts = {"Contract note": 0, "Ledger": 0, "Profit and Loss": 0, "Holdings": 0, "Tradebook": 0, "Other": 0}
        filed: list = []

        def draw_counts():
            summary.clear()
            with summary:
                for k, v in counts.items():
                    kpi(k if k != "Contract note" else "Contract notes", str(v), color="#2E7D32" if v else NAVY)

        def draw_files():
            files_box.clear()
            if not filed:
                return
            import pandas as pd
            with files_box:
                grid(pd.DataFrame(filed, columns=["Time", "File", "Type", "Result", "Saved in"]), pinned=0,
                     height="260px")
                ui.button("Open download folder", icon="folder_open",
                          on_click=lambda: open_folder(sess["s"].root if sess["s"] else L.portal)) \
                    .props("outline")

        def start():
            b = bsel.value
            try:
                s = portal.Session(store(), DATA, b)
                s.open()
            except Exception as exc:  # noqa: BLE001
                store().log(b or "Portal", "Portal not opened", str(exc))
                failure("The broker portal could not be opened", [{
                    "what": b, "why": str(exc),
                    "fix": "Install or update Microsoft Edge, check the portal address in Settings, or re-enter "
                           "the password there if Windows cannot read the saved one."}])
                return
            sess.update(s=s, dead=0, fill_until=time.time() + 300)
            store().log(b, "Portal session started", s.url)
            status.text = "Browser opened. Filling user id and password... then type the OTP / CAPTCHA and log in."
            status.style("color:#2A7F8F")
            log.push(f"Opened {s.url} for {b}. Downloads go to {s.inbox}")
            start_btn.disable()
            stop_btn.enable()
            draw_counts()
            sess["timer"] = ui.timer(2.0, tick)

        def stop(msg):
            if sess["timer"]:
                sess["timer"].cancel()
                sess["timer"] = None
            s = sess["s"]
            start_btn.enable()
            stop_btn.disable()
            n = sum(counts.values())
            status.text = f"{msg}. {n} file(s) received."
            status.style("color:#1F3A5F")
            if s:
                store().log(s.broker, "Portal session ended", f"{n} file(s): " +
                            ", ".join(f"{k} {v}" for k, v in counts.items() if v))
            if n:
                success(f"{msg}: {n} file(s) received, {counts['Contract note']} contract note file(s) imported")
            else:
                ui.notify(f"{msg}. No files were downloaded.", type="info", position="top")

        async def tick():
            s = sess["s"]
            if not s or sess["busy"]:
                return
            sess["busy"] = True
            try:
                if not s.filled and time.time() < sess["fill_until"]:
                    done = await run.io_bound(s.try_fill)
                    if done:
                        log.push(f"Filled {done}. Now type the OTP / CAPTCHA and press Login on the broker's page.")
                        if s.filled:
                            status.text = "User id and password filled. Type the OTP / CAPTCHA, log in, then download."
                alive = await run.io_bound(s.alive)
                sess["dead"] = 0 if alive else sess["dead"] + 1
                new = await run.io_bound(s.new_files)
                for p in new:
                    await handle(s, p)
                if new:
                    draw_counts()
                    draw_files()
                if sess["dead"] >= 3:
                    await asyncio.sleep(1)
                    for p in await run.io_bound(s.new_files):
                        await handle(s, p)
                    draw_counts()
                    draw_files()
                    stop("The portal window was closed")
            finally:
                sess["busy"] = False

        async def handle(s, p):
            kind = portal.classify(p.name)
            now = datetime.now().strftime("%H:%M:%S")
            log.push(f"Received {p.name} ({kind})")
            if kind == "Contract note":
                pw = passwords.all_passwords(store())

                def work():
                    with _lock:
                        st2 = store()
                        res = import_paths([str(p)], st2, DATA, pw, echo=lambda m: None)
                        reference.fill_master(st2)
                        assumed.refresh(st2)
                        return res
                try:
                    summary_, _ = await run.io_bound(work)
                except Exception as exc:  # noqa: BLE001
                    summary_ = {"notes_saved": 0, "duplicates": 0, "errors": 1, "tradebook": 0,
                                "problems": [{"message": str(exc)}]}
                if summary_["notes_saved"] or summary_["duplicates"] or summary_.get("tradebook"):
                    dest = await run.io_bound(lambda: s.file_away(p, "Contract notes"))
                    result = (f"{summary_['notes_saved']} note(s) imported" +
                              (f", {summary_['duplicates']} already imported" if summary_["duplicates"] else "") +
                              (f", {summary_['tradebook']} tradebook rows" if summary_.get("tradebook") else ""))
                    counts["Contract note"] += 1
                    if summary_["notes_saved"]:
                        success(f"{p.name}: {result}")
                else:
                    why = "; ".join(x.get("message") or x.get("status", "") for x in summary_["problems"])[:300]
                    other = portal.classify(p.stem + ".xlsx")
                    folder = other if other not in ("Contract note", "Other") else "Other"
                    dest = await run.io_bound(lambda: s.file_away(p, folder))
                    counts[folder] += 1
                    result = f"not a contract note / not imported: {why or 'no contract note found'}"
                    if summary_["problems"]:
                        failure(f"{p.name} was not imported", [{
                            "what": p.name, "why": why or "no contract note found",
                            "fix": "If it is a contract note, add its PDF password in Settings and import it from "
                                   "Import Contract Notes; the file is kept in the download folder."}])
            else:
                dest = await run.io_bound(lambda: s.file_away(p, kind))
                counts[kind] += 1
                result = "filed" + (" (use it on Holding Reconciliation)" if kind == "Holdings" else "")
            store().log(p.name, "Portal download", f"{kind}: {result}")
            filed.insert(0, [now, p.name, kind, result, str(dest.parent)])
            log.push(f"  -> {result}")

        draw_counts()


VALUE_MONEY = ["Cost (Rs)", "Market Value (Rs)", "Gain / Loss (Rs)"]
VALUE_COLOUR = ["Gain / Loss (Rs)", "Gain / Loss %", "Day Change %"]


@ui.page("/rates")
def rates_page():
    col = frame("Import Market Rates", "/rates")
    with col:
        ui.label("Market prices to compare the cost of holdings with their market value. Closing prices come from the "
                 "official NSE and BSE bhavcopy for the date chosen (mutual funds: latest AMFI NAV). Live prices come "
                 "from Yahoo Finance for the scripts held. Prices are kept date-wise, so holdings can be valued on any "
                 "date for which prices were imported.").classes("hint")
        with ui.card().classes("card p-4 w-full"):
            with ui.row().classes("items-end gap-4 flex-wrap"):
                d_in = ui.input("Closing prices of", value=prices.last_trading_day().isoformat()) \
                    .props("type=date outlined dense")

                async def closing():
                    from datetime import date as _d
                    async with busy(f"Closing prices of {d_in.value} are being imported..."):
                        res = await run.io_bound(lambda: _locked(lambda st: prices.closing_prices(
                            st, _d.fromisoformat(d_in.value))))
                    n = res["nse"] + res["bse"] + res["amfi"]
                    if n:
                        success(f"Prices of {d_in.value} imported: NSE {res['nse']}, BSE {res['bse']}, "
                                f"mutual fund NAVs {res['amfi']}")
                    if res["errors"]:
                        failure("Some prices could not be imported" if n else "No prices were imported",
                                [{"what": e.split(":", 1)[0], "why": e.split(":", 1)[-1].strip(),
                                  "fix": "Check the internet connection. If the date is a holiday or today before "
                                         "about 7 pm, choose the previous trading day. If the site is busy, try "
                                         "again in a few minutes, or use Live prices."} for e in res["errors"]])
                    draw()
                ui.button("Import closing prices (NSE + BSE + AMFI)", icon="cloud_download", on_click=closing) \
                    .props("unelevated color=primary no-caps")

                async def live():
                    async with busy("Prices are being updated from Yahoo Finance..."):
                        try:
                            res = await run.io_bound(lambda: _locked(lambda st: prices.live_prices(st)))
                        except Exception as exc:  # noqa: BLE001
                            res = {"prices": 0, "not_found": [], "error": str(exc)}
                    if res["prices"]:
                        success(f"{res['prices']} live price(s) from Yahoo Finance")
                    if res.get("error") or not res["prices"]:
                        failure("Live prices not received", [{"what": "Yahoo Finance",
                                                               "why": res.get("error") or "no prices returned",
                                                               "fix": "Check the internet connection and try again, or "
                                                                      "import closing prices."}])
                    elif res["not_found"]:
                        failure(f"{len(res['not_found'])} script(s) not found on Yahoo Finance",
                                [{"what": ", ".join(res["not_found"][:40]), "why": "the symbol is not listed there",
                                  "fix": "Import closing prices: they cover every NSE / BSE script and mutual fund."}])
                    draw()
                ui.button("Get live prices (Yahoo Finance)", icon="bolt", on_click=live) \
                    .props("unelevated color=positive no-caps")
        box = ui.column().classes("w-full")

        def draw():
            box.clear()
            import pandas as pd
            st = store()
            lp = prices.latest(st)
            names = {r["isin"]: (r["symbol"], r["company_name"]) for r in
                     st.query("SELECT isin, symbol, company_name FROM scrip_master")}
            held = {k for k in prices.known_isins(st)}
            lp = lp[lp["isin"].isin(held)]
            df = pd.DataFrame({"ISIN": lp["isin"], "Script": [names.get(i, ("", ""))[0] for i in lp["isin"]],
                               "Name of Company": [names.get(i, ("", ""))[1] for i in lp["isin"]],
                               "Price (Rs)": lp["close"], "Previous Close": lp["prev_close"],
                               "Price Date": lp["price_date"], "Source": lp["source"]})
            with box:
                n_days = st.query("SELECT COUNT(DISTINCT price_date) n FROM price_history")[0]["n"] \
                    if st.query("SELECT name FROM sqlite_master WHERE name='price_history'") else 0
                with ui.row().classes("gap-3"):
                    kpi("Scripts with a price", f"{len(df):,}")
                    kpi("Dates with prices", f"{n_days:,}")
                    kpi("Latest price date", df["Price Date"].max() if len(df) else "-")
                if len(df):
                    grid(df.sort_values("Script"), money=["Price (Rs)", "Previous Close"], pinned=2,
                         height="calc(100vh - 470px)")
                    ui.button("See Investment statement", icon="account_balance_wallet",
                              on_click=lambda: ui.navigate.to("/investment")).props("outline")
                else:
                    ui.label("No prices yet. Import closing prices or get live prices above.").classes("hint")
        prices.ensure(store())
        draw()


@ui.page("/reports/value")
def value_page_old():
    ui.navigate.to("/investment")


@ui.page("/investment")
def investment_page(as_on: str = "", only: str = ""):
    col = frame("Investment", "/investment")
    as_on = as_on or datetime.now().strftime("%Y-%m-%d")
    with col:
        with ui.row().classes("items-end gap-4 flex-wrap"):
            d_in = ui.input("Holdings as on", value=as_on).props("type=date outlined dense")
            ui.button("Show", icon="refresh",
                      on_click=lambda: ui.navigate.to(f"/investment?as_on={d_in.value}")).props("unelevated")
            price_buttons()
            excel_slot = ui.row()
        try:
            df = prices.valuation(store(), current_pan(), as_on)
        except Exception as exc:  # noqa: BLE001
            store().log("Investment", "Valuation failed", str(exc))
            failure("Holdings could not be valued", [{"what": "Investment", "why": str(exc),
                                                      "fix": "See the Import Log."}])
            return
        if not len(df):
            empty_state("No holdings on this date for the person chosen at the top.")
            return
        df["Name"] = [c or s_ for c, s_ in zip(df["Name of Company"], df["Script"])]
        if only == "noprice":
            df = df[df["Market Value (Rs)"].isna()]
            with ui.card().classes("card p-4 w-full").style("border-left:5px solid #E0A526"):
                ui.label(f"{len(df)} script(s) without a market price").classes("font-semibold")
                ui.label("Press Update prices now. If a script still has no price, its symbol is not listed on "
                         "Yahoo Finance under that name: use Closing prices (official NSE / BSE / AMFI lists), or "
                         "correct the symbol on Contract Notes > Scrip Master. Unlisted, delisted and suspended "
                         "scripts have no market price.").classes("hint")
                ui.button("Show all scripts", icon="list", on_click=lambda: ui.navigate.to("/investment")) \
                    .props("flat no-caps")
            if not len(df):
                return
        df = df.sort_values("Name", key=lambda c: c.str.upper()).reset_index(drop=True)
        more = app.storage.general.get("inv_more", False)
        cols = ["Name", "Script", "Quantity", "Avg Cost / Unit", "Cost (Rs)", "Market Price", "Market Value (Rs)",
                "Gain / Loss (Rs)", "Gain / Loss %", "Weight %", "Holding Since"]
        extra = ["Day Change %", "Price Date", "ISIN", "Asset Class", "Industry", "Price Source"]
        if more:
            cols += extra
        if (df["Name"] == df["Script"]).all():          # no company names yet: one name column is enough
            cols.remove("Script")
        view = df[cols]
        priced = view[view["Market Value (Rs)"].notna()]
        cost_all, cost_p = int(view["Cost (Rs)"].sum()), int(priced["Cost (Rs)"].sum())
        mv = int(priced["Market Value (Rs)"].sum())
        gain = mv - cost_p
        good = "#2E7D32" if gain >= 0 else "#C62828"
        with ui.row().classes("items-center gap-6 card px-4 py-2 w-full"):
            for label, value, colr in (("Scripts", f"{len(view)}", NAVY), ("Cost", inr(cost_all), NAVY),
                                       ("Market value", inr(mv) if len(priced) else "-", TEAL),
                                       ("Gain / loss", inr(gain) if len(priced) else "-", good),
                                       ("Gain / loss %", f"{gain * 100 / cost_p:+.2f}%" if cost_p else "-", good)):
                with ui.column().classes("gap-0"):
                    ui.label(label).classes("text-xs text-gray-500 uppercase")
                    ui.label(value).classes("text-lg font-bold").style(f"color:{colr}")
            if len(view) > len(priced):
                ui.label(f"{len(view) - len(priced)} script(s) have no price yet: press Update prices now") \
                    .classes("text-sm").style(f"color:{GOLD}")
        totals = {"Name": f"TOTAL ({len(view)} scripts)", "Cost (Rs)": cost_all,
                  "Market Value (Rs)": mv if len(priced) else None, "Gain / Loss (Rs)": gain if len(priced) else None,
                  "Gain / Loss %": round(gain * 100 / cost_p, 2) if cost_p else None,
                  "Weight %": 100.0}
        with ui.row().classes("items-center w-full"):
            ui.label("All scripts held, alphabetically (gains green, losses red; click a script for its purchases and "
                     "sales; click a column heading to sort)").classes("hint")
            ui.space()
            ui.switch("More details (day change, ISIN, industry, price date)", value=more,
                      on_change=lambda e: (app.storage.general.__setitem__("inv_more", e.value), ui.navigate.reload()))
        grid(view, rupee=VALUE_MONEY, money=["Market Price", "Avg Cost / Unit"], qty=["Quantity"],
             colour=VALUE_COLOUR, pinned=1, height="calc(100vh - 380px)", totals=totals, fit=not more,
             on_row=lambda r: r.get("ISIN") and script_dialog(r.get("ISIN", ""), r.get("Script", "")))

        def export():
            p = REPORTS / f"Investment_{as_on}_{datetime.now():%H%M%S}.xlsx"
            out = df[cols + [c for c in extra if c not in cols]].copy()
            out.loc[len(out)] = {**{c: None for c in out.columns}, **totals}
            write_value_excel(out, p, f"{person_label()} as on {as_on}")
            deliver([p])
        with excel_slot:
            ui.button("Open in Excel", icon="grid_on", on_click=export).props("outline no-caps")


def price_buttons():
    stale = prices.prices_stale(store())

    async def live():
        async with busy("Prices are being updated from Yahoo Finance..."):
            try:
                res = await run.io_bound(lambda: _locked(lambda st: prices.live_prices(st)))
            except Exception as exc:  # noqa: BLE001
                res = {"prices": 0, "not_found": [], "error": str(exc)}
        if res["prices"]:
            success(f"{res['prices']} latest price(s) received from Yahoo Finance")
            ui.navigate.reload()
        else:
            failure("Prices not received", [{"what": "Yahoo Finance", "why": res.get("error") or "no prices returned",
                                             "fix": "Check the internet connection, or use Imports > Import Market "
                                                    "Rates for official closing prices."}])
    b = ui.button("Update prices now", icon="bolt", on_click=live) \
        .props(f"unelevated no-caps color={'positive' if stale else 'primary'}" + (" glossy" if stale else ""))
    if stale:
        b.tooltip("Prices are not from today")
    ui.button("Closing prices", icon="trending_up", on_click=lambda: ui.navigate.to("/rates")).props("flat no-caps")


def investment_block(as_on: str, full: bool = False):
    """Investment boxes and charts; returns the script-wise table (None when nothing is held)."""
    key = current_pan()
    try:
        df = prices.valuation(store(), key, as_on)
    except Exception as exc:  # noqa: BLE001
        store().log("Investment", "Valuation failed", str(exc))
        failure("Holdings could not be valued", [{"what": "Investment", "why": str(exc),
                                                  "fix": "See the Import Log; try again after importing prices."}])
        return None
    if not len(df):
        with ui.card().classes("card p-4 w-full"):
            ui.label("No holdings yet for the person chosen at the top.").classes("font-semibold")
            ui.label("Holdings come from contract notes and Opening Holdings.").classes("hint")
        return None
    priced = df[df["Market Value (Rs)"].notna()]
    cost_all = int(df["Cost (Rs)"].sum())
    cost_p, mv = int(priced["Cost (Rs)"].sum()), int(priced["Market Value (Rs)"].sum())
    gain = mv - cost_p
    day = 0.0
    for _, r in priced.iterrows():
        if r["Day Change %"] is not None and r["Day Change %"] == r["Day Change %"]:
            day += r["Market Value (Rs)"] - r["Market Value (Rs)"] / (1 + r["Day Change %"] / 100)
    good = "#2E7D32" if gain >= 0 else "#C62828"
    with ui.row().classes("gap-3 flex-wrap"):
        tip = "Click for the script-wise details"
        kpi("Invested (cost)", inr(cost_all), f"{len(df)} scripts held", on_click=lambda: ui.navigate.to("/investment"), tip=tip)
        kpi("Market value", inr(mv) if len(priced) else "-",
            f"prices of {priced['Price Date'].max()}" if len(priced) else "update prices", TEAL,
            on_click=lambda: ui.navigate.to("/investment"), tip=tip)
        kpi("Gain / loss", inr(gain) if len(priced) else "-",
            f"on {len(priced)} scripts with a price" if len(priced) < len(df) else "all scripts", good,
            on_click=lambda: ui.navigate.to("/investment"), tip=tip)
        kpi("Gain / loss %", f"{gain * 100 / cost_p:+.2f}%" if cost_p else "-", "on cost", good,
            on_click=lambda: ui.navigate.to("/investment"), tip=tip)
        if full or day:
            kpi("Today's change", inr(day) if day else "-", "since previous close",
                "#2E7D32" if day >= 0 else "#C62828")
        kpi("In gain / in loss", f"{(priced['Gain / Loss (Rs)'] > 0).sum()} / {(priced['Gain / Loss (Rs)'] < 0).sum()}",
            "scripts", NAVY, on_click=lambda: ui.navigate.to("/investment"), tip=tip)
        if len(df) > len(priced):
            kpi("No price yet", str(len(df) - len(priced)), "click to see which scripts", GOLD,
                on_click=lambda: ui.navigate.to("/investment?only=noprice"),
                tip="Shows the scripts without a market price, and how to get it")
    with ui.row().classes("w-full gap-4 no-wrap items-start"):
        with ui.column().style("flex:1;min-width:0").classes("gap-0"):
            gain_chart(priced, "h-96")
        with ui.card().classes("card p-3").style("flex:0 0 320px"):
            ui.label("Where the money is (market value; cost if no price)").classes("font-semibold text-gray-700")
            base = df.assign(v=df["Market Value (Rs)"].fillna(df["Cost (Rs)"])).sort_values("v", ascending=False)
            top = base.head(8)
            data = [{"name": r["Script"], "value": int(r["v"])} for _, r in top.iterrows()]
            if len(base) > 8:
                data.append({"name": "Others", "value": int(base["v"].iloc[8:].sum())})
            rows = {r["Script"]: r for _, r in df.iterrows()}
            ui.echart({"tooltip": {"trigger": "item", "formatter": "{b}: ₹{c} ({d}%)"},
                       "legend": {"bottom": 0, "type": "scroll"},
                       "series": [{"type": "pie", "radius": ["40%", "65%"], "center": ["50%", "45%"],
                                   "label": {"show": False}, "data": data}],
                       "color": [NAVY, TEAL, GOLD, "#D9825B", "#7B8FA6", "#2E7D32", "#8E5BA8", "#B4572E", "#A0AEC0"]},
                      on_point_click=lambda e: rows.get(e.name) is not None and script_dialog(
                          rows[e.name]["ISIN"], e.name)).classes("w-full h-96")
    return df


def gain_chart(priced, height="h-96"):
    """Script-wise gain / loss: figures on the left, the bar on the right (click a row for details)."""
    if not len(priced):
        return
    g = priced.sort_values("Gain / Loss (Rs)", ascending=False)
    g = g if len(g) <= 20 else g.iloc[list(range(10)) + list(range(len(g) - 10, len(g)))]
    neg = float(-g["Gain / Loss (Rs)"].min()) if g["Gain / Loss (Rs)"].min() < 0 else 0.0
    pos = float(g["Gain / Loss (Rs)"].max()) if g["Gain / Loss (Rs)"].max() > 0 else 0.0
    has_neg, has_pos = neg > 0, pos > 0
    # the zero line sits where gains and losses share the width in proportion (at least 15% each side)
    split = (min(max(neg / (neg + pos) * 100, 15), 85) if has_neg and has_pos else (100 if has_neg else 0))
    cols = "minmax(84px,1fr) 92px 100px 96px 70px minmax(200px,3fr)"
    head = "font-size:11px;color:#5B6B7F;text-transform:uppercase;letter-spacing:.03em;text-align:right"
    with ui.card().classes("card p-3 w-full"):
        title = "Gain / loss by script" + (" (top 10 gains and top 10 losses)" if len(priced) > 20 else "")
        ui.label(title + ": click a row for its purchases and sales").classes("font-semibold text-gray-700")
        with ui.element("div").style(f"display:grid;grid-template-columns:{cols};column-gap:10px;row-gap:2px;"
                                     "align-items:center;width:100%"):
            for t, align in (("Script", "left"), ("Cost", "right"), ("Market Value", "right"), ("Gain (Rs)", "right"),
                             ("Gain %", "right"), ("", "left")):
                ui.label(t).style(head.replace("text-align:right", f"text-align:{align}"))
            for _, r in g.iterrows():
                v = float(r["Gain / Loss (Rs)"])
                colr = "#2E7D32" if v >= 0 else "#C62828"
                w = (v / pos * (100 - split)) if v >= 0 and pos else (abs(v) / neg * split if neg else 0)
                left = split if v >= 0 else split - w
                cells = [(r["Script"], "left", "#1F3A5F", 600), (inr(r["Cost (Rs)"]).replace("₹ ", ""), "right", "#334", 400),
                         (inr(r["Market Value (Rs)"]).replace("₹ ", ""), "right", "#334", 400),
                         (inr(v).replace("₹ ", ""), "right", colr, 700),
                         (f"{r['Gain / Loss %']:+.2f}%" if r["Gain / Loss %"] == r["Gain / Loss %"] else "-", "right", colr, 700)]
                isin, script = r["ISIN"], r["Script"]
                for text, align, c, wt in cells:
                    ui.label(str(text)).style(f"text-align:{align};color:{c};font-weight:{wt};font-size:13px;"
                                              "cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis") \
                        .on("click", lambda i=isin, sc=script: script_dialog(i, sc))
                with ui.element("div").style("position:relative;height:16px;cursor:pointer") \
                        .on("click", lambda i=isin, sc=script: script_dialog(i, sc)):
                    if has_neg and has_pos:
                        ui.element("div").style(f"position:absolute;left:{split}%;top:-3px;bottom:-3px;width:1px;"
                                                "background:#CBD5E1")
                    ui.element("div").style(f"position:absolute;left:{left:.2f}%;width:{max(w, .6):.2f}%;top:2px;"
                                            f"bottom:2px;background:{colr};border-radius:2px")


def write_value_excel(df, path, title):
    from openpyxl.styles import Font
    with __import__("pandas").ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Investment", startrow=2)
        ws = xw.sheets["Investment"]
        ws["A1"] = f"Investment: holdings, cost and gain / loss, {title}"
        ws["A1"].font = Font(bold=True, size=13)
        heads = [c.value for c in ws[3]]
        for name in VALUE_COLOUR:
            if name in heads:
                j = heads.index(name) + 1
                for row in ws.iter_rows(min_row=4, min_col=j, max_col=j):
                    c = row[0]
                    if isinstance(c.value, (int, float)):
                        c.font = Font(color="2E7D32" if c.value >= 0 else "C62828", bold=True)
        for colcells in ws.columns:
            ws.column_dimensions[colcells[0].column_letter].width = 16


def drill_dialog(title: str, df, register_url: str = ""):
    """Details behind a chart: opens over the dashboard."""
    with ui.dialog() as d, ui.card().classes("w-[1250px] max-w-[96vw]"):
        with ui.row().classes("items-center w-full"):
            ui.label(title).classes("text-lg font-semibold")
            ui.space()
            ui.label(f"{len(df)} row(s)").classes("hint")
        grid(first(df, SCRIP_LEAD), money=["Avg Gross Rate", "Gross Value", "Total Charges", "Net Rate per Unit (Rs)"],
             rupee=["Net Cost / Proceeds (Rs)"], qty=["Quantity"], pinned=2, height="60vh")
        with ui.row():
            if register_url:
                ui.button("Open in Script Register", icon="open_in_new",
                          on_click=lambda: ui.navigate.to(register_url)).props("outline")
            ui.button("Close", on_click=d.close).props("unelevated")
    d.open()


def script_dialog(isin: str, script: str):
    sf = report.frames(store(), *scope())["scrips"]
    rows = sf[(sf["ISIN"] == isin) | (sf["Script"] == script)] if "ISIN" in sf.columns else sf[sf["Script"] == script]
    drill_dialog(f"{script}: purchases and sales", rows, f"/register?script={script}")


@ui.page("/fmv")
def fmv_page():
    col = frame("Grandfathering FMV", "/fmv")
    with col:
        ui.label("Fair market value on 31-Jan-2018 (for long term gains on equity shares and equity funds bought "
                 "before 1-Feb-2018) and prices on 01-Apr-2001 (for assets bought before 2001). Upload the sheet "
                 "(e.g. FMV_2001Jan01_Winman.xlsx); a new sheet replaces the old one. A copy is kept in "
                 "Master Data as .md. Capital gains (Phase 2) will use these values.").classes("hint")

        async def got(batch, paths):
            p = paths[0]
            try:
                async with busy("The FMV sheet is being imported..."):
                    res = await run.io_bound(lambda: _locked(lambda st: grandfather.import_file(st, p, L.master)))
            except Exception as exc:  # noqa: BLE001
                store().log(p.name, "Grandfathering FMV not imported", str(exc))
                failure("The FMV sheet could not be imported", [{"what": p.name, "why": str(exc),
                                                                  "fix": "Upload the Excel sheet with the market "
                                                                         "quotations of 31-Jan-2018."}])
                return
            keep_copy(p, L.master / "Source files")
            success("Grandfathering values imported: " + ", ".join(f"{v:,} {grandfather.KINDS[k].split(':')[0]}"
                                                                    for k, v in res.items()))
            ui.navigate.reload()
        drop_zone("Grandfathering sheet: drop the Excel file here", ".xlsx,.xls", got, "Upload FMV sheet")
        c = grandfather.counts(store())
        with ui.row().classes("gap-3 flex-wrap"):
            for k, label in (("EQ2018", "Shares, 31-Jan-2018"), ("EOF2018", "Exchange-traded funds, 31-Jan-2018"),
                             ("NAV2018", "Fund NAVs, 31-Jan-2018"), ("P2001", "Prices 01-Apr-2001")):
                kpi(label, f"{c.get(k, 0):,}")
        if not c:
            return
        df = grandfather.held_scripts(store())
        found = (df["Matched by"] != "not found").sum()
        ui.label(f"Scripts in the app and their FMV on 31-Jan-2018: {found} of {len(df)} matched. Click a row to "
                 "choose the right name from the sheet.").classes("font-semibold text-gray-700")

        def pick(r):
            with ui.dialog() as d, ui.card().classes("w-[760px] max-w-[95vw]"):
                ui.label(f"FMV for {r['Script']} ({r['ISIN']})").classes("text-lg font-semibold")
                q = ui.input("Search the sheet", value=(r["Script"] or "")[:6]).props("outlined dense autofocus") \
                    .classes("w-full")
                res_box = ui.column().classes("w-full max-h-96 overflow-auto gap-1")

                def show():
                    res_box.clear()
                    with res_box:
                        for h in grandfather.search(store(), q.value or ""):
                            ui.button(f"{h['name']}  |  Rs {h['price']:,.2f}  |  {h['value_date']} {h['exchange']}",
                                      on_click=lambda h=h: (grandfather.set_map(store(), r["ISIN"], h["id"]), d.close(),
                                                            success(f"{r['Script']}: FMV Rs {h['price']:,.2f} saved"),
                                                            ui.navigate.reload())) \
                                .props("flat no-caps align=left").classes("w-full")
                q.on("keyup", lambda: show())
                show()
                with ui.row():
                    ui.button("No FMV (not listed on 31-Jan-2018)", on_click=lambda: (
                        grandfather.set_map(store(), r["ISIN"], None), d.close(), ui.navigate.reload())).props("flat")
                    ui.button("Close", on_click=d.close)
            d.open()
        grid(df, money=["FMV 31-Jan-2018 (Rs)"], pinned=2, height="calc(100vh - 520px)", on_row=pick)


@ui.page("/log")
def log_page():
    col = frame("Import Log", "/log")
    import pandas as pd
    rows = store().query("SELECT at AS Time, status AS Status, source AS Source, message AS Message "
                         "FROM import_log ORDER BY id DESC")
    with col:
        grid(pd.DataFrame(rows, columns=["Time", "Status", "Source", "Message"]), pinned=0)


# --------------------------------------------------------------------------- import masters

@ui.page("/masters")
def masters_page(auto: str = ""):
    col = frame("Import Market Masters", "/masters")
    s = store()
    q: queue.Queue = queue.Queue()
    with col:
        age = masters.age_days(s)
        if age is None:
            master_banner("The security masters have not been downloaded yet. Click 'Update all masters now' "
                          "(needs internet, about a minute).")
        elif age > MASTER_DAYS:
            master_banner(f"The masters are {age} days old. IPOs, bonus issues, splits, rights and mergers happen "
                          "every week; click 'Update all masters now'.")
        with ui.card().classes("card p-4 w-full"):
            ui.label("Official security lists: names, symbols, ISINs, asset class and industry for equity shares, "
                     "ETFs, mutual funds, debentures, bonds and commercial papers.").classes("font-semibold text-gray-700")
            ui.label("Each download is kept in Data\\Masters with its date. New listings are added; delisted "
                     "securities are kept so old holdings still show their names. After every update the Scrip "
                     "Master, contract notes and holdings are completed automatically (only empty fields).") \
                .classes("hint")
            with ui.row().classes("items-center gap-3"):
                upd = ui.button("Update all masters now", icon="cloud_download") \
                    .props("unelevated color=secondary size=lg no-caps")
                ui.button("Open Master Data folder", icon="folder_open",
                          on_click=lambda: open_folder(L.master)).props("outline") \
                    .tooltip("Opens Data\\Master Data in File Explorer: the downloaded master lists, kept as .md "
                             "files (for reference; the app reads them itself)")
            progress = ui.linear_progress(show_value=False).props("indeterminate color=secondary").classes("w-full")
            progress.visible = False
            log = ui.log(max_lines=300).classes("w-full h-40").style("font-size:12px")
            log.visible = False
        problems_box = ui.column().classes("w-full")

        st = masters.status(s)
        import pandas as pd
        ui.label("Status").classes("font-semibold text-gray-700")
        status_box = ui.column().classes("w-full")

        def draw_status():
            status_box.clear()
            with status_box:
                df = pd.DataFrame(masters.status(store()))[["Master", "Gives", "Last updated", "Records", "Status",
                                                             "Message", "File"]]
                grid(df, qty=["Records"], pinned=1, height="330px")
        draw_status()
        with ui.row().classes("gap-2 flex-wrap"):
            ui.label("If an automatic download fails, open the source page, download the file and drop it below:") \
                .classes("hint")
            for r in st:
                if r["page"]:
                    ui.button(r["Master"], icon="open_in_new", on_click=lambda u=r["page"]: open_url(u)) \
                        .props("outline no-caps dense").classes("text-xs")

        async def got(batch, paths):
            log.visible = True
            res = await run.io_bound(lambda: _locked(lambda st: masters.import_files(st, paths, echo=q.put, folder=L.master)))
            for _ in range(q.qsize()):
                log.push(q.get_nowait())
            bad = [r for r in res if not r["ok"]]
            good = [r for r in res if r["ok"]]
            problems_box.clear()
            if good:
                success(f"{len(good)} master file(s) imported successfully: "
                        f"{sum(r['records'] for r in good):,} securities")
            if bad:
                failure(f"{len(bad)} master file(s) could not be imported",
                        [{"what": r["file"], "why": r["error"], "fix": advice(r["error"])} for r in bad], problems_box)
            draw_status()
        drop_zone("Master files: drop BSE / NSE / Nifty / AMFI or your own lists (CSV, Excel, TXT, JSON)",
                  ".csv,.txt,.xlsx,.xls,.json", got, "Upload master file(s)")

        async def from_folder(p: Path):
            files = [f for f in sorted(p.rglob("*")) if f.suffix.lower() in (".csv", ".txt", ".xlsx", ".xls", ".json")]
            if not files:
                ui.notify("No CSV / Excel / TXT / JSON files in that folder", type="warning")
                return
            await got(None, files)
        ui.button("Import all master files from a folder", icon="folder",
                  on_click=lambda: folder_dialog(PROJECT / "Resources", from_folder)).props("outline")

        async def update_all():
            upd.disable()
            progress.visible = log.visible = True
            log.clear()
            timer = ui.timer(0.3, lambda: [log.push(q.get_nowait()) for _ in range(q.qsize())])
            try:
                async with busy("Market masters are being downloaded and updated (about a minute)..."):
                    res = await run.io_bound(lambda: _locked(lambda st: masters.update_online(st, L.master,
                                                                                               echo=q.put)))
            finally:
                await asyncio.sleep(0.4)
                timer.cancel()
                for _ in range(q.qsize()):
                    log.push(q.get_nowait())
                progress.visible = False
                upd.enable()
            bad = [r for r in res if not r["ok"]]
            good = [r for r in res if r["ok"]]
            problems_box.clear()
            if good:
                success(f"{len(good)} master(s) updated successfully: {sum(r['records'] for r in good):,} securities")
            if bad:
                failure(f"{len(bad)} master(s) could not be updated",
                        [{"what": r["label"], "why": r["error"], "fix": advice(r["error"])} for r in bad], problems_box)
            draw_status()
        upd.on_click(update_all)
        if auto:
            ui.timer(0.8, update_all, once=True)


def _locked(fn):
    with _lock:
        return fn(store())


def master_banner(text: str):
    with ui.card().classes("card p-3 w-full").style("border-left:5px solid #E0A526; background:#FFF9E6"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.icon("update").classes("text-2xl").style(f"color:{GOLD}")
            ui.label(text).classes("text-sm")
            ui.space()
            ui.button("Import Market Masters", on_click=lambda: ui.navigate.to("/masters")).props("flat no-caps")


# --------------------------------------------------------------------------- scrip master

@ui.page("/master")
def master_page():
    col = frame("Scrip Master", "/master")
    s = store()
    mf = report.master_frame(s)
    with col:
        incomplete = mf[(mf["Name of Company"].fillna("") == "") | (mf["Industry"].fillna("") == "")]
        with ui.row().classes("items-center gap-3"):
            ui.label(f"{len(mf)} scrips used in your contract notes and holdings; {len(incomplete)} with missing name "
                     "or industry. Yellow columns can be edited; changes are saved immediately and never overwritten "
                     "by master updates.").classes("hint")
        with ui.row().classes("items-center gap-3"):
            ui.button("Import / update masters", icon="cloud_download",
                      on_click=lambda: ui.navigate.to("/masters")).props("unelevated color=secondary no-caps")

            async def fill_now():
                r = await run.io_bound(lambda: _locked(masters.after))
                ui.notify(f"{r['filled']} scrip(s) completed, {r['resolved']} holding ISIN(s) found, "
                          f"{r['details']} holding detail(s) filled", type="positive", multi_line=True)
                ui.navigate.reload()
            ui.button("Fill missing details now", icon="auto_fix_high", on_click=fill_now).props("outline")

            def export():
                p = REPORTS / f"Scrip_Master_{datetime.now():%Y%m%d_%H%M}.xlsx"
                report.master_frame(store()).to_excel(p, index=False)
                deliver([p])
            ui.button("Open as Excel", icon="grid_on", on_click=export).props("outline")
            only = ui.switch("Show only incomplete", value=False)
        holder = ui.column().classes("w-full")

        def changed(e):
            r = e.args.get("data", {})
            store().upsert_master([{"isin": r.get("ISIN"), "company_name": r.get("Name of Company"),
                                    "industry": r.get("Industry"), "asset_class": r.get("Asset Class"),
                                    "sub_category": r.get("Sub Category"), "face_value": r.get("Face Value")}],
                                  "Edited in app")
            store().log(r.get("ISIN"), "Edited", f"Scrip Master {e.args.get('colId')}")
            ui.notify(f"Saved {r.get('Script')}", type="positive", timeout=1200)

        def draw():
            holder.clear()
            with holder:
                g = grid(incomplete if only.value else mf,
                         editable=["Name of Company", "Industry", "Asset Class", "Sub Category", "Face Value"],
                         pinned=2, height="calc(100vh - 300px)")
                g.on("cellValueChanged", changed)
        only.on_value_change(lambda _: draw())
        draw()


# --------------------------------------------------------------------------- opening holdings

@ui.page("/opening")
def opening_page():
    col = frame("Opening Holdings", "/opening")
    with col:
        ui.label("Shares held before the first contract note. Upload your holdings sheet: your own layout (Name, "
                 "Script, Date of Purchase, Qty, Purchase Value, ISIN, Broker...) or the template. Names are matched "
                 "to PAN, script names to ISIN, missing names are filled from the masters, and purchases already in "
                 "a contract note are skipped. Re-importing is safe. Every problem is listed and written to the "
                 "Import Log.").classes("hint")

        async def dropped(batch, paths):
            tot = {"added": 0, "duplicates": 0, "in_contract_notes": 0, "isin_pending": 0, "sold": 0}
            notes, probs = [], []
            for p in paths:
                try:
                    res = await run.io_bound(lambda p=p: opening.import_opening(p, store()))
                except Exception as exc:  # noqa: BLE001
                    store().log(p.name, "Holdings import failed", str(exc))
                    probs.append({"what": p.name, "why": f"could not read the file ({exc})",
                                  "fix": advice(f"could not read the file {exc}")})
                    continue
                opening.log_result(store(), p.name, res)
                for k in tot:
                    tot[k] += res[k]
                probs += [{"what": f"{p.name} {e.split(':', 1)[0]}", "why": e.split(":", 1)[-1].strip(),
                           "fix": advice(e)} for e in res["errors"]]
                notes += [f"{p.name} {e}" for e in res["skipped"]]
            await run.io_bound(lambda: _locked(masters.after))
            await run.io_bound(lambda: _locked(assumed.refresh))
            problems_box.clear()
            if tot["added"]:
                success(f"{tot['added']} holding lot(s) imported successfully"
                        + (f"; {tot['in_contract_notes']} already in contract notes were skipped"
                           if tot["in_contract_notes"] else ""))
            elif not probs:
                ui.notify("Nothing new to import: these holdings were already imported.", type="info",
                          position="top", timeout=5000)
            if probs:
                failure(f"{len(probs)} row(s) / file(s) could not be imported", probs, problems_box)
            with ui.dialog() as d, ui.card().classes("w-[780px] max-w-[95vw]"):
                ui.label("Opening holdings: import result").classes("text-lg font-semibold")
                with ui.row().classes("gap-3 flex-wrap"):
                    kpi("Lots added", str(tot["added"]), color="#2E7D32")
                    kpi("Already imported", str(tot["duplicates"]), color=GOLD)
                    kpi("In contract notes", str(tot["in_contract_notes"]), "skipped, not counted twice")
                    kpi("ISIN pending", str(tot["isin_pending"]), "update masters or type the ISIN",
                        color="#C62828" if tot["isin_pending"] else NAVY)
                    kpi("Problems", str(len(probs)), color="#C62828" if probs else NAVY)
                if probs:
                    problem_card("Not imported", probs)
                with ui.column().classes("max-h-48 overflow-auto gap-1"):
                    for msg in notes[:300]:
                        ui.label(msg).classes("text-sm text-gray-700")
                ui.label("All of this is also in the Import Log.").classes("hint")
                ui.button("OK", on_click=lambda: (d.close(), ui.navigate.reload()))
            d.open()

        drop_zone("Holdings sheet(s): drop here", ".xlsx,.xls", dropped, "Upload opening holdings file")
        problems_box = ui.column().classes("w-full")
        with ui.card().classes("card p-4 w-full").style("border-left:5px solid #E0A526"):
            n_as = assumed.count(store(), current_pan() if current_pan() and not current_pan().startswith("NAME:") else "")
            ui.label(f"Assumed past purchases: {n_as} lot(s)").classes("font-semibold")
            ui.label("A script sold that was neither bought in a contract note nor shown in these holdings is treated "
                     "as bought in the past. The app adds a lot marked 'Assumed' for the quantity short at that sale, "
                     "dated 3 years before it, at 80% of the sale proceeds, so cost and gains can be worked out. They "
                     "are rebuilt after every import: when you upload the real holdings, they take their place.") \
                .classes("hint")
            with ui.row().classes("items-center gap-3"):
                def toggle(e):
                    with _lock:
                        assumed.set_enabled(store(), e.value)
                        n = assumed.refresh(store())
                    success(f"Assumed purchases {'on' if e.value else 'off'}: {n} lot(s) now")
                    ui.navigate.reload()
                ui.switch("Add assumed purchases automatically", value=assumed.enabled(store()), on_change=toggle)

                def rebuild():
                    with _lock:
                        n = assumed.refresh(store())
                    success(f"{n} assumed purchase lot(s) in place")
                    ui.navigate.reload()
                ui.button("Rebuild now", icon="autorenew", on_click=rebuild).props("outline")
        with ui.row().classes("items-center gap-3"):
            def template():
                p = REPORTS / "Opening_Holdings_Template.xlsx"
                master.opening_template(p)
                deliver([p])
            ui.button("Open blank template in Excel", icon="grid_on", on_click=template).props("outline")

            async def find_isin():
                r = await run.io_bound(lambda: _locked(masters.after))
                ui.notify(f"{r['resolved']} ISIN(s) found, {r['details']} detail(s) filled",
                          type="positive" if r["resolved"] or r["details"] else "info")
                ui.navigate.reload()
            ui.button("Find missing ISINs and names", icon="search", on_click=find_isin).props("outline")
            ui.button("Persons and PAN", icon="people", on_click=lambda: ui.navigate.to("/persons")).props("outline")
            ui.space()
            dbtn = ui.button("Delete selected", icon="delete").props("color=negative outline")

        df = opening.lots(store(), current_pan()).rename(columns={"ID": "_id"})
        if len(df):
            hold = df[~df["Status"].isin(["Sold", "Assumed"])]
            with ui.row().classes("gap-3 flex-wrap"):
                kpi("Holding cost", inr(hold["Total Cost (Rs)"].sum()), f"{len(hold)} lot(s)")
                kpi("ISIN pending", str((df["Status"] == "ISIN pending").sum()), "type the ISIN in the yellow column",
                    color="#C62828" if (df["Status"] == "ISIN pending").any() else NAVY)
                kpi("Names without PAN", str(df.loc[df["PAN"].isna(), "Name"].nunique()), "set on Persons page")
        editable = ["Name", "Broker", "Date of Purchase", "Script", "ISIN", "Name of Company", "Quantity",
                    "Total Cost (Rs)", "Sale Date", "Sale Value (Rs)"]
        g = grid(df, rupee=["Total Cost (Rs)", "Sale Value (Rs)"], qty=QTY_COLS, editable=editable, pinned=2,
                 selectable=True, height="calc(100vh - 560px)")

        def changed(e):
            r, colid = e.args.get("data", {}), e.args.get("colId")
            try:
                opening.update_lot(store(), int(r["_id"]), colid, r.get(colid))
                ui.notify(f"Saved {colid}", type="positive", timeout=1200)
            except (ValueError, TypeError) as exc:
                ui.notify(f"Not saved: {exc}", type="negative")
        g.on("cellValueChanged", changed)

        async def delete_selected():
            rows = await g.get_selected_rows()
            if not rows:
                ui.notify("Tick one or more holdings first", type="warning")
                return

            def yes():
                opening.delete_lots(store(), [int(r["_id"]) for r in rows])
                ui.notify(f"{len(rows)} holding(s) deleted", type="positive")
                ui.navigate.reload()
            confirm(f"Delete {len(rows)} holding lot(s)?",
                    [f"{r['Name']}  {r['Script']}  {r['Date of Purchase']}  qty {r['Quantity']:g}" for r in rows], yes)
        dbtn.on_click(delete_selected)


# --------------------------------------------------------------------------- persons

@ui.page("/persons")
def persons_page():
    import pandas as pd
    col = frame("Persons and PAN", "/persons")
    s = store()
    with col:
        ui.label("Every name found in contract notes and holding sheets. Type the PAN in the yellow column; it is "
                 "applied to all holdings of that name at once. Contract-note clients already carry their PAN.") \
            .classes("hint")
        rows = []
        for c in s.query("SELECT pan, name FROM clients ORDER BY name"):
            rows.append({"Name": c["name"], "PAN": c["pan"], "Source": "Contract notes", "Matched": ""})
        for p in s.query("SELECT name, display_name, pan, how FROM persons ORDER BY display_name"):
            rows.append({"Name": p["display_name"], "PAN": p["pan"] or "", "Source": "Holdings sheet",
                         "Matched": p["how"] or "PAN not set"})
        df = pd.DataFrame(rows, columns=["Name", "PAN", "Source", "Matched"])
        ui.button("Add person / PAN", icon="person_add", on_click=lambda: add_person_dialog()) \
            .props("unelevated color=secondary size=lg no-caps")
        g = grid(df, editable=["PAN"], pinned=1, height="calc(100vh - 320px)")

        def changed(e):
            r = e.args.get("data", {})
            pan = (r.get("PAN") or "").strip().upper()
            if r.get("Source") != "Holdings sheet":
                ui.notify("PAN for contract-note clients comes from the contract note", type="warning")
                return
            if pan and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan):
                failure("PAN not saved", [{"what": r.get("Name"), "why": f"'{pan}' is not a valid PAN",
                                           "fix": advice("pan valid")}])
                return
            persons.set_pan(store(), r.get("Name"), pan)
            success(f"PAN saved for {r.get('Name')}")
        g.on("cellValueChanged", changed)


def add_person_dialog():
    with ui.dialog() as d, ui.card().classes("w-[460px] p-5"):
        ui.label("Add person / PAN").classes("text-xl font-semibold")
        name = ui.input("Name (as you want it to appear)").props("outlined autofocus").classes("w-full")
        pan = ui.input("PAN (10 characters)").props("outlined maxlength=10").classes("w-full")
        err = ui.label().classes("text-sm text-red-700")

        def save():
            n, p = (name.value or "").strip(), (pan.value or "").strip().upper()
            if not n:
                err.text = "Enter the name."
                return
            if p and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", p):
                err.text = f"'{p}' is not a valid PAN: it must look like ABCDE1234F (5 letters, 4 digits, 1 letter)."
                return
            st = store()
            if p:
                other = st.query("SELECT display_name FROM persons WHERE pan=? AND name<>?", (p, persons.key(n))) + \
                    st.query("SELECT name AS display_name FROM clients WHERE pan=?", (p,))
                if other:
                    err.text = f"PAN {p} already belongs to {other[0]['display_name']}."
                    return
            if st.query("SELECT 1 FROM persons WHERE name=?", (persons.key(n),)):
                err.text = f"'{n}' already exists; change its PAN in the table instead."
                return
            persons.set_pan(st, n, p)
            st.log(n, "Person added", f"PAN {p or 'not set'}")
            d.close()
            success(f"{n} added" + (f" with PAN {p}" if p else ""))
            ui.timer(1.5, ui.navigate.reload, once=True)
        with ui.row().classes("w-full justify-end gap-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Add", icon="check", on_click=save).props("unelevated color=positive")
    d.open()


# --------------------------------------------------------------------------- reports

@ui.page("/reports")
def reports_page():
    col = frame("Reports & Export", "/reports")
    out = REPORTS
    with col:
        people = person_options()
        pers = {"value": current_pan()}
        per = {"value": current_period()}
        with ui.card().classes("card p-4 w-full"):
            ui.label("What to export").classes("font-semibold text-gray-700")
            with ui.row().classes("items-end gap-4 flex-wrap"):
                ui.select(people, value=pers["value"] if pers["value"] in people else "", label="Person / PAN",
                          on_change=lambda e: pers.__setitem__("value", e.value or "")) \
                    .props("outlined dense options-dense").classes("w-80")
                popts = period_options()
                if per["value"] not in popts:
                    popts[per["value"]] = periods.label(per["value"])
                psel = ui.select({**popts, "custom": "Custom range..."}, value=per["value"] or "all", label="Period") \
                    .props("outlined dense options-dense").classes("w-64")
                f_in = ui.input("From", value=(periods.bounds(per["value"])[0] or "")).props("type=date outlined dense")
                t_in = ui.input("To", value=(periods.bounds(per["value"])[1] or "")).props("type=date outlined dense")

                def on_period(e):
                    if e.value and e.value != "custom":
                        per["value"] = e.value
                        a, b = periods.bounds(e.value)
                        f_in.value, t_in.value = a or "", b or ""

                def on_dates(_):
                    if f_in.value or t_in.value:
                        per["value"] = f"C:{f_in.value or ''}:{t_in.value or ''}"
                psel.on_value_change(on_period)
                f_in.on_value_change(on_dates)
                t_in.on_value_change(on_dates)
            ui.label(f"Files are saved in {out} and opened automatically.").classes("hint")

        def stamp():
            return datetime.now().strftime("%Y%m%d_%H%M%S")

        async def do(kind):
            key = pers["value"]
            pan = scope_pan(key)
            a, b = periods.bounds(per["value"])
            plabel, perlabel = people.get(key, "All persons"), periods.label(per["value"])
            ui.notify("Preparing...", timeout=800)

            def work():
                with _lock:
                    s = store()
                    fr = report.frames(s, pan, a, b)
                    if kind == "xlsx":
                        p = out / f"Contract_Note_Register_{stamp()}.xlsx"
                        report.build_workbook(s, p, pan, a, b)
                        return [p], len(fr["notes"])
                    if kind == "pdf":
                        p = out / f"Contract_Note_Register_{stamp()}.pdf"
                        return [build_pdf(fr, p, f"{plabel} | {perlabel}")], len(fr["notes"])
                    if kind == "xml":
                        p = out / f"Contract_Note_Register_{stamp()}.xml"
                        return [build_xml(fr, p, plabel, perlabel)], len(fr["notes"])
                    d = out / f"{kind.upper()}_{stamp()}"
                    return report.export_flat(fr, d, kind), len(fr["notes"])
            try:
                files, n = await run.io_bound(work)
            except Exception as exc:  # noqa: BLE001
                store().log(kind.upper(), "Export failed", str(exc))
                fix = ("Close the file if it is open in Excel or a PDF viewer, then export again."
                       if "permission" in str(exc).lower() else "Try again; the Import Log has the details.")
                failure("Export failed", [{"what": kind.upper(), "why": str(exc), "fix": fix}])
                return
            if not n:
                ui.notify("No contract notes for this person and period; the file is empty.", type="warning")
            deliver(files)

        with ui.row().classes("gap-4 flex-wrap"):
            for kind, icon, title, desc in (
                    ("xlsx", "grid_on", "Excel register", "All sheets: notes, script register, daily summary, trades, "
                                                          "reconciliation, scrip master, log"),
                    ("pdf", "picture_as_pdf", "PDF report", "Contract notes and daily summary, landscape A4"),
                    ("xml", "code", "XML file", "Contract notes with charges and script rows nested"),
                    ("csv", "description", "CSV files", "One CSV per table"),
                    ("json", "data_object", "JSON files", "One JSON per table")):
                with ui.card().classes("card p-4 w-72"):
                    with ui.row().classes("items-center"):
                        ui.icon(icon).classes("text-3xl").style(f"color:{TEAL}")
                        ui.label(title).classes("text-lg font-semibold")
                    ui.label(desc).classes("hint h-12")
                    ui.button("Export", icon="download", on_click=lambda k=kind: do(k)).classes("w-full")
        ui.button("Open Reports folder", icon="folder_open", on_click=lambda: open_folder(out)).props("outline")


# --------------------------------------------------------------------------- tally

def tally_cfg():
    return tally.load(store())


def refresh_tally_ledgers(cfg) -> int:
    """Read every ledger (with its group chain) of the Tally company and keep it in the app."""
    df = tally_link.ledgers(cfg.get("company", ""), datetime.now().strftime("%Y-%m-%d"),
                            cfg.get("tally_url") or tally_link.URL, balances=False)
    if not len(df):
        raise ValueError("Tally sent no ledgers: check the company name (or leave it blank for the open company)")
    company = cfg.get("company") or ""
    if not company:
        try:
            names = tally_link.companies(cfg.get("tally_url") or tally_link.URL)
            company = names[0] if len(names) == 1 else ""
        except Exception:  # noqa: BLE001
            company = ""
        if company:
            cfg["company"] = company
            tally.save(store(), cfg)
    return tally_match.save_ledgers(store(), company, df)


def create_ledger_dialog(name: str, group: str, key: str = "", after=None, why: str = ""):
    """Prompt, then create a ledger in Tally (and remember it for the script)."""
    cfg = tally_cfg()
    company = cfg.get("company", "")
    groups = sorted({g for g in tally_match.ledgers(store(), company)["parent"] if g} | {group})
    with ui.dialog() as d, ui.card().classes("w-[620px] max-w-[95vw]"):
        if why:
            ui.label(why).classes("font-semibold").style("color:#C62828")
        ui.label("Create this ledger in Tally?").classes("text-lg font-semibold")
        n_in = ui.input("Ledger name", value=name).props("outlined dense autocomplete=off").classes("w-full")
        g_in = ui.select(groups, value=group, label="Under group", with_input=True).props("outlined dense") \
            .classes("w-full")
        ui.label(f"Company: {company or '(the company open in Tally)'}").classes("hint")

        async def go():
            nm, gp = (n_in.value or "").strip(), g_in.value
            if not nm or not gp:
                failure("Ledger not created", [{"what": "Ledger", "why": "name and group are both needed",
                                                "fix": "Fill both."}])
                return
            try:
                async with busy(f"Ledger '{nm}' is being created in Tally..."):
                    await run.io_bound(lambda: tally_link.create_ledger(nm, gp, company,
                                                                         cfg.get("tally_url") or tally_link.URL))
                    await run.io_bound(lambda: refresh_tally_ledgers(cfg))
            except Exception as exc:  # noqa: BLE001
                store().log(nm, "Tally ledger not created", str(exc))
                failure("Tally did not create the ledger", [{"what": nm, "why": str(exc),
                                                             "fix": "Check that Tally is open with the company, "
                                                                    "and that the name is not already used."}])
                return
            if key:
                tally_match.set_map(store(), company, key, nm)
            store().log(nm, "Tally ledger created", f"under {gp} in {company}")
            d.close()
            success(f"Ledger '{nm}' created in Tally under {gp}")
            if after:
                after(nm)
            else:
                ui.navigate.reload()
        with ui.row().classes("gap-3"):
            ui.button("Yes, create in Tally", icon="add_circle", on_click=go).props("unelevated color=positive")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def bulk_create_dialog(items: list[dict]):
    """Create several missing script ledgers in one go (each in the share ledgers' group)."""
    cfg = tally_cfg()
    company = cfg.get("company", "")
    group = tally_match.share_group(store(), company, cfg.get("investment_group") or "Investments")
    rows = [{**r, "name": tally_match.suggest_name(r["symbol"], r["company"])} for r in items]
    with ui.dialog() as d, ui.card().classes("w-[680px] max-w-[95vw]"):
        ui.label(f"Create {len(rows)} ledger(s) in Tally under '{group}'?").classes("text-lg font-semibold")
        ui.label("Check the names; change any you want (or untick it) before creating.").classes("hint")
        boxes = []
        with ui.scroll_area().style("height:50vh"):
            for r in rows:
                with ui.row().classes("items-center gap-3 no-wrap"):
                    cb = ui.checkbox(value=True)
                    ui.label(r["symbol"]).classes("w-32 font-medium")
                    nm = ui.input(value=r["name"]).props("outlined dense autocomplete=off").classes("w-80")
                    boxes.append((r, cb, nm))

        async def go():
            ok, bad = 0, []
            todo = [(r, nm.value.strip()) for r, cb, nm in boxes if cb.value and nm.value.strip()]
            d.close()
            async with busy(f"{len(todo)} ledger(s) are being created in Tally..."):
                for r, nm in todo:
                    try:
                        await run.io_bound(lambda nm=nm: tally_link.create_ledger(
                            nm, group, company, cfg.get("tally_url") or tally_link.URL))
                        tally_match.set_map(store(), company, r["key"], nm)
                        ok += 1
                    except Exception as exc:  # noqa: BLE001
                        bad.append({"what": nm, "why": str(exc), "fix": "Create it in Tally, or choose another name."})
                try:
                    await run.io_bound(lambda: refresh_tally_ledgers(cfg))
                except Exception:  # noqa: BLE001
                    pass
            store().log(company, "Tally ledgers created", f"{ok} created, {len(bad)} failed")
            if ok:
                success(f"{ok} ledger(s) created in Tally under {group}")
            if bad:
                failure(f"{len(bad)} ledger(s) not created", bad)
            await asyncio.sleep(1.2)
            ui.navigate.reload()
        with ui.row().classes("gap-3"):
            ui.button("Yes, create them in Tally", icon="add_circle", on_click=go).props("unelevated color=positive")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def match_dialog(r: dict):
    """Choose the Tally ledger for a script, or create one."""
    cfg = tally_cfg()
    company = cfg.get("company", "")
    inv = tally_match.investment_ledgers(store(), company, cfg.get("investment_group") or "Investments")
    ranked = sorted(((tally_match.score(l, r["symbol"], r["company"])[0], l) for l in inv), reverse=True)
    opts = {"": "(none)", **{l: f"{l}   ({sc})" for sc, l in ranked}}
    with ui.dialog() as d, ui.card().classes("w-[680px] max-w-[95vw]"):
        ui.label(f"Tally ledger for {r['symbol']}").classes("text-lg font-semibold")
        ui.label(r["company"] or "").classes("hint")
        sel = ui.select(opts, value=r.get("ledger") or "", label="Choose the ledger (best matches first; the number "
                                                                    "is how close the name is)", with_input=True) \
            .props("outlined dense").classes("w-full")

        def save():
            tally_match.set_map(store(), company, r["key"], sel.value or None)
            d.close()
            success(f"{r['symbol']}: {sel.value or 'no ledger'} saved")
            ui.navigate.reload()
        with ui.row().classes("gap-3"):
            ui.button("Save", icon="save", on_click=save).props("unelevated color=positive")
            ui.button("Not in Tally: create a ledger", icon="add_circle", on_click=lambda: (
                d.close(), create_ledger_dialog(tally_match.suggest_name(r["symbol"], r["company"]),
                                                tally_match.share_group(store(), company,
                                                                        cfg.get("investment_group") or "Investments"),
                                                r["key"]))).props("outline")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def tally_connection_card(cfg, on_done):
    with ui.card().classes("card p-4 w-full"):
        ui.label("Tally connection").classes("font-semibold text-gray-700")
        ui.label("Tally Prime must be open with the company, and F1 Help > Settings > Connectivity set to act as Both "
                 "on port 9000.").classes("hint")
        with ui.row().classes("items-end gap-3 flex-wrap"):
            comp = ui.input("Tally company (blank = the one open)", value=cfg.get("company", "")) \
                .props("outlined dense autocomplete=off").classes("w-80")
            url = ui.input("Tally address", value=cfg.get("tally_url") or tally_link.URL).props("outlined dense") \
                .classes("w-56")

            async def check():
                try:
                    async with busy("Checking the connection to Tally..."):
                        names = await run.io_bound(lambda: tally_link.companies(url.value.strip()))
                except Exception as exc:  # noqa: BLE001
                    failure("Tally is not answering", [{"what": url.value, "why": str(exc),
                                                        "fix": "Open Tally Prime and the company; set Connectivity "
                                                               "to act as Both on port 9000."}])
                    return
                if names and not comp.value:
                    comp.value = names[0]
                success("Connected to Tally. Companies open: " + (", ".join(names) or "(none)"))

            async def do_import():
                cfg.update(company=comp.value.strip(), tally_url=url.value.strip())
                tally.save(store(), cfg)
                try:
                    async with busy("Ledger masters are being imported from Tally..."):
                        n = await run.io_bound(lambda: refresh_tally_ledgers(cfg))
                except Exception as exc:  # noqa: BLE001
                    store().log("Tally", "Tally masters not imported", str(exc))
                    failure("Tally masters could not be imported", [{"what": comp.value or "open company",
                                                                     "why": str(exc),
                                                                     "fix": "Open Tally with the company; close any "
                                                                            "report or message open in Tally (Esc), "
                                                                            "then press the button again."}])
                    return
                success(f"{n} ledgers imported from Tally ({cfg.get('company') or 'open company'})")
                on_done()
            ui.button("Check connection", icon="cable", on_click=check).props("outline no-caps")
            ui.button("Import ledgers from Tally", icon="download", on_click=do_import) \
                .props("unelevated color=primary no-caps")


@ui.page("/tally/masters")
def tally_masters_page():
    col = frame("Import Tally Masters", "/tally/masters", show_scope=False)
    cfg = tally_cfg()
    with col:
        ui.label("Brings the ledger names of your Tally company into the app, so every script is posted to its own "
                 "share ledger even when the names differ (e.g. TATATECH = 'Tata Tech', JIOFIN = 'Jio Finance'). "
                 "Import again after you add ledgers in Tally.").classes("hint")
        tally_connection_card(cfg, lambda: ui.navigate.reload())
        company = cfg.get("company", "")
        led = tally_match.ledgers(store(), company)
        if not len(led):
            empty_state("No Tally ledgers in the app yet: press Import ledgers from Tally.")
            return
        grp = cfg.get("investment_group") or "Investments"
        inv = tally_match.investment_ledgers(store(), company, grp)
        m = tally_match.match_all(store(), company, grp)
        missing = m[m["ledger"] == ""]
        with ui.row().classes("gap-3 flex-wrap"):
            kpi("Ledgers in Tally", f"{len(led):,}", company or "open company")
            kpi("Investment ledgers", f"{len(inv)}", f"share ledgers are in '{tally_match.share_group(store(), company, grp)}'")
            kpi("Scripts matched", f"{len(m) - len(missing)} / {len(m)}", "click a row to change", "#2E7D32")
            kpi("Scripts without a ledger", str(len(missing)), "click a row to choose or create",
                "#C62828" if len(missing) else NAVY)
            kpi("Imported", (led["imported_at"].max() or "")[:16].replace("T", " "))
        if len(missing):
            with ui.card().classes("card p-4 w-full").style("border-left:6px solid #C62828"):
                ui.label(f"{len(missing)} script(s) have no ledger in Tally: "
                         + ", ".join(missing["symbol"].head(30))).classes("font-semibold").style("color:#C62828")
                ui.label("Click a red row below to choose the right ledger, or to create it in Tally (it is created "
                         "in the same group as your other share ledgers).").classes("hint")
                miss_items = [{"key": r["key"], "symbol": r["symbol"], "company": r["company"]}
                              for _, r in missing.iterrows()]
                ui.button(f"Create all {len(missing)} missing ledgers in Tally", icon="playlist_add",
                          on_click=lambda: bulk_create_dialog(miss_items)).props("outline color=negative no-caps")
        view = m.assign(Status=["Matched" if l else "No ledger in Tally" for l in m["ledger"]]) \
            .sort_values(["Status", "symbol"], ascending=[False, True])
        view = view.rename(columns={"symbol": "Script", "company": "Name of Company", "ledger": "Tally Ledger",
                                    "score": "Match %", "how": "How matched", "key": "_key"})
        grid(view[["Script", "Name of Company", "Tally Ledger", "Match %", "How matched", "Status", "_key"]],
                 qty=["Match %"], pinned=1, height="calc(100vh - 560px)",
                 on_row=lambda r: match_dialog({"key": r["_key"], "symbol": r["Script"],
                                                "company": r.get("Name of Company") or "",
                                                "ledger": r.get("Tally Ledger") or ""}),
                 row_style="p => p.data && p.data.Status !== 'Matched' ? {color: '#C62828', fontWeight: 600} : null")


@ui.page("/tally")
def tally_page():
    col = frame("Export to Tally", "/tally")
    s = store()
    cfg = tally_cfg()
    company = cfg.get("company", "")
    with col:
        ui.label("Creates one voucher per contract note in Tally: purchases at cost (charges added), sales at FIFO "
                 "cost with the short / long term gain, and the broker's ledger for the net amount. Notes already "
                 "sent are never sent twice. Uses the person and period chosen at the top.").classes("hint")
        tally_connection_card(cfg, lambda: ui.navigate.reload())
        led = tally_match.ledgers(s, company)
        if not len(led):
            with ui.card().classes("card p-4 w-full").style("border-left:5px solid #E0A526"):
                ui.label("First import the ledger names from Tally").classes("font-semibold")
                ui.button("Import Tally Masters", icon="account_tree",
                          on_click=lambda: ui.navigate.to("/tally/masters")).props("unelevated color=primary")
            return
        names = sorted(led["name"], key=str.lower)
        with ui.expansion("Voucher settings: voucher type, gain ledgers and broker ledgers", icon="tune") \
                .classes("w-full card"):
            with ui.grid(columns=3).classes("w-full gap-3 p-2"):
                vt = ui.select(["Journal", "Purchase", "Sales", "Payment", "Receipt"], value=cfg["voucher_type"],
                               label="Voucher type").props("outlined dense")
                grp = ui.input("Group of investment ledgers", value=cfg["investment_group"]).props("outlined dense")
                cap = ui.switch("Add brokerage and levies to cost (else to the charges ledger)",
                                value=cfg["capitalise_charges"])
                stg = ui.select(names + [cfg["gain_ledger_st"]] if cfg["gain_ledger_st"] not in names else names,
                                value=cfg["gain_ledger_st"], label="Short term gain ledger", with_input=True,
                                new_value_mode="add-unique").props("outlined dense")
                ltg = ui.select(names + [cfg["gain_ledger_lt"]] if cfg["gain_ledger_lt"] not in names else names,
                                value=cfg["gain_ledger_lt"], label="Long term gain ledger", with_input=True,
                                new_value_mode="add-unique").props("outlined dense")
                chg = ui.select(names + [cfg["charges_ledger"]] if cfg["charges_ledger"] not in names else names,
                                value=cfg["charges_ledger"], label="Charges ledger (if not added to cost)",
                                with_input=True, new_value_mode="add-unique").props("outlined dense")
            bl = tally_export.broker_ledgers(cfg)
            sels = {}
            ui.label("Broker ledgers in Tally").classes("font-semibold text-gray-700 px-2")
            for b in sorted({r["broker"] for r in s.query("SELECT DISTINCT broker FROM notes")}):
                guess = bl.get(b) or tally_match.best_ledger(s, company, b.split()[0]) or ""
                with ui.row().classes("items-center gap-3 px-2"):
                    ui.label(b).classes("w-64")
                    sels[b] = ui.select({"": "(choose)", **{n: n for n in names}}, value=guess if guess in names else "",
                                        with_input=True).props("outlined dense").classes("w-80")

            def save():
                cfg.update(voucher_type=vt.value, investment_group=grp.value, capitalise_charges=cap.value,
                           gain_ledger_st=stg.value, gain_ledger_lt=ltg.value, charges_ledger=chg.value,
                           broker_ledgers={b: x.value for b, x in sels.items() if x.value})
                tally.save(store(), cfg)
                success("Voucher settings saved")
                ui.navigate.reload()
            ui.button("Save settings", icon="save", on_click=save).props("unelevated color=positive").classes("m-2")
        if not tally_export.broker_ledgers(cfg):          # first time: keep the guesses
            cfg["broker_ledgers"] = {b: x.value for b, x in sels.items() if x.value}
        pan, d_from, d_to = scope()
        include = app.storage.general.get("tally_include_sent", False)
        vouchers = tally_export.plan(s, pan, d_from, d_to, cfg)
        ready = [v for v in vouchers if v["status"] == "Ready"]
        sent = [v for v in vouchers if v["status"].startswith("Exported")]
        bad = [v for v in vouchers if v["status"] == "Problem"]
        with ui.row().classes("gap-3 flex-wrap"):
            kpi("Contract notes", str(len(vouchers)), f"{person_label()} | {periods.label(current_period())}")
            kpi("Ready to send", str(len(ready)), color="#2E7D32")
            kpi("With problems", str(len(bad)), "fix below", "#C62828" if bad else NAVY)
            kpi("Already in Tally", str(len(sent)), color=TEAL)
        # problems, one line per missing thing
        probs = {}
        for v in bad:
            for p in v["problems"]:
                probs.setdefault((p["kind"], p["key"]), p)
        if probs:
            with ui.card().classes("card p-4 w-full").style("border-left:6px solid #C62828"):
                ui.label(f"{len(probs)} thing(s) to fix before these vouchers can go to Tally") \
                    .classes("font-semibold").style("color:#C62828")
                share_grp = tally_match.share_group(s, company, cfg.get("investment_group") or "Investments")
                miss_items = [{"key": k, "symbol": p["symbol"], "company": p.get("company", "")}
                              for (kind, k), p in probs.items() if kind == "script"]
                if len(miss_items) > 1:
                    ui.button(f"Create all {len(miss_items)} missing script ledgers in Tally", icon="playlist_add",
                              on_click=lambda: bulk_create_dialog(miss_items)).props("outline color=negative no-caps")
                with ui.scroll_area().style(f"height:{min(340, 42 * len(probs) + 10)}px; width:100%"):
                    for (kind, key), p in sorted(probs.items(), key=lambda x: x[0]):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("error").style("color:#C62828")
                            ui.label(p["why"]).classes("w-[520px]")
                            if kind == "script":
                                r = {"key": key, "symbol": p["symbol"], "company": p.get("company", ""), "ledger": ""}
                                ui.button("Choose ledger", icon="link", on_click=lambda r=r: match_dialog(r)) \
                                    .props("outline dense no-caps")
                                ui.button("Create in Tally", icon="add_circle", on_click=lambda r=r: create_ledger_dialog(
                                    tally_match.suggest_name(r["symbol"], r["company"]), share_grp, r["key"],
                                    why=f"The ledger for {r['symbol']} is not in Tally.")) \
                                    .props("unelevated dense no-caps color=negative")
                            elif kind == "missing":
                                gp = ("Indirect Incomes" if "Gain" in key else "Indirect Expenses" if "Charge" in key
                                      else "Sundry Creditors")
                                ui.button("Create in Tally", icon="add_circle", on_click=lambda k=key, g=gp:
                                          create_ledger_dialog(k, g, why=f"The ledger '{k}' is not in Tally.")) \
                                    .props("unelevated dense no-caps color=negative")
                            elif kind == "broker":
                                def set_broker(name, b=key):
                                    c2 = tally_cfg()
                                    bl2 = tally_export.broker_ledgers(c2)
                                    bl2[b] = name
                                    c2["broker_ledgers"] = bl2
                                    tally.save(store(), c2)
                                    ui.navigate.reload()
                                ui.button("Create in Tally", icon="add_circle", on_click=lambda k=key, f=set_broker:
                                          create_ledger_dialog(k, "Sundry Creditors", after=f,
                                                               why=f"There is no ledger for broker {k}.")) \
                                    .props("unelevated dense no-caps color=negative")
                                ui.label("or choose it in Voucher settings above").classes("hint")
        show = vouchers if include else [v for v in vouchers if not v["status"].startswith("Exported")]
        with ui.row().classes("items-center gap-3 w-full"):
            ui.label(f"Vouchers ({len(show)})").classes("font-semibold text-gray-700")
            ui.switch("Show notes already sent", value=include,
                      on_change=lambda e: (app.storage.general.__setitem__("tally_include_sent", e.value),
                                           ui.navigate.reload()))
            ui.space()

            async def send():
                todo = [v for v in vouchers if v["status"] == "Ready"]
                if not todo:
                    ui.notify("No vouchers ready to send", type="warning")
                    return
                ok, errs = [], []
                async with busy(f"{len(todo)} voucher(s) are being created in Tally..."):
                    for v in todo:
                        try:
                            res = await run.io_bound(lambda v=v: tally_link.import_vouchers(
                                tally_export.xml([v], company, cfg["voucher_type"]),
                                cfg.get("tally_url") or tally_link.URL))
                        except Exception as exc:  # noqa: BLE001
                            errs.append({"what": f"CN {v['cn_no']}", "why": str(exc),
                                         "fix": "Check that Tally is open with the company."})
                            break
                        if res["created"] and not res["errors"]:
                            ok.append(v["note_id"])
                        else:
                            errs.append({"what": f"CN {v['cn_no']} ({v['date']})",
                                         "why": "; ".join(res["lines"]) or res["raw"][:300],
                                         "fix": "Fix the ledger named in the message (Import Tally Masters), or "
                                                "check that the date is inside the Tally company's period."})
                    tally_export.mark(store(), company, ok, "sent")
                store().log(company, "Vouchers sent to Tally", f"{len(ok)} created, {len(errs)} failed")
                if ok:
                    success(f"{len(ok)} voucher(s) created in Tally ({company or 'open company'})")
                if errs:
                    failure(f"{len(errs)} voucher(s) were not created", errs)
                await asyncio.sleep(1.5)
                ui.navigate.reload()

            def save_xml():
                todo = [v for v in vouchers if v["status"] == "Ready"]
                if not todo:
                    ui.notify("No vouchers ready", type="warning")
                    return
                p = REPORTS / f"Tally_Vouchers_{datetime.now():%Y%m%d_%H%M%S}.xml"
                p.write_text(tally_export.xml(todo, company, cfg["voucher_type"]), encoding="utf-8")
                store().log(p.name, "Tally XML saved", f"{len(todo)} vouchers")
                deliver([p.parent])
                success(f"{len(todo)} voucher(s) saved to {p.name}. In Tally: Gateway > Import > Transactions. "
                        "Mark them as sent after importing.")

            def forget():
                ids = [v["note_id"] for v in sent]
                if not ids:
                    ui.notify("No notes marked as sent in this person / period", type="info")
                    return
                confirm(f"Mark {len(ids)} note(s) as not sent?",
                        ["Do this only if you deleted those vouchers in Tally and want to send them again."],
                        lambda: (tally_export.unmark(store(), company, ids), ui.navigate.reload()), "Mark as not sent")
            ui.button(f"Send {len(ready)} voucher(s) to Tally", icon="send", on_click=send) \
                .props("unelevated color=positive no-caps")
            ui.button("Save as Tally XML file", icon="save_alt", on_click=save_xml).props("outline no-caps")
            ui.button("Mark sent notes as not sent", icon="undo", on_click=forget).props("flat no-caps")
        tb = tally_export.table(show)
        if len(tb):
            grid(tb, rupee=["Debit (Rs)", "Credit (Rs)"], pinned=0, height="calc(100vh - 480px)",
                 row_style="p => p.data && p.data.Ledger && p.data.Ledger.startsWith('??') ? "
                           "{color: '#C62828', fontWeight: 600} : null")
        else:
            empty_state("No contract notes for this person and period.")


# --------------------------------------------------------------------------- settings

@ui.page("/settings")
def settings_page():
    col = frame("Settings", "/settings", show_scope=False)
    with col:
        with ui.card().classes("card p-4 w-full"):
            ui.label("PDF passwords for contract notes").classes("font-semibold")
            ui.label("Enter the broker and the password it uses for its contract notes (often the client code or PAN). "
                     "All saved passwords are tried automatically on every protected contract note; PANs and client "
                     "codes already known from imported notes are tried as well.").classes("hint")
            blist = ["Any broker"] + brokers.names(store())
            blist += [r["broker"] for r in passwords.rows(store()) if r["broker"] and r["broker"] not in blist]
            rows_box = ui.column().classes("gap-2")
            entries: list = []

            def add_row(broker="", pw=""):
                with rows_box:
                    with ui.row().classes("items-center gap-3 no-wrap") as row:
                        b = ui.select(blist, value=broker or None, label="Broker", with_input=True,
                                      new_value_mode="add-unique").props("outlined dense").classes("w-72")
                        p = ui.input("Password", value=pw, password=True, password_toggle_button=True) \
                            .props("autocomplete=new-password outlined dense").classes("w-64")
                        item = (b, p, row)
                        entries.append(item)
                        ui.button(icon="delete", on_click=lambda it=item: (entries.remove(it), it[2].delete())) \
                            .props("flat round color=negative").tooltip("Remove this row")

            for r in passwords.rows(store()):
                add_row(r["broker"], r["password"])
            if not entries:
                add_row()
            with ui.row().classes("gap-3"):
                ui.button("Add another password", icon="add", on_click=lambda: add_row()).props("outline")

                def save_pw():
                    pairs = [(b.value or "", p.value or "") for b, p, _ in entries]
                    missing = [b.value for b, p, _ in entries if b.value and not (p.value or "").strip()]
                    n = passwords.save_all(store(), pairs)
                    for name, _ in pairs:          # a broker typed in the box joins the broker list
                        if name and name != "Any broker" and name not in blist:
                            try:
                                brokers.add(store(), name)
                            except ValueError:
                                pass
                    store().log("Settings", "Passwords saved", f"{n} broker password(s)")
                    if missing:
                        failure("Some rows were not saved", [{"what": m, "why": "the password is empty",
                                                              "fix": "Type the password, or remove the row."}
                                                             for m in missing])
                    success(f"{n} password(s) saved. They will be used for every protected contract note.")
                ui.button("Save passwords", icon="save", on_click=save_pw).props("unelevated color=positive")
        with ui.card().classes("card p-4 w-full"):
            ui.label("Registration, Administrator and users").classes("font-semibold")
            lic, valid = registration.licensee(store())
            reg = registration.load(store())
            ui.label(f"Licensee: {lic or '-'}   |   Valid Upto: {valid or '-'}   |   Administrator: "
                     f"{reg.get('admin_name', '-')} (user id {reg.get('admin_user', '-')})").classes("hint")
            with ui.row().classes("gap-3"):
                ui.button("View or edit registration", icon="badge",
                          on_click=lambda: ui.navigate.to("/registration")).props("outline")
                ui.button("Change Administrator password", icon="key", on_click=lambda: admin_pw_dialog()) \
                    .props("outline")
            ui.label("The Administrator was created at registration and cannot be deleted; only the password can "
                     "be changed. Other users are added, changed or deleted by the Administrator below (sign-in by "
                     "user comes with user roles later).").classes("hint")
            ulist = registration.users(store())
            for u in ulist:
                with ui.row().classes("items-center gap-3"):
                    ui.icon("person").classes("text-gray-500")
                    ui.label(f"{u['name']}  ({u['user_id']})").classes("w-72")
                    ui.label(u["role"]).classes("w-32 text-gray-600")
                    ui.button(icon="edit", on_click=lambda u=u: user_dialog(u)).props("flat round dense") \
                        .tooltip("Change name, role or password")
                    ui.button(icon="delete", on_click=lambda u=u: confirm(
                        f"Delete user {u['name']} ({u['user_id']})?", ["The user will not be able to use the app."],
                        lambda: (registration.delete_user(store(), u["user_id"]), success("User deleted"),
                                 ui.navigate.reload()))).props("flat round dense color=negative")
            if not ulist:
                ui.label("No other users yet.").classes("hint")
            ui.button("Add user", icon="person_add", on_click=lambda: user_dialog(None)).props("outline")
        broker_list_card()
        portal_logins_card()
        with ui.card().classes("card p-4 w-full"):
            ui.label("Locations").classes("font-semibold")
            for k, v in (("Data folder", DATA), ("Database", L.db), ("Master Data", L.master),
                         ("Transaction Data", L.trans), ("Reports", REPORTS), ("Backup", L.backup)):
                with ui.row().classes("items-center gap-2"):
                    ui.label(k).classes("w-36 text-gray-600")
                    ui.label(str(v)).classes("font-mono text-sm")
            ui.button("Open data folder", icon="folder_open", on_click=lambda: open_folder(DATA)).props("outline")
        with ui.card().classes("card p-4 w-full"):
            ui.label("About").classes("font-semibold")
            tess = os.environ.get("CNM_TESSERACT", "")
            ui.label(f"Version {VERSION}. Everything runs on this computer; internet is used only for masters and broker portals. "
                     f"OCR for scanned notes: {'available' if tess and Path(tess).exists() else 'not found'}.") \
                .classes("hint")


def admin_pw_dialog():
    with ui.dialog() as d, ui.card().classes("w-[460px]"):
        ui.label("Change Administrator password").classes("text-lg font-semibold")
        cur = ui.input("Present password", password=True).props("autocomplete=new-password outlined dense") \
            .classes("w-full")
        new = ui.input("New password", password=True, password_toggle_button=True) \
            .props("autocomplete=new-password outlined dense").classes("w-full")
        new2 = ui.input("Confirm new password", password=True).props("autocomplete=new-password outlined dense") \
            .classes("w-full")

        def save():
            try:
                registration.change_admin_password(store(), cur.value or "", new.value or "", new2.value or "")
            except ValueError as exc:
                failure("Password not changed", [{"what": "Administrator password", "why": str(exc),
                                                  "fix": "Correct it and press Save again."}])
                return
            d.close()
            success("Administrator password changed")
        with ui.row():
            ui.button("Save", icon="save", on_click=save).props("unelevated color=positive")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def user_dialog(u):
    new = u is None
    with ui.dialog() as d, ui.card().classes("w-[480px]"):
        ui.label("Add user" if new else f"Change user {u['user_id']}").classes("text-lg font-semibold")
        name = ui.input("Name", value="" if new else u["name"]).props("outlined dense autocomplete=off").classes("w-full")
        uid = ui.input("User id", value="" if new else u["user_id"]).props("outlined dense autocomplete=off") \
            .classes("w-full")
        if not new:
            uid.disable()
        role = ui.select(registration.ROLES, value=registration.ROLES[0] if new else u["role"], label="Role") \
            .props("outlined dense").classes("w-full")
        pw = ui.input("Password" + ("" if new else " (blank = keep)"), password=True, password_toggle_button=True) \
            .props("autocomplete=new-password outlined dense").classes("w-full")

        def save():
            try:
                registration.save_user(store(), uid.value, name.value, role.value, pw.value or None, new)
            except ValueError as exc:
                failure("User not saved", [{"what": uid.value or "(user id)", "why": str(exc),
                                            "fix": "Correct it and press Save again."}])
                return
            d.close()
            success("User saved")
            ui.navigate.reload()
        with ui.row():
            ui.button("Save", icon="save", on_click=save).props("unelevated color=positive")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def broker_list_card():
    """Brokers shown in every drop-down; add any broker that is not in the list."""
    with ui.card().classes("card p-4 w-full"):
        ui.label("Brokers").classes("font-semibold")
        ui.label("These brokers appear in every broker drop-down (PDF passwords, portal logins, reconciliations). "
                 "If your broker is not in the list, type its name and press Add broker. Brokers found in imported "
                 "contract notes are added automatically.").classes("hint")
        st = store()
        user_added = {r["name"] for r in st.query("SELECT name FROM brokers WHERE added_by='user'")}
        with ui.row().classes("gap-1 flex-wrap"):
            for name in brokers.names(st):
                if name in user_added:
                    ui.chip(name, icon="person_add", removable=True, color="amber-2",
                            on_value_change=lambda e, n=name: (brokers.remove(store(), n),
                                                               store().log(n, "Broker removed", "from the broker list"),
                                                               ui.notify(f"{n} removed", type="info"))) \
                        .tooltip("Added by you: click x to remove")
                else:
                    ui.chip(name, color="blue-1")
        with ui.row().classes("items-center gap-3"):
            new = ui.input("New broker name", placeholder="e.g. Choice Equity Broking").props("outlined dense") \
                .classes("w-80")

            def add():
                try:
                    name = brokers.add(store(), new.value)
                except ValueError as exc:
                    failure("Broker not added", [{"what": new.value or "(blank)", "why": str(exc),
                                                  "fix": "Type the full name of the broker as on its contract note."}])
                    return
                success(f"{name} added to the broker list")
                ui.navigate.reload()
            new.on("keydown.enter", add)
            ui.button("Add broker", icon="add_business", on_click=add).props("unelevated color=primary")


def portal_logins_card():
    """User id / password for each broker's web portal (password encrypted with the Windows login)."""
    with ui.card().classes("card p-4 w-full"):
        ui.label("Broker web portal logins").classes("font-semibold")
        ui.label("For Broker Portal Download: the app opens the broker's site, fills the user id and password, and "
                 "waits for you to type the OTP / CAPTCHA. Passwords are encrypted with your Windows login and "
                 "cannot be read on another computer. Leave the password blank to keep the saved one.").classes("hint")
        blist = brokers.names(store())
        saved = portal.logins(store())
        blist += [r["broker"] for r in saved if r["broker"] not in blist]
        box = ui.column().classes("gap-2")
        rows: list = []

        def add_row(broker="", user="", url="", has_pw=False):
            with box:
                with ui.row().classes("items-center gap-3 no-wrap") as line:
                    b = ui.select(blist, value=broker or None, label="Broker", with_input=True) \
                        .props("outlined dense").classes("w-64")
                    u = ui.input("User id / client code", value=user).props("outlined dense autocomplete=off").classes("w-48")
                    p = ui.input("Password", password=True, password_toggle_button=True,
                                 placeholder="saved (blank = keep)" if has_pw else "") \
                        .props("autocomplete=new-password outlined dense").classes("w-56")
                    w = ui.input("Portal address", value=url).props("outlined dense").classes("w-80")
                    b.on_value_change(lambda e, w=w: (not w.value) and setattr(w, "value",
                                                                             portal.DEFAULT_URLS.get(e.value, "")))
                    item = (b, u, p, w, line)
                    rows.append(item)
                    ui.button(icon="delete", on_click=lambda it=item: (rows.remove(it), it[4].delete())) \
                        .props("flat round color=negative").tooltip("Remove this login")

        for r in saved:
            add_row(r["broker"], r["user_id"], r["url"], bool(r["secret"]))
        if not rows:
            add_row()
        with ui.row().classes("gap-3"):
            ui.button("Add portal login", icon="add", on_click=lambda: add_row()).props("outline")

            def save():
                problems = []
                data = []
                for b, u, p, w, _ in rows:
                    if not b.value and not u.value:
                        continue
                    if not b.value or not (u.value or "").strip():
                        problems.append({"what": b.value or "(no broker)", "why": "broker and user id are both needed",
                                         "fix": "Fill both boxes, or remove the row."})
                        continue
                    if not (w.value or "").startswith("http"):
                        problems.append({"what": b.value, "why": "the portal address is missing or not a web address",
                                         "fix": "Paste the address of the broker's login page (starts with https://)."})
                        continue
                    data.append((b.value, u.value, p.value or None, w.value))
                try:
                    n = portal.save_all(store(), data)
                except Exception as exc:  # noqa: BLE001
                    store().log("Settings", "Portal logins not saved", str(exc))
                    failure("Portal logins not saved", [{"what": "Saving", "why": str(exc),
                                                         "fix": "Try again; if it repeats, see the Import Log."}])
                    return
                store().log("Settings", "Portal logins saved", f"{n} login(s)")
                if problems:
                    failure("Some rows were not saved", problems)
                success(f"{n} portal login(s) saved (passwords encrypted)")
            ui.button("Save portal logins", icon="save", on_click=save).props("unelevated color=positive")


@ui.page("/maintenance")
def maintenance_page():
    col = frame("Data Maintenance", "/maintenance", show_scope=False)
    st = store()
    cfg = maintenance.settings(st)
    with col:
        ui.label("Everything the app keeps is in the Data folder next to the exe, in these sub folders. Once a contract "
                 "note or statement is imported, its details are in the database, so the source files can be deleted "
                 "to save space (they are only needed to import again).").classes("hint")
        sz = maintenance.sizes(L)
        with ui.row().classes("gap-3 flex-wrap"):
            for _, r in sz.iterrows():
                kpi(r["Folder"], f"{r['Size (MB)']:,.1f} MB", f"{r['Files']:,} files")
        with ui.row().classes("gap-3"):
            ui.button("Open Data folder", icon="folder_open", on_click=lambda: open_folder(DATA)).props("outline")
            ui.button("Refresh", icon="refresh", on_click=ui.navigate.reload).props("flat")

        # ---- clean up
        with ui.card().classes("card p-4 w-full"):
            ui.label("Free up space").classes("font-semibold")
            with ui.row().classes("items-center gap-4 flex-wrap"):
                def clear_temp():
                    keep = {f.resolve() for f in L.logs.glob("*")} if L.logs.exists() else set()
                    n, freed = maintenance.clear_temp(L, keep={k for k in keep if k.stat().st_mtime > time.time() - 86400})
                    store().log("Temporary Data", "Temporary files deleted", f"{n} files, {freed / 2 ** 20:.1f} MB")
                    success(f"{n} temporary file(s) deleted, {freed / 2 ** 20:.1f} MB freed")
                    ui.navigate.reload()
                ui.button("Delete temporary files", icon="cleaning_services", on_click=clear_temp) \
                    .props("unelevated color=primary").tooltip("Uploads in progress and old logs. Always safe.")
            ui.separator()
            ui.label("Delete imported source files (the tabulated data stays in the app)").classes("text-gray-700")
            checks = {k: ui.checkbox(k, value=k == "Contract note files") for k in maintenance.SOURCE_KINDS}
            with ui.row().classes("items-end gap-3"):
                before = ui.input("Only files saved before (blank = all)", value="").props("type=date outlined dense") \
                    .classes("w-64")

                def ask_sources():
                    kinds = [k for k, c in checks.items() if c.value]
                    if not kinds:
                        failure("Nothing chosen", [{"what": "Source files", "why": "no type of file is ticked",
                                                    "fix": "Tick the files to delete."}])
                        return

                    def go():
                        n, freed = maintenance.delete_sources(L, kinds, before.value or None)
                        store().log("Transaction Data", "Source files deleted",
                                    f"{', '.join(kinds)}: {n} files, {freed / 2 ** 20:.1f} MB"
                                    + (f", before {before.value}" if before.value else ""))
                        success(f"{n} file(s) deleted, {freed / 2 ** 20:.1f} MB freed")
                        ui.navigate.reload()
                    confirm("Delete these source files?",
                            [f"- {k}" for k in kinds] + [
                                f"Saved before {before.value}" if before.value else "All of them",
                                "", "The imported data stays in the app. A deleted contract note file cannot be "
                                    "imported again unless you have the file elsewhere."], go, "Delete files")
                ui.button("Delete chosen source files", icon="delete_sweep", on_click=ask_sources) \
                    .props("unelevated color=negative")

                def ask_reports():
                    def go():
                        n, freed = maintenance.delete_reports(L, before.value or None)
                        success(f"{n} report file(s) deleted, {freed / 2 ** 20:.1f} MB freed")
                        ui.navigate.reload()
                    confirm("Delete report files?", ["Reports can be created again at any time."], go, "Delete reports")
                ui.button("Delete old reports", icon="delete", on_click=ask_reports).props("outline color=negative")

            def do_compact():
                with _lock:
                    maintenance.compact(store())
                success("Database compacted")
                ui.navigate.reload()
            ui.button("Compact database", icon="compress", on_click=do_compact).props("flat") \
                .tooltip("Reclaims space after deleting contract notes")

        # ---- backups
        with ui.card().classes("card p-4 w-full"):
            ui.label("Backup").classes("font-semibold")
            lb = maintenance.last_backup(L)
            ui.label(f"Backups are zip files in Data\\Backup. Last backup: "
                     f"{lb.strftime('%d %b %Y %H:%M') if lb else 'none yet'}.").classes("hint")
            with ui.row().classes("items-end gap-4 flex-wrap"):
                auto = ui.switch("Automatic backup", value=cfg["auto_backup"])
                every = ui.number("Every (days)", value=cfg["every_days"], min=1, max=90, step=1, format="%d") \
                    .props("outlined dense").classes("w-32")
                keep = ui.number("Keep backups for (years)", value=cfg["keep_years"], min=0.25, max=20, step=0.5) \
                    .props("outlined dense").classes("w-48")
                inc_m = ui.checkbox("Include Master Data", value=cfg["include_masters"])
                inc_t = ui.checkbox("Include Transaction Data (source files)", value=cfg["include_transactions"])

                def save_cfg():
                    maintenance.save_settings(store(), {"auto_backup": auto.value, "every_days": int(every.value or 7),
                                                        "keep_years": float(keep.value or 2),
                                                        "include_masters": inc_m.value,
                                                        "include_transactions": inc_t.value})
                    success("Backup settings saved")
                ui.button("Save settings", icon="save", on_click=save_cfg).props("outline")

            async def do_backup():
                try:
                    async with busy("Backup is being made..."):
                        out = await run.io_bound(lambda: _locked(lambda s2: maintenance.backup(s2, L)))
                except Exception as exc:  # noqa: BLE001
                    store().log("Backup", "Backup failed", str(exc))
                    failure("Backup failed", [{"what": "Backup", "why": str(exc),
                                               "fix": "Check that the disk has free space and try again."}])
                    return
                success(f"Backup created: {out.name} ({out.stat().st_size / 2 ** 20:.1f} MB)")
                ui.navigate.reload()
            ui.button("Back up now", icon="backup", on_click=do_backup).props("unelevated color=positive size=lg")
            bl = maintenance.backups(L)
            if bl:
                for b in bl[:30]:
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("inventory").classes("text-gray-500")
                        ui.label(b.name).classes("font-mono text-sm w-96")
                        ui.label(f"{b.stat().st_size / 2 ** 20:.1f} MB").classes("text-sm w-20")

                        def ask_restore(b=b):
                            async def go():
                                try:
                                    async with busy(f"Data is being restored from {b.name}..."):
                                        safety = await run.io_bound(
                                            lambda: _locked(lambda s2: maintenance.restore(s2, L, b)))
                                except Exception as exc:  # noqa: BLE001
                                    store().log(b.name, "Restore failed", str(exc))
                                    failure("Restore failed", [{"what": b.name, "why": str(exc),
                                                                "fix": "Choose another backup."}])
                                    return
                                success(f"Data restored from {b.name}. Your previous data was saved as {safety.name}.")
                                ui.navigate.reload()
                            confirm(f"Restore {b.name}?", [
                                "All data in the app will be replaced by this backup.",
                                "A backup of the present data is made first, so this can be undone."], go, "Restore")
                        ui.button("Restore", icon="restore", on_click=ask_restore).props("flat dense color=primary")
            else:
                ui.label("No backups yet.").classes("hint")

        with ui.card().classes("card p-4 w-full"):
            ui.label("CSV copy of each person's data").classes("font-semibold")
            ui.label("Client Data\\<PAN>_<name> has contract notes, scrip lines, trades and opening holdings as CSV "
                     "files, refreshed after every import and backup.").classes("hint")

            async def csv_now():
                n = await run.io_bound(lambda: _locked(lambda s2: maintenance.write_csv(s2, L)))
                success(f"CSV files written for {n} person(s)")
            ui.button("Write CSV copies now", icon="table_view", on_click=csv_now).props("outline")


@ui.page("/delete")
def delete_page():
    col = frame("Delete Data", "/delete", show_scope=False)
    st = store()
    people = {p["key"]: p["label"] for p in persons.all_people(st) if not p["key"].startswith("NAME:")}
    state = {"undo": None}
    with col:
        with ui.card().classes("card p-4 w-full").style("border-left:6px solid #C62828"):
            ui.label("Delete client data: contract notes, script lines, trades and (if you tick it) opening holdings")\
                .classes("font-semibold").style("color:#C62828")
            ui.label("Masters, market prices, settings, brokers, passwords and registration are never deleted. A "
                     "backup is always made first, so you can undo a deletion with one click (or later from Data "
                     "Maintenance > Backup).").classes("hint")
            mode = ui.radio({"fy": "One PAN, one financial year", "pan": "One PAN, all years",
                             "all": "All PANs (all client data)"}, value="fy").props("inline color=negative")
            with ui.row().classes("items-end gap-4 flex-wrap"):
                psel = ui.select(people, value=next(iter(people), None), label="PAN / person") \
                    .props("outlined dense").classes("w-96")
                fsel = ui.select([], label="Financial year").props("outlined dense").classes("w-40")
            opening_cb = ui.checkbox("Also delete opening holdings of this PAN / all PANs", value=False)
            files_cb = ui.checkbox("Also delete the stored contract note files (Transaction Data)", value=False)
            info = ui.column().classes("gap-1")

            def label():
                if mode.value == "all":
                    return "ALL PANs (all client data)"
                who = people.get(psel.value, psel.value or "")
                return f"{who} for {fsel.value}" if mode.value == "fy" else f"{who} (all years)"

            def refresh():
                fsel.set_visibility(mode.value == "fy")
                psel.set_visibility(mode.value != "all")
                ys = deletion.years(store(), psel.value or "") if psel.value else []
                fsel.options = ys
                if fsel.value not in ys:
                    fsel.value = ys[0] if ys else None
                fsel.update()
                info.clear()
                pan = "" if mode.value == "all" else (psel.value or "")
                fy = fsel.value if mode.value == "fy" else ""
                c = deletion.preview(store(), pan, fy or "", opening_cb.value)
                with info:
                    ui.label(f"Will be deleted for {label()}:").classes("font-semibold")
                    ui.label(", ".join(f"{k}: {v:,}" for k, v in c.items())).classes("text-sm")
            for el in (mode, psel, fsel, opening_cb):
                el.on_value_change(lambda e: refresh())
            refresh()

            def ask():
                pan = "" if mode.value == "all" else (psel.value or "")
                fy = fsel.value if mode.value == "fy" else ""
                if mode.value != "all" and not pan:
                    failure("Choose the PAN first", [{"what": "PAN", "why": "none chosen", "fix": "Choose it above."}])
                    return
                if mode.value == "fy" and not fy:
                    failure("Choose the year", [{"what": "Financial year", "why": "none chosen",
                                                 "fix": "Choose the year above."}])
                    return
                c = deletion.preview(store(), pan, fy, opening_cb.value)
                with ui.dialog().props("persistent") as d, ui.card().classes("w-[640px] max-w-[95vw]") \
                        .style("border:3px solid #C62828"):
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        ui.icon("warning").classes("text-5xl").style("color:#C62828")
                        ui.label(f"DATA OF {label().upper()} WILL BE DELETED.").classes("cnm-blink text-xl")
                    ui.label("ARE YOU SURE?").classes("cnm-blink text-2xl")
                    for k, v in c.items():
                        ui.label(f"{k}: {v:,}").classes("text-base font-semibold")
                    if files_cb.value:
                        ui.label("The stored contract note files will also be deleted.").classes("font-semibold")
                    ui.label("A backup is made first; you can undo this from the next screen or from Data "
                             "Maintenance > Backup.").classes("hint")

                    async def go():
                        d.close()
                        async with busy(f"Backup is being made and data of {label()} deleted..."):
                            res = await run.io_bound(lambda: _locked(lambda s2: deletion.delete(
                                s2, DATA, pan, fy, opening_cb.value, files_cb.value, label())))
                            await run.io_bound(lambda: _locked(lambda s2: (assumed.refresh(s2),
                                                                           maintenance.write_csv(s2, L))))
                        state["undo"] = res["backup"]
                        success(f"Data of {label()} deleted. Backup kept: {res['backup'].name}")
                        draw_undo()
                        refresh()
                    with ui.row().classes("w-full justify-end gap-3"):
                        ui.button("Cancel (keep the data)", on_click=d.close).props("unelevated color=primary")
                        ui.button("Yes, delete", icon="delete_forever", on_click=go) \
                            .props("unelevated color=negative size=lg")
                d.open()
            ui.button("Delete", icon="delete_forever", on_click=ask) \
                .props("unelevated color=negative size=lg").classes("font-bold")
        undo_box = ui.column().classes("w-full")

        def draw_undo():
            undo_box.clear()
            b = state["undo"]
            if not b:
                return
            with undo_box, ui.card().classes("card p-4 w-full").style("border-left:6px solid #2E7D32"):
                ui.label("Changed your mind?").classes("font-semibold")
                ui.label(f"The data as it was just before deleting is in {b.name}.").classes("hint")

                async def undo():
                    async with busy("The deleted data is being brought back from the backup..."):
                        await run.io_bound(lambda: _locked(lambda s2: maintenance.restore(s2, L, b)))
                    state["undo"] = None
                    success("Deleted data brought back from the backup")
                    draw_undo()
                    refresh()
                ui.button("Undo: bring the deleted data back", icon="restore", on_click=undo) \
                    .props("unelevated color=positive size=lg")


def startup_tasks():
    """Runs once when the app starts: finish the folder move, convert old masters, weekly backup."""
    try:
        with _lock:
            st = store()
            if MIGRATED:
                st.log("Data folder", "Folders reorganised", "; ".join(MIGRATED))
                old = str(DATA / "clients")
                st.db.execute("UPDATE clients SET folder=REPLACE(folder, ?, ?)", (old, str(L.notes)))
                st.db.commit()
            todo = L.master / "_to_convert"
            if todo.exists():
                for f in sorted(todo.iterdir()):
                    try:
                        reference.to_markdown(f, L.master)
                    except Exception as exc:  # noqa: BLE001
                        st.log(f.name, "Old master not converted", str(exc))
                        dpaths._move(f, L.master / f.name)
                try:
                    todo.rmdir()
                except OSError:
                    pass
            assumed.refresh(st)
            if maintenance.due(st, L):
                maintenance.backup(st, L)
            else:
                maintenance.prune(st, L)
        st = store()                         # outside the lock: the internet may be slow
        if prices.prices_stale(st):
            try:
                prices.live_prices(st, echo=lambda m: None)
            except Exception as exc:  # noqa: BLE001
                st.log("Yahoo Finance", "Daily price update failed", str(exc))
    except Exception as exc:  # noqa: BLE001 - never stop the app for housekeeping
        try:
            store().log("Start-up", "Housekeeping failed", str(exc))
        except Exception:  # noqa: BLE001
            pass


app.on_startup(lambda: threading.Thread(target=startup_tasks, daemon=True).start())


# --------------------------------------------------------------------------- lifecycle

_live = {"n": 0}


def _connected():
    _live["n"] += 1


async def _disconnected():
    _live["n"] -= 1
    await asyncio.sleep(15)          # page changes reconnect within a second
    if _live["n"] <= 0 and os.environ.get("CNM_AUTOCLOSE", "1") == "1":
        app.shutdown()


app.on_connect(_connected)
app.on_disconnect(_disconnected)
