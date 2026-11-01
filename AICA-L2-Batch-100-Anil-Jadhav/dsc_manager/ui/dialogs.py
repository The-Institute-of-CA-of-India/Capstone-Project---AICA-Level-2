"""Modal dialogs: client, expected DSC, certificate edit/renewal and history,
token reading, internal movements, consultants and custodian appointment."""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import config, dates, token_reader
from ..database import (CERT_STATUSES, CONSULTANT_KINDS, INACTIVE_REASONS, PURPOSES, CertificateConflict,
                        ValidationError)
from .widgets import (ClientPicker, DataTable, DateEntry, DateTimeEntry, combo_autocomplete, enter_moves_focus,
                      labeled)


class Dialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.form = ttk.Frame(self, padding=16)
        self.form.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def buttons(self, ok_text="Save"):
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(bar, text=f"{ok_text}  (Ctrl+S)", style="Accent.TButton", command=self.ok).pack(side="right", padx=6)
        enter_moves_focus(self.form)  # Enter moves to the next field; Ctrl+S saves

    def show(self):
        self.update_idletasks()
        p = self.master.winfo_toplevel()
        x = p.winfo_rootx() + max(0, (p.winfo_width() - self.winfo_width()) // 2)
        y = p.winfo_rooty() + max(0, (p.winfo_height() - self.winfo_height()) // 3)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.wait_window()
        return self.result

    def cancel(self):
        self.destroy()

    def ok(self):
        try:
            self.result = self.save()
        except (ValidationError, ValueError) as exc:
            messagebox.showerror("Please check", str(exc), parent=self)
            return
        if self.result is not None:
            self.destroy()

    def save(self):
        raise NotImplementedError


# ---------------------------------------------------------------------- reading a token
class TokenPickerDialog(Dialog):
    """Choose one of several tokens/certificates read from the PC."""

    def __init__(self, parent, tokens, note=""):
        super().__init__(parent, "Choose the DSC token")
        self.resizable(True, True)
        ttk.Label(self.form, text="More than one certificate was found. Select the one to use:").pack(anchor="w")
        if note:
            ttk.Label(self.form, text=note, style="Muted.TLabel", wraplength=760).pack(anchor="w", pady=(2, 6))
        self.table = DataTable(self.form, [
            ("token_serial", "Token Serial", 150), ("holder_name", "Certificate Holder", 210),
            ("issuer", "Issued By", 200), ("expiry_date", "Expiry", 150, "datetime"),
            ("driver", "Driver / Source", 160)], height=8, on_double=lambda r: self.ok())
        self.table.pack(fill="both", expand=True)
        self.table.set_rows(tokens)
        self.buttons("Use Selected")

    def save(self):
        row = self.table.selected()
        if not row:
            raise ValidationError("Please select a token in the list.")
        return row


def read_token_details(parent):
    """Read the DSC token(s) plugged in and return one token's details, or None.

    The returned dict has token_serial (blank when read from the Windows
    certificate store), holder_name, cert_serial, issuer, issue_date and
    expiry_date (ISO date-times in local time) and source.
    """
    top = parent.winfo_toplevel()
    top.configure(cursor="watch")
    top.update()
    try:
        result = token_reader.read_tokens(config.token_driver_paths())
    finally:
        top.configure(cursor="")
    note = "\n".join(result.notes)
    if not result.tokens:
        messagebox.showwarning("Read from Token", "No DSC token could be read.\n\n" + (note or
                               "Plug in the token and make sure its driver is installed."), parent=parent)
        return None
    if len(result.tokens) == 1:
        if result.method == "store":
            messagebox.showinfo("Read from Token", note, parent=parent)
        return result.tokens[0]
    return TokenPickerDialog(parent, result.tokens, note if result.method == "store" else "").show()


# ---------------------------------------------------------------------- clients & expected DSCs
class ClientDialog(Dialog):
    def __init__(self, parent, db, client=None, initial=None):
        super().__init__(parent, "Edit Client" if client else "Add New Client")
        self.db, self.client = db, client
        f = self.form
        src = client or initial or {}
        self.vars = {k: tk.StringVar(value=src.get(k) or "") for k in
                     ("holder_name", "firm_name", "pan", "mobile", "email", "remarks")}
        self.vars["status"] = tk.StringVar(value=(client or {}).get("status") or "Active")
        r = 0
        if client:
            labeled(f, "Client ID", r, 0, ttk.Label(f, text=client["client_code"], font=("Segoe UI", 10, "bold")))
            r += 1
        fields = [("DSC Holder Name *", "holder_name", 40), ("Firm/Company Name", "firm_name", 40),
                  ("Mobile Number *", "mobile", 16), ("PAN (if available)", "pan", 16),
                  ("Email Address", "email", 40), ("Remarks", "remarks", 50)]
        first = None
        for label, key, width in fields:
            e = labeled(f, label, r, 0, ttk.Entry(f, textvariable=self.vars[key], width=width))
            first = first or e
            r += 1
        status = ttk.Frame(f)
        for s in ("Active", "Inactive"):
            ttk.Radiobutton(status, text=s, value=s, variable=self.vars["status"]).pack(side="left", padx=(0, 12))
        labeled(f, "Status", r, 0, status)
        ttk.Label(f, text="* mandatory.  PAN can be added later; when given it must be the individual DSC holder's "
                          "(4th character 'P')\nand unique. Two clients may share a mobile number only if their "
                          "names differ.", style="Muted.TLabel", justify="left").grid(
            row=r + 1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons()
        first.focus_set()

    def save(self):
        data = {k: v.get() for k, v in self.vars.items()}
        if self.client:
            self.db.update_client(self.client["client_id"], data)
            return self.client["client_id"]
        return self.db.add_client(data)


class ExpectedDialog(Dialog):
    """Record that a DSC is expected from a client (shows as 'Awaited')."""

    def __init__(self, parent, db, client_id=None):
        super().__init__(parent, "Add Expected DSC (Awaited from Client)")
        self.db = db
        f = self.form
        self.client = ClientPicker(f, width=48, on_change=self._client_changed)
        self.client.load(db.list_clients(status="Active"))
        labeled(f, "Client *", 0, 0, self.client)
        self.holder = tk.StringVar()
        labeled(f, "DSC Holder Name", 1, 0, ttk.Entry(f, textvariable=self.holder, width=40))
        self.token = tk.StringVar()
        labeled(f, "Token Serial (if known)", 2, 0, ttk.Entry(f, textvariable=self.token, width=24))
        self.purpose = ttk.Combobox(f, values=PURPOSES, state="readonly", width=22)
        labeled(f, "Purpose/Assignment *", 3, 0, self.purpose)
        self.expected = DateEntry(f)
        labeled(f, "Expected By", 4, 0, self.expected)
        self.staff = ttk.Combobox(f, values=db.list_staff(), width=24)
        combo_autocomplete(self.staff)
        labeled(f, "Follow-up Staff", 5, 0, self.staff)
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 6, 0, ttk.Entry(f, textvariable=self.remarks, width=48))
        if client_id:
            self.client.set_id(client_id)
            self._client_changed(client_id)
        self.buttons()

    def _client_changed(self, cid):
        c = self.db.get_client(cid) if cid else None
        if c:
            self.holder.set(c["holder_name"])

    def save(self):
        return self.db.add_expected({
            "client_id": self.client.get_id(), "holder_name": self.holder.get(), "token_serial": self.token.get(),
            "purpose": self.purpose.get(), "expected_date": self.expected.get_iso("Expected By"),
            "followup_staff": self.staff.get(), "remarks": self.remarks.get()})


# ---------------------------------------------------------------------- certificates
class CertificateDialog(Dialog):
    """mode='edit' updates the current certificate; mode='renew' records a new one."""

    def __init__(self, parent, db, token_id, mode="edit"):
        self.db, self.token_id, self.mode = db, token_id, mode
        self.token = token = db.get_token(token_id)
        current = db.get_current_certificate(token_id)
        title = "Record Certificate Renewal" if mode == "renew" else "Certificate Details"
        super().__init__(parent, title)
        f = self.form
        info = f"Token: {token['token_serial']}    Holder: {token['holder_name']}    Client: {token['client_code']}"
        ttk.Label(f, text=info, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        if mode == "renew" and current:
            prev = (f"Current certificate: {current['cert_serial'] or '-'}, expiry "
                    f"{dates.to_display_dt(current['expiry_date']) or 'unknown'}. It will be kept in history.")
            ttk.Label(f, text=prev, style="Muted.TLabel", wraplength=480).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(4, 6))
        src = current if (mode == "edit" and current) else {}
        ttk.Button(f, text="Read from Token", command=self._read_token).grid(row=2, column=1, sticky="w", pady=4)
        self.serial = tk.StringVar(value=src.get("cert_serial") or "")
        labeled(f, "Certificate Serial No.", 3, 0, ttk.Entry(f, textvariable=self.serial, width=30))
        self.issue = DateTimeEntry(f)
        self.issue.set_iso(src.get("issue_date"))
        labeled(f, "Issue Date", 4, 0, self.issue)
        self.expiry = DateTimeEntry(f)
        self.expiry.set_iso(src.get("expiry_date"))
        labeled(f, "Expiry Date", 5, 0, self.expiry)
        self.issuer = tk.StringVar(value=src.get("issuer") or "")
        labeled(f, "Certifying Authority", 6, 0, ttk.Entry(f, textvariable=self.issuer, width=40))
        self.status = ttk.Combobox(f, values=CERT_STATUSES, state="readonly", width=22)
        self.status.set(src.get("admin_status") or "Active")
        labeled(f, "Administrative Status", 7, 0, self.status)
        self.followup = tk.StringVar(value=src.get("followup") or "")
        labeled(f, "Follow-up Note", 8, 0, ttk.Entry(f, textvariable=self.followup, width=50))
        self.remarks = tk.StringVar(value=src.get("remarks") or "")
        labeled(f, "Remarks", 9, 0, ttk.Entry(f, textvariable=self.remarks, width=50))
        ttk.Label(f, text="Time is optional (e.g. 11:00 AM). Without a time, expiry is taken as 12:00 AM that day. "
                          "Never record DSC PINs or passwords.", style="Muted.TLabel", wraplength=520).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Save Renewal" if mode == "renew" else "Save")

    def _read_token(self):
        t = read_token_details(self)
        if not t:
            return
        if t["token_serial"] and t["token_serial"] != self.token["token_serial"].upper():
            if not messagebox.askyesno(
                    "Different token",
                    f"The token plugged in has serial {t['token_serial']}, but this record is for token "
                    f"{self.token['token_serial']}.\n\nUse its certificate details anyway?", parent=self):
                return
        self.serial.set(t["cert_serial"])
        self.issue.set_iso(t["issue_date"])
        self.expiry.set_iso(t["expiry_date"])
        self.issuer.set(t["issuer"])

    def save(self):
        data = {"cert_serial": self.serial.get(), "issue_date": self.issue.get_iso("Issue Date"),
                "expiry_date": self.expiry.get_iso("Expiry Date"), "issuer": self.issuer.get(),
                "admin_status": self.status.get(), "followup": self.followup.get(), "remarks": self.remarks.get()}
        if self.mode == "renew":
            if not data["expiry_date"]:
                raise ValidationError("Please enter the Expiry Date of the renewed certificate.")
            return self.db.save_certificate(self.token_id, data, action="renew")
        try:
            return self.db.save_certificate(self.token_id, data)
        except CertificateConflict as exc:
            cur = exc.current
            ans = messagebox.askyesnocancel(
                "Certificate changed",
                f"The serial number or expiry of the existing certificate is being changed\n"
                f"(currently {cur['cert_serial'] or '-'}, expiry {dates.to_display_dt(cur['expiry_date']) or '-'}).\n\n"
                "YES  - this is a RENEWED / replacement certificate (the old one is kept in history)\n"
                "NO   - this is a CORRECTION of a data-entry mistake (a note is added to remarks)\n"
                "CANCEL - go back", parent=self)
            if ans is None:
                return None
            return self.db.save_certificate(self.token_id, data, action="renew" if ans else "correct")


class CertHistoryDialog(Dialog):
    def __init__(self, parent, db, token_id):
        token = db.get_token(token_id)
        super().__init__(parent, f"Certificate History - Token {token['token_serial']}")
        self.resizable(True, True)
        table = DataTable(self.form, [
            ("cert_id", "Cert ID", 60, "num"), ("cert_serial", "Certificate Serial", 150),
            ("issue_date", "Issued", 140, "datetime"), ("expiry_date", "Expiry", 140, "datetime"),
            ("issuer", "Certifying Authority", 180), ("admin_status", "Admin Status", 120),
            ("state", "Record", 80), ("remarks", "Remarks", 240),
        ], height=8)
        table.pack(fill="both", expand=True)
        rows = db.certificate_history(token_id)
        for r in rows:
            r["state"] = "Current" if r["is_current"] else "Replaced"
        table.set_rows(rows, lambda r: None if r["is_current"] else "grey")
        if not rows:
            ttk.Label(self.form, text="No certificate details recorded for this token yet.").pack(pady=6)
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")


class TokenInactiveDialog(Dialog):
    """Mark a token Inactive (lost, replaced, damaged...). Ends custody if the firm holds it."""

    def __init__(self, parent, db, token_id):
        self.db, self.token = db, db.get_token(token_id)
        super().__init__(parent, "Mark Token Inactive")
        f = self.form
        t = self.token
        ttk.Label(f, text=f"Token {t['token_serial']}  |  {t['holder_name']} ({t['client_code']})",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        open_inw = db.open_inward_for_token(token_id)
        if open_inw:
            holder = db.holder_of(open_inw["inward_id"])
            ttk.Label(f, wraplength=460, justify="left", foreground="#c0392b", text=(
                f"The token is in the firm's custody (with {holder['holder_type']} {holder['holder_name']}). "
                "Marking it Inactive ends the custody and records who had it.")).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.reason = ttk.Combobox(f, values=INACTIVE_REASONS, width=30)
        self.reason.set("Lost")
        labeled(f, "Reason *", 2, 0, self.reason)
        self.note = tk.StringVar()
        labeled(f, "Details", 3, 0, ttk.Entry(f, textvariable=self.note, width=46))
        ttk.Label(f, text="e.g. where it was lost, client informed, revocation requested with the CA on ...\n"
                          "Date and time = now, from the system clock. An Inactive token leaves the expiry alerts.",
                  style="Muted.TLabel", justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Mark Inactive")

    def save(self):
        reason = self.reason.get().strip()
        if self.note.get().strip():
            reason = f"{reason} - {self.note.get().strip()}" if reason else self.note.get().strip()
        self.db.set_token_inactive(self.token["token_id"], reason)
        return True


class ReplaceTokensDialog(Dialog):
    """A new token arrived for a client who already has active tokens: which ones does it replace?"""

    def __init__(self, parent, client, new_serial, tokens):
        super().__init__(parent, "New token for this client")
        f = self.form
        ttk.Label(f, wraplength=520, justify="left", text=(
            f"Token {new_serial} is NEW - it has not been recorded before.\n"
            f"{client['holder_name']} ({client['client_code']}) already has the active token(s) below. "
            "Tick any token that this new one replaces; it will be marked Inactive "
            "(\"Replaced by new token\") and leave the expiry alerts.")).pack(anchor="w", pady=(0, 8))
        self.vars = []
        for t in tokens:
            exp = dates.to_display_dt(t["expiry_date"]) or "expiry not recorded"
            due = t["days"] is not None and t["days"] <= 30
            var = tk.BooleanVar(value=due)
            text = f"{t['token_serial']}  -  {t['holder_name']}  -  {t['expiry_status']} ({exp})"
            if t["in_custody"]:
                text += "  -  in custody"
            ttk.Checkbutton(f, text=text, variable=var).pack(anchor="w", pady=2)
            self.vars.append((t["token_id"], var))
        self.buttons("Save Inward Entry")

    def save(self):
        return [tid for tid, var in self.vars if var.get()]


class ImportPreviewDialog(Dialog):
    """What importing the Excel file will do, row by row, before anything is saved."""

    def __init__(self, parent, db, plan, filename):
        super().__init__(parent, "Import Clients from Excel")
        self.resizable(True, True)
        self.db, self.plan = db, plan
        n_import = sum(1 for r in plan if r["action"] == "Import")
        n_skip = len(plan) - n_import
        n_note = sum(1 for r in plan if r["action"] == "Import" and r["reason"])
        ttk.Label(self.form, text=f"File: {filename}", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(self.form, font=("Segoe UI", 11, "bold"), text=(
            f"{n_import} of {len(plan)} row(s) will be imported"
            f"{f' ({n_note} with a note)' if n_note else ''};  {n_skip} will be skipped.")).pack(anchor="w", pady=4)
        ttk.Label(self.form, style="Muted.TLabel", text=(
            "Skipped: name or mobile missing, invalid mobile number, or the client already exists. "
            "Nothing is saved until you click Import.")).pack(anchor="w", pady=(0, 6))
        self.table = DataTable(self.form, [
            ("row", "Excel Row", 70, "num"), ("action", "Result", 70), ("holder_name", "DSC Holder Name", 190),
            ("mobile", "Mobile", 100), ("firm_name", "Firm/Company", 180), ("pan", "PAN", 95),
            ("reason", "Reason / Note", 380)], height=16)
        self.table.pack(fill="both", expand=True)
        self.table.set_rows(plan, lambda r: "red" if r["action"] == "Skip" else ("yellow" if r["reason"] else "green"))
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save This Report…",
                   command=lambda: self.table.export_csv("Client_Import_Report")).pack(side="left")
        ttk.Button(bar, text="Cancel", command=self.cancel).pack(side="right")
        b = ttk.Button(bar, text=f"Import {n_import} Client(s)", style="Accent.TButton", command=self.ok)
        b.pack(side="right", padx=6)
        if not n_import:
            b.state(["disabled"])

    def save(self):
        return self.db.apply_client_import(self.plan)


class StartupSummaryDialog(Dialog):
    """Shown when the app opens: what needs attention today, each with a button to go there."""

    def __init__(self, app, items):
        super().__init__(app, "Needs attention today")
        self.app = app
        ttk.Label(self.form, text=f"Good {_part_of_day()}! Today ({dates.to_display(dates.today_iso())}):",
                  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, (text, screen, options) in enumerate(items, start=1):
            ttk.Label(self.form, text=f"•  {text}", font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Button(self.form, text="Open", width=8,
                       command=lambda s=screen, o=options: self._open(s, o)).grid(row=i, column=1, padx=(16, 0))
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Button(bar, text="Close", style="Accent.TButton", command=self.destroy).pack(side="right")

    def _open(self, screen, options):
        self.destroy()
        self.app.show(screen, **options)


def _part_of_day():
    hour = dates.now().hour
    return "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")


class ClientDetailDialog(Dialog):
    """Everything about one client on one screen: details, tokens, history and awaited DSCs."""

    def __init__(self, parent, db, client_id, app):
        self.db, self.client_id, self.app = db, client_id, app
        super().__init__(parent, "Client Details")
        self.resizable(True, True)
        self.head = ttk.Frame(self.form)
        self.head.pack(fill="x")
        nb = ttk.Notebook(self.form)
        nb.pack(fill="both", expand=True, pady=(10, 0))
        t1, t2, t3 = (ttk.Frame(nb, padding=6) for _ in range(3))
        nb.add(t1, text="  DSC Tokens  ")
        nb.add(t2, text="  History  ")
        nb.add(t3, text="  Awaited DSCs  ")
        self.tokens = DataTable(t1, [
            ("token_serial", "Token Serial", 140), ("holder_name", "DSC Holder", 160),
            ("status_text", "Token Status", 180), ("expiry_date", "Expiry", 140, "datetime"),
            ("expiry_status", "Expiry Status", 150), ("with_label", "Currently With", 190)], height=8,
            on_double=lambda r: TokenHistoryDialog(self, self.db, r["token_id"]).show(),
            empty_text="No DSC tokens recorded for this client yet.")
        self.tokens.pack(fill="both", expand=True)
        ttk.Label(t1, text="Double-click a token for its full history.", style="Muted.TLabel").pack(anchor="w")
        self.history = DataTable(t2, [
            ("at", "Date / Time", 145, "datetime"), ("token_serial", "Token", 120), ("event", "Event", 220),
            ("from", "From", 150), ("to", "To", 170), ("details", "Details", 220)], height=10,
            empty_text="No history yet.")
        self.history.pack(fill="both", expand=True)
        self.awaited = DataTable(t3, [
            ("expected_id", "Request", 60, "num"), ("purpose", "Purpose", 120), ("expected_date", "Expected By", 95, "date"),
            ("await_status", "Status", 150), ("followup_staff", "Follow-up Staff", 130), ("remarks", "Remarks", 240)],
            height=8, empty_text="No DSCs awaited from this client.")
        self.awaited.pack(fill="both", expand=True)
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Button(bar, text="Edit Client…", command=self._edit).pack(side="left")
        ttk.Button(bar, text="Record Inward", command=self._inward).pack(side="left", padx=6)
        ttk.Button(bar, text="Add Expected DSC…", command=self._expected).pack(side="left")
        ttk.Button(bar, text="Close", style="Accent.TButton", command=self.destroy).pack(side="right")
        self.refresh()

    def refresh(self):
        c = self.db.get_client(self.client_id)
        for w in self.head.winfo_children():
            w.destroy()
        ttk.Label(self.head, text=f"{c['client_code']} - {c['holder_name']}", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w")
        facts = [("Firm/Company", c["firm_name"] or "-"), ("PAN", c["pan"] or "PAN pending"),
                 ("Mobile", c["mobile"] or "-"), ("Email", c["email"] or "-"), ("Status", c["status"]),
                 ("Remarks", c["remarks"] or "-")]
        for i, (label, value) in enumerate(facts):
            ttk.Label(self.head, text=f"{label}:", style="Muted.TLabel").grid(row=1 + i // 3, column=(i % 3) * 2,
                                                                              sticky="w", padx=(0, 4), pady=2)
            ttk.Label(self.head, text=value).grid(row=1 + i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=(0, 24))
        held = {r["token_id"]: r["with_label"] for r in self.db.custody_register({"client_id": self.client_id})}
        tokens = self.db.tokens_for_client(self.client_id)
        for t in tokens:
            t["with_label"] = held.get(t["token_id"], "-")
        self.tokens.set_rows(tokens, lambda t: "cancelled" if t["status"] == "Inactive" else None)
        events = []
        for t in tokens:
            for e in self.db.token_history(t["token_id"]):
                events.append(dict(e, token_serial=t["token_serial"]))
        events.sort(key=lambda e: e["at"] or "", reverse=True)
        self.history.set_rows(events, lambda e: "cancelled" if e["status"] == "Cancelled" else None)
        self.awaited.set_rows(self.db.awaited_list({"client_id": self.client_id}))

    def _edit(self):
        if ClientDialog(self, self.db, self.db.get_client(self.client_id)).show():
            self.refresh()

    def _inward(self):
        self.destroy()
        self.app.show("inward", client_id=self.client_id)

    def _expected(self):
        if ExpectedDialog(self, self.db, self.client_id).show():
            self.refresh()


class TokenHistoryDialog(Dialog):
    """Full chain of custody of one token: inward, every movement, outward."""

    def __init__(self, parent, db, token_id):
        token = db.get_token(token_id)
        super().__init__(parent, f"Token History - {token['token_serial']} ({token['holder_name']})")
        self.resizable(True, True)
        table = DataTable(self.form, [
            ("at", "Date / Time", 150, "datetime"), ("event", "Event", 210), ("from", "From", 170),
            ("to", "To", 200), ("details", "Details", 260), ("status", "Status", 90),
        ], height=14)
        table.pack(fill="both", expand=True)
        table.set_rows(db.token_history(token_id),
                       lambda r: "cancelled" if r["status"] == "Cancelled" else
                       ("grey" if r["status"] == "Superseded" else None))
        bar = ttk.Frame(self, padding=(16, 0, 16, 14))
        bar.pack(fill="x")
        ttk.Label(bar, text="Movement times are stamped automatically from the system clock.",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")


# ---------------------------------------------------------------------- movements
def _token_line(row):
    return f"Token {row['token_serial']}  |  {row['holder_name']} ({row['client_code']})"


class IssueToStaffDialog(Dialog):
    def __init__(self, parent, db, row):
        super().__init__(parent, "Issue Token to Staff")
        self.db, self.row = db, row
        f = self.form
        custodian = db.current_custodian()
        ttk.Label(f, text=_token_line(row), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2,
                                                                                  sticky="w", pady=(0, 6))
        labeled(f, "From (custodian)", 1, 0, ttk.Label(f, text=custodian["name"] if custodian else "-"))
        self.staff = ttk.Combobox(f, values=db.list_staff(), width=28)
        combo_autocomplete(self.staff)
        labeled(f, "Issue to (staff) *", 2, 0, self.staff)
        self.purpose = ttk.Combobox(f, values=PURPOSES, width=26)
        self.purpose.set(row["purpose"])
        labeled(f, "Purpose", 3, 0, self.purpose)
        self.due = DateTimeEntry(f)
        self.due.set_iso(f"{dates.today_iso()} 23:59:00")
        labeled(f, "Expected back by", 4, 0, self.due)
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 5, 0, ttk.Entry(f, textvariable=self.remarks, width=46))
        ttk.Label(f, text=f"Date and time of issue = now ({dates.to_display_dt(dates.now_iso())}), "
                          "taken from the system clock.", style="Muted.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Issue Token")

    def save(self):
        return self.db.issue_to_staff(self.row["inward_id"], self.staff.get(), self.purpose.get(),
                                      self.due.get_iso("Expected back by"), self.remarks.get())


class HandToConsultantDialog(Dialog):
    def __init__(self, parent, db, row):
        super().__init__(parent, "Hand Token to Consultant")
        self.db, self.row = db, row
        f = self.form
        ttk.Label(f, text=_token_line(row), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2,
                                                                                  sticky="w", pady=(0, 6))
        cf = ttk.Frame(f)
        self.consultant = ttk.Combobox(cf, state="readonly", width=40)
        self.consultant.pack(side="left")
        ttk.Button(cf, text="+ New", width=6, command=self._new).pack(side="left", padx=4)
        labeled(f, "Consultant *", 1, 0, cf)
        self.purpose = ttk.Combobox(f, values=PURPOSES, width=26)
        self.purpose.set("ROC Filing" if row["purpose"] == "ROC Filing" else row["purpose"])
        labeled(f, "Purpose", 2, 0, self.purpose)
        self.due = DateTimeEntry(f)
        labeled(f, "Expected back by", 3, 0, self.due)
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 4, 0, ttk.Entry(f, textvariable=self.remarks, width=46))
        ttk.Label(f, text="Date and time of hand-over = now, taken from the system clock.",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._load()
        self.buttons("Hand Over")

    def _load(self, select_id=None):
        self._items = self.db.list_consultants(active_only=True)
        self.consultant["values"] = [f"{c['name']} ({c['kind']}{', ' + c['firm'] if c['firm'] else ''})"
                                     for c in self._items]
        if select_id:
            idx = next((i for i, c in enumerate(self._items) if c["consultant_id"] == select_id), None)
            if idx is not None:
                self.consultant.current(idx)

    def _new(self):
        cid = ConsultantDialog(self, self.db).show()
        if cid:
            self._load(cid)

    def save(self):
        i = self.consultant.current()
        if i < 0:
            raise ValidationError("Please select the consultant (or add a new one).")
        return self.db.hand_to_consultant(self.row["inward_id"], self._items[i]["consultant_id"],
                                          self.purpose.get(), self.due.get_iso("Expected back by"),
                                          self.remarks.get())


class ClientCollectedDialog(Dialog):
    def __init__(self, parent, db, row):
        super().__init__(parent, "Client Collected Token from Consultant")
        self.db, self.row = db, row
        f = self.form
        ttk.Label(f, text=_token_line(row), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2,
                                                                                  sticky="w", pady=(0, 6))
        labeled(f, "Consultant", 1, 0, ttk.Label(f, text=row["with_name"]))
        self.collected_by = tk.StringVar(value=row["holder_name"])
        labeled(f, "Collected by *", 2, 0, ttk.Entry(f, textvariable=self.collected_by, width=40))
        self.remarks = tk.StringVar()
        labeled(f, "Note", 3, 0, ttk.Entry(f, textvariable=self.remarks, width=46))
        self.wa = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Send WhatsApp message to the client", variable=self.wa).grid(
            row=4, column=1, sticky="w")
        ttk.Label(f, text="This ends the firm's custody of the token (recorded as returned to the client\n"
                          "through the consultant). Date and time = now, from the system clock.",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Record")

    def save(self):
        self.send_whatsapp = self.wa.get()
        return self.db.client_collected_from_consultant(self.row["inward_id"], self.collected_by.get(),
                                                        self.remarks.get())


class ConsultantDialog(Dialog):
    def __init__(self, parent, db, consultant=None):
        super().__init__(parent, "Edit Consultant" if consultant else "Add Consultant")
        self.db, self.consultant = db, consultant
        f = self.form
        src = consultant or {}
        self.vars = {k: tk.StringVar(value=src.get(k) or "") for k in ("name", "firm", "mobile", "email", "remarks")}
        labeled(f, "Name *", 0, 0, ttk.Entry(f, textvariable=self.vars["name"], width=36))
        labeled(f, "Firm", 1, 0, ttk.Entry(f, textvariable=self.vars["firm"], width=36))
        self.kind = ttk.Combobox(f, values=CONSULTANT_KINDS, state="readonly", width=12)
        self.kind.set(src.get("kind") or "CS")
        labeled(f, "Type", 2, 0, self.kind)
        labeled(f, "Mobile", 3, 0, ttk.Entry(f, textvariable=self.vars["mobile"], width=18))
        labeled(f, "Email", 4, 0, ttk.Entry(f, textvariable=self.vars["email"], width=36))
        labeled(f, "Remarks", 5, 0, ttk.Entry(f, textvariable=self.vars["remarks"], width=46))
        self.buttons()

    def save(self):
        data = {k: v.get() for k, v in self.vars.items()}
        data["kind"] = self.kind.get()
        if self.consultant:
            self.db.update_consultant(self.consultant["consultant_id"], data)
            return self.consultant["consultant_id"]
        return self.db.add_consultant(data)


class AppointCustodianDialog(Dialog):
    def __init__(self, parent, db):
        super().__init__(parent, "Appoint Custodian")
        self.db = db
        f = self.form
        current = db.current_custodian()
        held = sum(1 for r in db.custody_register() if r["with_type"] == "custodian")
        if current:
            msg = (f"Current custodian: {current['name']} (since {dates.to_display_dt(current['appointed_at'])}).\n"
                   f"On saving, {current['name']} is relieved and the {held} token(s) held by the custodian are "
                   "handed over to the new custodian. Tokens out with staff or consultants come back to the new "
                   "custodian.")
        else:
            msg = "No custodian is appointed yet. Every inward DSC goes to the custodian automatically."
        ttk.Label(f, text=msg, wraplength=460, justify="left").grid(row=0, column=0, columnspan=2, sticky="w",
                                                                     pady=(0, 8))
        self.name = tk.StringVar()
        e = labeled(f, "New custodian name *", 1, 0, ttk.Entry(f, textvariable=self.name, width=32))
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 2, 0, ttk.Entry(f, textvariable=self.remarks, width=40))
        ttk.Label(f, text="Appointment time = now, from the system clock.", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Appoint")
        e.focus_set()

    def save(self):
        return self.db.appoint_custodian(self.name.get(), self.remarks.get())


# ---------------------------------------------------------------------- correcting an entry
class CorrectEntryDialog(Dialog):
    """Correct an inward or outward entry. The client and token stay fixed; every change is kept with
    the old value, the new value and the reason (shown in Token History)."""

    def __init__(self, parent, db, kind, row):
        super().__init__(parent, f"Correct {kind.title()} #{row[f'{kind}_id']}")
        self.db, self.kind, self.row = db, kind, row
        f = self.form
        ttk.Label(f, text=f"Token {row['token_serial']}  -  {row['holder_name']}  ({row['client_code']})",
                  style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        r = 1
        # A return recorded by the system (collected from a consultant, token made inactive) keeps its date.
        self.date_fixed = kind == "outward" and (row.get("via_consultant_id") is not None
                                                 or row.get("returned_via") == "Token made inactive")
        if self.date_fixed:
            self.date = ttk.Label(f, text=f"{dates.to_display(row['outward_date'])}  (taken from the system clock)")
        else:
            self.date = DateEntry(f)
            self.date.set_iso(row[f"{kind}_date"])
        labeled(f, f"{kind.title()} Date *", r, 0, self.date)
        self.person = tk.StringVar(value=row["received_from" if kind == "inward" else "returned_to"] or "")
        labeled(f, "Received From *" if kind == "inward" else "Returned To *", r + 1, 0,
                ttk.Entry(f, textvariable=self.person, width=40))
        self.purpose = ttk.Combobox(f, values=PURPOSES, width=22, state="readonly" if kind == "inward" else "normal")
        self.purpose.set(row["purpose"] or "")
        labeled(f, "Purpose/Assignment *" if kind == "inward" else "Purpose", r + 2, 0, self.purpose)
        r += 3
        if kind == "inward":
            self.expected = DateEntry(f)
            self.expected.set_iso(row["expected_return_date"])
            labeled(f, "Expected Return Date", r, 0, self.expected)
            r += 1
        self.remarks = tk.StringVar(value=row["remarks"] or "")
        labeled(f, "Remarks", r, 0, ttk.Entry(f, textvariable=self.remarks, width=48))
        self.reason = tk.StringVar()
        reason = labeled(f, "Reason for correction *", r + 1, 0, ttk.Entry(f, textvariable=self.reason, width=48))
        ttk.Label(f, style="Muted.TLabel", wraplength=520, text=(
            "The client and token cannot be changed here - for a wrong client or token, cancel the entry and "
            "enter it again. The old and new values are kept in the token's history.")).grid(
            row=r + 2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        earlier = db.corrections_for(kind, row[f"{kind}_id"])
        if earlier:
            ttk.Label(f, style="Muted.TLabel", wraplength=520, text="Earlier corrections: " + "; ".join(
                f"{dates.to_display_dt(x['corrected_at'])} {db.correction_text(x['field'], x['old_value'], x['new_value'])}"
                for x in earlier)).grid(row=r + 3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.buttons("Save Correction")
        reason.focus_set()

    def save(self):
        data = {"received_from" if self.kind == "inward" else "returned_to": self.person.get(),
                "purpose": self.purpose.get(), "remarks": self.remarks.get()}
        if not self.date_fixed:
            data[f"{self.kind}_date"] = self.date.get_iso(f"{self.kind.title()} Date")
        if self.kind == "inward":
            data["expected_return_date"] = self.expected.get_iso("Expected Return Date")
            return self.db.correct_inward(self.row["inward_id"], data, self.reason.get())
        return self.db.correct_outward(self.row["outward_id"], data, self.reason.get())
