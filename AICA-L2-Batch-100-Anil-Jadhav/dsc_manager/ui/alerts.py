"""Expiry Alerts: certificate validity, tracked separately from custody."""
import tkinter as tk
from tkinter import ttk

from .. import dates, whatsapp
from ..database import EXPIRY_FILTERS
from .base import Screen, legend
from .dialogs import CertHistoryDialog, CertificateDialog
from .widgets import ClientPicker, DataTable, live_search


def expiry_tag(r):
    d = r["days"]
    if r["admin_status"] in ("Revoked", "Inactive") or r.get("token_status") == "Inactive":
        return "cancelled"
    if d is None:
        return "grey"
    if r["expiry_status"] == "Expired":
        return "red"
    if d <= 7:
        return "orange"
    if d <= 30:
        return "yellow"
    return "green"


class AlertsScreen(Screen):
    title = "Expiry Alerts"
    show_firm = True
    subtitle = "Certificate validity of every DSC token (custody shown separately)"

    def build(self, body):
        self.asof = ttk.Label(self.head, style="Muted.TLabel")
        self.asof.pack(side="right")
        self.flt = tk.StringVar(value="30")
        radios = ttk.Frame(body, style="Screen.TFrame")
        radios.pack(fill="x", pady=(0, 6))
        ttk.Label(radios, text="Show:").pack(side="left", padx=(0, 6))
        self.radio_buttons = {}
        for key in ("7", "15", "30", "expired", "today", "unknown", "renewal", "beyond", "all"):
            rb = ttk.Radiobutton(radios, text=EXPIRY_FILTERS[key], value=key, variable=self.flt,
                                 command=self.refresh)
            rb.pack(side="left", padx=(0, 10))
            self.radio_buttons[key] = rb

        bar = ttk.Frame(body, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Client").pack(side="left")
        self.client = ClientPicker(bar, include_all=True, width=30)
        self.client.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Custody").pack(side="left")
        self.custody = ttk.Combobox(bar, state="readonly", width=14, values=["All", "In Custody", "Returned"])
        self.custody.set("All")
        self.custody.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Holder / client name:").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.search, width=20)
        e.pack(side="left", padx=(2, 8))
        e.bind("<Return>", lambda ev: self.refresh())
        live_search(e, self.refresh)
        ttk.Button(bar, text="Apply", style="Accent.TButton", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Clear Filters", command=self._clear).pack(side="left", padx=4)
        ttk.Button(bar, text="⟳ Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Export to Excel", command=self._export).pack(side="right")
        self.count = ttk.Label(bar, style="Muted.TLabel")
        self.count.pack(side="right", padx=10)

        acts = ttk.Frame(body, style="Screen.TFrame")
        acts.pack(fill="x", pady=(0, 6))
        ttk.Button(acts, text="Update Certificate / Follow-up", command=lambda: self._cert("edit")).pack(side="left")
        ttk.Button(acts, text="Record Renewal (new certificate)", command=lambda: self._cert("renew")).pack(
            side="left", padx=6)
        ttk.Button(acts, text="Certificate History", command=self._history).pack(side="left")
        ttk.Button(acts, text="WhatsApp Reminder to Client", command=self._remind).pack(side="left", padx=(18, 0))

        self.table = DataTable(body, [
            ("client_code", "Client", 65), ("holder_name", "DSC Holder Name", 170),
            ("token_serial", "Token Serial", 120), ("cert_serial", "Certificate Serial", 130),
            ("expiry_date", "Expiry", 140, "datetime"), ("days_text", "Days Remaining / Overdue", 190),
            ("expiry_status", "Expiry Status", 160), ("admin_status", "Renewal Status", 125),
            ("custody", "Physical Custody", 105), ("with_label", "Currently With", 170),
            ("issuer", "Certifying Authority", 170),
            ("followup_text", "Remarks / Follow-up", 220),
        ], height=18, on_double=lambda r: self._cert("edit"), empty_text="No certificates in this list - all clear.",
            menu=lambda r: self.token_menu(r, [("Update Certificate / Follow-up", lambda: self._cert("edit")),
                                               ("Record Renewal", lambda: self._cert("renew")),
                                               ("WhatsApp Reminder to Client", self._remind)]))
        self.table.pack(fill="both", expand=True)
        legend(body, [("red", "Expired"), ("orange", "Expires within 7 days"), ("yellow", "Within 8-30 days"),
                      ("green", "Valid beyond 30 days"), ("grey", "Expiry unknown")]).pack(anchor="w", pady=(6, 0))
        ttk.Label(body, style="Muted.TLabel", text=(
            "Expiry is checked to the minute: a certificate expiring at 11:00 AM shows Expired from 11:00 AM. "
            "Without a recorded time, expiry is taken as 12:00 AM. The 7/15/30-day lists overlap; "
            "Revoked/Inactive certificates show only under 'All tokens'.")
        ).pack(anchor="w")

    def reset_filters(self):
        self.client.set_id(None)
        self.custody.set("All")
        self.search.set("")
        self.flt.set("30")

    def _clear(self):
        flt = self.flt.get()   # the Clear button keeps the chosen list
        self.reset_filters()
        self.flt.set(flt)
        self.refresh()

    def on_show(self, flt=None, **kw):
        if flt in EXPIRY_FILTERS:
            self.flt.set(flt)
        self.client.load(self.db.list_clients())
        self.refresh()

    def refresh(self):
        self.asof.configure(text=f"Calculated as on {dates.to_display_dt(dates.now_iso())}")
        f = {"client_id": self.client.get_id(), "search": self.search.get(),
             "custody": None if self.custody.get() == "All" else self.custody.get()}
        rows = self.db.expiry_alerts(self.flt.get(), f)
        self.table.set_rows(rows, expiry_tag)
        self.count.configure(text=f"{len(rows)} token(s) - {EXPIRY_FILTERS[self.flt.get()]}")

    def _selected(self):
        row = self.table.selected()
        if not row:
            self.error("Please select a token in the list first.", "Nothing selected")
        return row

    def _cert(self, mode):
        row = self._selected()
        if row and CertificateDialog(self, self.db, row["token_id"], mode).show():
            self.refresh()
            self.app.refresh_dashboard()

    def _remind(self):
        row = self._selected()
        if row:
            self.send_whatsapp(whatsapp.for_expiry(self.db, row["token_id"]))

    def _history(self):
        row = self._selected()
        if row:
            CertHistoryDialog(self, self.db, row["token_id"]).show()

    def _export(self):
        self.table.export_csv(f"DSC_Expiry_Alerts_{EXPIRY_FILTERS[self.flt.get()].replace(' ', '_')}")
