"""DSC Outward: the custodian returns tokens in custody to clients."""
import tkinter as tk
from tkinter import ttk

from .. import dates, whatsapp
from ..database import PURPOSES
from .base import Screen
from .dashboard import custody_tag
from .dialogs import CorrectEntryDialog, TokenHistoryDialog
from .reports import RegisterPanel
from .widgets import COLORS, DataTable, DateEntry, ask_text, enter_moves_focus, labeled


class OutwardScreen(Screen):
    title = "DSC Outward"
    subtitle = "The custodian returns a DSC to the client"

    def build(self, body):
        self.selected = None
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        rec = ttk.Frame(self.nb, padding=10, style="Screen.TFrame")
        hist = ttk.Frame(self.nb, padding=8, style="Screen.TFrame")
        self.nb.add(rec, text="  Record Return  ")
        self.nb.add(hist, text="  Outward History  ")
        self._build_record(rec)
        self.register = RegisterPanel(hist, self, "outward", height=8, extra_buttons=[
            ("Correct Entry…", self._correct),
            ("Cancel Outward Entry", self._cancel),
            ("Token History", lambda r: TokenHistoryDialog(self, self.db, r["token_id"]).show())])
        self.register.pack(fill="both", expand=True)
        self.register.set_filters()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.nb.index("current") == 1 and self.register.refresh())

    def _build_record(self, tab):
        bar = ttk.Frame(tab, style="Screen.TFrame")
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Step 1 - select the DSC being returned (tokens with the custodian)",
                  style="Section.TLabel").pack(side="left")
        self.count = ttk.Label(bar, style="Muted.TLabel")
        self.count.pack(side="right")
        bar2 = ttk.Frame(tab, style="Screen.TFrame")
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Holder / client name:").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar2, textvariable=self.search, width=28)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", lambda ev: self.refresh_custody())
        ttk.Button(bar2, text="Clear", command=lambda: (self.search.set(""), self.refresh_custody())).pack(side="left")
        ttk.Button(bar2, text="⟳ Refresh", command=self.refresh_custody).pack(side="left", padx=4)
        self.out_note = ttk.Label(bar2, style="Muted.TLabel")
        self.out_note.pack(side="left", padx=12)

        self.custody = DataTable(tab, [
            ("inward_id", "Inward ID", 65, "num"), ("client_code", "Client", 65),
            ("holder_name", "DSC Holder Name", 180), ("token_serial", "Token Serial", 130),
            ("inward_date", "Inward Date", 85, "date"), ("purpose", "Purpose", 110),
            ("expected_return_date", "Expected Return", 95, "date"),
            ("days_in_custody", "Days", 50, "num"), ("custody_status", "Status", 150),
        ], height=5, on_select=self._pick, menu=lambda r: self.token_menu(r),
            empty_text="No DSC is with the custodian right now.")
        self.custody.pack(fill="both", expand=True)

        f = ttk.LabelFrame(tab, text=" Step 2 - return details  (* mandatory) ", padding=12)
        f.pack(fill="x", pady=(10, 0))
        self.sel_label = tk.Label(f, text="No DSC selected.", anchor="w", bg=COLORS["bg"],
                                  font=("Segoe UI", 10, "bold"), fg=COLORS["muted"])
        self.sel_label.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        self.out_date = DateEntry(f, default_today=True)
        labeled(f, "Outward Date *", 1, 0, self.out_date)
        self.returned_to = tk.StringVar()
        labeled(f, "Returned To *", 1, 2, ttk.Entry(f, textvariable=self.returned_to, width=32))
        self.custodian_lbl = tk.Label(f, anchor="w", bg=COLORS["bg"], font=("Segoe UI", 9, "bold"))
        labeled(f, "Returned By (custodian)", 2, 0, self.custodian_lbl)
        self.purpose = ttk.Combobox(f, values=PURPOSES, state="readonly", width=24)
        labeled(f, "Purpose/Assignment", 2, 2, self.purpose)
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 3, 0, ttk.Entry(f, textvariable=self.remarks, width=80), colspan=3)
        b = ttk.Frame(tab, style="Screen.TFrame")
        b.pack(fill="x", pady=10)
        ttk.Button(b, text="Save Outward Entry  (Ctrl+S)", style="Accent.TButton", command=self._save).pack(side="left")
        ttk.Button(b, text="Clear", command=self._clear).pack(side="left", padx=6)
        self.wa = tk.BooleanVar(value=True)
        ttk.Checkbutton(b, text="Send WhatsApp message to the client", variable=self.wa).pack(side="left", padx=16)
        enter_moves_focus(f)

    def refresh_custody(self, select_inward=None):
        all_rows = self.db.custody_register({"search": self.search.get()})
        rows = [r for r in all_rows if r["with_type"] == "custodian"]
        out = len(all_rows) - len(rows)
        self.custody.set_rows(rows, custody_tag)
        self.count.configure(text=f"{len(rows)} DSC(s) with the custodian")
        self.out_note.configure(text=(f"{out} token(s) out with staff or consultants are not listed - record their "
                                      "return on the DSC in Custody screen first." if out else ""))
        if select_inward:
            row = self.custody.select(lambda r: r["inward_id"] == select_inward)
            if row:
                self._pick(row)
            elif any(r["inward_id"] == select_inward for r in all_rows):
                held = next(r for r in all_rows if r["inward_id"] == select_inward)
                self.error(f"Token {held['token_serial']} is with {held['with_label']}. Record its return to the "
                           "custodian (DSC in Custody screen) before returning it to the client.", "Not with custodian")

    def _pick(self, row):
        if not row:
            return
        self.selected = row
        self.sel_label.configure(fg=COLORS["blue"], text=(
            f"Returning: token {row['token_serial']}  |  {row['holder_name']} ({row['client_code']})  |  "
            f"received {dates.to_display(row['inward_date'])} for {row['purpose']}  [Inward #{row['inward_id']}]"))
        self.returned_to.set(row["holder_name"])
        self.purpose.set(row["purpose"])

    def _clear(self):
        self.selected = None
        self.sel_label.configure(text="No DSC selected.", fg=COLORS["muted"])
        self.out_date.set_iso(dates.today_iso())
        self.returned_to.set("")
        self.purpose.set("")
        self.remarks.set("")
        self.custody.tree.selection_remove(self.custody.tree.selection())

    def _save(self):
        row = self.selected
        if not row:
            self.error("Please select the DSC being returned from the custody list (Step 1).")
            return
        ok, out_date = self.run(self.out_date.get_iso, "Outward Date", True)
        if not ok:
            return
        custodian = self.db.current_custodian()
        msg = (f"Record return of this DSC?\n\nToken: {row['token_serial']}\nHolder: {row['holder_name']}\n"
               f"Returned to: {self.returned_to.get() or '-'}\n"
               f"Returned by: {custodian['name'] if custodian else '-'} (custodian)\n"
               f"Outward date: {dates.to_display(out_date)}\n\nThe token will be removed from live custody.")
        if not self.confirm(msg, "Confirm DSC return"):
            return
        ok, new_id = self.run(self.db.save_outward, {
            "inward_id": row["inward_id"], "outward_date": out_date, "returned_to": self.returned_to.get(),
            "purpose": self.purpose.get(), "remarks": self.remarks.get()})
        if not ok:
            return
        sent = self.wa.get() and self.send_whatsapp(whatsapp.for_outward(self.db, new_id), quiet=True)
        self.app.toast(f"Outward #{new_id} saved: token {row['token_serial']} returned."
                       + (" WhatsApp opened - press Send." if sent else ""),
                       undo=lambda: self.db.cancel_outward(new_id, "Undone straight after entry"))
        self._clear()
        self.refresh_custody()
        self.app.refresh_dashboard()

    def _correct(self, row):
        if row["status"] == "Cancelled":
            self.error(f"Outward #{row['outward_id']} is cancelled and cannot be corrected.")
            return
        changes = CorrectEntryDialog(self, self.db, "outward", row).show()
        if changes:
            self.app.toast(f"Outward #{row['outward_id']} corrected: " + "; ".join(changes))
            self.register.refresh()
            self.app.refresh_dashboard()

    def _cancel(self, row):
        if row["status"] != "Active":
            self.error(f"Outward #{row['outward_id']} is already cancelled.")
            return
        reason = ask_text(self, "Cancel Outward Entry",
                          f"Cancel outward #{row['outward_id']} (token {row['token_serial']})?\n"
                          "The token will show as in custody again. The entry stays in the register marked "
                          "'Cancelled'.\n\nReason for cancellation:")
        if reason and self.run(self.db.cancel_outward, row["outward_id"], reason)[0]:
            self.register.refresh()
            self.refresh_custody()
            self.app.refresh_dashboard()

    def on_ctrl_s(self):
        if self.nb.index("current") == 0:
            self._save()

    def refresh(self):
        self.refresh_custody()
        self.register.refresh()

    def reset_filters(self):
        self.search.set("")
        self.register.reset()
        self.nb.select(0)

    def on_show(self, inward_id=None, **kw):
        c = self.db.current_custodian()
        self.custodian_lbl.configure(text=c["name"] if c else "No custodian appointed",
                                     fg=COLORS["text"] if c else COLORS["red"])
        self.register.reload_lists()
        if inward_id:
            self.nb.select(0)
            self.search.set("")
        self.refresh_custody(select_inward=inward_id)
        if self.nb.index("current") == 1:
            self.register.refresh()
