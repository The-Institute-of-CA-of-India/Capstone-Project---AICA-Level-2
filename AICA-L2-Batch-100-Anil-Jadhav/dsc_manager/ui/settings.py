"""Settings: the custodian, staff and consultants, WhatsApp message wording, the Google Sheet for the partners, text size and
DSC token drivers."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import webbrowser

from .. import config, dates, firm_info, gsheet, token_reader, whatsapp
from .base import Screen
from .handlers import HandlersPanel

TEXT_SIZES = {"Normal": 1.0, "Large": 1.15}


class SettingsScreen(Screen):
    title = "Settings"
    subtitle = "Custodian, staff and consultants, WhatsApp messages, Google Sheet for the partners, text size and DSC token drivers"

    def build(self, body):
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        tabs = {}
        for key, text in (("dh", "  Custodian, Staff & Consultants  "), ("wa", "  WhatsApp Messages  "),
                          ("gs", "  Google Sheet for Partners  "),
                          ("pc", "  Token Drivers & Text Size  ")):
            tabs[key] = ttk.Frame(self.nb, padding=10, style="Screen.TFrame")
            self.nb.add(tabs[key], text=text)
        self.handlers = HandlersPanel(tabs["dh"], self)
        self.handlers.pack(fill="both", expand=True)
        self._build_sheet(tabs["gs"])
        wa = ttk.LabelFrame(tabs["wa"], text=" WhatsApp Messages to Clients ", padding=12)
        wa.pack(fill="x")
        top = ttk.Frame(wa)
        top.pack(fill="x")
        ttk.Label(top, text="Message:").pack(side="left")
        self.kind = ttk.Combobox(top, state="readonly", width=34, values=list(whatsapp.KINDS.values()))
        self.kind.current(0)
        self.kind.pack(side="left", padx=6)
        self.kind.bind("<<ComboboxSelected>>", lambda e: self._load_template())
        ttk.Label(top, style="Muted.TLabel", text=(
            "The app opens WhatsApp with the client's number and this message typed in; you press Send.")).pack(
            side="left", padx=12)
        mid = ttk.Frame(wa)
        mid.pack(fill="x", pady=8)
        self.text = tk.Text(mid, height=7, width=72, wrap="word", font=("Segoe UI", 10), relief="solid", borderwidth=1)
        self.text.pack(side="left")
        help_box = ttk.Frame(mid)
        help_box.pack(side="left", padx=16, anchor="n")
        ttk.Label(help_box, text="Blanks filled in for each message:", style="Section.TLabel").pack(anchor="w")
        for key, meaning in whatsapp.PLACEHOLDERS:
            ttk.Label(help_box, text=f"{key}  -  {meaning}").pack(anchor="w")
        if not firm_info.FIRM_NAME:
            ttk.Label(help_box, style="Muted.TLabel", text="({firm} is empty when running from the source code.)").pack(
                anchor="w", pady=(4, 0))
        how = ttk.Frame(wa)
        how.pack(fill="x", pady=(0, 8))
        ttk.Label(how, text="Open messages in:").pack(side="left")
        self.mode = tk.StringVar()
        installed = whatsapp.desktop_installed()
        ttk.Radiobutton(how, variable=self.mode, value="desktop", command=self._mode_changed,
                        text="WhatsApp Desktop app" + (" (recommended - installed)" if installed
                                                      else " (not installed on this PC)")).pack(side="left", padx=8)
        ttk.Radiobutton(how, variable=self.mode, value="web", command=self._mode_changed,
                        text="WhatsApp Web in the browser (opens a new tab for each message)").pack(side="left")
        bar = ttk.Frame(wa)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save Message", style="Accent.TButton", command=self._save_template).pack(side="left")
        ttk.Button(bar, text="Back to Default Wording", command=self._reset_template).pack(side="left", padx=6)
        ttk.Button(bar, text="Preview", command=self._preview).pack(side="left")

        lower = ttk.Frame(tabs["pc"], style="Screen.TFrame")
        lower.pack(fill="x")
        ts = ttk.LabelFrame(lower, text=" Text Size ", padding=12)
        ts.pack(side="left", fill="both")
        self.size = tk.StringVar()
        for name in TEXT_SIZES:
            ttk.Radiobutton(ts, text=name, value=name, variable=self.size, command=self._size_changed).pack(anchor="w")
        ttk.Label(ts, style="Muted.TLabel", text="Takes effect the next time\nthe app is started (this PC).").pack(
            anchor="w", pady=(6, 0))

        tbox = ttk.LabelFrame(lower, text=" DSC Token Drivers (used by 'Read from Token') ", padding=12)
        tbox.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(tbox, wraplength=820, text=(
            "Drivers of common DSC tokens (ePass2003/HYP2003, ProxKey, mToken, Trust Key, Watchdata, SafeNet, "
            "Gemalto and others) are found automatically in the Windows system folder. Add a driver's DLL file "
            "here only if a token of another brand is not detected. Saved for this PC.")).pack(anchor="w")
        drow = ttk.Frame(tbox)
        drow.pack(fill="x", pady=(6, 0))
        self.driver_list = tk.Listbox(drow, height=3, width=80)
        self.driver_list.pack(side="left")
        dbtn = ttk.Frame(drow)
        dbtn.pack(side="left", padx=8, anchor="n")
        ttk.Button(dbtn, text="Add Driver DLL…", command=self._add_driver).pack(fill="x")
        ttk.Button(dbtn, text="Remove", command=self._remove_driver).pack(fill="x", pady=4)
        ttk.Button(dbtn, text="Test: Read Tokens Now", command=self._test_tokens).pack(fill="x")
        self.driver_status = ttk.Label(tbox, style="Muted.TLabel")
        self.driver_status.pack(anchor="w", pady=(6, 0))

    # ---------------------------------------------------------------- Google Sheet
    SHEET_STEPS = [
        "1.  Sign in to the firm's Google account and create a new, blank Google Sheet (Open Google Sheets).",
        "2.  In the sheet: Extensions > Apps Script. Delete what is there, paste the script (Copy Script), "
        "click Save.",
        "3.  Deploy > New deployment > select type 'Web app'. Execute as: Me. Who has access: Anyone. Click "
        "Deploy and allow access (if Google warns 'unverified app': Advanced > Go to ... (unsafe) - it is "
        "your own script).",
        "4.  Copy the 'Web app' URL, paste it below and click Save & Test.",
        "5.  Share the sheet with the partners as Viewer. They can sort and filter; they cannot change it.",
    ]

    def _build_sheet(self, f):
        box = ttk.LabelFrame(f, text=" Google Sheet for the Partners ", padding=12)
        box.pack(fill="x")
        ttk.Label(box, wraplength=1000, text=(
            "This PC sends every report to a Google Sheet - DSC in Custody, DSC Awaited, Expiry Alerts, the "
            "Inward, Outward and Movement registers, Holdings by Person and Clients, one tab each with filters, "
            "plus a Dashboard tab - so the partners can check them from their own desks. The sheet is updated "
            "about a minute after each entry and every time the app starts. PAN and mobile numbers are masked "
            "in the sheet. Changes made in the sheet do not come back to this app.")).pack(anchor="w")
        steps = ttk.LabelFrame(f, text=" Setting it up (once) ", padding=12)
        steps.pack(fill="x", pady=(10, 0))
        for line in self.SHEET_STEPS:
            ttk.Label(steps, text=line, wraplength=1000).pack(anchor="w", pady=1)
        sb = ttk.Frame(steps)
        sb.pack(fill="x", pady=(8, 0))
        ttk.Button(sb, text="Open Google Sheets", command=lambda: webbrowser.open("https://sheets.new")).pack(
            side="left")
        ttk.Button(sb, text="Copy Script", style="Accent.TButton", command=self._copy_script).pack(
            side="left", padx=6)

        link = ttk.LabelFrame(f, text=" Web app link ", padding=12)
        link.pack(fill="x", pady=(10, 0))
        row = ttk.Frame(link)
        row.pack(fill="x")
        self.sheet_url = tk.StringVar()
        ttk.Entry(row, textvariable=self.sheet_url, width=100).pack(side="left")
        ttk.Button(row, text="Save & Test", style="Accent.TButton", command=self._save_sheet).pack(
            side="left", padx=6)
        acts = ttk.Frame(link)
        acts.pack(fill="x", pady=(8, 0))
        ttk.Button(acts, text="Update Google Sheet Now", command=self._update_sheet).pack(side="left")
        ttk.Button(acts, text="Stop Updating", command=self._stop_sheet).pack(side="left", padx=6)
        self.sheet_status = ttk.Label(link, style="Muted.TLabel", wraplength=1000)
        self.sheet_status.pack(anchor="w", pady=(8, 0))

    def _show_sheet_status(self):
        st = gsheet.status(self.db)
        if not st["url"]:
            text = "Not set up yet - the reports are not being sent to a Google Sheet."
        else:
            text = ("Last updated: " + (dates.to_display_dt(st["last_ok"]) if st["last_ok"] else "not yet")
                    + ".  Updated automatically about a minute after each entry and when the app starts.")
            if st["last_error"]:
                text += f"\nLast problem: {st['last_error']}"
        self.sheet_status.configure(text=text)

    def _copy_script(self):
        self.clipboard_clear()
        self.clipboard_append(gsheet.script_text(self.db))
        self.info("The script is copied. In the Google Sheet open Extensions > Apps Script, delete what is "
                  "there, paste (Ctrl+V) and click Save. Then deploy it as a web app (step 3).", "Script copied", popup=True)

    def _save_sheet(self):
        ok, _ = self.run(gsheet.set_url, self.db, self.sheet_url.get())
        if not ok:
            return
        if not gsheet.get_url(self.db):
            self._show_sheet_status()
            return
        self.app.update_sheet(manual=True, on_done=lambda err: self._sheet_done(err, "The Google Sheet is set up"))

    def _update_sheet(self):
        if not gsheet.get_url(self.db):
            self.error("Paste the Web app link and click Save & Test first.", "Google Sheet not set up")
            return
        self.app.update_sheet(manual=True, on_done=lambda err: self._sheet_done(err, "The Google Sheet is updated"))

    def _sheet_done(self, error, ok_text):
        if self.winfo_exists():
            self._show_sheet_status()
        if error:
            self.error(f"The Google Sheet could not be updated:\n\n{error}", "Google Sheet")
        else:
            self.info(f"{ok_text}: all reports and the dashboard were sent.")

    def _stop_sheet(self):
        if gsheet.get_url(self.db) and self.confirm(
                "Stop sending the reports to the Google Sheet? The sheet keeps its last update; you can set it "
                "up again later with the same link."):
            gsheet.set_url(self.db, "")
            self.sheet_url.set("")
            self._show_sheet_status()

    def _kind(self):
        return list(whatsapp.KINDS)[self.kind.current()]

    def _load_template(self):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", whatsapp.get_template(self.db, self._kind()))

    def _save_template(self):
        whatsapp.set_template(self.db, self._kind(), self.text.get("1.0", "end"))
        self._load_template()
        self.info(f"'{self.kind.get()}' message saved.")

    def _reset_template(self):
        if self.confirm(f"Put back the default wording of the '{self.kind.get()}' message?"):
            whatsapp.set_template(self.db, self._kind(), "")
            self._load_template()
            self.info("Default wording restored.")

    def _preview(self):
        sample = {"name": "Rajesh Sharma", "token": "EP2003-123456", "date": dates.to_display(dates.today_iso()),
                  "purpose": "ITR Filing", "returned_to": "Rajesh Sharma", "consultant": "CS Neha Kapoor",
                  "expiry": dates.to_display_dt(dates.now_iso())}
        messagebox.showinfo("Preview", whatsapp.render(self.text.get("1.0", "end"), sample), parent=self)

    def _mode_changed(self):
        config.set_setting("whatsapp_mode", self.mode.get())
        self.info(f"WhatsApp messages will open in {whatsapp.MODES[self.mode.get()]}.")

    def _size_changed(self):
        config.set_setting("text_size", self.size.get())
        self.info("Text size saved. It takes effect the next time the app is started.")

    def on_show(self, tab=None, **kwargs):
        if tab is not None:
            self.nb.select(tab)
        self.refresh()

    def refresh(self):
        self.handlers.refresh()
        self.sheet_url.set(gsheet.get_url(self.db))
        self._show_sheet_status()
        self._load_template()
        self.mode.set(whatsapp.current_mode())
        self.size.set(config.get_setting("text_size", "Normal"))
        self.driver_list.delete(0, "end")
        for p in config.token_driver_paths():
            self.driver_list.insert("end", p)
        found = token_reader.find_drivers(config.token_driver_paths())
        pk = "PyKCS11 installed" if token_reader._pkcs11_module() else "PyKCS11 NOT installed (pip install PyKCS11)"
        self.driver_status.configure(text=f"{pk}  |  Drivers found: " + (
            ", ".join(sorted({label for label, _ in found if label != token_reader.OTHER_DRIVER})) or "none"))

    def _add_driver(self):
        path = filedialog.askopenfilename(parent=self, title="Choose the token's PKCS#11 driver DLL",
                                          filetypes=[("Driver DLL", "*.dll")])
        if not path:
            return
        paths = config.token_driver_paths()
        if path not in paths:
            config.set_token_driver_paths(paths + [path])
        self.refresh()

    def _remove_driver(self):
        sel = self.driver_list.curselection()
        if not sel:
            self.error("Select a driver path in the list first.")
            return
        paths = config.token_driver_paths()
        paths.pop(sel[0])
        config.set_token_driver_paths(paths)
        self.refresh()

    def _test_tokens(self):
        self.configure(cursor="watch")
        self.update()
        try:
            result = token_reader.read_tokens(config.token_driver_paths())
        finally:
            self.configure(cursor="")
        lines = [f"Drivers tried: {len(result.drivers)}"]
        for t in result.tokens:
            lines.append(f"- {t['holder_name'] or '(no certificate)'} | token {t['token_serial'] or 'serial n/a'} | "
                         f"expires {dates.to_display_dt(t['expiry_date']) or '-'} | {t['driver'] or t['source']}")
        if not result.tokens:
            lines.append("No token could be read.")
        if result.notes:
            lines += ["", *result.notes]
        messagebox.showinfo("Token reading test", "\n".join(lines), parent=self)
