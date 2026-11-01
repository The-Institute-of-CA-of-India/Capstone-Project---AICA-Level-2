"""Dashboard: quick actions, today's activity, live summary cards, expiry alert
counts and quick tables."""
import tkinter as tk
from datetime import timedelta
from tkinter import ttk

from .. import dates
from .base import Screen, filter_bar, legend
from .widgets import COLORS, DataTable, DateEntry, Tooltip


def period_range(name):
    t = dates.today()
    if name == "Today":
        return t, t
    if name == "This Week":
        return t - timedelta(days=t.weekday()), t
    if name == "This Month":
        return t.replace(day=1), t
    if name == "Last 30 Days":
        return t - timedelta(days=29), t
    if name == "This Financial Year":
        start_year = t.year if t.month >= 4 else t.year - 1
        return t.replace(year=start_year, month=4, day=1), t
    return None, None  # All Time


class Card(tk.Frame):
    """A summary tile. Neutral tiles show their number in dark text; alert tiles turn their
    number red/amber only when it is above zero."""

    def __init__(self, parent, title, command, color=None, alert=False):
        color = color or COLORS["accent"]
        super().__init__(parent, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"],
                         cursor="hand2")
        self.color, self.alert = color, alert
        tk.Frame(self, bg=color, width=4).pack(side="left", fill="y")
        inner = tk.Frame(self, bg=COLORS["card"], padx=12, pady=6)
        inner.pack(side="left", fill="both", expand=True)
        self.title = tk.Label(inner, text=title.upper(), bg=COLORS["card"], fg=COLORS["muted"],
                              font=("Segoe UI", 8, "bold"), anchor="w", justify="left", wraplength=180)
        self.title.pack(fill="x")
        self.value = tk.Label(inner, text="-", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 20, "bold"),
                              anchor="w")
        self.value.pack(fill="x")
        self.sub = tk.Label(inner, text="", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8), anchor="w",
                            justify="left", wraplength=180)
        self.sub.pack(fill="x")
        for w in (self, inner, self.title, self.value, self.sub):
            w.bind("<Button-1>", lambda e: command())
            w.bind("<Enter>", lambda e: self.configure(highlightbackground=COLORS["accent"]))
            w.bind("<Leave>", lambda e: self.configure(highlightbackground=COLORS["border"]))

    def set(self, value, sub=""):
        hot = self.alert and isinstance(value, int) and value > 0
        self.value.configure(text=str(value), fg=self.color if hot else COLORS["text"])
        self.sub.configure(text=sub)


def card_row(parent, cards, specs, pady=(0, 8)):
    row = ttk.Frame(parent, style="Screen.TFrame")
    row.pack(fill="x", pady=pady)
    for i, (key, title, command, color, alert) in enumerate(specs):
        cards[key] = Card(row, title, command, color, alert)
        cards[key].grid(row=0, column=i, sticky="nsew", padx=(0, 10))
        row.columnconfigure(i, weight=1, uniform="card")
    return row


