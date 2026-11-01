"""Reports: Inward Register, Outward Register and Custody Register (with the
'DSC Awaited from Clients' view). The register panel is also embedded in the
DSC Inward and DSC Outward screens."""
import tkinter as tk
from tkinter import ttk

from ..database import PURPOSES
from .base import Screen, legend
from .dashboard import custody_tag
from .dialogs import ExpectedDialog, TokenHistoryDialog
from .movements import CustodyActions
from .widgets import ClientPicker, DataTable, DateEntry, ask_text, live_search

ALL_STAFF = "(All staff)"
ALL_PURPOSES = "(All purposes)"
ALL_PEOPLE = "(Everyone)"
WITH_ANYONE = "(Anyone)"
WITH_GROUPS = {"Custodian": ("custodian", None), "All staff": ("staff", None),
               "All consultants": ("consultant", None), "Overdue back to custodian": ("internal_overdue", None)}

INWARD_COLUMNS = [
    ("inward_id", "Inward ID", 65, "num"), ("inward_date", "Inward Date", 85, "date"),
    ("client_code", "Client", 65), ("holder_name", "DSC Holder Name", 170), ("token_serial", "Token Serial", 120),
    ("cert_serial", "Certificate Serial", 130), ("expiry_date", "Cert Expiry", 140, "datetime"),
    ("purpose", "Purpose", 105), ("received_from", "Received From", 130),
    ("received_by", "Received By (Custodian)", 150),
    ("expected_return_date", "Expected Return", 95, "date"), ("custody", "Status", 140), ("remarks", "Remarks", 180),
]
OUTWARD_COLUMNS = [
    ("outward_id", "Outward ID", 70, "num"), ("outward_date", "Outward Date", 90, "date"),
    ("client_code", "Client", 65), ("holder_name", "DSC Holder Name", 170), ("token_serial", "Token Serial", 120),
    ("purpose", "Purpose", 105), ("returned_to", "Returned To", 140), ("returned_by", "Returned By", 130),
    ("returned_via", "Returned Via", 170), ("inward_id", "Inward ID", 65, "num"), ("inward_date", "Inward Date", 85, "date"),
    ("status_text", "Status", 120), ("remarks", "Remarks", 180),
]


def staff_combo(parent, db, all_label=ALL_STAFF, width=18, names=None):
    cb = ttk.Combobox(parent, state="readonly", width=width)
    cb.reload = lambda: cb.configure(values=[all_label] + (names or db.list_staff)())
    cb.reload()
    cb.set(all_label)
    return cb


def register_tag(r):
    status = r.get("status")
    if status == "Cancelled":
        return "cancelled"
    if status == "Superseded":
        return "grey"
    return None


