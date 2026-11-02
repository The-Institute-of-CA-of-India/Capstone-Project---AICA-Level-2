"""Clients Master."""
import os
import tkinter as tk
from tkinter import filedialog, ttk

from .. import client_import

from .base import Screen, button_bar, filter_bar
from .dialogs import (CertHistoryDialog, ClientDetailDialog, ClientDialog, ExpectedDialog, ImportPreviewDialog,
                      TokenHistoryDialog, TokenInactiveDialog)
from .widgets import ask_text
from .widgets import DataTable, live_search


class ClientsScreen(Screen):
    title = "Clients"
    subtitle = "Client master - a client may hold several DSC tokens"

    def build(self, body):
        bar = filter_bar(body)
        ttk.Label(bar, text="Search name / code / PAN:").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.search, width=30)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self.refresh())
        live_search(e, self.refresh)
        ttk.Label(bar, text="Status:").pack(side="left", padx=(12, 2))
        self.status = ttk.Combobox(bar, values=["All", "Active", "Inactive", "PAN pending"], state="readonly",
                                   width=12)
        self.status.set("Active")
        self.status.pack(side="left")
        self.status.bind("<<ComboboxSelected>>", lambda ev: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side="left")

        btns = button_bar(body)
        ttk.Button(btns, text="+ Add Client", style="Accent.TButton", command=self._add).pack(side="left")
        ttk.Button(btns, text="Edit", command=self._edit).pack(side="left", padx=4)
        ttk.Button(btns, text="Mark Active / Inactive", command=self._toggle).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete", command=self._delete).pack(side="left", padx=4)
        ttk.Button(btns, text="Add Expected DSC", command=self._expected).pack(side="left", padx=(16, 4))
        ttk.Button(btns, text="Record Inward", command=self._inward).pack(side="left", padx=4)
        ttk.Button(btns, text="Import from Excel…", command=self._import).pack(side="right")
        ttk.Button(btns, text="Download Excel Template", command=self._template).pack(side="right", padx=4)

        self.table = DataTable(body, [
            ("client_code", "Client ID", 75), ("holder_name", "DSC Holder Name", 190),
            ("firm_name", "Firm/Company Name", 210), ("pan", "PAN", 95), ("mobile", "Mobile", 95),
            ("email", "Email", 170), ("status", "Status", 65), ("token_count", "Tokens", 55, "num"),
            ("in_custody", "In Custody", 70, "num"), ("remarks", "Remarks", 180),
        ], height=12, on_select=self._selected, on_double=lambda r: self._details(),
            empty_text="No clients match the search.",
            menu=lambda r: [("Client Details…", self._details), ("Edit Client…", self._edit), None,
                            ("Record Inward", self._inward), ("Add Expected DSC…", self._expected)])
        self.table.pack(fill="both", expand=True)

        tbar = ttk.Frame(body, style="Screen.TFrame")
        tbar.pack(fill="x", pady=(10, 2))
        self.tok_label = ttk.Label(tbar, text="DSC tokens of selected client", style="Section.TLabel")
        self.tok_label.pack(side="left")
        ttk.Button(tbar, text="Token History", command=self._token_history).pack(side="right")
        ttk.Button(tbar, text="Mark Token Active…", command=self._token_active).pack(side="right", padx=4)
        ttk.Button(tbar, text="Mark Token Inactive…", command=self._token_inactive).pack(side="right")
        self.tokens = DataTable(body, [
            ("token_serial", "Token Serial", 140), ("status_text", "Token Status", 220),
            ("cert_serial", "Certificate Serial", 140), ("expiry_date", "Expiry", 140, "datetime"),
            ("expiry_status", "Expiry Status", 160), ("custody_status", "Custody", 130),
        ], height=5, on_double=lambda r: TokenHistoryDialog(self, self.db, r["token_id"]).show(),
            empty_text="Select a client to see their DSC tokens.",
            menu=lambda r: self.token_menu(r, [("Mark Token Inactive…", self._token_inactive),
                                               ("Mark Token Active…", self._token_active)]))
        self.tokens.pack(fill="x")

    def reset_filters(self):
        self.search.set("")
        self.status.set("Active")

    def _clear(self):
        self.search.set("")
        self.status.set("All")
        self.refresh()

    def refresh(self):
        self.table.set_rows(self.db.list_clients(self.search.get(), self.status.get()),
                            lambda r: "cancelled" if r["status"] == "Inactive" else None)
        self._selected(self.table.selected())

    def _selected(self, row):
        if not row:
            self.tokens.set_rows([])
            self.tok_label.configure(text="DSC tokens of selected client")
            return
        self.tok_label.configure(text=f"DSC tokens of {row['client_code']} - {row['holder_name']} "
                                      f"(double-click a token for certificate history)")
        self.tokens.set_rows(self.db.tokens_for_client(row["client_id"]),
                             lambda t: "cancelled" if t["status"] == "Inactive" else None)

    def _template(self):
        path = filedialog.asksaveasfilename(parent=self, title="Save the client import template",
                                            defaultextension=".xlsx", initialfile="Client_Import_Template.xlsx",
                                            filetypes=[("Excel workbook", "*.xlsx")])
        if not path:
            return
        try:
            client_import.make_template(path)
        except (client_import.TemplateError, OSError) as exc:
            self.error(f"The template could not be saved:\n{exc}")
            return
        self.info(f"Template saved:\n{path}\n\nFill in the 'Clients' sheet (see the 'Instructions' sheet), save it, "
                  "then click 'Import from Excel'.", "Template saved", popup=True)

    def _import(self):
        path = filedialog.askopenfilename(parent=self, title="Choose the filled-in client template",
                                          filetypes=[("Excel workbook", "*.xlsx")])
        if not path:
            return
        try:
            rows = client_import.read_rows(path)
        except client_import.TemplateError as exc:
            self.error(str(exc), "Cannot import")
            return
        if not rows:
            self.error("The 'Clients' sheet has no rows to import.", "Nothing to import")
            return
        plan = self.db.plan_client_import(rows)
        count = ImportPreviewDialog(self, self.db, plan, os.path.basename(path)).show()
        if count:
            self.info(f"{count} client(s) imported.", "Import complete")
            self.status.set("All")
            self.refresh()

    def _token(self):
        t = self.tokens.selected()
        if not t:
            self.error("Please select a token in the lower list first.", "No token selected")
        return t

    def _token_inactive(self):
        t = self._token()
        if t and t["status"] == "Inactive":
            self.error(f"Token {t['token_serial']} is already Inactive.")
        elif t and TokenInactiveDialog(self, self.db, t["token_id"]).show():
            self.refresh()
            self.app.refresh_dashboard()

    def _token_active(self):
        t = self._token()
        if not t:
            return
        if t["status"] == "Active":
            self.error(f"Token {t['token_serial']} is already Active.")
            return
        reason = ask_text(self, "Mark Token Active", f"Token {t['token_serial']} was made Inactive "
                          f"({t['inactive_reason']}).\n\nReason for making it Active again (e.g. Found):")
        if reason and self.run(self.db.set_token_active, t["token_id"], reason)[0]:
            self.refresh()
            self.app.refresh_dashboard()

    def _token_history(self):
        t = self._token()
        if t:
            TokenHistoryDialog(self, self.db, t["token_id"]).show()

    def _details(self):
        row = self._need()
        if row:
            ClientDetailDialog(self, self.db, row["client_id"], self.app).show()
            self.refresh()

    def _need(self):
        row = self.table.selected()
        if not row:
            self.error("Please select a client in the list first.", "No client selected")
        return row

    def _add(self):
        if ClientDialog(self, self.db).show():
            self.refresh()

    def _edit(self):
        row = self._need()
        if row and ClientDialog(self, self.db, self.db.get_client(row["client_id"])).show():
            self.refresh()

    def _toggle(self):
        row = self._need()
        if not row:
            return
        new = "Inactive" if row["status"] == "Active" else "Active"
        if self.confirm(f"Mark client {row['client_code']} - {row['holder_name']} as {new}?"):
            self.run(self.db.set_client_status, row["client_id"], new)
            self.refresh()

    def _delete(self):
        row = self._need()
        if not row:
            return
        if self.db.client_has_transactions(row["client_id"]):
            self.error("This client has DSC tokens or transactions, so it cannot be deleted.\n"
                       "Use 'Mark Active / Inactive' to mark the client Inactive instead.", "Cannot delete")
            return
        if self.confirm(f"Permanently delete client {row['client_code']} - {row['holder_name']}?\n"
                        "This client has no DSC transactions."):
            self.run(self.db.delete_client, row["client_id"])
            self.refresh()

    def _expected(self):
        row = self.table.selected()
        if ExpectedDialog(self, self.db, row["client_id"] if row else None).show():
            self.info("Expected DSC recorded. It will show under 'DSC Awaited from Clients' until received.")
            self.app.refresh_dashboard()

    def _inward(self):
        row = self.table.selected()
        self.app.show("inward", client_id=row["client_id"] if row else None)
