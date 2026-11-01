"""Reusable Tkinter widgets: sortable data table (right-click menu, Excel
export), date field with calendar, client picker with suggestions as you
type, and keyboard helpers."""
import calendar
import csv
import tkinter as tk
import tkinter.font as tkfont
import weakref
from datetime import date
from tkinter import filedialog, messagebox, ttk

from .. import config, dates, firm_info

# A restrained, professional palette: deep navy and one corporate blue accent; red/amber only
# where something needs attention. Row highlights are soft tints so long lists stay readable.
COLORS = {
    "sidebar": "#1b2a41", "sidebar_hover": "#26395a", "sidebar_active": "#2f4f7f", "sidebar_fg": "#ffffff",
    "sidebar_muted": "#9fb0c7",
    "bg": "#f4f6f9", "card": "#ffffff", "border": "#dde3ea", "text": "#1f2937", "muted": "#6b7280",
    "accent": "#2b5797",
    "red": "#b42318", "orange": "#c4520f", "yellow": "#a16207", "green": "#2f7d4f",
    "blue": "#2b5797", "teal": "#0f766e", "purple": "#5b4b8a", "grey": "#64748b",
}
ROW_TAGS = {
    "stripe": {"background": "#f7f9fb"},
    "red": {"background": "#fbe9e7"}, "orange": {"background": "#fdf0e3"},
    "yellow": {"background": "#fdf8e1"}, "green": {"background": "#eaf5ee"},
    "grey": {"background": "#f1f3f5"}, "cancelled": {"foreground": "#9aa3ae"},
}


