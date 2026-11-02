"""Date and time helpers.

Dates are stored in SQLite as ISO text so they sort and compare correctly:
'YYYY-MM-DD' for a date, 'YYYY-MM-DD HH:MM:SS' for a date and time (local
Indian time). A certificate expiry stored as a date only means "time not
recorded" and is treated as the start of that day (12:00 AM), so alerts err
on the early side. Everything is shown to the user in Indian format
(DD-MM-YYYY, hh:mm AM/PM).
"""
import re
from datetime import date, datetime, time

DISPLAY_FORMAT = "%d-%m-%Y"
ISO_FORMAT = "%Y-%m-%d"
ISO_DT_FORMAT = "%Y-%m-%d %H:%M:%S"

_INPUT_RE = re.compile(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})\s*$")
_DIGITS_RE = re.compile(r"^(\d{8}|\d{6})$")
_TIME_RE = re.compile(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\s*$", re.IGNORECASE)


def today():
    return date.today()


def now():
    """Current system time to the second (local time)."""
    return datetime.now().replace(microsecond=0)


def today_iso():
    return today().isoformat()


def now_iso():
    return now().strftime(ISO_DT_FORMAT)


def iso_to_date(iso):
    """Convert an ISO date/datetime string (or date) to a date; blank gives None."""
    if not iso:
        return None
    if isinstance(iso, datetime):
        return iso.date()
    if isinstance(iso, date):
        return iso
    return datetime.strptime(str(iso)[:10], ISO_FORMAT).date()


def has_time(iso):
    return bool(iso) and len(str(iso)) > 10


def iso_to_datetime(iso):
    """ISO date or datetime -> datetime (a date alone = 12:00 AM that day)."""
    if not iso:
        return None
    if isinstance(iso, datetime):
        return iso
    if isinstance(iso, date):
        return datetime.combine(iso, time())
    s = str(iso)
    if len(s) <= 10:
        return datetime.combine(iso_to_date(s), time())
    return datetime.strptime(s[:19], ISO_DT_FORMAT if len(s) >= 19 else "%Y-%m-%d %H:%M")


def to_display(iso):
    """ISO string -> DD-MM-YYYY; blank stays blank."""
    d = iso_to_date(iso)
    return d.strftime(DISPLAY_FORMAT) if d else ""


def time_display(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def to_display_dt(iso):
    """ISO date/datetime -> 'DD-MM-YYYY hh:mm AM' (date only when no time is recorded)."""
    if not iso:
        return ""
    if not has_time(iso):
        return to_display(iso)
    dt = iso_to_datetime(iso)
    return f"{dt.strftime(DISPLAY_FORMAT)} {time_display(dt)}"


def parse_display(text, field="Date", required=False):
    """Parse user input in DD-MM-YYYY (also accepts / or .) and return ISO text.

    Raises ValueError with a user-friendly message when the value is invalid.
    Returns None for a blank, optional value.
    """
    text = (text or "").strip()
    if not text:
        if required:
            raise ValueError(f"{field} is required.")
        return None
    m = _INPUT_RE.match(text)
    digits = _DIGITS_RE.match(text)
    if m:
        day, month, year = (int(g) for g in m.groups())
    elif digits:  # typed without separators: 29102026 or 291026
        day, month, year = int(text[:2]), int(text[2:4]), int(text[4:])
    else:
        raise ValueError(f"{field} '{text}' is not valid. Please use DD-MM-YYYY.")
    if year < 100:  # two-digit year: 26 -> 2026
        year += 2000
    try:
        d = date(year, month, day)
    except ValueError:
        raise ValueError(f"{field} '{text}' is not a real calendar date.") from None
    if not 1900 <= year <= 2200:
        raise ValueError(f"{field} '{text}' has an unrealistic year.")
    return d.isoformat()


def parse_time(text, field="Time"):
    """'11', '11:30', '2:15 pm', '14:15' -> (hour, minute); blank -> None."""
    text = (text or "").strip()
    if not text:
        return None
    m = _TIME_RE.match(text)
    if not m:
        raise ValueError(f"{field} '{text}' is not valid. Use hh:mm, e.g. 11:00 AM or 14:30.")
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm:
        if not 1 <= hour <= 12:
            raise ValueError(f"{field} '{text}': hour must be 1-12 with AM/PM.")
        hour = hour % 12 + (12 if ampm == "pm" else 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"{field} '{text}' is not a real time.")
    return hour, minute


def combine(date_iso, hm):
    """ISO date + (hour, minute) -> ISO datetime; no time keeps the date alone."""
    if not date_iso:
        return None
    if hm is None:
        return date_iso
    return f"{date_iso} {hm[0]:02d}:{hm[1]:02d}:00"


def days_between(start_iso, end):
    """Whole days from start_iso to end (a date)."""
    s = iso_to_date(start_iso)
    return (end - s).days if s else None
