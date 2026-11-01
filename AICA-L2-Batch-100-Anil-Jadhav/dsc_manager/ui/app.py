"""Main application window: left menu, screen area and status bar."""
import gc
import os
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import config, dates, firm_info, gsheet, single_user
from ..database import Database
from ..sample_data import load_sample_data
from .alerts import AlertsScreen
from .backup import BackupScreen
from .clients import ClientsScreen
from .dashboard import DashboardScreen
from .dialogs import (AppointCustodianDialog, ClientDetailDialog, Dialog, StartupSummaryDialog,
                      TokenHistoryDialog)
from .help import HelpScreen
from .inward import InwardScreen
from .movements import HoldingsScreen, MovementRegisterScreen
from .outward import OutwardScreen
from .reports import CustodyScreen, InwardRegisterScreen, OutwardRegisterScreen
from .settings import TEXT_SIZES, SettingsScreen
from .widgets import COLORS, Autocomplete, DataTable, Tooltip

APP_TITLE = firm_info.window_title()

SCREENS = {
    "dashboard": DashboardScreen, "clients": ClientsScreen, "inward": InwardScreen, "outward": OutwardScreen,
    "inward_register": InwardRegisterScreen, "outward_register": OutwardRegisterScreen,
    "custody": CustodyScreen, "alerts": AlertsScreen, "backup": BackupScreen,
    "movement_register": MovementRegisterScreen, "holdings": HoldingsScreen,
    "settings": SettingsScreen, "help": HelpScreen,
}
REFRESH_MS = 5 * 60 * 1000   # the dashboard refreshes itself every 5 minutes
SHEET_DELAY_MS = 60 * 1000   # the Google Sheet is updated this long after the last entry

MENU = [
    ("dashboard", "1.  Dashboard"),
    ("clients", "2.  Clients"),
    ("inward", "3.  DSC Inward"),
    ("outward", "4.  DSC Outward"),
    ("custody", "5.  DSC in Custody"),
    (None, "6.  Reports"),
    ("inward_register", "      Inward Register"),
    ("outward_register", "      Outward Register"),
    ("movement_register", "      Movement Register"),
    ("holdings", "      Holdings by Person"),
    ("alerts", "7.  Expiry Alerts"),
    ("backup", "8.  Backup Database"),
    ("settings", "9.  Settings"),
    ("help", "10. Help"),
    ("exit", "11. Exit"),
]


def choose_db_path(root):
    """Work out which database file to open, running first-time setup if needed."""
    env = config.env_db_path()
    if env:
        return env
    cfg = config.load_config()
    if cfg:
        path = cfg["db_path"]
        if os.path.isdir(os.path.dirname(path)):
            if not os.path.exists(path) and not messagebox.askyesno(
                    APP_TITLE, f"The database file was not found:\n{path}\n\nCreate a new, empty database there?\n"
                               "(Choose No to pick another folder.)", parent=root):
                return pick_folder(root)
            return path
        moved = config.moved_db_path(path)
        if moved:
            if not messagebox.askyesno(
                    APP_TITLE, f"The saved database folder is not available on this PC:\n{os.path.dirname(path)}\n\n"
                               f"A database was found in the application's own folder:\n{moved}\n\nUse this database?\n"
                               "(Choose No to pick another folder.)", parent=root):
                return pick_folder(root)
            config.save_config({"db_path": moved})
            return moved
        messagebox.showwarning(APP_TITLE, f"The database folder is not available:\n{os.path.dirname(path)}\n\n"
                                          "Please choose the folder that holds the DSC database.", parent=root)
        return pick_folder(root)
    ans = messagebox.askyesnocancel(
        f"{APP_TITLE} - First-time setup",
        "Welcome! Where should the DSC database be stored?\n\n"
        f"YES - use the default location:\n{config.DEFAULT_DB_PATH}\n\n"
        "NO - choose a different folder (for example a folder that is backed up)\n\nCANCEL - exit\n\n"
        f"Note: {single_user.NOTE} Keep the database on this PC, not in a folder shared by several PCs.",
        parent=root)
    if ans is None:
        return None
    path = config.DEFAULT_DB_PATH if ans else pick_folder(root)
    if path:
        config.save_config({"db_path": path})
    return path


