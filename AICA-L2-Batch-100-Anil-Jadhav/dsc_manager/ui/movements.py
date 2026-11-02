"""Internal and external movements: the actions on tokens in custody (custodian <-> staff,
custodian <-> consultant), plus the Movement Register and Holdings by Person reports."""
import tkinter as tk
from tkinter import ttk

from .. import dates, whatsapp
from ..database import HOLDER_LABELS, MOVEMENT_LABELS
from .base import Screen, legend
from .dialogs import (ClientCollectedDialog, HandToConsultantDialog, IssueToStaffDialog, TokenHistoryDialog,
                      TokenInactiveDialog)
from .widgets import DataTable, DateEntry, Tooltip, ask_text, live_search




class CustodyActions:
    """Actions on the token selected in a list of tokens in custody: issue to staff, return from
    staff, hand to / return from a consultant, client collected from the consultant, return to the
    client, lost / inactive, cancel the last movement and token history. Used by the DSC in Custody
    screen. Everything goes through the custodian: no staff-to-staff transfers.

    The screen provides self.action_table (the DataTable) and refresh_actions() (reload it).
    """
    ACTIONS = [
        ("issue", "Issue to Staff…", "_issue"),
        ("return_staff", "Return from Staff", "_return_staff"),
        ("to_consultant", "Hand to Consultant…", "_to_consultant"),
        ("return_consultant", "Return from Consultant", "_return_consultant"),
        ("collected", "Client Collected from Consultant…", "_collected"),
        ("return_client", "Return to Client…", "_return_client"),
        ("inactive", "Lost / Inactive…", "_inactive"),
        ("cancel", "Cancel Last Movement…", "_cancel"),
        ("history", "Token History", "_history"),
    ]
    TIPS = {
        "issue": "Give the selected token (with the custodian) to a staff member",
        "return_staff": "The staff member has given the token back to the custodian",
        "to_consultant": "Give the selected token (with the custodian) to an outside consultant, e.g. a CS",
        "return_consultant": "The consultant has given the token back to the custodian",
        "collected": "The client took the token directly from the consultant - ends the firm's custody",
        "return_client": "The custodian returns the token to the client (DSC Outward)",
        "inactive": "The token is lost / damaged / replaced - ends custody and records who had it",
        "cancel": "Cancel the last movement of this token (kept in the register as Cancelled)",
        "history": "Everything that happened to this token",
    }

    def build_actions(self, parent):
        bar = ttk.Frame(parent, style="Screen.TFrame")
        self.buttons = {}
        # Two rows: staff and consultant hand-overs, then the client and other actions.
        rows = [ttk.Frame(bar, style="Screen.TFrame") for _ in range(2)]
        rows[0].pack(fill="x")
        rows[1].pack(fill="x", pady=(4, 0))
        for i, (key, text, method) in enumerate(self.ACTIONS):
            b = ttk.Button(rows[0] if i < 5 else rows[1], text=text, command=getattr(self, method))
            b.pack(side="left", padx=(0, 6))
            Tooltip(b, self.TIPS[key])
            self.buttons[key] = b
        return bar

    def action_menu(self, row):
        self._update_buttons()
        items = [(text, getattr(self, method)) for key, text, method in self.ACTIONS
                 if key != "history" and "disabled" not in self.buttons[key].state()]
        return self.token_menu(row, items)

    def _update_buttons(self):
        row = self.action_table.selected()
        has_custodian = self.db.current_custodian() is not None
        kind = row["with_type"] if row else None
        allowed = {
            "issue": kind == "custodian" and has_custodian,
            "to_consultant": kind == "custodian" and has_custodian,
            "return_staff": kind == "staff" and has_custodian,
            "return_consultant": kind == "consultant" and has_custodian,
            "collected": kind == "consultant",
            "return_client": kind == "custodian",
            "cancel": bool(row and row["with_movement_id"] and row["with_kind"] != "handover"),
            "history": row is not None,
            "inactive": row is not None,
        }
        for key, b in self.buttons.items():
            b.state(["!disabled"] if allowed[key] else ["disabled"])

    def _row(self):
        row = self.action_table.selected()
        if not row:
            self.error("Please select a token in the list first.", "No token selected")
        return row

    def _done(self, msg, undo=None):
        self.app.toast(msg, undo=undo)
        selected = self.action_table.selected()
        self.refresh_actions()
        if selected:
            self.action_table.select(lambda r: r["inward_id"] == selected["inward_id"])
            self._update_buttons()
        self.app.refresh_dashboard()

    def _issue(self):
        row = self._row()
        mid = row and IssueToStaffDialog(self, self.db, row).show()
        if mid:
            self._done(f"Token {row['token_serial']} issued.", self._undo_movement(mid))

    def _to_consultant(self):
        row = self._row()
        mid = row and HandToConsultantDialog(self, self.db, row).show()
        if mid:
            self._done(f"Token {row['token_serial']} handed to the consultant.", self._undo_movement(mid))

    def _return_staff(self):
        row = self._row()
        if not row:
            return
        c = self.db.current_custodian()
        if self.confirm(f"Record that {row['with_name']} has returned token {row['token_serial']} to the "
                        f"custodian ({c['name']}) now?"):
            ok, mid = self.run(self.db.return_from_staff, row["inward_id"])
            if ok:
                self._done(f"Token {row['token_serial']} is back with the custodian.", self._undo_movement(mid))

    def _return_consultant(self):
        row = self._row()
        if not row:
            return
        c = self.db.current_custodian()
        if self.confirm(f"Record that consultant {row['with_name']} has returned token {row['token_serial']} "
                        f"to the custodian ({c['name']}) now?"):
            ok, mid = self.run(self.db.return_from_consultant, row["inward_id"])
            if ok:
                self._done(f"Token {row['token_serial']} is back with the custodian.", self._undo_movement(mid))

    def _collected(self):
        row = self._row()
        if not row:
            return
        dlg = ClientCollectedDialog(self, self.db, row)
        outward_id = dlg.show()
        if outward_id:
            sent = dlg.send_whatsapp and self.send_whatsapp(whatsapp.for_outward(self.db, outward_id), quiet=True)
            self._done(f"Recorded: the client collected token {row['token_serial']} from {row['with_name']}."
                       + (" WhatsApp opened - press Send." if sent else ""),
                       lambda: self.db.cancel_outward(outward_id, "Undone straight after entry"))

    def _return_client(self):
        row = self._row()
        if row:
            self.app.show("outward", inward_id=row["inward_id"])

    def _undo_movement(self, movement_id):
        return lambda: self.db.cancel_movement(movement_id, "Undone straight after entry")

    def _cancel(self):
        row = self._row()
        if not row:
            return
        reason = ask_text(self, "Cancel Last Movement",
                          f"Cancel the last movement of token {row['token_serial']} "
                          f"({MOVEMENT_LABELS.get(row['with_kind'], '')} - now {row['with_label']})?\n"
                          "The entry stays in the Movement Register marked 'Cancelled'.\n\nReason:")
        if reason and self.run(self.db.cancel_movement, row["with_movement_id"], reason)[0]:
            self._done("Movement cancelled.")

    def _history(self):
        row = self._row()
        if row:
            TokenHistoryDialog(self, self.db, row["token_id"]).show()

    def _inactive(self):
        row = self._row()
        if row and TokenInactiveDialog(self, self.db, row["token_id"]).show():
            self._done(f"Token {row['token_serial']} marked Inactive; it is no longer in custody.")