class Tooltip:
    """A small hint shown when the mouse rests on a widget."""

    def __init__(self, widget, text, delay=500):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, event=None):
        self.hide()
        self.job = self.widget.after(self.delay, self.show)

    def show(self, x=None, y=None, text=None):
        self.hide()
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        tk.Label(self.tip, text=text or self.text, bg="#1f2937", fg="#ffffff", font=("Segoe UI", 9),
                 padx=8, pady=4, wraplength=420, justify="left").pack()
        if x is None:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip.geometry(f"+{x}+{y}")

    def hide(self, event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip is not None and self.tip.winfo_exists():
            self.tip.destroy()
        self.tip = None


def write_xlsx(path, headings, rows, preamble=(), sheet="Report"):
    """Write an Excel workbook: firm heading rows, then a formatted table with filters."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    for i, line in enumerate(preamble, start=1):
        if line:
            cell = ws.cell(row=i, column=1, value=line[0])
            cell.font = Font(bold=(i == 1), size=13 if i == 1 else 10)
    head_row = len(preamble) + 1
    for col, heading in enumerate(headings, start=1):
        cell = ws.cell(row=head_row, column=col, value=heading)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2A41")
    for r, values in enumerate(rows, start=head_row + 1):
        for col, value in enumerate(values, start=1):
            ws.cell(row=r, column=col, value=value)
    for col, heading in enumerate(headings, start=1):
        longest = max([len(str(heading))] + [len(str(v[col - 1])) for v in rows[:500]])
        ws.column_dimensions[ws.cell(row=head_row, column=col).column_letter].width = min(longest + 2, 50)
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)
    if rows:
        ws.auto_filter.ref = f"A{head_row}:{ws.cell(row=head_row + len(rows), column=len(headings)).coordinate}"
    wb.save(path)


def write_csv(path, headings, rows, preamble=()):
    """Write a CSV that opens cleanly in Excel (UTF-8 with BOM); preamble rows go above the headings."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerows(preamble)
        writer.writerow(headings)
        writer.writerows(rows)


class DataTable(ttk.Frame):
    """Treeview with scrollbars, click-to-sort headings, a right-click menu,
    a hint when it is empty, and export to Excel.

    columns: list of (key, heading, width[, kind]) where kind is 'text',
    'date' (ISO value shown as DD-MM-YYYY), 'datetime' (shown with the time
    of day when one is recorded) or 'num'. menu: function(row) returning
    [(label, function), ...] for the row right-clicked (None = separator).
    """

    def __init__(self, parent, columns, height=12, on_select=None, on_double=None, menu=None,
                 empty_text="Nothing to show for the current filters."):
        super().__init__(parent)
        self.menu, self.empty_text = menu, empty_text
        DataTable._all.add(self)
        self.columns = [(c + ("text",))[:4] if len(c) == 3 else c for c in columns]
        self.rows = []
        self._by_iid = {}
        self._sort = (None, False)
        keys = [c[0] for c in self.columns]
        self.tree = ttk.Treeview(self, columns=keys, show="headings", height=height, selectmode="browse")
        saved = (config.get_setting("column_widths", {}) or {}).get(self.layout_key(), {})
        for key, heading, width, kind in self.columns:
            self.tree.heading(key, text=heading, command=lambda k=key: self.sort_by(k))
            anchor = "e" if kind == "num" else ("center" if kind in ("date", "datetime") else "w")
            width = saved.get(key, width) if isinstance(saved.get(key, width), int) else width
            self.tree.column(key, width=width, minwidth=40, anchor=anchor, stretch=True)
        for tag, opts in ROW_TAGS.items():
            self.tree.tag_configure(tag, **opts)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self.selected()))
        if on_double:
            self.tree.bind("<Double-1>", lambda e: self.selected() and on_double(self.selected()))
        self.tree.bind("<Button-3>", self._right_click)
        self._font = tkfont.Font(family="Segoe UI", size=9)
        self._cell_tip = Tooltip(self.tree, "")
        self._tip_cell = None
        self.tree.bind("<Motion>", self._cell_hover, add="+")
        self.tree.bind("<Leave>", lambda e: (self._cell_tip.hide(), setattr(self, "_tip_cell", None)), add="+")
        self.empty_label = tk.Label(self, text="", bg="#ffffff", fg=COLORS["muted"], font=("Segoe UI", 10, "italic"))

    _all = weakref.WeakSet()  # every table, so column widths can be saved when the app closes

    def layout_key(self):
        return "|".join(c[0] for c in self.columns)

    @classmethod
    def save_widths(cls):
        """Remember the column widths people set, per table layout (this PC)."""
        widths = dict(config.get_setting("column_widths", {}) or {})
        for table in list(cls._all):
            try:
                widths[table.layout_key()] = {c[0]: int(table.tree.column(c[0], "width")) for c in table.columns}
            except tk.TclError:
                continue
        config.set_setting("column_widths", widths)

    def _cell_hover(self, event):
        """Show the full text of a cell that is too narrow to show it."""
        iid, col = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
        cell = (iid, col)
        if cell == self._tip_cell:
            return
        self._tip_cell = cell
        self._cell_tip.hide()
        if not iid or not col:
            return
        try:
            index = int(col[1:]) - 1
            text = str(self.tree.item(iid, "values")[index])
            width = self.tree.column(self.columns[index][0], "width")
        except (ValueError, IndexError, tk.TclError):
            return
        if text and self._font.measure(text) > width - 12:
            self._cell_tip.show(event.x_root + 12, event.y_root + 16, text)

    def _right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or not self.menu:
            return
        self.tree.selection_set(iid)
        items = self.menu(self._by_iid[iid])
        if not items:
            return
        m = tk.Menu(self, tearoff=False)
        for item in items:
            if item is None:
                m.add_separator()
            else:
                m.add_command(label=item[0], command=item[1])
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _display(self, row, key, kind):
        v = row.get(key)
        if v is None:
            return ""
        if kind == "date":
            return dates.to_display(v)
        if kind == "datetime":
            return dates.to_display_dt(v)
        return str(v)

    def select(self, predicate):
        """Select and show the first row for which predicate(row) is true; returns that row."""
        for iid, row in self._by_iid.items():
            if predicate(row):
                self.tree.selection_set(iid)
                self.tree.see(iid)
                return row
        return None

    def set_rows(self, rows, tag_fn=None):
        self.rows = list(rows)
        self._tag_fn = tag_fn
        if self._sort[0]:
            self._apply_sort()
        self._render()

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for i, row in enumerate(self.rows):
            values = [self._display(row, k, kind) for k, _, _, kind in self.columns]
            tags = ()
            if self._tag_fn:
                t = self._tag_fn(row)
                tags = tuple(t) if isinstance(t, (list, tuple)) else ((t,) if t else ())
            if i % 2 and not any(t in ("red", "orange", "yellow", "green", "grey") for t in tags):
                tags += ("stripe",)  # alternate rows lightly shaded
            iid = self.tree.insert("", "end", values=values, tags=tags)
            self._by_iid[iid] = row
        if self.rows or not self.empty_text:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text=self.empty_text)
            self.empty_label.place(relx=0.5, rely=0.45, anchor="center")

    def sort_by(self, key):
        col, desc = self._sort
        self._sort = (key, not desc if col == key else False)
        self._apply_sort()
        self._render()
        for k, heading, _, _ in self.columns:
            arrow = (" ▼" if self._sort[1] else " ▲") if k == key else ""
            self.tree.heading(k, text=heading + arrow)

    def _apply_sort(self):
        key, desc = self._sort
        kind = next(c[3] for c in self.columns if c[0] == key)

        def sort_key(row):
            v = row.get(key)
            if v is None or v == "":
                return (1, "")
            if kind == "num":
                try:
                    return (0, float(v))
                except (TypeError, ValueError):
                    return (0, 0.0)
            return (0, str(v).lower())
        blanks = [r for r in self.rows if sort_key(r)[0]]
        filled = sorted((r for r in self.rows if not sort_key(r)[0]), key=sort_key, reverse=desc)
        self.rows = filled + blanks

    def selected(self):
        sel = self.tree.selection()
        return self._by_iid.get(sel[0]) if sel else None

    def export(self, default_name, title=None):
        """Export the rows shown (current filters) to Excel, under the firm's name and the report title.
        Falls back to CSV if Excel support (openpyxl) is not installed."""
        if not self.rows:
            messagebox.showinfo("Export", "There are no rows to export with the current filters.", parent=self)
            return None
        try:
            import openpyxl  # noqa: F401
            ext, kind = ".xlsx", ("Excel workbook", "*.xlsx")
        except ImportError:
            ext, kind = ".csv", ("CSV (Excel)", "*.csv")
        path = filedialog.asksaveasfilename(
            parent=self, title="Export", defaultextension=ext,
            initialfile=f"{default_name}_{date.today().strftime('%d-%m-%Y')}{ext}", filetypes=[kind])
        if not path:
            return None
        headings = [c[1] for c in self.columns]
        data = [[self._cell(r, k, kind_) for k, _, _, kind_ in self.columns] for r in self.rows]
        title = title or default_name.replace("_", " ")
        preamble = firm_info.report_header(title) + [
            [f"Generated on {dates.to_display_dt(dates.now_iso())}"], []]
        try:
            if path.lower().endswith(".xlsx"):
                write_xlsx(path, headings, data, preamble, sheet=title)
            else:
                write_csv(path, headings, data, preamble)
        except OSError as exc:
            messagebox.showerror("Export", f"Could not save the file:\n{exc}", parent=self)
            return None
        toast = getattr(self.winfo_toplevel(), "toast", None)
        msg = f"{len(data)} row(s) exported to {path}"
        toast(msg) if toast else messagebox.showinfo("Export", msg, parent=self)
        return path

    export_csv = export  # older name

    def _cell(self, row, key, kind):
        """A value for the exported file: numbers stay numbers, everything else as shown on screen."""
        v = row.get(key)
        if kind == "num" and isinstance(v, (int, float)):
            return v
        return self._display(row, key, kind)