class RegisterPanel(ttk.Frame):
    """Filterable inward or outward register with CSV export."""

    def __init__(self, parent, screen, kind, extra_buttons=(), height=16):
        super().__init__(parent, style="Screen.TFrame")
        self.screen, self.kind = screen, kind
        db = screen.db
        bar = ttk.Frame(self, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="From").pack(side="left")
        self.from_d = DateEntry(bar)
        self.from_d.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="To").pack(side="left")
        self.to_d = DateEntry(bar)
        self.to_d.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Client").pack(side="left")
        self.client = ClientPicker(bar, include_all=True, width=30)
        self.client.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Received by" if kind == "inward" else "Returned by").pack(side="left")
        self.staff = staff_combo(bar, db, ALL_PEOPLE, width=18, names=db.person_names)
        self.staff.pack(side="left", padx=(2, 8))

        bar2 = ttk.Frame(self, style="Screen.TFrame")
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Label(bar2, text="Holder / client name:").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar2, textvariable=self.search, width=24)
        e.pack(side="left", padx=(2, 8))
        e.bind("<Return>", lambda ev: self.refresh())
        live_search(e, self.refresh)
        self.cancelled = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show cancelled entries", variable=self.cancelled,
                        command=self.refresh).pack(side="left", padx=(0, 8))
        ttk.Button(bar2, text="Apply Filters", style="Accent.TButton", command=self.refresh).pack(side="left")
        ttk.Button(bar2, text="Clear Filters", command=self.clear).pack(side="left", padx=4)
        ttk.Button(bar2, text="⟳ Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar2, text="Export to Excel", command=self.export).pack(side="right")
        self.count = ttk.Label(bar2, style="Muted.TLabel")
        self.count.pack(side="right", padx=10)

        if extra_buttons:
            eb = ttk.Frame(self, style="Screen.TFrame")
            eb.pack(fill="x", pady=(0, 6))
            for text, fn in extra_buttons:
                ttk.Button(eb, text=text, command=lambda fn=fn: self._with_selected(fn)).pack(side="left", padx=(0, 6))

        menu_extra = [(text, fn) for text, fn in extra_buttons]
        self.table = DataTable(
            self, INWARD_COLUMNS if kind == "inward" else OUTWARD_COLUMNS, height=height,
            on_double=screen.open_token_history,
            menu=lambda r: screen.token_menu(r, [(t, lambda fn=fn, r=r: fn(r)) for t, fn in menu_extra]),
            empty_text="No entries for the current filters.")
        self.table.pack(fill="both", expand=True)

    def _with_selected(self, fn):
        row = self.table.selected()
        if not row:
            self.screen.error("Please select an entry in the list first.", "No entry selected")
            return
        fn(row)

    def reload_lists(self):
        self.client.load(self.screen.db.list_clients())
        current = self.staff.get()
        self.staff.reload()
        self.staff.set(current if current in self.staff["values"] else ALL_PEOPLE)

    def set_filters(self, from_date=None, to_date=None, client_id=None, **_):
        self.reload_lists()
        self.from_d.set_iso(from_date)
        self.to_d.set_iso(to_date)
        self.client.set_id(client_id)
        self.staff.set(ALL_PEOPLE)
        self.search.set("")

    def reset(self):
        self.set_filters()
        self.cancelled.set(False)

    def clear(self):
        self.reset()
        self.refresh()

    def filters(self):
        f = {"from_date": self.from_d.get_iso("From date"), "to_date": self.to_d.get_iso("To date"),
             "client_id": self.client.get_id(), "search": self.search.get(),
             "staff": None if self.staff.get() == ALL_PEOPLE else self.staff.get(),
             "include_cancelled": self.cancelled.get()}
        if f["from_date"] and f["to_date"] and f["from_date"] > f["to_date"]:
            raise ValueError("From date cannot be after To date.")
        return f

    def refresh(self):
        ok, f = self.screen.run(self.filters)
        if not ok:
            return
        db = self.screen.db
        rows = db.inward_register(f) if self.kind == "inward" else db.outward_register(f)
        self.table.set_rows(rows, register_tag)
        self.count.configure(text=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")

    def export(self):
        self.table.export_csv("DSC_Inward_Register" if self.kind == "inward" else "DSC_Outward_Register")


class InwardRegisterScreen(Screen):
    title = "Inward Register"
    show_firm = True
    subtitle = "All DSC inward transactions"

    def build(self, body):
        self.panel = RegisterPanel(body, self, "inward", height=8)
        self.panel.pack(fill="both", expand=True)

    def reset_filters(self):
        self.panel.reset()

    def on_show(self, **kw):
        if kw:
            self.panel.set_filters(**kw)
        else:
            self.panel.reload_lists()
        self.panel.refresh()


class OutwardRegisterScreen(InwardRegisterScreen):
    title = "Outward Register"
    show_firm = True
    subtitle = "All DSC outward (return) transactions"

    def build(self, body):
        self.panel = RegisterPanel(body, self, "outward", height=8)
        self.panel.pack(fill="both", expand=True)


class CustodyScreen(CustodyActions, Screen):
    title = "DSC in Custody"
    show_firm = True
    subtitle = "Who holds each DSC now - issue, return and hand over tokens here"

    def build(self, body):
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        live = ttk.Frame(self.nb, padding=8, style="Screen.TFrame")
        awaited = ttk.Frame(self.nb, padding=8, style="Screen.TFrame")
        self.nb.add(live, text="  Tokens in Custody  ")
        self.nb.add(awaited, text="  DSC Awaited from Clients  ")
        self._build_live(live)
        self._build_awaited(awaited)

    # ---------------------------------------------------------------- live custody
    def _build_live(self, f):
        bar = ttk.Frame(f, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Client").pack(side="left")
        self.c_client = ClientPicker(bar, include_all=True, width=30)
        self.c_client.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Currently with").pack(side="left")
        self.c_with = ttk.Combobox(bar, state="readonly", width=24)
        self.c_with.set(WITH_ANYONE)
        self.c_with.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Purpose").pack(side="left")
        self.c_purpose = ttk.Combobox(bar, state="readonly", width=15, values=[ALL_PURPOSES] + PURPOSES)
        self.c_purpose.set(ALL_PURPOSES)
        self.c_purpose.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Return status").pack(side="left")
        self.c_overdue = ttk.Combobox(bar, state="readonly", width=20, values=[
            "All", "Overdue", "Due within 3 days", "Not overdue"])
        self.c_overdue.set("All")
        self.c_overdue.pack(side="left", padx=(2, 8))

        bar2 = ttk.Frame(f, style="Screen.TFrame")
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Label(bar2, text="Holder / client name:").pack(side="left")
        self.c_search = tk.StringVar()
        e = ttk.Entry(bar2, textvariable=self.c_search, width=24)
        e.pack(side="left", padx=(2, 8))
        e.bind("<Return>", lambda ev: self.refresh_live())
        live_search(e, self.refresh_live)
        ttk.Button(bar2, text="Apply Filters", style="Accent.TButton", command=self.refresh_live).pack(side="left")
        ttk.Button(bar2, text="Clear Filters", command=self._clear_live).pack(side="left", padx=4)
        ttk.Button(bar2, text="⟳ Refresh", command=self.refresh_live).pack(side="left")
        ttk.Button(bar2, text="Export to Excel", command=lambda: self.live.export_csv("DSC_Custody_Register")).pack(
            side="right")
        self.c_count = ttk.Label(bar2, style="Muted.TLabel")
        self.c_count.pack(side="right", padx=10)
        self.build_actions(f).pack(fill="x", pady=(0, 6))

        self.live = DataTable(f, [
            ("client_code", "Client", 65), ("holder_name", "DSC Holder Name", 170),
            ("token_serial", "Token Serial", 120), ("with_label", "Currently With", 190),
            ("with_since", "Since", 140, "datetime"), ("with_status", "Back to Custodian", 200),
            ("expiry_date", "Cert Expiry", 140, "datetime"),
            ("expiry_status", "Certificate Status", 160), ("inward_date", "Inward Date", 85, "date"),
            ("purpose", "Purpose", 105), ("received_by", "Received By", 120),
            ("expected_return_date", "Expected Return", 95, "date"), ("days_in_custody", "Days in Custody", 90, "num"),
            ("custody_status", "Current Custody Status", 160), ("inward_id", "Inward ID", 65, "num"),
        ], height=8, on_double=self.open_token_history, on_select=lambda r: self._update_buttons(),
            menu=self.action_menu, empty_text="No DSC in custody matches the current filters.")
        self.live.pack(fill="both", expand=True)
        self.action_table = self.live
        legend(f, [("red", "Overdue (to the client, or back to the custodian)"), ("orange", "Due within 3 days"),
                   ("green", "In custody - normal")]).pack(anchor="w", pady=(6, 0))
        ttk.Label(f, style="Muted.TLabel", text=(
            "Select a token, then use the buttons above (or right-click it). Tokens always go back to the "
            "custodian - no staff-to-staff transfers. Every movement is time-stamped.")).pack(anchor="w")

    def refresh_actions(self):
        self.refresh_live()

    def _reset_live(self):
        self.c_client.set_id(None)
        self.c_with.set(WITH_ANYONE)
        self.c_purpose.set(ALL_PURPOSES)
        self.c_overdue.set("All")
        self.c_search.set("")

    def _clear_live(self):
        self._reset_live()
        self.refresh_live()

    def refresh_live(self):
        overdue = {"Overdue": "overdue", "Due within 3 days": "soon", "Not overdue": "not_overdue"}
        names = sorted({r["with_label"] for r in self.db.custody_register()}, key=str.lower)
        self.c_with["values"] = [WITH_ANYONE] + list(WITH_GROUPS) + names
        choice = self.c_with.get()
        if choice not in self.c_with["values"]:
            choice = WITH_ANYONE
            self.c_with.set(choice)
        holder, with_name = WITH_GROUPS.get(choice, (None, None))
        f = {"client_id": self.c_client.get_id(), "search": self.c_search.get(), "holder": holder,
             "purpose": None if self.c_purpose.get() == ALL_PURPOSES else self.c_purpose.get(),
             "overdue": overdue.get(self.c_overdue.get())}
        rows = self.db.custody_register(f)
        if choice in names:  # one particular person
            rows = [r for r in rows if r["with_label"] == choice]
        self.live.set_rows(rows, lambda r: "red" if r["internal_overdue"] else custody_tag(r))
        self.c_count.configure(text=f"{len(rows)} token(s) in custody")
        self._update_buttons()


    # ---------------------------------------------------------------- awaited
    def _build_awaited(self, f):
        bar = ttk.Frame(f, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Client").pack(side="left")
        self.a_client = ClientPicker(bar, include_all=True, width=30)
        self.a_client.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Follow-up staff").pack(side="left")
        self.a_staff = staff_combo(bar, self.db, width=15)
        self.a_staff.pack(side="left", padx=(2, 8))
        self.a_overdue = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Only overdue", variable=self.a_overdue,
                        command=self.refresh_awaited).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Apply Filters", style="Accent.TButton", command=self.refresh_awaited).pack(side="left")
        ttk.Button(bar, text="Clear Filters", command=self._clear_awaited).pack(side="left", padx=4)
        ttk.Button(bar, text="Export to Excel", command=lambda: self.awaited.export_csv("DSC_Awaited_From_Clients")).pack(
            side="right")
        self.a_count = ttk.Label(bar, style="Muted.TLabel")
        self.a_count.pack(side="right", padx=10)

        bar2 = ttk.Frame(f, style="Screen.TFrame")
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Button(bar2, text="+ Add Expected DSC", style="Accent.TButton", command=self._add_expected).pack(side="left")
        ttk.Button(bar2, text="Record Inward for Selected", command=self._receive).pack(side="left", padx=6)
        ttk.Button(bar2, text="Cancel Selected Request", command=self._cancel_expected).pack(side="left")
        ttk.Label(bar2, text="An item stays here until an inward entry is recorded against it.",
                  style="Muted.TLabel").pack(side="left", padx=12)

        self.awaited = DataTable(f, [
            ("expected_id", "Request ID", 70, "num"), ("client_code", "Client", 65),
            ("holder_name", "DSC Holder Name", 180), ("firm_name", "Firm/Company", 180),
            ("token_serial", "Token Serial", 120), ("purpose", "Purpose", 110),
            ("expected_date", "Expected By", 90, "date"), ("await_status", "Status", 140),
            ("followup_staff", "Follow-up Staff", 120), ("remarks", "Remarks", 200),
        ], height=8, empty_text="No DSCs are awaited from clients.",
            menu=lambda r: [("Record Inward for this", self._receive), ("Cancel this request", self._cancel_expected)])
        self.awaited.pack(fill="both", expand=True)

    def _reset_awaited(self):
        self.a_client.set_id(None)
        self.a_staff.set(ALL_STAFF)
        self.a_overdue.set(False)

    def _clear_awaited(self):
        self._reset_awaited()
        self.refresh_awaited()

    def reset_filters(self):
        self._reset_live()
        self._reset_awaited()
        self.nb.select(0)

    def refresh_awaited(self):
        f = {"client_id": self.a_client.get_id(),
             "staff": None if self.a_staff.get() == ALL_STAFF else self.a_staff.get(),
             "overdue": "overdue" if self.a_overdue.get() else None}
        rows = self.db.awaited_list(f)
        self.awaited.set_rows(rows, custody_tag)
        self.a_count.configure(text=f"{len(rows)} DSC(s) awaited")

    def _add_expected(self):
        if ExpectedDialog(self, self.db, self.a_client.get_id()).show():
            self.refresh()
            self.app.refresh_dashboard()

    def _receive(self):
        row = self.awaited.selected()
        if not row:
            self.error("Please select an awaited DSC first.", "Nothing selected")
            return
        self.app.show("inward", client_id=row["client_id"], expected_id=row["expected_id"])

    def _cancel_expected(self):
        row = self.awaited.selected()
        if not row:
            self.error("Please select an awaited DSC first.", "Nothing selected")
            return
        reason = ask_text(self, "Cancel Expected DSC",
                          f"Reason for cancelling request #{row['expected_id']} ({row['holder_name']}):")
        if reason and self.run(self.db.cancel_expected, row["expected_id"], reason)[0]:
            self.refresh()
            self.app.refresh_dashboard()

    # ----------------------------------------------------------------
    def on_show(self, view=None, holder=None, overdue=None, inward_id=None, **kw):
        if view == "awaited":
            self.nb.select(1)
        elif view == "custody" or inward_id:
            self.nb.select(0)
            self.c_with.set(next((k for k, v in WITH_GROUPS.items() if v[0] == holder), WITH_ANYONE))
            if overdue:
                self.c_overdue.set(overdue)
        self.refresh()
        if inward_id:
            self.live.select(lambda r: r["inward_id"] == inward_id)
            self._update_buttons()

    def refresh(self):
        clients = self.db.list_clients()
        for picker in (self.c_client, self.a_client):
            picker.load(clients)
        cur = self.a_staff.get()
        self.a_staff.reload()
        self.a_staff.set(cur if cur in self.a_staff["values"] else ALL_STAFF)
        self.refresh_live()
        self.refresh_awaited()