class MovementRegisterScreen(Screen):
    title = "Movement Register"
    show_firm = True
    subtitle = "Every issue, return and hand-over of tokens, with system time stamps"

    ALL_PEOPLE = "(Everyone)"
    ALL_KINDS = "(All movements)"

    def build(self, body):
        bar = ttk.Frame(body, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="From").pack(side="left")
        self.from_d = DateEntry(bar)
        self.from_d.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="To").pack(side="left")
        self.to_d = DateEntry(bar)
        self.to_d.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Person").pack(side="left")
        self.person = ttk.Combobox(bar, state="readonly", width=22)
        self.person.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Movement").pack(side="left")
        self.kind = ttk.Combobox(bar, state="readonly", width=28,
                                 values=[self.ALL_KINDS] + list(MOVEMENT_LABELS.values()))
        self.kind.set(self.ALL_KINDS)
        self.kind.pack(side="left", padx=(2, 8))

        bar2 = ttk.Frame(body, style="Screen.TFrame")
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
        ttk.Button(bar2, text="Clear Filters", command=self._clear).pack(side="left", padx=4)
        ttk.Button(bar2, text="Token History", command=self._history).pack(side="left", padx=(12, 0))
        ttk.Button(bar2, text="Export to Excel",
                   command=lambda: self.table.export_csv("DSC_Movement_Register")).pack(side="right")
        self.count = ttk.Label(bar2, style="Muted.TLabel")
        self.count.pack(side="right", padx=10)

        self.table = DataTable(body, [
            ("moved_at", "Date / Time", 145, "datetime"), ("kind_label", "Movement", 200),
            ("token_serial", "Token Serial", 125), ("holder_name", "DSC Holder", 170), ("client_code", "Client", 65),
            ("from_name", "From", 150), ("to_name", "To", 150), ("purpose", "Purpose", 105),
            ("expected_return", "Due Back", 140, "datetime"), ("remarks", "Remarks", 180), ("status", "Status", 75),
        ], height=20, on_double=lambda r: self._history(), menu=lambda r: self.token_menu(r),
            empty_text="No movements for the current filters.")
        self.table.pack(fill="both", expand=True)

    def reset_filters(self):
        self.from_d.clear()
        self.to_d.clear()
        self.person.set(self.ALL_PEOPLE)
        self.kind.set(self.ALL_KINDS)
        self.search.set("")
        self.cancelled.set(False)

    def _clear(self):
        self.reset_filters()
        self.refresh()

    def on_show(self, **kw):
        current = self.person.get()
        self.person["values"] = [self.ALL_PEOPLE] + self.db.person_names()
        self.person.set(current if current in self.person["values"] else self.ALL_PEOPLE)
        self.refresh()

    def refresh(self):
        try:
            f = {"from_date": self.from_d.get_iso("From date"), "to_date": self.to_d.get_iso("To date")}
        except ValueError as exc:
            self.error(str(exc))
            return
        kind = next((k for k, v in MOVEMENT_LABELS.items() if v == self.kind.get()), None)
        f.update({"person": None if self.person.get() == self.ALL_PEOPLE else self.person.get(), "kind": kind,
                  "search": self.search.get(), "include_cancelled": self.cancelled.get()})
        rows = self.db.movement_register(f)
        self.table.set_rows(rows, lambda r: "cancelled" if r["status"] == "Cancelled" else None)
        self.count.configure(text=f"{len(rows)} movement(s)")

    def _history(self):
        row = self.table.selected()
        if not row:
            self.error("Please select a movement first.", "Nothing selected")
            return
        TokenHistoryDialog(self, self.db, row["token_id"]).show()