class CalendarPopup(tk.Toplevel):
    def __init__(self, parent, initial, on_pick):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.on_pick = on_pick
        self.configure(bg="#ffffff", highlightthickness=1, highlightbackground="#8a99ad")
        d = initial or date.today()
        self.year, self.month = d.year, d.month
        self.frame = tk.Frame(self, bg="#ffffff", padx=4, pady=4)
        self.frame.pack()
        self._draw()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", self._focus_out)

    def _focus_out(self, _e):
        self.after(100, lambda: self.winfo_exists() and self.focus_get() is None and self.destroy())

    def _shift(self, delta):
        m = self.month - 1 + delta
        self.year, self.month = self.year + m // 12, m % 12 + 1
        self._draw()

    def _draw(self):
        for w in self.frame.winfo_children():
            w.destroy()
        head = tk.Frame(self.frame, bg="#ffffff")
        head.grid(row=0, column=0, columnspan=7, sticky="ew")
        tk.Button(head, text="◀", width=3, relief="flat", command=lambda: self._shift(-1)).pack(side="left")
        tk.Label(head, text=f"{calendar.month_name[self.month]} {self.year}", bg="#ffffff",
                 font=("Segoe UI", 10, "bold")).pack(side="left", expand=True)
        tk.Button(head, text="▶", width=3, relief="flat", command=lambda: self._shift(1)).pack(side="right")
        for i, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(self.frame, text=name, bg="#ffffff", fg="#5a6473", width=4).grid(row=1, column=i)
        today = date.today()
        for r, week in enumerate(calendar.monthcalendar(self.year, self.month), start=2):
            for c, day in enumerate(week):
                if not day:
                    continue
                d = date(self.year, self.month, day)
                b = tk.Button(self.frame, text=str(day), width=3, relief="flat",
                              bg="#dbeafe" if d == today else "#ffffff",
                              command=lambda d=d: self._pick(d))
                b.grid(row=r, column=c, padx=1, pady=1)
        tk.Button(self.frame, text="Today", relief="groove", command=lambda: self._pick(today)).grid(
            row=9, column=0, columnspan=7, sticky="ew", pady=(4, 0))

    def _pick(self, d):
        self.on_pick(d)
        self.destroy()

    def show_below(self, widget):
        self.update_idletasks()
        self.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height()}")
        self.deiconify()
        self.lift()
        self.focus_force()


