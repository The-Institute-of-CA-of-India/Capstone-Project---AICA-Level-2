"""Settings > Custodian, Staff & Consultants: everyone who can hold a token - the custodian (one in office
at a time), the staff members and the outside consultants (e.g. Company Secretaries)."""
import tkinter as tk
from tkinter import ttk

from .. import dates
from .dialogs import AppointCustodianDialog, ConsultantDialog
from .widgets import COLORS, DataTable, ask_text


class HandlersPanel(ttk.Frame):
    def __init__(self, parent, screen):
        super().__init__(parent, style="Screen.TFrame")
        self.screen = screen
        self.build()

    @property
    def db(self):
        return self.screen.db

    def build(self):
        top = ttk.Frame(self, style="Screen.TFrame")
        top.pack(fill="x")
        # Staff is packed first so that on a small window it is the custodian's table that narrows.
        st = ttk.LabelFrame(top, text=" Staff Members ", padding=12)
        st.pack(side="right", fill="y", padx=(12, 0))
        cbox = ttk.LabelFrame(top, text=" Custodian ", padding=12)
        cbox.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(cbox)
        head.pack(fill="x")
        ttk.Button(head, text="Appoint New Custodian…", style="Accent.TButton",
                   command=self._appoint).pack(side="right", anchor="n")
        self.current = tk.Label(head, font=("Segoe UI", 13, "bold"), anchor="w", justify="left", wraplength=320,
                                bg=COLORS["bg"])
        self.current.pack(side="left")
        ttk.Label(cbox, style="Muted.TLabel", wraplength=470, text=(
            "One custodian at a time; every inward DSC goes to the custodian. When a new custodian is appointed, the "
            "previous one is relieved and all tokens with the custodian are handed over automatically (recorded in "
            "the Movement Register).")).pack(anchor="w", pady=(4, 6))
        self.custodians = DataTable(cbox, [
            ("name", "Custodian", 170), ("appointed_at", "Appointed", 135, "datetime"),
            ("relieved_at", "Relieved", 135, "datetime"), ("state", "Status", 75), ("remarks", "Remarks", 180),
        ], height=4)
        self.custodians.pack(fill="x")

        self.staff_list = tk.Listbox(st, height=8, width=30)
        self.staff_list.pack(side="left", fill="y")
        sb = ttk.Frame(st)
        sb.pack(side="left", padx=(8, 0), anchor="n")
        ttk.Button(sb, text="Add Staff...", command=self._add_staff).pack(fill="x")
        ttk.Button(sb, text="Remove from List", command=self._remove_staff).pack(fill="x", pady=4)
        ttk.Label(sb, style="Muted.TLabel", text="Names offered when a\ntoken is issued to staff.\n\n"
                                                 "Removing only hides the\nname from the lists;\nhistory is kept.").pack(
            anchor="w")

        kbox = ttk.LabelFrame(self, text=" Consultants (e.g. Company Secretaries) ", padding=12)
        kbox.pack(fill="both", expand=True, pady=(12, 0))
        bar = ttk.Frame(kbox)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="+ Add Consultant", style="Accent.TButton", command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Mark Active / Inactive", command=self._toggle).pack(side="left", padx=4)
        self.consultants = DataTable(kbox, [
            ("name", "Name", 190), ("kind", "Type", 70), ("firm", "Firm", 200), ("mobile", "Mobile", 100),
            ("email", "Email", 180), ("holding", "Holding Now", 85, "num"), ("state", "Status", 70),
            ("remarks", "Remarks", 200),
        ], height=8, on_double=lambda r: self._edit())
        self.consultants.pack(fill="both", expand=True)

    def refresh(self):
        c = self.db.current_custodian()
        if c:
            self.current.configure(text=f"Current custodian: {c['name']}   "
                                        f"(since {dates.to_display_dt(c['appointed_at'])})", fg=COLORS["text"])
        else:
            self.current.configure(text="No custodian appointed - inward entries are blocked until one is.",
                                   fg=COLORS["red"])
        rows = self.db.list_custodians()
        for r in rows:
            r["state"] = "In office" if r["relieved_at"] is None else "Relieved"
        self.custodians.set_rows(rows, lambda r: "green" if r["relieved_at"] is None else None)
        self.staff_list.delete(0, "end")
        for s in self.db.list_staff():
            self.staff_list.insert("end", s)
        cons = self.db.list_consultants()
        for r in cons:
            r["state"] = "Active" if r["active"] else "Inactive"
        self.consultants.set_rows(cons, lambda r: None if r["active"] else "cancelled")

    def _appoint(self):
        if AppointCustodianDialog(self.screen, self.db).show():
            self.screen.info(f"{self.db.current_custodian()['name']} is now the custodian.", "Custodian appointed")
            self.refresh()
            self.screen.app.refresh_dashboard()
            self.screen.app.update_status()

    def _add_staff(self):
        name = ask_text(self.screen, "Add Staff Member", "Staff member name:")
        if name and self.screen.run(self.db.add_staff, name)[0]:
            self.refresh()

    def _remove_staff(self):
        sel = self.staff_list.curselection()
        if not sel:
            self.screen.error("Select a staff member in the list first.")
            return
        name = self.staff_list.get(sel[0])
        if self.screen.confirm(f"Remove '{name}' from the staff dropdown lists?"):
            self.db.remove_staff(name)
            self.refresh()

    def _add(self):
        if ConsultantDialog(self.screen, self.db).show():
            self.refresh()

    def _edit(self):
        row = self.consultants.selected()
        if not row:
            self.screen.error("Please select a consultant first.", "Nothing selected")
            return
        if ConsultantDialog(self.screen, self.db, self.db.get_consultant(row["consultant_id"])).show():
            self.refresh()

    def _toggle(self):
        row = self.consultants.selected()
        if not row:
            self.screen.error("Please select a consultant first.", "Nothing selected")
            return
        if row["active"] and row["holding"]:
            self.screen.error(f"{row['name']} still holds {row['holding']} token(s). Record their return first.")
            return
        new = "Inactive" if row["active"] else "Active"
        if self.screen.confirm(f"Mark consultant {row['name']} as {new}?"):
            self.db.set_consultant_active(row["consultant_id"], not row["active"])
            self.refresh()
