"""DSC Inward: record tokens received from clients."""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import dates, whatsapp
from ..database import (PURPOSES, CertificateConflict, DuplicateCustodyError, InactiveTokenError, ValidationError,
                        name_key)
from .base import Screen
from .dialogs import (CertHistoryDialog, CertificateDialog, ClientDialog, CorrectEntryDialog, ReplaceTokensDialog,
                      TokenHistoryDialog, read_token_details)
from .reports import RegisterPanel
from .widgets import (COLORS, ClientPicker, DateEntry, DateTimeEntry, Tooltip, ask_text, combo_autocomplete,
                      enter_moves_focus, labeled)

NO_REQUEST = "(Not against an awaited request)"


class InwardScreen(Screen):
    title = "DSC Inward"
    subtitle = "Record a DSC token received from a client"

    def build(self, body):
        self._token_prefilled, self._requests, self._auto_holder, self._from_token = None, [], "", False
        self._cert_action = "auto"
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        form_tab = ttk.Frame(self.nb, padding=(12, 6), style="Screen.TFrame")
        list_tab = ttk.Frame(self.nb, padding=8, style="Screen.TFrame")
        self.nb.add(form_tab, text="  New Inward Entry  ")
        self.nb.add(list_tab, text="  Previous Inward Entries  ")
        self._build_form(form_tab)
        self.register = RegisterPanel(list_tab, self, "inward", height=8, extra_buttons=[
            ("Update Certificate Details", lambda r: self._cert(r["token_id"], "edit")),
            ("Record Certificate Renewal", lambda r: self._cert(r["token_id"], "renew")),
            ("Certificate History", lambda r: CertHistoryDialog(self, self.db, r["token_id"]).show()),
            ("Token History", lambda r: TokenHistoryDialog(self, self.db, r["token_id"]).show()),
            ("Correct Entry…", self._correct),
            ("Cancel Entry", self._cancel),
            ("Return this DSC (Outward)", self._to_outward),
        ])
        self.register.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.nb.index("current") == 1 and self.register.refresh())
        self.register.set_filters()

    # ---------------------------------------------------------------- form
    def _build_form(self, tab):
        start = tk.Frame(tab, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"])
        start.pack(fill="x", pady=(0, 6))
        ttk.Button(start, text="Read from Token", style="Big.TButton", command=self._read_token).pack(
            side="left", padx=12, pady=4)
        tk.Label(start, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10), justify="left",
                 text="Start here: plug the client's DSC token into this PC and click Read from Token.\n"
                      "The token, holder and certificate details fill in by themselves - then choose the "
                      "purpose and save.").pack(side="left", padx=4)
        f = ttk.LabelFrame(tab, text=" Inward Details  (* mandatory) ", padding=(12, 2))
        f.pack(fill="x")
        self.inward_date = DateEntry(f, default_today=True)
        labeled(f, "Inward Date *", 0, 0, self.inward_date)
        cf = ttk.Frame(f)
        self.client = ClientPicker(cf, width=30, on_change=self._client_changed)
        self.client.pack(side="left")
        ttk.Button(cf, text="+ New", width=6, command=self._new_client).pack(side="left", padx=4)
        labeled(f, "Client *", 0, 2, cf)

        self.holder = tk.StringVar()
        labeled(f, "DSC Holder Name *", 1, 0, ttk.Entry(f, textvariable=self.holder, width=32))
        tf = ttk.Frame(f)
        self.token = ttk.Combobox(tf, width=22)
        self.token.pack(side="left")
        combo_autocomplete(self.token)
        ttk.Button(tf, text="Read from Token", command=self._read_token).pack(side="left", padx=4)
        self.token.bind("<<ComboboxSelected>>", lambda e: self._token_changed())
        self.token.bind("<FocusOut>", lambda e: self._token_changed())
        labeled(f, "Token Serial No. / Token ID *", 1, 2, tf)

        self.received_from = tk.StringVar()
        labeled(f, "Received From *", 2, 0, ttk.Entry(f, textvariable=self.received_from, width=32))
        self.custodian_lbl = tk.Label(f, anchor="w", bg=COLORS["bg"], font=("Segoe UI", 9, "bold"))
        labeled(f, "Goes to (custodian)", 2, 2, self.custodian_lbl)

        self.purpose = ttk.Combobox(f, values=PURPOSES, state="readonly", width=29)
        labeled(f, "Purpose/Assignment *", 3, 0, self.purpose)
        self.expected_return = DateEntry(f)
        labeled(f, "Expected Return Date", 3, 2, self.expected_return)

        self.request = ttk.Combobox(f, state="readonly", width=70)
        labeled(f, "Against Awaited Request", 4, 0, self.request, colspan=3)
        self.remarks = tk.StringVar()
        labeled(f, "Remarks", 5, 0, ttk.Entry(f, textvariable=self.remarks, width=88), colspan=3)

        self.token_info = tk.Label(f, text="", anchor="w", justify="left", bg=COLORS["bg"], font=("Segoe UI", 9, "bold"),
                                   wraplength=900)
        self.token_info.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        c = ttk.LabelFrame(tab, text=" Certificate Details (optional - can be entered or updated later) ", padding=(12, 2))
        c.pack(fill="x", pady=(6, 0))
        self.cert_serial = tk.StringVar()
        labeled(c, "Certificate Serial No.", 0, 0, ttk.Entry(c, textvariable=self.cert_serial, width=24))
        self.issuer = tk.StringVar()
        labeled(c, "Certifying Authority", 0, 2, ttk.Entry(c, textvariable=self.issuer, width=24))
        self.issue = DateTimeEntry(c)
        labeled(c, "Issue Date", 1, 0, self.issue)
        self.expiry = DateTimeEntry(c)
        labeled(c, "Expiry Date", 1, 2, self.expiry)
        ttk.Label(c, text="Use 'Read from Token' to fill these from the token plugged in. Time is optional "
                          "(e.g. 11:00 AM); without it, expiry is taken as 12:00 AM that day. "
                          "Never record DSC PINs or passwords.", style="Muted.TLabel").grid(
            row=2, column=0, columnspan=4, sticky="w")

        b = ttk.Frame(tab, style="Screen.TFrame")
        b.pack(fill="x", pady=(8, 2))
        ttk.Button(b, text="Save Inward Entry  (Ctrl+S)", style="Accent.TButton", command=self._save).pack(side="left")
        save_more = ttk.Button(b, text="Save & Add Another", command=lambda: self._save(add_another=True))
        save_more.pack(side="left", padx=6)
        Tooltip(save_more, "Save, then keep the client, date and purpose for the next token of the same client "
                           "(e.g. the directors' tokens).")
        ttk.Button(b, text="Clear Form", command=self._clear_form).pack(side="left")
        self.wa = tk.BooleanVar(value=True)
        ttk.Checkbutton(b, text="Send WhatsApp message to the client", variable=self.wa).pack(side="left", padx=16)
        enter_moves_focus(tab)  # Enter moves to the next field

    def _new_client(self):
        cid = ClientDialog(self, self.db, initial={"holder_name": self.holder.get()}).show()
        if cid:
            self.client.load(self.db.list_clients(status="Active"))
            self.client.set_id(cid)
            self._client_changed(cid)

    def _client_changed(self, cid, expected_id=None):
        c = self.db.get_client(cid) if cid else None
        prev = self._auto_holder
        if c:
            if self.holder.get() in ("", prev):
                self.holder.set(c["holder_name"])
            if self.received_from.get() in ("", prev):
                self.received_from.set(c["holder_name"])
            self._auto_holder = c["holder_name"]
            self.token["values"] = [t["token_serial"] for t in self.db.tokens_for_client(cid)]
        else:
            self.token["values"] = []
        self._load_requests(cid, expected_id)
        self._token_changed()

    def _load_requests(self, cid, expected_id=None):
        self._requests = self.db.awaited_for_client(cid) if cid else []
        labels = [NO_REQUEST] + [
            f"#{r['expected_id']} - {r['purpose']} - {r['holder_name']}"
            f"{' - token ' + r['token_serial'] if r['token_serial'] else ''}"
            f"{' - expected by ' + dates.to_display(r['expected_date']) if r['expected_date'] else ''}"
            for r in self._requests]
        self.request["values"] = labels
        pick = 0
        if expected_id:
            pick = next((i + 1 for i, r in enumerate(self._requests) if r["expected_id"] == expected_id), 0)
        elif len(self._requests) == 1:
            pick = 1  # only one pending request for this client - most likely this one
        self.request.current(pick)
        if pick and not self.purpose.get():
            self.purpose.set(self._requests[pick - 1]["purpose"])

    def _selected_request(self):
        i = self.request.current()
        return self._requests[i - 1]["expected_id"] if i and i > 0 else None

    def _token_changed(self):
        serial = self.token.get().strip().upper()
        t = self.db.find_token(serial) if serial else None
        cid = self.client.get_id()
        if not t:
            if not serial:
                self.token_info.configure(text="")
                return
            msg = f"NEW TOKEN - {serial} has not been recorded before."
            others = self.db.tokens_for_client(cid, active_only=True) if cid else []
            if others:
                msg += " This client's active token(s): " + "; ".join(
                    f"{o['token_serial']} ({o['expiry_status'].lower()})" for o in others)
                msg += ". On saving you can mark the token it replaces as Inactive."
            self.token_info.configure(fg=COLORS["orange"], text=msg)
            return
        if cid and t["client_id"] != cid:
            self.token_info.configure(fg=COLORS["red"], text=(
                f"⚠ Token {t['token_serial']} is registered to another client "
                f"({t['client_code']} - {t['client_holder']})."))
            return
        if self._token_prefilled != serial:
            cert = self.db.get_current_certificate(t["token_id"])
            if cert or not self._from_token:  # keep details just read from the token
                self.cert_serial.set((cert or {}).get("cert_serial") or "")
                self.issue.set_iso((cert or {}).get("issue_date"))
                self.expiry.set_iso((cert or {}).get("expiry_date"))
                self.issuer.set((cert or {}).get("issuer") or "")
            self._token_prefilled = serial
        open_inw = self.db.open_inward_for_token(t["token_id"])
        if t["status"] == "Inactive":
            self.token_info.configure(fg=COLORS["red"], text=(
                f"⚠ This token is marked INACTIVE ({t['inactive_reason']}). Saving will ask whether to make it "
                "Active again."))
        elif open_inw:
            self.token_info.configure(fg=COLORS["red"], text=(
                f"⚠ This token is ALREADY IN CUSTODY (Inward #{open_inw['inward_id']} dated "
                f"{dates.to_display(open_inw['inward_date'])}, received by {open_inw['received_by']})."))
        else:
            self.token_info.configure(fg=COLORS["green"],
                                      text="Known token, not currently in custody. Current certificate shown below.")
        for r in self._requests:  # match an awaited request for this exact token
            if r["token_serial"] and r["token_serial"].upper() == serial:
                self._load_requests(cid, r["expected_id"])
                break

    def _read_token(self):
        """Fill the token and certificate fields from the DSC token plugged in."""
        t = read_token_details(self)
        if not t:
            return
        self._from_token = True
        if t["token_serial"]:
            known = self.db.find_token(t["token_serial"])
            if known:  # a token we have seen before: its client is known
                self.client.set_id(known["client_id"])
                if self.client.get_id() is None:
                    self.error(f"Token {t['token_serial']} belongs to client {known['client_code']}, who is "
                               "Inactive. Mark the client Active first.")
                    return
                self._client_changed(known["client_id"])
            elif not self.client.get_id():
                match = [c for c in self.db.list_clients(status="Active")
                         if c["holder_name"].strip().lower() == t["holder_name"].strip().lower()]
                if len(match) == 1:
                    self.client.set_id(match[0]["client_id"])
                    self._client_changed(match[0]["client_id"])
            self.token.set(t["token_serial"])
        if t["holder_name"]:
            self.holder.set(t["holder_name"])
        self.cert_serial.set(t["cert_serial"])
        self.issue.set_iso(t["issue_date"])
        self.expiry.set_iso(t["expiry_date"])
        self.issuer.set(t["issuer"])
        self._token_prefilled = (t["token_serial"] or "").upper()
        self._token_changed()
        if not t["token_serial"]:  # read from the Windows certificate store: no hardware serial available
            self.token.focus_set()
            self.token_info.configure(fg=COLORS["orange"], text=(
                "Certificate details were read, but the token's serial number could not be (its driver is not "
                "installed). Type the Token Serial No. printed on the token, or install the driver and read again."))
            return
        if not self.client.get_id():
            self.token_info.configure(fg=COLORS["orange"], text=(
                f"Read from token: {t['holder_name']}. No matching client was found - select the client "
                "(or add a new one with '+ New')."))
            return
        self._compare_with_records(t)

    def _compare_with_records(self, t):
        """Tell the user whether the token plugged in is new, the same, or the same with a renewed certificate."""
        known = self.db.find_token(t["token_serial"]) if t["token_serial"] else None
        if not known or known["status"] == "Inactive" or self.db.open_inward_for_token(known["token_id"]):
            return  # new token / inactive / already in custody: _token_changed has said it
        cur = self.db.get_current_certificate(known["token_id"])
        on_token = f"serial {t['cert_serial'] or '-'}, expiry {dates.to_display_dt(t['expiry_date']) or '-'}"
        if not cur:
            msg, colour = f"KNOWN TOKEN (registered {dates.to_display(known['created_at'])}). Certificate read from " \
                          f"the token ({on_token}) will be recorded.", COLORS["green"]
        elif (cur["cert_serial"] or "").upper() == (t["cert_serial"] or "").upper():
            msg, colour = f"KNOWN TOKEN, SAME CERTIFICATE as on record ({on_token}).", COLORS["green"]
        else:
            old = f"serial {cur['cert_serial'] or '-'}, expiry {dates.to_display_dt(cur['expiry_date']) or '-'}"
            newer = t["expiry_date"] and (not cur["expiry_date"] or
                                          dates.iso_to_datetime(t["expiry_date"]) > dates.iso_to_datetime(cur["expiry_date"]))
            if newer:
                self._cert_action = "renew"
                msg = (f"KNOWN TOKEN with a RENEWED CERTIFICATE. On record: {old}. On the token: {on_token}. "
                       "It will be saved as a renewal (the old certificate stays in history).")
            else:
                msg = (f"KNOWN TOKEN, but its certificate differs from the record ({old}; token: {on_token}). "
                       "You will be asked what to do when saving.")
            colour = COLORS["orange"]
        client = self.db.get_client(self.client.get_id())
        if client and t["holder_name"] and name_key(t["holder_name"]) != name_key(client["holder_name"]):
            msg += f"  Note: certificate holder '{t['holder_name']}' differs from client '{client['holder_name']}'."
        self.token_info.configure(fg=colour, text=msg)

    def _clear_form(self):
        self.inward_date.set_iso(dates.today_iso())
        self.client.set_id(None)
        for v in (self.holder, self.received_from, self.remarks, self.cert_serial, self.issuer):
            v.set("")
        self.token.set("")
        self.token["values"] = []
        self.purpose.set("")
        self.expected_return.clear()
        self.issue.clear()
        self.expiry.clear()
        self._auto_holder = ""
        self._token_prefilled = None
        self._from_token = False
        self._cert_action = "auto"
        self._load_requests(None)
        self.token_info.configure(text="")

    def _collect(self):
        data = {
            "client_id": self.client.get_id(),
            "inward_date": self.inward_date.get_iso("Inward Date", required=True),
            "holder_name": self.holder.get(), "token_serial": self.token.get(),
            "received_from": self.received_from.get(),
            "purpose": self.purpose.get(),
            "expected_return_date": self.expected_return.get_iso("Expected Return Date"),
            "remarks": self.remarks.get(), "expected_id": self._selected_request(),
        }
        if not data["client_id"]:
            raise ValidationError("Please select the client from the list (type to search).")
        cert = {"cert_serial": self.cert_serial.get(), "issue_date": self.issue.get_iso("Certificate Issue Date"),
                "expiry_date": self.expiry.get_iso("Certificate Expiry Date"), "issuer": self.issuer.get()}
        return data, cert

    def _save(self, add_another=False):
        ok, collected = self.run(self._collect)
        if not ok:
            return
        data, cert = collected
        replaces = []
        if not self.db.find_token(data["token_serial"]):  # a new token: does it replace an older one?
            others = self.db.tokens_for_client(data["client_id"], active_only=True)
            if others:
                client = self.db.get_client(data["client_id"])
                replaces = ReplaceTokensDialog(self, client, data["token_serial"].strip().upper(), others).show()
                if replaces is None:
                    return
        allow_dup, action, reactivate = False, self._cert_action, False
        while True:
            try:
                new_id = self.db.save_inward(data, allow_duplicate=allow_dup, cert=cert, cert_action=action,
                                             reactivate=reactivate, replaces=replaces)
                break
            except InactiveTokenError as exc:
                if not messagebox.askyesno(
                        "Token marked Inactive",
                        f"Token {exc.token['token_serial']} is marked Inactive "
                        f"({exc.token['inactive_reason']}).\n\nMake it Active again and record this receipt?",
                        icon="warning", parent=self):
                    return
                reactivate = True
            except DuplicateCustodyError as exc:
                o = exc.open_inward
                if not messagebox.askyesno(
                        "Token already in custody",
                        f"Token {o['token_serial']} is already in the firm's custody\n"
                        f"(Inward #{o['inward_id']} dated {dates.to_display(o['inward_date'])}, "
                        f"received by {o['received_by']}).\n\n"
                        "Record this receipt anyway?\nThe earlier receipt will be marked 'Superseded' so the "
                        "token is counted only once in live custody.", icon="warning", parent=self):
                    return
                allow_dup = True
            except CertificateConflict as exc:
                cur = exc.current
                ans = messagebox.askyesnocancel(
                    "Certificate details differ",
                    f"The certificate details entered differ from the certificate on record for this token\n"
                    f"(serial {cur['cert_serial'] or '-'}, expiry {dates.to_display_dt(cur['expiry_date']) or '-'}).\n\n"
                    "YES  - record as a RENEWED / new certificate (old details kept in history)\n"
                    "NO   - keep the existing certificate unchanged and save the inward entry\n"
                    "CANCEL - go back and check", parent=self)
                if ans is None:
                    return
                action = "renew" if ans else "keep"
            except (ValidationError, ValueError) as exc:
                self.error(str(exc))
                return
        custodian = self.db.current_custodian()
        extra = f" {len(replaces)} older token(s) marked Inactive (replaced)." if replaces else ""
        sent = self.wa.get() and self.send_whatsapp(whatsapp.for_inward(self.db, new_id), quiet=True)
        msg = (f"Inward #{new_id} saved: token {data['token_serial'].upper()} is with the custodian, "
               f"{custodian['name']}.{extra}" + (" WhatsApp opened - press Send." if sent else ""))
        # Undo = cancel this entry (kept in the register as Cancelled). Not offered when older tokens
        # were retired by it, since that would need more than a cancellation to reverse.
        undo = None if replaces else (lambda: self.db.cancel_inward(new_id, "Undone straight after entry"))
        self.app.toast(msg, undo=undo)
        if add_another:
            self._next_token_same_client()
        else:
            self._clear_form()
        self.app.refresh_dashboard()

    def _next_token_same_client(self):
        """Save & Add Another: keep client, date, purpose and return date; clear the token part."""
        cid = self.client.get_id()
        for v in (self.cert_serial, self.issuer, self.remarks):
            v.set("")
        self.token.set("")
        self.issue.clear()
        self.expiry.clear()
        self._token_prefilled, self._from_token, self._cert_action = None, False, "auto"
        self._client_changed(cid)
        self.holder.set(self.db.get_client(cid)["holder_name"])
        self.token_info.configure(fg=COLORS["muted"], text="Same client - plug in the next token and click "
                                                          "Read from Token, or type its serial number.")
        self.token.focus_set()

    # ---------------------------------------------------------------- list actions
    def _cert(self, token_id, mode):
        if CertificateDialog(self, self.db, token_id, mode).show():
            self.register.refresh()
            self.app.refresh_dashboard()

    def _correct(self, row):
        if row["status"] == "Cancelled":
            self.error(f"Inward #{row['inward_id']} is cancelled and cannot be corrected.")
            return
        changes = CorrectEntryDialog(self, self.db, "inward", row).show()
        if changes:
            self.app.toast(f"Inward #{row['inward_id']} corrected: " + "; ".join(changes))
            self.register.refresh()
            self.app.refresh_dashboard()

    def _cancel(self, row):
        if row["status"] != "Active":
            self.error(f"Inward #{row['inward_id']} is already {row['status']}.")
            return
        reason = ask_text(self, "Cancel Inward Entry",
                          f"Cancel inward #{row['inward_id']} (token {row['token_serial']})?\n"
                          "The entry is kept in the register marked 'Cancelled'.\n\nReason for cancellation:")
        if reason and self.run(self.db.cancel_inward, row["inward_id"], reason)[0]:
            self.register.refresh()
            self.app.refresh_dashboard()

    def _to_outward(self, row):
        if row["custody"] != "In Custody":
            self.error(f"Token {row['token_serial']} is not in custody under this entry ({row['custody']}).")
            return
        self.app.show("outward", inward_id=row["inward_id"])

    # ----------------------------------------------------------------
    def on_ctrl_s(self):
        if self.nb.index("current") == 0:
            self._save()

    def refresh(self):
        self.register.refresh()

    def reset_filters(self):
        """Clears the Previous Entries filters; a half-filled new entry is kept."""
        self.register.reset()
        self.nb.select(0)

    def on_show(self, client_id=None, expected_id=None, **kw):
        self.client.load(self.db.list_clients(status="Active"))
        c = self.db.current_custodian()
        self.custodian_lbl.configure(text=c["name"] if c else "No custodian appointed - appoint one first",
                                     fg=COLORS["text"] if c else COLORS["red"])
        self.register.reload_lists()
        if client_id:
            self.nb.select(0)
            self.client.set_id(client_id)
            self._client_changed(client_id, expected_id)
        if self.nb.index("current") == 1:
            self.register.refresh()