class DateEntry(ttk.Frame):
    """Text box for DD-MM-YYYY with a calendar button."""

    def __init__(self, parent, width=12, default_today=False):
        super().__init__(parent)
        self.var = tk.StringVar(value=dates.to_display(dates.today_iso()) if default_today else "")
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left")
        ttk.Button(self, text="📅", width=3, command=self._open).pack(side="left", padx=(2, 0))

    def _open(self):
        try:
            current = dates.iso_to_date(dates.parse_display(self.var.get()))
        except ValueError:
            current = None
        CalendarPopup(self, current, lambda d: self.var.set(d.strftime(dates.DISPLAY_FORMAT))).show_below(self.entry)

    def get_iso(self, field, required=False):
        """Return ISO date or None; raises ValueError with a friendly message."""
        return dates.parse_display(self.var.get(), field, required)

    def set_iso(self, iso):
        self.var.set(dates.to_display(iso))

    def clear(self):
        self.var.set("")


class DateTimeEntry(ttk.Frame):
    """Date (DD-MM-YYYY, with calendar) plus an optional time such as 11:00 AM."""

    def __init__(self, parent, width=12):
        super().__init__(parent)
        self.date = DateEntry(self, width=width)
        self.date.pack(side="left")
        ttk.Label(self, text="  Time").pack(side="left")
        self.time = tk.StringVar()
        ttk.Entry(self, textvariable=self.time, width=9).pack(side="left", padx=(4, 0))

    def get_iso(self, field, required=False):
        """ISO date-time, or the date alone when no time is typed; raises ValueError."""
        d = self.date.get_iso(field, required)
        hm = dates.parse_time(self.time.get(), f"{field} time")
        if hm is not None and not d:
            raise ValueError(f"{field}: please enter the date as well as the time.")
        return dates.combine(d, hm)

    def set_iso(self, iso):
        self.date.set_iso(iso)
        self.time.set(dates.time_display(dates.iso_to_datetime(iso)) if dates.has_time(iso) else "")

    def clear(self):
        self.date.clear()
        self.time.set("")


