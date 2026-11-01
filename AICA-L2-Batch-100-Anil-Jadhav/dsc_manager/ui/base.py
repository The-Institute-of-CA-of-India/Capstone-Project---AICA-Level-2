"""Base class shared by all screens."""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import firm_info
from ..database import CertificateConflict, ValidationError
from .widgets import COLORS, ROW_TAGS, ScrollArea


class Screen(ttk.Frame):
    title = ""
    subtitle = ""
    show_firm = False   # report screens show the firm's name and address in their heading

    def __init__(self, parent, app):
        super().__init__(parent, padding=(16, 12), style="Screen.TFrame")
        self.app = app
        head = ttk.Frame(self, style="Screen.TFrame")
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text=self.title, style="Title.TLabel").pack(side="left")
        if self.subtitle:
            ttk.Label(head, text=self.subtitle, style="Muted.TLabel").pack(side="left", padx=12, pady=(6, 0))
        if self.show_firm and firm_info.FIRM_NAME:
            firm = ttk.Frame(head, style="Screen.TFrame")
            firm.pack(side="right")
            ttk.Label(firm, text=firm_info.FIRM_NAME, style="Section.TLabel").pack(anchor="e")
            if firm_info.address_lines():
                ttk.Label(firm, text=", ".join(firm_info.address_lines()), style="Muted.TLabel").pack(anchor="e")
        self.head = head
        self.scroll = ScrollArea(self)
        self.scroll.pack(fill="both", expand=True)
        self.body = self.scroll.inner
        self.build(self.body)

    @property
    def db(self):
        return self.app.db

    def build(self, body):
        pass

    def on_show(self, **kwargs):
        self.refresh()

    def reset_filters(self):
        """Put search boxes and filters back to their defaults (no refresh).

        Called each time the user comes to this screen from another one, so
        filters set on an earlier visit are never silently still applied.
        """

    def refresh(self):
        pass

    # Convenience wrappers so every screen reports problems the same way.
    def error(self, msg, title="Please check"):
        messagebox.showerror(title, msg, parent=self)

    def info(self, msg, title="Saved", popup=False):
        """A success message: a short note that fades by itself (popup=True for a box to read and close)."""
        if popup:
            messagebox.showinfo(title, msg, parent=self)
        else:
            self.app.toast(msg)

    def token_menu(self, row, extra=()):
        """Right-click menu for a row that belongs to a token: extra items, then the token's histories."""
        items = list(extra)
        if row and row.get("token_id"):
            from .dialogs import CertHistoryDialog, TokenHistoryDialog
            if items:
                items.append(None)
            items += [("Token History", lambda: TokenHistoryDialog(self, self.db, row["token_id"]).show()),
                      ("Certificate History", lambda: CertHistoryDialog(self, self.db, row["token_id"]).show())]
        return items

    def open_token_history(self, row):
        if row and row.get("token_id"):
            from .dialogs import TokenHistoryDialog
            TokenHistoryDialog(self, self.db, row["token_id"]).show()

    def send_whatsapp(self, message, quiet=False):
        """message = (mobile, client name, text) from dsc_manager.whatsapp; opens WhatsApp with it typed in.
        Returns True when WhatsApp was opened; quiet=True leaves the confirmation to the caller."""
        from .. import whatsapp
        mobile, client, text = message
        if whatsapp.open_chat(mobile, text):
            if not quiet:
                self.app.toast(f"WhatsApp opened for {client} - check the message and press Send.")
            return True
        else:
            self.error(f"{client} has no valid mobile number ({mobile or 'blank'}), so the WhatsApp message "
                       "could not be prepared. Correct the mobile number on the Clients screen.", "WhatsApp")
            return False

    def confirm(self, msg, title="Please confirm"):
        return messagebox.askyesno(title, msg, parent=self)

    def run(self, fn, *args, **kwargs):
        """Call fn and show ValidationError/ValueError as a message. Returns (ok, result)."""
        try:
            return True, fn(*args, **kwargs)
        except (ValidationError, ValueError) as exc:
            self.error(str(exc))
        except CertificateConflict:
            raise
        except Exception as exc:  # unexpected - show rather than crash the app
            self.error(f"Unexpected error: {exc}", "Error")
        return False, None


def filter_bar(parent):
    bar = ttk.Frame(parent, style="Screen.TFrame")
    bar.pack(fill="x", pady=(0, 6))
    return bar


def button_bar(parent, side="top"):
    bar = ttk.Frame(parent, style="Screen.TFrame")
    bar.pack(fill="x", pady=6, side=side)
    return bar


def legend(parent, items):
    """Small colour legend: items = [(color_key, text), ...]."""
    f = ttk.Frame(parent, style="Screen.TFrame")
    for key, text in items:
        tk.Label(f, text="  ", bg=ROW_TAGS[key]["background"], relief="solid", bd=1).pack(side="left", padx=(8, 3))
        ttk.Label(f, text=text, style="Muted.TLabel").pack(side="left")
    return f


__all__ = ["Screen", "filter_bar", "button_bar", "legend", "COLORS"]
