"""Backup Database: backups (manual and automatic daily), database location and sample data."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import config, dates, single_user
from ..database import ValidationError, backup_summary, is_valid_database
from ..sample_data import load_sample_data
from .base import Screen


class BackupScreen(Screen):
    title = "Backup Database"
    subtitle = "Backups, database location and sample data"

    def build(self, body):
        db_box = ttk.LabelFrame(body, text=" Database ", padding=12)
        db_box.pack(fill="x")
        ttk.Label(db_box, text="Database file in use:").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar()
        ttk.Entry(db_box, textvariable=self.path_var, width=95, state="readonly").grid(
            row=0, column=1, sticky="w", padx=6)
        ttk.Button(db_box, text="Open Folder", command=self._open_folder).grid(row=0, column=2)
        self.stats = ttk.Label(db_box, style="Muted.TLabel")
        self.stats.grid(row=1, column=1, sticky="w", padx=6, pady=(4, 0))
        ttk.Label(db_box, text=f"{single_user.NOTE} Do not open this database from two PCs, or keep it in a "
                               "folder that several PCs share.", foreground="#b7791f").grid(
            row=2, column=1, sticky="w", padx=6, pady=(4, 0))
        ttk.Button(db_box, text="Change Database Location...", command=self._change_location).grid(
            row=3, column=1, sticky="w", padx=6, pady=(8, 0))

        bk = ttk.LabelFrame(body, text=" Backup ", padding=12)
        bk.pack(fill="x", pady=(12, 0))
        row = ttk.Frame(bk)
        row.pack(fill="x")
        left = ttk.Frame(row)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Backup now: save a dated copy (e.g. DSC_Backup_2026-10-29_153000.db) to a folder "
                             "of your choice.", wraplength=520).pack(anchor="w")
        ttk.Button(left, text="Backup Now...", style="Accent.TButton", command=self._backup).pack(anchor="w", pady=6)
        self.last = ttk.Label(left, style="Muted.TLabel", wraplength=520)
        self.last.pack(anchor="w")

        auto = ttk.Frame(row)
        auto.pack(side="left", fill="both", expand=True, padx=(24, 0))
        self.auto_on = tk.BooleanVar()
        ttk.Checkbutton(auto, text="Automatic daily backup (when the app is opened, once a day)",
                        variable=self.auto_on, command=self._auto_toggled).pack(anchor="w")
        frow = ttk.Frame(auto)
        frow.pack(anchor="w", pady=4)
        ttk.Label(frow, text="Folder:").pack(side="left")
        self.auto_folder = tk.StringVar()
        ttk.Entry(frow, textvariable=self.auto_folder, width=48, state="readonly").pack(side="left", padx=4)
        ttk.Button(frow, text="Choose…", command=self._auto_choose).pack(side="left")
        self.auto_last = ttk.Label(auto, style="Muted.TLabel", wraplength=520)
        self.auto_last.pack(anchor="w")
        ttk.Label(auto, style="Muted.TLabel", wraplength=520, text=(
            "Choose a USB drive or a Google Drive / OneDrive folder. One file per day is kept for the last 30 "
            "days. You are reminded if there has been no backup for 7 days.")).pack(anchor="w")
        rs = ttk.Frame(bk)
        rs.pack(fill="x", pady=(10, 0))
        ttk.Button(rs, text="Restore from Backup...", command=self._restore).pack(side="left")
        ttk.Label(rs, style="Muted.TLabel", text=(
            "Replaces all the data with a backup's. A copy of the current data is saved first "
            "(DSC_BeforeRestore_...db in the database folder), so a restore can be undone.")).pack(
            side="left", padx=10)

        sm = ttk.LabelFrame(body, text=" Sample Data ", padding=12)
        sm.pack(fill="x", pady=(12, 0))
        ttk.Label(sm, text="Demonstration clients whose names end with '(Sample)'. Remove them before using the "
                           "tool for real work.").pack(anchor="w")
        ttk.Button(sm, text="Load Sample Data", command=self._load_sample).pack(anchor="w", pady=(8, 4))
        ttk.Button(sm, text="Remove Sample Data", command=self._remove_sample).pack(anchor="w")

    def refresh(self):
        self.path_var.set(self.db.path)
        try:
            size = os.path.getsize(self.db.path) / 1024
        except OSError:
            size = 0
        n = lambda sql: self.db._scalar(sql)  # noqa: E731
        self.stats.configure(text=(
            f"Size {size:,.0f} KB  |  {n('SELECT COUNT(*) FROM clients')} clients  |  "
            f"{n('SELECT COUNT(*) FROM tokens')} tokens  |  {n('SELECT COUNT(*) FROM inward')} inward  |  "
            f"{n('SELECT COUNT(*) FROM outward')} outward entries"))
        days = self.db.days_since_backup()
        age = "" if days is None else (" (today)" if days == 0 else f" ({days} day(s) ago)")
        self.last.configure(text=f"Last backup: {self.db.get_meta('last_backup', 'never')}{age}")
        self.auto_on.set(bool(config.get_setting("auto_backup_enabled", False)))
        self.auto_folder.set(config.get_setting("auto_backup_folder", "") or "")
        last_auto = self.db.get_meta("last_auto_backup_at")
        self.auto_last.configure(text=f"Last automatic backup: {dates.to_display_dt(last_auto) if last_auto else 'never'}")

    def _open_folder(self):
        try:
            os.startfile(os.path.dirname(self.db.path))
        except (OSError, AttributeError) as exc:
            self.error(f"Could not open the folder: {exc}")

    def _backup(self):
        folder = filedialog.askdirectory(parent=self, title="Choose a folder for the backup")
        if not folder:
            return
        problem = config.check_folder_writable(folder)
        if problem:
            self.error(problem, "Backup failed")
            return
        ok, dest = self.run(self.db.backup_to, folder)
        if ok:
            self.info(f"Backup saved: {dest}")
            self.refresh()

    def _restore(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose the backup to restore",
            initialdir=config.get_setting("auto_backup_folder", "") or os.path.dirname(self.db.path),
            filetypes=[("DSC Manager backup", "*.db"), ("All files", "*.*")])
        if not path:
            return
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(self.db.path):
            self.error("That is the database in use, not a backup.", "Cannot restore")
            return
        if not is_valid_database(path):
            self.error(f"{path}\n\nis not a DSC Management Tool backup, or the file is damaged.", "Cannot restore")
            return
        b = backup_summary(path)
        n = lambda sql: self.db._scalar(sql)  # noqa: E731
        now = {"clients": n("SELECT COUNT(*) FROM clients"), "tokens": n("SELECT COUNT(*) FROM tokens"),
               "inward": n("SELECT COUNT(*) FROM inward"), "outward": n("SELECT COUNT(*) FROM outward")}
        last = lambda v: dates.to_display(v) if v else "none"  # noqa: E731
        counts = "\n".join(f"{label}: {b[key]} in the backup, {now[key]} now" for key, label in (
            ("clients", "Clients"), ("tokens", "Tokens"), ("inward", "Inward entries"), ("outward", "Outward entries")))
        if not messagebox.askyesno("Restore from Backup", (
                f"Backup file:\n{path}\nsaved on {dates.to_display_dt(b['saved_at'])}\n\n{counts}\n"
                f"Latest inward in the backup: {last(b['last_inward'])}; latest outward: {last(b['last_outward'])}\n\n"
                "ALL the current data will be replaced by the backup's. Entries made after this backup was saved "
                "will no longer show.\n\nA copy of the current data is saved first, so this can be undone."
                "\n\nRestore this backup?"), icon="warning", parent=self):
            return
        ok, safety = self.run(self.db.restore_from, path)
        if not ok:
            return
        self.app.reload_database()
        messagebox.showinfo("Restore from Backup", (
            f"The backup has been restored.\n\nThe data as it was before the restore is saved in:\n{safety}"
            "\n\nTo undo the restore, restore that file."), parent=self.app)

    def _auto_choose(self):
        folder = filedialog.askdirectory(parent=self, title="Choose the folder for automatic daily backups")
        if not folder:
            return
        problem = config.check_folder_writable(folder)
        if problem:
            self.error(problem, "Folder not usable")
            return
        config.set_setting("auto_backup_folder", os.path.abspath(folder))
        config.set_setting("auto_backup_enabled", True)
        self.app.run_auto_backup(force=True)
        self.refresh()

    def _auto_toggled(self):
        if self.auto_on.get() and not config.get_setting("auto_backup_folder"):
            self.auto_on.set(False)
            self._auto_choose()
            return
        config.set_setting("auto_backup_enabled", self.auto_on.get())
        if self.auto_on.get():
            self.app.run_auto_backup(force=True)
        self.refresh()

    def _change_location(self):
        folder = filedialog.askdirectory(parent=self, title="Choose the folder for the database")
        if not folder:
            return
        folder = os.path.abspath(folder)
        problem = config.check_folder_writable(folder)
        if problem:
            self.error(problem, "Folder not usable")
            return
        target = os.path.join(folder, config.DB_FILENAME)
        if os.path.normcase(target) == os.path.normcase(self.db.path):
            self.info("That folder already holds the database in use.")
            return
        if os.path.exists(target):
            if not is_valid_database(target):
                self.error(f"{target}\nexists but is not a valid DSC Management database.", "Cannot use file")
                return
            if not self.confirm(f"A DSC database already exists in this folder:\n{target}\n\n"
                                "Switch to that database? (The current database file is left unchanged.)"):
                return
            self.app.switch_database(target, copy_current=False)
            return
        ans = messagebox.askyesnocancel(
            "Change database location",
            f"New location:\n{target}\n\nYES - copy the current data to the new location and use it there\n"
            "NO - start a new, empty database there\nCANCEL - keep the current location", parent=self)
        if ans is not None:
            self.app.switch_database(target, copy_current=ans)

    def _load_sample(self):
        if self.db.has_sample_data():
            self.info("Sample data is already loaded.")
            return
        if self.confirm("Load demonstration clients, DSC tokens and transactions (all marked '(Sample)')?"):
            ok, _ = self.run(load_sample_data, self.db)
            if ok:
                self.info("Sample data loaded.")
                self.refresh()
                self.app.refresh_dashboard()

    def _remove_sample(self):
        if not self.db.has_sample_data():
            self.info("There is no sample data in this database.")
            return
        if self.confirm("Permanently remove all SAMPLE clients, tokens and transactions?\n"
                        "Real records are not affected."):
            try:
                self.db.remove_sample_data()
            except ValidationError as exc:
                self.error(str(exc))
                return
            self.info("Sample data removed.")
            self.refresh()
            self.app.refresh_dashboard()
