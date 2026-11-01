"""WhatsApp messages to clients: DSC received, returned, collected from a
consultant, and certificate expiry reminders.

The app opens WhatsApp with the client's chat and the message already typed;
the user checks it and presses Send. Nothing is sent automatically. The
WhatsApp Desktop app is used when installed (every message goes into the app
that is already open); otherwise WhatsApp Web in the browser (Settings). The wording of each message is editable (Settings screen) and
is kept in the firm's own database; {placeholders} are filled in per message.
"""
import webbrowser
from urllib.parse import quote

from . import config, dates, firm_info
from .database import mobile_key

KINDS = {
    "inward": "DSC received (inward)",
    "outward": "DSC returned (outward)",
    "collected": "DSC collected from consultant",
    "expiry": "Certificate expiry reminder",
}

DEFAULTS = {
    "inward": "Dear {name},\nWe have received your DSC token ({token}) on {date} for {purpose}.\n\n{firm}",
    "outward": "Dear {name},\nYour DSC token ({token}) has been returned to {returned_to} on {date}.\n\n{firm}",
    "collected": ("Dear {name},\nYour DSC token ({token}) has been collected by {returned_to} from "
                  "{consultant} on {date}.\n\n{firm}"),
    "expiry": ("Dear {name},\nYour Digital Signature Certificate (token {token}) expires on {expiry}. "
               "Please arrange for its renewal.\n\n{firm}"),
}

PLACEHOLDERS = [
    ("{name}", "DSC holder name"), ("{token}", "token serial number"), ("{date}", "date of the entry"),
    ("{purpose}", "purpose / assignment"), ("{returned_to}", "person the token was returned to"),
    ("{consultant}", "consultant who had the token"), ("{expiry}", "certificate expiry date and time"),
    ("{firm}", "your firm's name"),
]


def get_template(db, kind):
    return db.get_meta(f"whatsapp_{kind}", DEFAULTS[kind])


def set_template(db, kind, text):
    """Save the wording; an empty text goes back to the default."""
    db.set_meta(f"whatsapp_{kind}", (text or "").strip() or DEFAULTS[kind])


class _Values(dict):
    def __missing__(self, key):  # an unknown {placeholder} is left as typed
        return "{" + key + "}"


def render(text, values):
    filled = text.format_map(_Values(values, firm=firm_info.FIRM_NAME))
    return "\n".join(line.rstrip() for line in filled.strip().splitlines()).strip()


def phone(mobile):
    """WhatsApp number (country code 91 + 10 digits) or None if the mobile is not a valid Indian mobile."""
    digits = mobile_key(mobile)
    return f"91{digits}" if len(digits) == 10 and digits[0] in "6789" else None


MODES = {"desktop": "WhatsApp Desktop app", "web": "WhatsApp Web (browser)"}


def desktop_installed():
    """True when the WhatsApp Desktop app is installed (it handles whatsapp: links)."""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "whatsapp"))
        return True
    except (ImportError, OSError):
        return False


def current_mode():
    """'desktop' or 'web' (Settings); by default the Desktop app when it is installed."""
    mode = config.get_setting("whatsapp_mode", "auto")
    if mode in MODES:
        return mode
    return "desktop" if desktop_installed() else "web"


def chat_url(mobile, text, mode=None):
    """Link that opens the client's chat with the message typed in.

    Desktop: the running WhatsApp app opens the chat - no browser tab, no prompt.
    Web: goes straight to the chat in WhatsApp Web (skipping the 'Share on WhatsApp' page);
    the browser opens a new tab for each message.
    """
    number = phone(mobile)
    if not number:
        return None
    if (mode or current_mode()) == "desktop":
        return f"whatsapp://send?phone={number}&text={quote(text)}"
    return f"https://web.whatsapp.com/send?phone={number}&text={quote(text)}"


def open_chat(mobile, text):
    url = chat_url(mobile, text)
    if url:
        webbrowser.open(url)
    return url


# ---------------------------------------------------------------------- messages for each event
def for_inward(db, inward_id):
    r = db._one("SELECT i.*, t.token_serial, c.mobile, c.holder_name AS client_name FROM inward i "
                "JOIN tokens t USING (token_id) JOIN clients c ON c.client_id = i.client_id "
                "WHERE i.inward_id = ?", (inward_id,))
    text = render(get_template(db, "inward"), {
        "name": r["holder_name"], "token": r["token_serial"], "date": dates.to_display(r["inward_date"]),
        "purpose": r["purpose"]})
    return r["mobile"], r["client_name"], text


def for_outward(db, outward_id):
    r = db._one("SELECT o.*, t.token_serial, c.mobile, c.holder_name AS client_name FROM outward o "
                "JOIN tokens t USING (token_id) JOIN clients c ON c.client_id = o.client_id "
                "WHERE o.outward_id = ?", (outward_id,))
    kind = "collected" if r["via_consultant_id"] else "outward"
    text = render(get_template(db, kind), {
        "name": r["holder_name"], "token": r["token_serial"], "date": dates.to_display(r["outward_date"]),
        "purpose": r["purpose"] or "", "returned_to": r["returned_to"], "consultant": r["returned_by"]})
    return r["mobile"], r["client_name"], text


def for_expiry(db, token_id):
    r = db._one("SELECT t.*, c.mobile, c.holder_name AS client_name, cur.expiry_date FROM tokens t "
                "JOIN clients c USING (client_id) "
                "LEFT JOIN certificates cur ON cur.token_id = t.token_id AND cur.is_current = 1 "
                "WHERE t.token_id = ?", (token_id,))
    text = render(get_template(db, "expiry"), {
        "name": r["holder_name"], "token": r["token_serial"],
        "expiry": dates.to_display_dt(r["expiry_date"]) or "(expiry date not recorded)"})
    return r["mobile"], r["client_name"], text
