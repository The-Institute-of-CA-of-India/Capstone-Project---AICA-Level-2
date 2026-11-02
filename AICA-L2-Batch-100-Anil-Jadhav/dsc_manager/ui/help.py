"""Help: a one-page guide to the daily work and the keyboard shortcuts."""
import tkinter as tk
from tkinter import ttk

from .. import single_user
from .base import Screen
from .widgets import COLORS

GUIDE = [
    ("h", "Receiving a DSC from a client (DSC Inward)"),
    ("p", "1. Plug the client's token into the PC and click Read Token (on the Dashboard or DSC Inward). "
          "The token serial, holder, certificate and expiry fill in by themselves."),
    ("p", "2. Check the client (type a few letters of the name to pick it, or + New), choose the Purpose and "
          "click Save (Ctrl+S). The token goes to the custodian. Leave 'Send WhatsApp message' ticked to "
          "inform the client."),
    ("p", "3. Several tokens from the same client? Use Save & Add Another: the client and purpose stay, only "
          "the token changes."),
    ("h", "Giving a token to staff or a consultant (DSC in Custody)"),
    ("p", "Open DSC in Custody, select the token and click Issue to Staff or Hand to Consultant. When it comes "
          "back, select it and click Return from Staff / Return from Consultant. Tokens always go back to the "
          "custodian - there are no staff-to-staff transfers. If the client collects the token directly from "
          "the consultant, use Client Collected from Consultant: this ends the firm's custody."),
    ("h", "Returning a DSC to the client (DSC Outward)"),
    ("p", "Only tokens with the custodian are listed. Select the token, check 'Returned To', and save. "
          "A token out with staff or a consultant must be returned to the custodian first."),
    ("h", "Certificates and expiry"),
    ("p", "Expiry Alerts lists certificates expired or expiring in 7/15/30 days (checked to the minute). "
          "Use Record Renewal for a renewed certificate, or WhatsApp Reminder to Client."),
    ("h", "Lost or replaced tokens"),
    ("p", "Mark the token Inactive (Clients > select client > Mark Token Inactive, or DSC in Custody > Lost / "
          "Inactive) with the reason. When a client brings a new token, the app asks which old token it "
          "replaces."),
    ("h", "Partners' Google Sheet"),
    ("p", "If set up (Settings > Google Sheet for Partners), every report goes to a Google Sheet about a minute "
          "after each entry, so the partners can see them from their desks. PAN and mobile numbers are masked "
          "there. Changes made in the sheet do not come back to this app."),
    ("h", "Finding anything"),
    ("p", "Use the search box at the top (Ctrl+F): type a name, PAN, mobile or token number. Right-click any "
          "row for its actions; double-click a token for its full history, or a client for all their details."),
    ("h", "Mistakes"),
    ("p", "Click Undo on the message that appears after saving (for about 10 seconds). Later, select the entry "
          "in Previous Inward Entries or Outward History: Correct Entry fixes the date, names, purpose or "
          "remarks (with a reason; the old values are kept in Token History). For a wrong client or token, "
          "Cancel Entry and enter it again. Nothing is ever deleted."),
    ("h", "Custodian, staff and consultants"),
    ("p", "Settings > Custodian, Staff & Consultants holds everyone who can hold a token: appoint the custodian, keep the list of "
          "staff members, and add or edit consultants."),
    ("h", "Restoring a backup"),
    ("p", "Backup Database > Restore from Backup replaces all the data with a backup's, after showing what the "
          "backup holds. The current data is saved first (DSC_BeforeRestore_...), so a restore can be undone."),
    ("h", "Keyboard"),
    ("p", "Ctrl+F  search      Ctrl+S  save      F5  refresh      Enter  next field      Esc  close a window\n"
          "Dates can be typed without dashes: 29102026 or 291026."),
    ("h", "Good to know"),
    ("p", f"{single_user.NOTE} Switch on the automatic daily backup (Backup Database). "
          "No DSC PINs or passwords are stored by this application."),
]


class HelpScreen(Screen):
    title = "Help"
    subtitle = "How to use the DSC Management Tool"

    def build(self, body):
        frame = tk.Frame(body, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"])
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", bg=COLORS["card"], relief="flat", padx=24, pady=16,
                       font=("Segoe UI", 10), fg=COLORS["text"], cursor="arrow")
        sb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure("h", font=("Segoe UI", 11, "bold"), foreground=COLORS["accent"], spacing1=12,
                           spacing3=4)
        text.tag_configure("p", spacing3=4, lmargin1=8, lmargin2=8)
        for kind, line in GUIDE:
            text.insert("end", line + "\n", kind)
        text.configure(state="disabled")