class Autocomplete:
    """A list of matching names that drops down under a box and narrows as the user types.

    Typing stays in the box: Down/Up move through the list, Enter or a click
    picks a name, Esc closes it. get_items() returns (shown text, text to
    match against) pairs; matching is case-insensitive, anywhere in the text.
    """
    MAX_ROWS = 10
    _IGNORE = {"Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L",
               "Control_R", "Alt_L", "Alt_R", "Left", "Right", "Home", "End"}

    def __init__(self, widget, get_items, on_choose=None):
        self.widget, self.get_items, self.on_choose = widget, get_items, on_choose
        self.popup = self.listbox = None
        widget.bind("<KeyRelease>", self._typed, add="+")
        widget.bind("<Down>", lambda e: self._move(1), add="+")
        widget.bind("<Up>", lambda e: self._move(-1), add="+")
        widget.bind("<Return>", self._enter, add="+")
        widget.bind("<KP_Enter>", self._enter, add="+")
        widget.bind("<Escape>", lambda e: self._escape(), add="+")
        widget.bind("<FocusOut>", lambda e: widget.after(200, self._hide_if_left), add="+")
        widget.bind("<Destroy>", lambda e: self.hide(), add="+")

    def visible(self):
        return self.popup is not None and self.popup.winfo_exists() and self.popup.winfo_viewable()

    def matches(self, text):
        text = text.strip().lower()
        if not text:
            return []
        return [shown for shown, search in self.get_items() if text in search.lower()]

    def _typed(self, event):
        if event.keysym in self._IGNORE:
            return
        found = self.matches(self.widget.get())
        if not found or found == [self.widget.get()]:
            self.hide()
        else:
            self.show(found)

    def show(self, items):
        if self.popup is None or not self.popup.winfo_exists():
            self.popup = tk.Toplevel(self.widget)
            self.popup.withdraw()
            self.popup.overrideredirect(True)
            self.popup.attributes("-topmost", True)
            self.listbox = tk.Listbox(self.popup, activestyle="none", exportselection=False, relief="solid",
                                      borderwidth=1, font=("Segoe UI", 9), selectbackground="#2b5797")
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<ButtonRelease-1>", lambda e: self._pick_at(e.y))
        self.listbox.delete(0, "end")
        for text in items:
            self.listbox.insert("end", text)
        self.listbox.configure(height=min(len(items), self.MAX_ROWS), width=max(len(t) for t in items) + 2)
        self.popup.update_idletasks()
        w = min(max(self.widget.winfo_width(), self.listbox.winfo_reqwidth()), 720)  # wide enough for the names
        h = self.listbox.winfo_reqheight()
        x, y = self.widget.winfo_rootx(), self.widget.winfo_rooty() + self.widget.winfo_height()
        self.popup.geometry(f"{w}x{h}+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()

    def hide(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.withdraw()

    def _hide_if_left(self):
        try:
            focus = self.widget.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        if focus is not self.widget and focus is not self.listbox:
            self.hide()

    def _move(self, step):
        if not self.visible():
            return None
        size = self.listbox.size()
        cur = self.listbox.curselection()
        i = (cur[0] + step) if cur else (0 if step > 0 else size - 1)
        i = max(0, min(size - 1, i))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(i)
        self.listbox.see(i)
        return "break"

    def _enter(self, event):
        if not self.visible():
            return None
        cur = self.listbox.curselection()
        if cur:
            self.choose(self.listbox.get(cur[0]))
        elif self.listbox.size() == 1:
            self.choose(self.listbox.get(0))
        return "break"

    def _escape(self):
        if self.visible():
            self.hide()
            return "break"
        return None

    def _pick_at(self, y):
        i = self.listbox.nearest(y)
        if i >= 0:
            self.choose(self.listbox.get(i))

    def choose(self, text):
        self.widget.delete(0, "end")
        self.widget.insert(0, text)
        self.hide()
        self.widget.focus_set()
        self.widget.icursor("end")
        if self.on_choose:
            self.on_choose(text)


def combo_autocomplete(combo):
    """Suggest a combobox's own values (e.g. staff names) as the user types."""
    return Autocomplete(combo, lambda: [(v, v) for v in combo.cget("values")])


def live_search(entry, callback, delay=350):
    """Run callback a moment after the user stops typing, so tables filter as they type."""
    state = {"job": None}

    def typed(event):
        if event.keysym in Autocomplete._IGNORE and event.keysym not in ("BackSpace", "Delete"):
            return
        if state["job"]:
            entry.after_cancel(state["job"])
        state["job"] = entry.after(delay, callback)
    entry.bind("<KeyRelease>", typed, add="+")


class ClientPicker(ttk.Combobox):
    """Combobox listing clients as 'CL0001 - Holder (Firm)'. Typing shows the matching clients
    (by name, firm, client ID or PAN) in a list under the box."""

    ALL = "(All clients)"

    def __init__(self, parent, include_all=False, width=40, on_change=None):
        super().__init__(parent, width=width)
        self.include_all = include_all
        self.on_change = on_change
        self._items = []
        self._values = []
        self.autocomplete = Autocomplete(self, lambda: self._search_items, on_choose=lambda t: self._changed())
        self._search_items = []
        self.bind("<<ComboboxSelected>>", lambda e: self._changed())
        self.bind("<FocusOut>", lambda e: self._changed())
        self._last = None

    @staticmethod
    def label(c):
        firm = f" ({c['firm_name']})" if c.get("firm_name") else ""
        return f"{c['client_code']} - {c['holder_name']}{firm}"

    def load(self, clients):
        keep = self.get_id()
        self._items = [(self.label(c), c["client_id"]) for c in clients]
        self._search_items = [(self.label(c), f"{self.label(c)} {c.get('pan') or ''}") for c in clients]
        self._values = ([self.ALL] if self.include_all else []) + [x[0] for x in self._items]
        self["values"] = self._values
        if keep and any(cid == keep for _, cid in self._items):
            self.set_id(keep)
        elif self.include_all:
            self.set(self.ALL)
        else:
            self.set("")

    def _changed(self):
        cid = self.get_id()
        if cid != self._last:
            self._last = cid
            if self.on_change:
                self.on_change(cid)

    def get_id(self):
        text = self.get().strip()
        for label, cid in self._items:
            if label == text:
                return cid
        return None

    def set_id(self, client_id):
        for label, cid in self._items:
            if cid == client_id:
                self.set(label)
                self._last = cid
                return
        self.set(self.ALL if self.include_all else "")
        self._last = None


def enter_moves_focus(container):
    """In a form, Enter moves to the next field (as Tab does) instead of doing nothing."""
    def next_field(event):
        nxt = event.widget.tk_focusNext()
        for _ in range(30):  # skip buttons (e.g. the calendar button) to reach the next field to type in
            if nxt is None or not isinstance(nxt, (ttk.Button, tk.Button)):
                break
            nxt = nxt.tk_focusNext()
        if nxt is not None:
            nxt.focus_set()
        return "break"

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, (ttk.Entry, tk.Entry)):  # ttk.Combobox is a ttk.Entry too
                child.bind("<Return>", next_field, add="+")
            walk(child)
    walk(container)


class ScrollArea(ttk.Frame):
    """A page that fills the space it is given and shows a scrollbar only when its contents are too tall
    (small or low-resolution screens). Put the contents in .inner. Wide tables scroll sideways by themselves."""
    NO_WHEEL = ("Treeview", "Listbox", "Text", "TCombobox")   # these scroll their own contents

    def __init__(self, parent):
        super().__init__(parent, style="Screen.TFrame")
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0, borderwidth=0, width=1, height=1)
        self.inner = ttk.Frame(self.canvas, style="Screen.TFrame")
        self._window = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.ys = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.ys.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._laid_out = None
        self._alive = True      # the window's bindings below outlive a screen that is rebuilt
        self.bind("<Configure>", lambda e: self.layout())
        top = self.winfo_toplevel()
        top.bind("<MouseWheel>", self._wheel, add="+")
        top.bind("<FocusIn>", self._show_focus, add="+")
        self._watch()

    def _watch(self):
        # A label or tab can make the contents taller at any time; Tk sends no event for that.
        self.layout()
        self._watch_job = self.after(300, self._watch)

    def destroy(self):
        self.after_cancel(self._watch_job)
        self._alive = False
        super().destroy()

    def layout(self):
        have_w, have_h = self.winfo_width(), self.winfo_height()
        need_h = self.inner.winfo_reqheight()
        state = (have_w, have_h, need_h)
        if state == self._laid_out or have_w <= 1:
            return
        self._laid_out = state
        over = need_h > have_h
        self.ys.grid(row=0, column=1, sticky="ns") if over else self.ys.grid_remove()
        width = have_w - (self.ys.winfo_reqwidth() if over else 0)
        height = max(need_h, have_h)
        self.canvas.itemconfigure(self._window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if not over:
            self.canvas.yview_moveto(0)

    def needs_scroll(self):
        return bool(self.ys.winfo_manager())

    def _wheel(self, event):
        if not self._alive or not self.winfo_ismapped() or not self.ys.winfo_manager():
            return
        if isinstance(event.widget, tk.Misc) and event.widget.winfo_class() in self.NO_WHEEL:
            return
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _show_focus(self, event):
        """Enter or Tab moving to a field below the visible part: bring it into view."""
        w = event.widget
        if not self._alive or not isinstance(w, tk.Misc) or not self.ys.winfo_manager() or not str(w).startswith(str(self.inner)):
            return
        total = self.canvas.bbox("all")
        if not total or total[3] <= 0:
            return
        top = w.winfo_rooty() - self.inner.winfo_rooty()
        first = self.canvas.canvasy(0)
        shown = self.canvas.winfo_height()
        if top < first or top + w.winfo_height() > first + shown:
            self.canvas.yview_moveto(max(0, top - 20) / total[3])


def labeled(parent, text, row, col, widget, colspan=1):
    """Place a label + widget pair in a grid form."""
    ttk.Label(parent, text=text).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=4)
    widget.grid(row=row, column=col + 1, columnspan=colspan, sticky="w", pady=4, padx=(0, 18))
    return widget


def ask_text(parent, title, prompt):
    """Small modal prompt for a reason/remark; returns the text or None."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent.winfo_toplevel())
    win.resizable(False, False)
    ttk.Label(win, text=prompt, wraplength=380).pack(padx=14, pady=(14, 6), anchor="w")
    var = tk.StringVar()
    entry = ttk.Entry(win, textvariable=var, width=55)
    entry.pack(padx=14)
    result = {"value": None}

    def ok():
        result["value"] = var.get().strip()
        win.destroy()
    bar = ttk.Frame(win)
    bar.pack(pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left", padx=4)
    win.bind("<Return>", lambda e: ok())
    win.bind("<Escape>", lambda e: win.destroy())
    entry.focus_set()
    win.grab_set()
    win.wait_window()
    return result["value"] or None