class DashboardScreen(Screen):
    title = "Dashboard"

    def build(self, body):
        self.asof = ttk.Label(self.head, style="Muted.TLabel")
        self.asof.pack(side="right")

        bar = filter_bar(body)
        ttk.Label(bar, text="Period:").pack(side="left")
        self.period = ttk.Combobox(bar, state="readonly", width=18, values=[
            "Today", "This Week", "This Month", "Last 30 Days", "This Financial Year", "All Time", "Custom"])
        self.period.set("This Month")
        self.period.pack(side="left", padx=4)
        self.period.bind("<<ComboboxSelected>>", lambda e: self._preset())
        ttk.Label(bar, text="From").pack(side="left", padx=(10, 2))
        self.from_d = DateEntry(bar)
        self.from_d.pack(side="left")
        ttk.Label(bar, text="To").pack(side="left", padx=(10, 2))
        self.to_d = DateEntry(bar)
        self.to_d.pack(side="left")
        ttk.Button(bar, text="Apply", command=self._custom).pack(side="left", padx=8)
        ttk.Button(bar, text="⟳ Refresh", command=self.refresh).pack(side="left")
        for text, tip, fn in reversed([
                ("+ New Inward", "Record a DSC received from a client", lambda: self.app.show("inward")),
                ("Read Token", "Plug in a DSC token and start an inward entry from it", self._read_token),
                ("Return a DSC", "Record a DSC returned to the client", lambda: self.app.show("outward")),
                ("Issue to Staff", "Issue a token to a staff member or consultant",
                 lambda: self.app.show("custody", view="custody", holder="custodian"))]):
            b = ttk.Button(bar, text=text, command=fn, style="Accent.TButton" if text.startswith("+") else "TButton")
            b.pack(side="right", padx=(6, 0))
            Tooltip(b, tip)
        self._preset(refresh=False)

        self.today = tk.Frame(body, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"])
        self.today.pack(fill="x", pady=(2, 10))

        self.cards = {}
        custody = lambda **kw: (lambda: self.app.show("custody", view="custody", **kw))  # noqa: E731
        card_row(body, self.cards, [
            ("inward", "DSC inward (period)", lambda: self._open_register("inward_register"), None, False),
            ("outward", "DSC outward (period)", lambda: self._open_register("outward_register"), None, False),
            ("custody", "Live DSC custody", custody(), None, False),
            ("awaited", "DSC awaited from clients", lambda: self.app.show("custody", view="awaited"), None, False)])
        card_row(body, self.cards, [
            ("with_custodian", "With custodian", custody(holder="custodian"), None, False),
            ("with_staff", "Issued to staff", custody(holder="staff"), None, False),
            ("with_consultant", "With consultants", custody(holder="consultant"), None, False),
            ("internal_overdue", "Overdue back to custodian", custody(holder="internal_overdue"),
             COLORS["red"], True)])
        alerts = lambda k: (lambda: self.app.show("alerts", flt=k))  # noqa: E731
        card_row(body, self.cards, [
            ("exp_expired", "Certificates expired", alerts("expired"), COLORS["red"], True),
            ("exp_7", "Expiring in 7 days", alerts("7"), COLORS["orange"], True),
            ("exp_15", "Expiring in 15 days", alerts("15"), COLORS["yellow"], True),
            ("exp_30", "Expiring in 30 days", alerts("30"), COLORS["yellow"], True),
            ("exp_unknown", "Expiry unknown", alerts("unknown"), COLORS["grey"], False)], pady=(0, 4))

        tables = ttk.Frame(body, style="Screen.TFrame")
        tables.pack(fill="both", expand=True, pady=(8, 0))
        tables.columnconfigure(0, weight=1)
        tables.columnconfigure(1, weight=1)
        tables.rowconfigure(1, weight=1)
        ttk.Label(tables, text="Recently Received DSCs", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(tables, text="DSCs Awaiting Return (in custody)", style="Section.TLabel").grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        self.recent = DataTable(tables, [
            ("inward_date", "Inward Date", 80, "date"), ("holder_name", "DSC Holder", 150),
            ("token_serial", "Token", 100), ("purpose", "Purpose", 90), ("custody", "Status", 100)], height=4,
            on_double=self.open_token_history, menu=lambda r: self.token_menu(r),
            empty_text="No DSC received yet.")
        self.recent.grid(row=1, column=0, sticky="nsew")
        self.awaiting = DataTable(tables, [
            ("holder_name", "DSC Holder", 150), ("token_serial", "Token", 100),
            ("expected_return_date", "Return By", 80, "date"), ("with_label", "Currently With", 150),
            ("custody_status", "Status", 130)], height=4,
            on_double=self.open_token_history, menu=lambda r: self.token_menu(r),
            empty_text="No DSC in custody.")
        self.awaiting.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        legend(body, [("red", "Expired / overdue"), ("orange", "Urgent"), ("yellow", "Approaching"),
                      ("green", "Normal")]).pack(anchor="w", pady=(6, 0))

    def _read_token(self):
        self.app.show("inward")._read_token()

    def _preset(self, refresh=True):
        name = self.period.get()
        if name == "Custom":
            return
        start, end = period_range(name)
        self.from_d.set_iso(start.isoformat() if start else None)
        self.to_d.set_iso(end.isoformat() if end else None)
        if refresh:
            self.refresh()

    def _custom(self):
        self.period.set("Custom")
        self.refresh()

    def _range(self):
        f = self.from_d.get_iso("From date")
        t = self.to_d.get_iso("To date")
        if f and t and f > t:
            raise ValueError("From date cannot be after To date.")
        return f, t

    def _open_register(self, name):
        ok, rng = self.run(self._range)
        if ok:
            self.app.show(name, from_date=rng[0], to_date=rng[1])

    def _fill_today(self):
        for w in self.today.winfo_children():
            w.destroy()
        t = self.db.today_summary()
        tk.Label(self.today, text="TODAY", bg=COLORS["card"], fg=COLORS["accent"], font=("Segoe UI", 9, "bold"),
                 padx=12, pady=7).pack(side="left")
        today = dates.today_iso()
        items = [
            (t["received"], "received", lambda: self.app.show("inward_register", from_date=today, to_date=today)),
            (t["returned"], "returned to clients",
             lambda: self.app.show("outward_register", from_date=today, to_date=today)),
            (t["due_back"], "due back today from staff / consultants",
             lambda: self.app.show("custody", view="custody", holder="staff")),
            (t["expiring"], "certificate(s) expire today", lambda: self.app.show("alerts", flt="today")),
            (t["awaited"], "awaited DSC(s) expected today", lambda: self.app.show("custody", view="awaited")),
        ]
        for i, (n, text, fn) in enumerate(items):
            if i:
                tk.Label(self.today, text="·", bg=COLORS["card"], fg=COLORS["muted"]).pack(side="left")
            lbl = tk.Label(self.today, text=f"{n} {text}", bg=COLORS["card"], cursor="hand2",
                           fg=COLORS["text"] if n else COLORS["muted"],
                           font=("Segoe UI", 9, "bold" if n else "normal"), padx=8)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, f=fn: f())

    def refresh(self):
        ok, rng = self.run(self._range)
        if not ok:
            return
        now = dates.now()
        self.asof.configure(text=f"As on {now.strftime('%A, %d-%m-%Y')} {dates.time_display(now)}")
        self._fill_today()
        c = self.db.dashboard_counts(rng[0], rng[1])
        label = self.period.get() if self.period.get() != "Custom" else (
            f"{dates.to_display(rng[0]) or 'start'} to {dates.to_display(rng[1]) or 'today'}")
        self.cards["inward"].set(c["inward"], f"Received - {label}")
        self.cards["outward"].set(c["outward"], f"Returned - {label}")
        self.cards["custody"].set(c["custody"], f"Tokens held  |  {c['overdue']} overdue for return to clients")
        self.cards["awaited"].set(c["awaited"], "Expected but not yet received")
        custodian = self.db.current_custodian()
        self.cards["with_custodian"].set(c["with_custodian"], custodian["name"] if custodian else
                                         "No custodian appointed")
        self.cards["with_staff"].set(c["with_staff"], f"{c['staff_overdue']} overdue back to custodian")
        self.cards["with_consultant"].set(c["with_consultant"], f"{c['consultant_overdue']} overdue back")
        self.cards["internal_overdue"].set(c["staff_overdue"] + c["consultant_overdue"],
                                           "Staff or consultants past their due time")
        self.cards["exp_expired"].set(c["exp_expired"], "Expiry time has passed")
        self.cards["exp_7"].set(c["exp_7"], f"Incl. {c['exp_today']} expiring today")
        self.cards["exp_15"].set(c["exp_15"], "Within the next 15 days")
        self.cards["exp_30"].set(c["exp_30"], "Within the next 30 days")
        self.cards["exp_unknown"].set(c["exp_unknown"], "Certificate expiry not recorded")

        self.recent.set_rows(self.db.recent_inwards(10),
                             lambda r: "green" if r["custody"] == "In Custody" else None)
        custody = sorted(self.db.custody_register(),
                         key=lambda r: (r["days_to_return"] is None, r["days_to_return"] or 0))
        self.awaiting.set_rows(custody, custody_tag)
        self.app.update_badges(c)


def custody_tag(r):
    return {"overdue": "red", "soon": "orange", "ok": "green"}.get(r["overdue_flag"])