class HoldingsScreen(Screen):
    title = "Holdings by Person"
    show_firm = True
    subtitle = "What the custodian, each staff member and each consultant holds right now"

    def build(self, body):
        pane = ttk.Frame(body, style="Screen.TFrame")
        pane.pack(fill="both", expand=True)
        pane.columnconfigure(1, weight=1)
        pane.rowconfigure(1, weight=1)
        ttk.Label(pane, text="People holding tokens", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.title_lbl = ttk.Label(pane, text="Tokens held", style="Section.TLabel")
        self.title_lbl.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.people = DataTable(pane, [
            ("role", "Role", 85), ("name", "Name", 160), ("count", "Tokens", 55, "num"),
            ("overdue", "Overdue", 60, "num")], height=18, on_select=lambda r: self._show_person(r))
        self.people.grid(row=1, column=0, sticky="nsew")
        right = ttk.Frame(pane, style="Screen.TFrame")
        right.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        bar = ttk.Frame(right, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="⟳ Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Token History", command=self._history).pack(side="left", padx=6)
        ttk.Button(bar, text="Export to Excel",
                   command=lambda: self.tokens.export_csv("DSC_Holdings_By_Person")).pack(side="right")
        self.tokens = DataTable(right, [
            ("token_serial", "Token Serial", 125), ("holder_name", "DSC Holder", 170), ("client_code", "Client", 65),
            ("with_since", "Since", 140, "datetime"), ("with_due", "Due Back", 140, "datetime"),
            ("with_purpose", "Purpose", 105), ("expiry_status", "Certificate", 150)], height=17,
            on_double=lambda r: self._history(), menu=lambda r: self.token_menu(r),
            empty_text="Select a person on the left to see the tokens they hold.")
        self.tokens.pack(fill="both", expand=True)
        legend(body, [("red", "Overdue back to the custodian")]).pack(anchor="w", pady=(6, 0))

    def refresh(self):
        self._rows = self.db.custody_register()
        groups = {}
        for r in self._rows:
            g = groups.setdefault((r["with_type"], r["with_name"]),
                                  {"role": HOLDER_LABELS[r["with_type"]], "name": r["with_name"],
                                   "type": r["with_type"], "count": 0, "overdue": 0})
            g["count"] += 1
            g["overdue"] += 1 if r["internal_overdue"] else 0
        order = {"custodian": 0, "staff": 1, "consultant": 2}
        people = sorted(groups.values(), key=lambda g: (order[g["type"]], g["name"].lower()))
        keep = self.people.selected()
        self.people.set_rows(people, lambda g: "red" if g["overdue"] else None)
        if keep and self.people.select(lambda g: (g["type"], g["name"]) == (keep["type"], keep["name"])):
            self._show_person(self.people.selected())
        else:
            self._show_person(None)

    def _show_person(self, g):
        if not g:
            self.tokens.set_rows([])
            self.title_lbl.configure(text="Tokens held (select a person)")
            return
        rows = [r for r in self._rows if (r["with_type"], r["with_name"]) == (g["type"], g["name"])]
        self.title_lbl.configure(text=f"Tokens held by {g['role'].lower()} {g['name']}")
        self.tokens.set_rows(rows, lambda r: "red" if r["internal_overdue"] else None)

    def _history(self):
        row = self.tokens.selected()
        if not row:
            self.error("Please select a token first.", "Nothing selected")
            return
        TokenHistoryDialog(self, self.db, row["token_id"]).show()