def pick_folder(root):
    while True:
        folder = filedialog.askdirectory(parent=root, title="Choose the folder for the DSC database")
        if not folder:
            return None
        problem = config.check_folder_writable(folder)
        if not problem:
            path = os.path.join(os.path.abspath(folder), config.DB_FILENAME)
            config.save_config({"db_path": path})
            return path
        messagebox.showerror(APP_TITLE, problem, parent=root)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title(APP_TITLE)
        self.db = None
        try:  # the app's own icon: on this window directly, and as the default for every dialog
            self.iconbitmap(config.asset("dsc_manager.ico"))
            self.iconbitmap(default=config.asset("dsc_manager.ico"))
        except tk.TclError:
            pass
        self._setup_style()
        path = choose_db_path(self)
        if not path:
            self.destroy()
            return
        self._lock = single_user.acquire(os.path.abspath(path))
        if self._lock is None:
            messagebox.showerror(APP_TITLE, "The DSC Management Tool is already open with this database.\n\n"
                                            f"{single_user.NOTE} Switch to the window that is already open "
                                            "(see the taskbar).", parent=self)
            self.destroy()
            return
        self._lock_path = os.path.abspath(path)
        try:
            self.db = Database(path)
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror(APP_TITLE, f"Could not open the database:\n{path}\n\n{exc}", parent=self)
            single_user.release(self._lock, self._lock_path)
            self.destroy()
            return
        # The firms' .exe starts clean; sample data stays available on the Backup Database screen.
        if self.db.is_new and not config.env_db_path() and not getattr(sys, "frozen", False) and messagebox.askyesno(
                APP_TITLE, "A new database has been created.\n\nLoad SAMPLE demonstration data?\n"
                           "(Sample records are clearly marked and can be removed later from 'Backup Database'.)",
                parent=self):
            load_sample_data(self.db)
        self._sheet_job, self._sheet_busy, self._sheet_again = None, False, False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.exit)
        self.deiconify()
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.show("dashboard")
        for seq in ("<Control-s>", "<Control-S>"):
            self.bind_all(seq, self._ctrl_s)
        for seq in ("<Control-f>", "<Control-F>"):
            self.bind_all(seq, self._focus_search)
        self.update_sample_strip()
        self.bind_all("<F5>", self._f5)
        self._today = dates.today_iso()
        self.after(REFRESH_MS, self._tick)
        if not config.env_db_path():   # the automated tests skip the start-up questions
            self.after(400, self._startup)

    def _startup(self):
        if not self.db.current_custodian():
            self._ask_custodian()
        self.run_auto_backup()
        self.schedule_sheet_update(3000)
        items = self.db.attention_summary()
        if items:
            StartupSummaryDialog(self, items).show()
        else:
            self.toast("All clear: nothing needs attention today.")

    def _ask_custodian(self):
        messagebox.showinfo(APP_TITLE, "No custodian has been appointed yet.\n\nEvery DSC received goes to the "
                                       "custodian automatically, so please appoint the custodian now.", parent=self)
        if AppointCustodianDialog(self, self.db).show():
            self.refresh_dashboard()
            self.update_status()

    def run_auto_backup(self, force=False):
        """The automatic daily backup, if switched on (Backup Database screen): once a day."""
        if not config.get_setting("auto_backup_enabled", False):
            return
        folder = config.get_setting("auto_backup_folder", "")
        last = self.db.get_meta("last_auto_backup_at") or ""
        if not force and last[:10] == dates.today_iso():
            return
        if not folder or config.check_folder_writable(folder):
            self.toast(f"Automatic backup could not be saved: the folder is not available ({folder or 'not set'}).",
                       error=True)
            return
        try:
            self.db.auto_backup(folder)
            self.toast("Automatic daily backup saved.")
        except Exception as exc:
            self.toast(f"Automatic backup failed: {exc}", error=True)

    def _tick(self):
        """Every few minutes: keep the dashboard and status bar current; a new day runs the daily backup."""
        try:
            if self.current == "dashboard":
                self.screens["dashboard"].refresh()
            else:
                self.update_badges()
            self._update_status()
            if dates.today_iso() != self._today:
                self._today = dates.today_iso()
                self.run_auto_backup()
                self.schedule_sheet_update(1000)   # expiry counts change with the date
            elif gsheet.status(self.db)["last_error"]:
                self.schedule_sheet_update(1000)   # try again after a failed update (no internet, ...)
        finally:
            self.after(REFRESH_MS, self._tick)

    def _focus_top(self):
        try:
            w = self.focus_get()
        except (KeyError, tk.TclError):
            w = None
        return w.winfo_toplevel() if w else self

    def _ctrl_s(self, event=None):
        """Ctrl+S saves the open dialog, or the form on the current screen."""
        top = self._focus_top()
        if isinstance(top, Dialog):
            top.ok()
        elif top is self:
            fn = getattr(self.screens.get(self.current), "on_ctrl_s", None)
            if fn:
                fn()
        return "break"

    def _f5(self, event=None):
        if self._focus_top() is self and self.current in self.screens:
            self.screens[self.current].refresh()
        return "break"

    def toast(self, message, error=False, ms=4500, undo=None):
        """A short message at the bottom right that disappears by itself. With undo=function, it
        carries an Undo button for about 10 seconds."""
        old = getattr(self, "_toast", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        bg = COLORS["red"] if error else "#1f2937"
        box = self._toast = tk.Frame(self, bg=bg)
        tk.Label(box, text=message, bg=bg, fg="#ffffff", font=("Segoe UI", 10), padx=14, pady=8, wraplength=520,
                 justify="left").pack(side="left")
        if undo:
            ms = max(ms, 10000)

            def do_undo():
                box.destroy()
                try:
                    undo()
                except Exception as exc:  # e.g. the token has moved on since
                    self.toast(f"Could not undo: {exc}", error=True)
                    return
                self.toast("Undone. The entry is kept in its register marked 'Cancelled'.")
                if self.current in self.screens:
                    self.screens[self.current].refresh()
                self.refresh_dashboard()
            tk.Button(box, text="Undo", command=do_undo, bg=bg, fg="#93c5fd", activebackground=bg,
                      activeforeground="#ffffff", relief="flat", font=("Segoe UI", 10, "bold underline"),
                      cursor="hand2", padx=10).pack(side="left", padx=(0, 6))
        box.place(relx=1.0, rely=1.0, x=-20, y=-36, anchor="se")
        box.lift()
        self.after(ms if not error else ms * 2, lambda: box.winfo_exists() and box.destroy())

    def _setup_style(self):
        self.geometry("1366x768")
        # Never larger than the screen: on a small one the window fits and the screens scroll.
        self.minsize(min(1150, self.winfo_screenwidth() - 40), min(680, self.winfo_screenheight() - 100))
        self.configure(bg=COLORS["bg"])
        # Text size (Settings): scale all fonts; row height and menu width follow.
        self.scale = TEXT_SIZES.get(config.get_setting("text_size", "Normal"), 1.0)
        if self.scale != 1.0:
            self.tk.call("tk", "scaling", float(self.tk.call("tk", "scaling")) * self.scale)
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        # Only classic widgets here: a global "*Font" would override ttk style fonts.
        self.option_add("*Listbox.Font", ("Segoe UI", 9))
        self.option_add("*TCombobox*Listbox.Font", ("Segoe UI", 9))
        bg = COLORS["bg"]
        style.configure(".", font=("Segoe UI", 9))
        style.configure("Screen.TFrame", background=bg)
        style.configure("TLabel", background=bg)
        style.configure("TCheckbutton", background=bg)
        style.configure("TRadiobutton", background=bg)
        style.configure("TLabelframe", background=bg)
        style.configure("TLabelframe.Label", background=bg, foreground=COLORS["blue"], font=("Segoe UI", 9, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=COLORS["text"])
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground=COLORS["text"])
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=(16, 8))
        style.configure("Treeview", rowheight=int(24 * self.scale), font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", padding=(10, 4), font=("Segoe UI", 9, "bold"))

    def _build(self):
        side = tk.Frame(self, bg=COLORS["sidebar"], width=int(210 * self.scale))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="DSC Manager", bg=COLORS["sidebar"], fg="#ffffff",
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=16, pady=(18, 16))
        self.menu_buttons = {}
        self.menu_text = dict(MENU)
        for key, text in MENU:
            if key is None:
                tk.Label(side, text=text, bg=COLORS["sidebar"], fg="#ffffff", anchor="w",
                         font=("Segoe UI", 10)).pack(fill="x", padx=8, ipady=4, ipadx=8)
                continue
            b = tk.Label(side, text=text, bg=COLORS["sidebar"], fg="#ffffff", anchor="w", cursor="hand2",
                         font=("Segoe UI", 10))
            b.pack(fill="x", padx=8, ipady=4, ipadx=8)
            b.bind("<Button-1>", lambda e, k=key: self.exit() if k == "exit" else self.show(k))
            b.bind("<Enter>", lambda e, w=b, k=key: w.configure(
                bg=COLORS["sidebar_active"] if k == self.current else COLORS["sidebar_hover"]))
            b.bind("<Leave>", lambda e, w=b, k=key: w.configure(
                bg=COLORS["sidebar_active"] if k == self.current else COLORS["sidebar"]))
            self.menu_buttons[key] = b
        tk.Label(side, text="Designed by ABJ@2026", bg=COLORS["sidebar"],
                 fg=COLORS["sidebar_muted"], justify="left", font=("Segoe UI", 8)).pack(side="bottom", anchor="w",
                                                                                      padx=16, pady=12)

        right = tk.Frame(self, bg=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)
        status = tk.Frame(right, bg="#e2e8f0")
        status.pack(side="bottom", fill="x")
        self.status_db = tk.Label(status, bg="#e2e8f0", fg=COLORS["muted"], anchor="w", font=("Segoe UI", 8))
        self.status_db.pack(side="left", padx=10, pady=3)
        self.status_date = tk.Label(status, bg="#e2e8f0", fg=COLORS["muted"], font=("Segoe UI", 8))
        self.status_date.pack(side="right", padx=10)
        tk.Label(status, text="No PINs or passwords are stored by this application", bg="#e2e8f0",
                 fg=COLORS["muted"], font=("Segoe UI", 8)).pack(side="right", padx=10)
        top = tk.Frame(right, bg=COLORS["bg"])
        top.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(top, text="Search", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")).pack(
            side="left")
        self.search = ttk.Entry(top, width=56)
        self.search.pack(side="left", padx=8)
        tk.Label(top, text="client name, PAN, mobile or token number  (Ctrl+F)", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._search_items = []
        Autocomplete(self.search, lambda: [(i["label"], f"{i['label']} {i['text']}") for i in self._search_items],
                     on_choose=self._search_chosen)
        self.search.bind("<FocusIn>", lambda e: self._load_search_index(), add="+")
        self.sample_strip = tk.Frame(right, bg="#fdf3d7", highlightthickness=1, highlightbackground="#ecd9a0")
        tk.Label(self.sample_strip, bg="#fdf3d7", fg="#7a5a00", font=("Segoe UI", 9, "bold"),
                 text="Sample data is loaded. Remove it before entering real records.").pack(side="left", padx=12,
                                                                                           pady=5)
        ttk.Button(self.sample_strip, text="Remove sample data…",
                   command=lambda: self.show("backup")).pack(side="left")
        self.content = tk.Frame(right, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True)
        self.screens = {}
        self.current = None
        self._update_status()

    def update_status(self):
        self._update_status()

    # ---------------------------------------------------------------- search, counts, sample strip
    def _load_search_index(self):
        self._search_items = self.db.search_index()

    def _focus_search(self, event=None):
        if self._focus_top() is self:
            self.search.focus_set()
            self.search.select_range(0, "end")
        return "break"

    def _search_chosen(self, label):
        item = next((i for i in self._search_items if i["label"] == label), None)
        self.search.delete(0, "end")
        if not item:
            return
        if item["kind"] == "client":
            ClientDetailDialog(self, self.db, item["id"], self).show()
        else:
            TokenHistoryDialog(self, self.db, item["id"]).show()
        self.refresh_dashboard()

    def update_badges(self, counts=None):
        """Counts on the left menu: tokens in custody, certificates needing attention, overdue movements."""
        if not getattr(self, "menu_buttons", None):
            return
        c = counts or self.db.dashboard_counts()
        alerts = c["exp_expired"] + c["exp_7"]
        overdue = c["staff_overdue"] + c["consultant_overdue"]
        extra = {"custody": f"  ({c['custody']}" + (f" · {overdue} late)" if overdue else ")"),
                 "alerts": f"  ({alerts})" if alerts else ""}
        for key, suffix in extra.items():
            self.menu_buttons[key].configure(text=self.menu_text[key] + suffix)

    def update_sample_strip(self):
        if self.db.has_sample_data():
            if not self.sample_strip.winfo_ismapped():
                self.sample_strip.pack(fill="x", padx=16, pady=(8, 0), before=self.content)
        else:
            self.sample_strip.pack_forget()

    def _update_status(self):
        c = self.db.current_custodian()
        self.status_db.configure(text=f"Custodian: {c['name'] if c else 'not appointed'}    |    "
                                      f"Database: {self.db.path}")
        self.status_date.configure(text=f"Today: {dates.to_display(dates.today_iso())}")

    def show(self, name, **kwargs):
        if name == "movements":  # the Movements screen is now part of DSC in Custody
            name = "custody"
            kwargs.setdefault("view", "custody")
        if name not in self.screens:
            self.screens[name] = SCREENS[name](self.content, self)
        for key, scr in self.screens.items():
            if key != name:
                scr.pack_forget()
        screen = self.screens[name]
        if name != self.current:  # coming from another screen: start with cleared filters
            screen.reset_filters()
        screen.pack(fill="both", expand=True)
        self.current = name
        for key, b in self.menu_buttons.items():
            b.configure(bg=COLORS["sidebar_active"] if key == name else COLORS["sidebar"])
        self._update_status()
        screen.on_show(**kwargs)
        return screen

    def refresh_dashboard(self):
        """Called after every inward/outward/certificate change."""
        if "dashboard" in self.screens:
            self.screens["dashboard"].refresh()
        else:
            self.update_badges()
        self.update_sample_strip()
        self.schedule_sheet_update()

    # ---------------------------------------------------------------- Google Sheet for the partners
    def schedule_sheet_update(self, delay=SHEET_DELAY_MS):
        """Update the Google Sheet a little after the latest entry (several entries in a row: one update)."""
        if not self.db or not gsheet.get_url(self.db):
            return
        if self._sheet_job:
            self.after_cancel(self._sheet_job)
        self._sheet_job = self.after(delay, self.update_sheet)

    def update_sheet(self, manual=False, on_done=None):
        """Send all reports to the Google Sheet in the background; on_done(error or None) afterwards."""
        self._sheet_job = None
        url = gsheet.get_url(self.db)
        if not url:
            return
        if self._sheet_busy:
            if on_done:   # clicked during an automatic update: run it right after that one
                self.after(500, lambda: self.update_sheet(manual, on_done))
            else:
                self._sheet_again = True   # an entry came in during the update: send again after it
            return
        try:
            payload = gsheet.build_payload(self.db, gsheet.get_key(self.db))
        except Exception as exc:
            self._sheet_finished(f"Could not prepare the reports: {exc}", manual, on_done)
            return
        self._sheet_busy = True
        if manual:
            self.configure(cursor="watch")
        result = []
        post = self._post_sheet
        # Tkinter objects must only be freed on this thread: clear Python's pending clean-up here first,
        # so it does not run on the background thread.
        gc.collect()
        worker = threading.Thread(target=lambda: result.append(post(url, payload)), daemon=True)
        worker.start()

        def wait():
            if worker.is_alive():
                self.after(300, wait)
                return
            self._sheet_busy = False
            if manual:
                self.configure(cursor="")
            self._sheet_finished(result[0] if result else "The update stopped unexpectedly.", manual, on_done)
        self.after(300, wait)

    @staticmethod
    def _post_sheet(url, payload, timeout=gsheet.TIMEOUT):
        try:
            gsheet.post(url, payload, timeout)
            return None
        except Exception as exc:
            return str(exc)

    def _sheet_finished(self, error, manual, on_done):
        if not self.db:
            return
        had_error = bool(gsheet.status(self.db)["last_error"])
        gsheet.record_result(self.db, error)
        if error and not manual and not had_error:   # say so once, not at every retry
            self.toast(f"Google Sheet not updated: {error} It will try again in a few minutes.", error=True)
        if on_done:
            on_done(error)
        if self._sheet_again:
            self._sheet_again = False
            self.schedule_sheet_update(1000)

    def switch_database(self, path, copy_current):
        try:
            if copy_current:
                target = sqlite3.connect(path)
                try:
                    with target:
                        self.db.conn.backup(target)
                finally:
                    target.close()
            new_lock = single_user.acquire(os.path.abspath(path))
            if new_lock is None:
                messagebox.showerror(APP_TITLE, "That database is already open in another window.", parent=self)
                return
            new_db = Database(path)
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror(APP_TITLE, f"Could not use the new location:\n{exc}", parent=self)
            return
        self.db.close()
        single_user.release(self._lock, self._lock_path)
        self._lock, self._lock_path = new_lock, os.path.abspath(path)
        self.db = new_db
        if not config.env_db_path():
            config.save_config({"db_path": path})
        for scr in self.screens.values():
            scr.destroy()
        self.screens = {}
        self.show("dashboard")
        messagebox.showinfo(APP_TITLE, f"Now using database:\n{path}", parent=self)

    def reload_database(self):
        """Reopen the database in use (after a restore): screens are rebuilt from the new data."""
        path = self.db.path
        self.db.close()
        self.db = Database(path)   # an older backup is brought up to date here
        for scr in self.screens.values():
            scr.destroy()
        self.screens = {}
        gc.collect()   # free the old screens here, on the main thread
        self.show("dashboard")
        self.update_sample_strip()
        self.schedule_sheet_update(3000)

    def exit(self):
        if messagebox.askyesno(APP_TITLE, "Exit the DSC Management Tool?\n\nAll entries are already saved.",
                               parent=self):
            self.close()

    def close(self):
        try:
            DataTable.save_widths()  # column widths people set are kept for next time (this PC)
        except Exception:
            pass
        if self.db and getattr(self, "_sheet_job", None) and gsheet.get_url(self.db):
            # Entries of the last minute are not in the Google Sheet yet: send them now (20 seconds at most).
            self.configure(cursor="watch")
            self.update()
            error = self._post_sheet(gsheet.get_url(self.db), gsheet.build_payload(self.db, gsheet.get_key(self.db)), 20)
            gsheet.record_result(self.db, error)
        if self.db:
            self.db.close()
            single_user.release(self._lock, self._lock_path)
        self.destroy()


def main():
    app = App()
    if app.db:
        app.mainloop()
