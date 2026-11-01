"""SQLite data layer and business rules for the DSC Management Tool.

Key design points
-----------------
* Every inward, outward and internal movement is stored permanently. Mistakes
  are handled by *cancelling* an entry (with a reason), never by deleting it.
* Live custody is never stored as a number. A token is in custody when it has
  an active inward entry that has no active outward entry against it.
* Inside the firm, a token is always with the custodian, a staff member or an
  outside consultant. That holder is never stored either: it is worked out
  from the latest active movement of the open inward entry (no movement =
  with the custodian). Every movement goes through the custodian: no
  staff-to-staff transfers, and staff or consultants return only to the
  custodian. Movement times are stamped from the system clock.
* There is exactly one custodian at a time. Appointing a new one relieves the
  old one and moves every token he held to the new one with a hand-over entry.
* Only one live custody record may exist per token. If a token that is
  already in custody is received again (after the user confirms), the older
  open inward entry is marked "Superseded" by the new one.
* Certificate validity is tracked in its own table, separate from physical
  custody, to the minute. Renewals create a new certificate record; the old
  record (and its expiry) is kept as history.
* No DSC PINs, passwords or private keys are stored anywhere.
"""
import os
import re
import sqlite3
from datetime import datetime

from . import dates

PURPOSES = ["Statutory Audit", "Tax Audit", "ITR Filing", "GST", "ROC Filing",
            "Bank Audit", "Other"]
CERT_STATUSES = ["Active", "Renewal in Progress", "Revoked", "Inactive"]
CONSULTANT_KINDS = ["CS", "CA", "Advocate", "Other"]
# Certificates with these administrative statuses are left out of expiry alert
# counts (they are not expected to be renewed or used).
ALERT_EXCLUDED_STATUSES = ("Revoked", "Inactive")
DUE_SOON_DAYS = 3

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# An Indian mobile number: 10 digits starting 6-9, optionally written with +91, 91 or 0 in front.
MOBILE_RE = re.compile(r"^(\+?91|0)?[6-9][0-9]{9}$")
MOBILE_MSG = "Mobile number must be 10 digits starting with 6, 7, 8 or 9 (a +91 or 0 prefix is allowed)."

EXPIRY_FILTERS = {
    "all": "All tokens",
    "expired": "Expired",
    "today": "Expires today",
    "7": "Within 7 days",
    "15": "Within 15 days",
    "30": "Within 30 days",
    "beyond": "Valid beyond 30 days",
    "unknown": "Expiry date unknown",
    "renewal": "Renewal in progress",
}

MOVEMENT_LABELS = {
    "issue_staff": "Issued to staff",
    "return_staff": "Returned by staff",
    "to_consultant": "Handed to consultant",
    "return_consultant": "Returned by consultant",
    "handover": "Custodian hand-over",
    "client_collected": "Client collected from consultant",
    "token_inactive": "Custody ended - token made inactive",
}
OUTWARD_KINDS = ("client_collected", "token_inactive")   # movement-register rows that come from outward entries
INACTIVE_REASONS = ["Lost", "Replaced by a new token", "Damaged", "Surrendered", "Certificate revoked"]
HOLDER_LABELS = {"custodian": "Custodian", "staff": "Staff", "consultant": "Consultant"}

# Fields of an entry that can be corrected (with a reason); the client and token cannot - cancel and re-enter.
INWARD_CORRECTABLE = {"inward_date": "Inward Date", "received_from": "Received From", "purpose": "Purpose",
                      "expected_return_date": "Expected Return Date", "remarks": "Remarks"}
OUTWARD_CORRECTABLE = {"outward_date": "Outward Date", "returned_to": "Returned To", "purpose": "Purpose",
                       "remarks": "Remarks"}
DATE_FIELDS = {"inward_date", "expected_return_date", "outward_date"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    client_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    client_code TEXT UNIQUE,
    holder_name TEXT NOT NULL,
    firm_name   TEXT,
    pan         TEXT UNIQUE,          -- optional; blank = "PAN pending"
    mobile      TEXT,
    email       TEXT,
    remarks     TEXT,
    status      TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    is_sample   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS custodians (
    custodian_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    appointed_at TEXT NOT NULL,
    relieved_at  TEXT,
    remarks      TEXT,
    is_sample    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
-- Exactly one custodian may be in office (relieved_at empty) at a time.
CREATE UNIQUE INDEX IF NOT EXISTS ux_one_custodian ON custodians (coalesce(relieved_at, '')) WHERE relieved_at IS NULL;

CREATE TABLE IF NOT EXISTS consultants (
    consultant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    firm          TEXT,
    kind          TEXT NOT NULL DEFAULT 'CS' CHECK (kind IN ('CS', 'CA', 'Advocate', 'Other')),
    mobile        TEXT,
    email         TEXT,
    remarks       TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    is_sample     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS tokens (
    token_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id         INTEGER NOT NULL REFERENCES clients (client_id),
    token_serial      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    holder_name       TEXT NOT NULL,
    remarks           TEXT,
    status            TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    inactive_reason   TEXT,
    status_changed_at TEXT,
    replaced_by       INTEGER REFERENCES tokens (token_id),
    is_sample    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS certificates (
    cert_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id     INTEGER NOT NULL REFERENCES tokens (token_id),
    client_id    INTEGER NOT NULL REFERENCES clients (client_id),
    holder_name  TEXT,
    cert_serial  TEXT,
    issue_date   TEXT,
    expiry_date  TEXT,
    issuer       TEXT,
    admin_status TEXT NOT NULL DEFAULT 'Active'
                 CHECK (admin_status IN ('Active', 'Renewal in Progress', 'Revoked', 'Inactive')),
    is_current   INTEGER NOT NULL DEFAULT 1,
    replaced_by  INTEGER REFERENCES certificates (cert_id),
    remarks      TEXT,
    followup     TEXT,
    is_sample    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cert_current ON certificates (token_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS expected_dscs (
    expected_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL REFERENCES clients (client_id),
    holder_name    TEXT NOT NULL,
    token_serial   TEXT,
    purpose        TEXT NOT NULL,
    expected_date  TEXT,
    followup_staff TEXT,
    remarks        TEXT,
    status         TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Cancelled')),
    status_note    TEXT,
    is_sample      INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS inward (
    inward_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inward_date          TEXT NOT NULL,
    client_id            INTEGER NOT NULL REFERENCES clients (client_id),
    token_id             INTEGER NOT NULL REFERENCES tokens (token_id),
    holder_name          TEXT NOT NULL,
    received_from        TEXT NOT NULL,
    received_by          TEXT NOT NULL,
    purpose              TEXT NOT NULL,
    expected_return_date TEXT,
    remarks              TEXT,
    expected_id          INTEGER REFERENCES expected_dscs (expected_id),
    cert_id              INTEGER REFERENCES certificates (cert_id),
    custodian_id         INTEGER REFERENCES custodians (custodian_id),
    status               TEXT NOT NULL DEFAULT 'Active'
                         CHECK (status IN ('Active', 'Superseded', 'Cancelled')),
    superseded_by        INTEGER REFERENCES inward (inward_id),
    status_note          TEXT,
    is_sample            INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS ix_inward_token ON inward (token_id);

CREATE TABLE IF NOT EXISTS outward (
    outward_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    outward_date      TEXT NOT NULL,
    inward_id         INTEGER NOT NULL REFERENCES inward (inward_id),
    token_id          INTEGER NOT NULL REFERENCES tokens (token_id),
    client_id         INTEGER NOT NULL REFERENCES clients (client_id),
    holder_name       TEXT NOT NULL,
    returned_to       TEXT NOT NULL,
    returned_by       TEXT NOT NULL,
    purpose           TEXT,
    remarks           TEXT,
    via_consultant_id INTEGER REFERENCES consultants (consultant_id),
    collected_by      TEXT,
    closed_as         TEXT,                 -- 'inactive' when custody ended because the token was made inactive
    status            TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Cancelled')),
    status_note       TEXT,
    is_sample         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
-- A received DSC can be returned only once (cancelled outward entries excepted).
CREATE UNIQUE INDEX IF NOT EXISTS ux_outward_active ON outward (inward_id) WHERE status = 'Active';

CREATE TABLE IF NOT EXISTS movements (
    movement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    inward_id       INTEGER NOT NULL REFERENCES inward (inward_id),
    token_id        INTEGER NOT NULL REFERENCES tokens (token_id),
    kind            TEXT NOT NULL CHECK (kind IN ('issue_staff', 'return_staff', 'to_consultant',
                                                  'return_consultant', 'handover')),
    moved_at        TEXT NOT NULL,
    from_name       TEXT NOT NULL,
    to_name         TEXT NOT NULL,
    custodian_id    INTEGER REFERENCES custodians (custodian_id),
    consultant_id   INTEGER REFERENCES consultants (consultant_id),
    purpose         TEXT,
    expected_return TEXT,
    remarks         TEXT,
    status          TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Cancelled')),
    status_note     TEXT,
    is_sample       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Corrections to inward/outward entries: every changed field with its old and new value and the reason.
CREATE TABLE IF NOT EXISTS corrections (
    correction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type      TEXT NOT NULL CHECK (entry_type IN ('inward', 'outward')),
    entry_id        INTEGER NOT NULL,
    token_id        INTEGER NOT NULL REFERENCES tokens (token_id),
    field           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    reason          TEXT NOT NULL,
    corrected_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_movements_inward ON movements (inward_id);

-- Every change of a token between Active and Inactive, with the reason.
CREATE TABLE IF NOT EXISTS token_status_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id   INTEGER NOT NULL REFERENCES tokens (token_id),
    status     TEXT NOT NULL CHECK (status IN ('Active', 'Inactive')),
    reason     TEXT,
    changed_at TEXT NOT NULL,
    is_sample  INTEGER NOT NULL DEFAULT 0
);

-- Inward entries whose token has not been returned = live custody.
CREATE VIEW IF NOT EXISTS v_open_inward AS
SELECT i.* FROM inward i
WHERE i.status = 'Active'
  AND NOT EXISTS (SELECT 1 FROM outward o
                  WHERE o.inward_id = i.inward_id AND o.status = 'Active');

-- Expected DSCs for which no (non-cancelled) inward entry exists yet.
CREATE VIEW IF NOT EXISTS v_awaited AS
SELECT e.* FROM expected_dscs e
WHERE e.status = 'Active'
  AND NOT EXISTS (SELECT 1 FROM inward i
                  WHERE i.expected_id = e.expected_id AND i.status IN ('Active', 'Superseded'));

-- The latest active movement of every inward entry (none = still with the custodian).
CREATE VIEW IF NOT EXISTS v_last_movement AS
SELECT m.* FROM movements m
WHERE m.movement_id = (SELECT MAX(x.movement_id) FROM movements x
                       WHERE x.inward_id = m.inward_id AND x.status = 'Active');
"""

# Columns added after the first release, so older database files are upgraded in place.
MIGRATIONS = [
    ("certificates", "issuer", "TEXT"),
    ("inward", "custodian_id", "INTEGER REFERENCES custodians (custodian_id)"),
    ("outward", "via_consultant_id", "INTEGER REFERENCES consultants (consultant_id)"),
    ("outward", "collected_by", "TEXT"),
    ("outward", "closed_as", "TEXT"),
    ("tokens", "status", "TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive'))"),
    ("tokens", "inactive_reason", "TEXT"),
    ("tokens", "status_changed_at", "TEXT"),
    ("tokens", "replaced_by", "INTEGER REFERENCES tokens (token_id)"),
]

REQUIRED_TABLES = {"clients", "tokens", "certificates", "inward", "outward", "expected_dscs"}


class ValidationError(Exception):
    """A user-facing validation problem (shown as-is in the UI)."""


class DuplicateCustodyError(Exception):
    """Raised when a token being received is already in the firm's custody."""

    def __init__(self, open_inward):
        self.open_inward = open_inward
        super().__init__(
            f"Token {open_inward['token_serial']} is already in custody "
            f"(Inward #{open_inward['inward_id']} dated {dates.to_display(open_inward['inward_date'])}).")


class InactiveTokenError(Exception):
    """Raised when a token marked Inactive is received again."""

    def __init__(self, token):
        self.token = token
        super().__init__(f"Token {token['token_serial']} is marked Inactive ({token['inactive_reason'] or '-'}).")


class CertificateConflict(Exception):
    """Raised when entered certificate details differ from the current certificate."""

    def __init__(self, current):
        self.current = current
        super().__init__("Certificate details differ from the current certificate on record.")


def classify_expiry(expiry_iso, as_of=None):
    """Return (days, status_text) for a certificate expiry, to the minute.

    days = calendar days from as_of's date to the expiry date (None when the
    expiry is unknown). A certificate is Expired as soon as its expiry time
    has passed, even later the same day. An expiry with no recorded time is
    taken as 12:00 AM on that day.
    """
    if not expiry_iso:
        return None, "Expiry Date Unknown"
    now = dates.iso_to_datetime(as_of) if as_of else dates.now()
    exp = dates.iso_to_datetime(expiry_iso)
    days = (exp.date() - now.date()).days
    if exp <= now:
        status = "Expired"
    elif days == 0:
        status = "Expires Today"
    elif days <= 7:
        status = "Expiring Within 7 Days"
    elif days <= 15:
        status = "Expiring Within 15 Days"
    elif days <= 30:
        status = "Expiring Within 30 Days"
    else:
        status = "Valid Beyond 30 Days"
    return days, status


def days_text(days, status, expiry_iso=None):
    if days is None:
        return "-"
    at = ""
    if dates.has_time(expiry_iso):
        at = f" at {dates.time_display(dates.iso_to_datetime(expiry_iso))}"
    if status == "Expired":
        if days == 0:
            return f"Expired today{at}" if at else "Expired today (time not recorded)"
        return f"{-days} day(s) overdue"
    if status == "Expires Today":
        return f"Expires today{at}"
    return f"{days} day(s) left"


def matches_expiry_filter(flt, days, status, admin_status):
    """Whether one certificate belongs in the given alert list.

    The 7/15/30-day lists are cumulative windows starting now (so a
    certificate expiring in 5 days appears in all three lists, once each);
    an already expired certificate is in none of them.
    """
    if flt == "all":
        return True
    if flt == "renewal":
        return admin_status == "Renewal in Progress"
    if admin_status in ALERT_EXCLUDED_STATUSES:
        return False
    if flt == "unknown":
        return days is None
    if days is None:
        return False
    if flt == "expired":
        return status == "Expired"
    if flt == "today":
        return status == "Expires Today"
    if status == "Expired":
        return False
    if flt == "beyond":
        return days > 30
    return 0 <= days <= int(flt)


def _clean(value):
    return (value or "").strip() if isinstance(value, str) or value is None else value


def _date(value, field, required=False):
    """Accept an ISO date string (from the UI/date helpers) and validate it."""
    value = _clean(value)
    if not value:
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        return dates.iso_to_date(value).isoformat()
    except (ValueError, TypeError):
        raise ValidationError(f"{field} is not a valid date.") from None


def _datetime(value, field, required=False):
    """Accept an ISO date or date-time; keep 'date only' when no time is given."""
    value = _clean(value)
    if not value:
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        dt = dates.iso_to_datetime(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field} is not a valid date/time.") from None
    return dt.strftime(dates.ISO_DT_FORMAT) if dates.has_time(value) else dt.date().isoformat()


def _same_moment(a, b):
    """Two expiry values agree unless their dates differ, or both carry different times."""
    if not a or not b:
        return True
    if a[:10] != b[:10]:
        return False
    return not (dates.has_time(a) and dates.has_time(b) and a[:16] != b[:16])


def _more_precise(current, new):
    """Fill a blank, or add a time to a date-only value for the same day."""
    if not current:
        return new
    if new and not dates.has_time(current) and dates.has_time(new) and current[:10] == new[:10]:
        return new
    return current


def name_key(name):
    """A name reduced to letters and digits, so 'R. K. Sharma' and 'RK Sharma' compare equal."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def mobile_key(mobile):
    digits = re.sub(r"\D", "", mobile or "")
    return digits[-10:]


def is_valid_database(path):
    """True if the file is an SQLite database containing this tool's tables."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return False
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return REQUIRED_TABLES <= names
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def backup_summary(path):
    """What a backup file holds, to show before restoring it: counts and the latest entry dates."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        return {"clients": one("SELECT COUNT(*) FROM clients"), "tokens": one("SELECT COUNT(*) FROM tokens"),
                "inward": one("SELECT COUNT(*) FROM inward"), "outward": one("SELECT COUNT(*) FROM outward"),
                "last_inward": one("SELECT MAX(inward_date) FROM inward"),
                "last_outward": one("SELECT MAX(outward_date) FROM outward"),
                "saved_at": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")}
    finally:
        conn.close()


class Database:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        self.is_new = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._make_pan_optional()
        with self.conn:
            self._migrate_columns()
            self.conn.executescript(SCHEMA)
            self.conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '2')")
            self.conn.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")

    def _make_pan_optional(self):
        """Older databases required a PAN; rebuild the clients table so PAN may be blank."""
        info = self.conn.execute("PRAGMA table_info(clients)").fetchall()
        pan = next((r for r in info if r[1] == "pan"), None)
        if not pan or not pan[3]:  # no table yet, or PAN already optional
            return
        ddl = re.search(r"CREATE TABLE IF NOT EXISTS clients \(.*?\n\);", SCHEMA, re.S).group(0)
        cols = ", ".join(r[1] for r in info)
        self.conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self.conn.execute("BEGIN")
            for (view,) in self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
                self.conn.execute(f"DROP VIEW {view}")  # recreated from SCHEMA straight after
            self.conn.execute(ddl.replace("CREATE TABLE IF NOT EXISTS clients", "CREATE TABLE clients_new"))
            self.conn.execute(f"INSERT INTO clients_new ({cols}) SELECT {cols} FROM clients")
            self.conn.execute("UPDATE clients_new SET pan = NULL WHERE pan = ''")
            self.conn.execute("DROP TABLE clients")
            self.conn.execute("ALTER TABLE clients_new RENAME TO clients")
            self.conn.execute("COMMIT")
        except sqlite3.Error:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.execute("PRAGMA foreign_keys = ON")

    def _migrate_columns(self):
        """Add columns introduced after the first release to an older database."""
        tables = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column, decl in MIGRATIONS:
            if table in tables:
                cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def close(self):
        self.conn.close()

    # ------------------------------------------------------------------ helpers
    def _all(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _one(self, sql, params=()):
        r = self.conn.execute(sql, params).fetchone()
        return dict(r) if r else None

    def _scalar(self, sql, params=()):
        r = self.conn.execute(sql, params).fetchone()
        return r[0] if r else None

    def get_meta(self, key, default=None):
        v = self._scalar("SELECT value FROM meta WHERE key = ?", (key,))
        return default if v is None else v

    def set_meta(self, key, value):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    # ------------------------------------------------------------------ staff
    def list_staff(self):
        return [r["name"] for r in self._all("SELECT name FROM staff WHERE active = 1 ORDER BY name")]

    def add_staff(self, name):
        name = _clean(name)
        if not name:
            raise ValidationError("Staff name is required.")
        with self.conn:
            self._ensure_staff(name)

    def remove_staff(self, name):
        """Hide a staff member from dropdowns (history keeps the name)."""
        with self.conn:
            self.conn.execute("UPDATE staff SET active = 0 WHERE name = ?", (name,))

    def _ensure_staff(self, name):
        name = _clean(name)
        if name:
            self.conn.execute("INSERT OR IGNORE INTO staff (name) VALUES (?)", (name,))
            self.conn.execute("UPDATE staff SET active = 1 WHERE name = ?", (name,))

    # ------------------------------------------------------------------ custodians
    def current_custodian(self):
        return self._one("SELECT * FROM custodians WHERE relieved_at IS NULL")

    def list_custodians(self):
        return self._all("SELECT * FROM custodians ORDER BY appointed_at DESC, custodian_id DESC")

    def _require_custodian(self):
        c = self.current_custodian()
        if not c:
            raise ValidationError("No custodian has been appointed. Appoint the custodian first "
                                  "(Settings > Custodian, Staff & Consultants).")
        return c

    def appoint_custodian(self, name, remarks="", at=None, is_sample=0):
        """Appoint a new custodian. The previous one is relieved at the same moment
        and every token he held moves to the new custodian (hand-over entries)."""
        name = _clean(name)
        if not name:
            raise ValidationError("Custodian name is required.")
        at = _datetime(at, "Appointment time") if at else dates.now_iso()
        old = self.current_custodian()
        if old and old["name"].lower() == name.lower():
            raise ValidationError(f"{name} is already the custodian.")
        if old and at < old["appointed_at"]:
            raise ValidationError("A new custodian cannot be appointed before the current one was appointed.")
        with self.conn:
            if old:
                held = [r for r in self._holders() if r["holder_type"] == "custodian"]
                self.conn.execute("UPDATE custodians SET relieved_at = ? WHERE custodian_id = ?",
                                  (at, old["custodian_id"]))
            cur = self.conn.execute("INSERT INTO custodians (name, appointed_at, remarks, is_sample) "
                                    "VALUES (?, ?, ?, ?)", (name, at, _clean(remarks), is_sample))
            new_id = cur.lastrowid
            if old:
                for r in held:
                    self.conn.execute(
                        "INSERT INTO movements (inward_id, token_id, kind, moved_at, from_name, to_name, "
                        "custodian_id, remarks, is_sample) VALUES (?, ?, 'handover', ?, ?, ?, ?, ?, ?)",
                        (r["inward_id"], r["token_id"], at, old["name"], name, new_id,
                         "Custodian changed", is_sample))
        return new_id

    # ------------------------------------------------------------------ consultants
    def _clean_consultant(self, data):
        c = {"name": _clean(data.get("name")), "firm": _clean(data.get("firm")),
             "kind": _clean(data.get("kind")) or "CS", "mobile": re.sub(r"[\s-]", "", _clean(data.get("mobile"))),
             "email": _clean(data.get("email")), "remarks": _clean(data.get("remarks"))}
        if not c["name"]:
            raise ValidationError("Consultant name is required.")
        if c["kind"] not in CONSULTANT_KINDS:
            raise ValidationError("Consultant type must be CS, CA, Advocate or Other.")
        if c["mobile"] and not MOBILE_RE.match(c["mobile"]):
            raise ValidationError(MOBILE_MSG)
        if c["email"] and not EMAIL_RE.match(c["email"]):
            raise ValidationError(f"Email address '{c['email']}' is not valid.")
        return c

    def add_consultant(self, data, is_sample=0):
        c = self._clean_consultant(data)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO consultants (name, firm, kind, mobile, email, remarks, is_sample) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (c["name"], c["firm"], c["kind"], c["mobile"], c["email"], c["remarks"], is_sample))
            return cur.lastrowid

    def update_consultant(self, consultant_id, data):
        c = self._clean_consultant(data)
        with self.conn:
            self.conn.execute("UPDATE consultants SET name = ?, firm = ?, kind = ?, mobile = ?, email = ?, "
                              "remarks = ? WHERE consultant_id = ?",
                              (c["name"], c["firm"], c["kind"], c["mobile"], c["email"], c["remarks"],
                               consultant_id))

    def set_consultant_active(self, consultant_id, active):
        with self.conn:
            self.conn.execute("UPDATE consultants SET active = ? WHERE consultant_id = ?",
                              (1 if active else 0, consultant_id))

    def get_consultant(self, consultant_id):
        return self._one("SELECT * FROM consultants WHERE consultant_id = ?", (consultant_id,))

    def list_consultants(self, active_only=False):
        sql = """SELECT c.*, (SELECT COUNT(*) FROM v_last_movement m JOIN v_open_inward i USING (inward_id)
                              WHERE m.kind = 'to_consultant' AND m.consultant_id = c.consultant_id) AS holding
                 FROM consultants c"""
        if active_only:
            sql += " WHERE c.active = 1"
        return self._all(sql + " ORDER BY c.name COLLATE NOCASE")

    # ------------------------------------------------------------------ clients
    def _clean_client(self, data, client_id=None):
        holder = _clean(data.get("holder_name"))
        pan = _clean(data.get("pan")).upper()
        mobile = re.sub(r"[\s-]", "", _clean(data.get("mobile")))
        email = _clean(data.get("email"))
        status = _clean(data.get("status")) or "Active"
        if not holder:
            raise ValidationError("DSC Holder Name is required.")
        if not mobile:
            raise ValidationError("Mobile Number is required.")
        if pan and not PAN_RE.match(pan):
            raise ValidationError(f"PAN '{pan}' is not valid. Expected format: AAAAA9999A.")
        if pan and pan[3] != "P":
            raise ValidationError(
                f"PAN '{pan}' is not an individual's PAN (its 4th character is '{pan[3]}').\n"
                "A DSC is issued to an individual, so the 4th character of the PAN must be 'P' "
                "(e.g. ABCPS1234K).")
        if not MOBILE_RE.match(mobile):
            raise ValidationError(MOBILE_MSG)
        if email and not EMAIL_RE.match(email):
            raise ValidationError(f"Email address '{email}' is not valid.")
        if status not in ("Active", "Inactive"):
            raise ValidationError("Status must be Active or Inactive.")
        if pan:
            dup = self._one("SELECT client_code, holder_name FROM clients WHERE pan = ? AND client_id IS NOT ?",
                            (pan, client_id))
            if dup:
                raise ValidationError(
                    f"PAN {pan} already exists for client {dup['client_code']} - {dup['holder_name']}.")
        # Several DSC holders may share a mobile number (family members), but not with the same name.
        for other in self._all("SELECT client_id, client_code, holder_name, mobile FROM clients "
                               "WHERE client_id IS NOT ?", (client_id,)):
            if mobile_key(other["mobile"]) == mobile_key(mobile) and name_key(other["holder_name"]) == name_key(holder):
                raise ValidationError(
                    f"Client {other['client_code']} - {other['holder_name']} already has mobile number {mobile}.\n"
                    "The same mobile number can be used for another DSC holder only with a different name.")
        return {
            "holder_name": holder, "firm_name": _clean(data.get("firm_name")), "pan": pan or None,
            "mobile": mobile, "email": email, "remarks": _clean(data.get("remarks")), "status": status,
        }

    def add_client(self, data, is_sample=0):
        c = self._clean_client(data)
        with self.conn:
            return self._insert_client(c, is_sample)

    def _insert_client(self, c, is_sample=0):
        cur = self.conn.execute(
            "INSERT INTO clients (holder_name, firm_name, pan, mobile, email, remarks, status, is_sample) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (c["holder_name"], c["firm_name"], c["pan"], c["mobile"], c["email"], c["remarks"],
             c.get("status") or "Active", is_sample))
        cid = cur.lastrowid
        self.conn.execute("UPDATE clients SET client_code = ? WHERE client_id = ?", (f"CL{cid:04d}", cid))
        return cid

    # ------------------------------------------------------------------ bulk import (Excel template)
    def plan_client_import(self, rows):
        """Decide, row by row, what importing these clients would do - nothing is saved.

        rows: [(excel row number, {holder_name, mobile, firm_name, pan, email, remarks}), ...]
        A row is skipped only when the DSC Holder Name or Mobile Number is missing, the
        mobile number is not a valid Indian mobile, or the client already exists (same
        name and mobile, or same PAN) in the app or earlier in the file. A wrong PAN or
        email does not stop the row: the client is imported without it and a note says so.
        Returns one dict per row with action 'Import' or 'Skip' and the reason / note.
        """
        existing_key, existing_pan = {}, {}
        for c in self._all("SELECT client_code, holder_name, mobile, pan FROM clients"):
            existing_key[(mobile_key(c["mobile"]), name_key(c["holder_name"]))] = c["client_code"]
            if c["pan"]:
                existing_pan[c["pan"].upper()] = c["client_code"]
        seen_key, seen_pan, plan = {}, {}, []
        for row_no, raw in rows:
            r = {k: _clean(str(raw.get(k) or "")) for k in ("holder_name", "mobile", "firm_name", "pan", "email",
                                                            "remarks")}
            r["holder_name"] = " ".join(r["holder_name"].split())
            r["mobile"] = re.sub(r"[\s().-]", "", r["mobile"])
            r["pan"] = r["pan"].upper()
            entry = dict(r, row=row_no, action="Skip", reason="")
            plan.append(entry)
            if not r["holder_name"]:
                entry["reason"] = "DSC Holder Name is missing"
                continue
            if not r["mobile"]:
                entry["reason"] = "Mobile Number is missing"
                continue
            if not MOBILE_RE.match(r["mobile"]):
                entry["reason"] = f"Mobile number '{r['mobile']}' is not valid (10 digits starting with 6-9)"
                continue
            entry["mobile"] = mobile_key(r["mobile"])
            key = (entry["mobile"], name_key(r["holder_name"]))
            if key in existing_key:
                entry["reason"] = f"Already in the app as {existing_key[key]} (same name and mobile)"
                continue
            if key in seen_key:
                entry["reason"] = f"Same name and mobile as row {seen_key[key]}"
                continue
            notes = []
            if r["pan"]:
                if not PAN_RE.match(r["pan"]) or r["pan"][3] != "P":
                    notes.append(f"PAN '{r['pan']}' not valid for an individual - imported without PAN")
                    entry["pan"] = ""
                elif r["pan"] in existing_pan:
                    entry["reason"] = f"PAN {r['pan']} already belongs to {existing_pan[r['pan']]}"
                    continue
                elif r["pan"] in seen_pan:
                    entry["reason"] = f"Same PAN as row {seen_pan[r['pan']]}"
                    continue
            if r["email"] and not EMAIL_RE.match(r["email"]):
                notes.append(f"Email '{r['email']}' not valid - imported without email")
                entry["email"] = ""
            entry["action"], entry["reason"] = "Import", "; ".join(notes)
            seen_key[key] = row_no
            if entry["pan"]:
                seen_pan[entry["pan"]] = row_no
        return plan

    def apply_client_import(self, plan):
        """Save the rows planned for import, all in one transaction. Returns the number imported."""
        rows = [r for r in plan if r["action"] == "Import"]
        with self.conn:
            for r in rows:
                self._insert_client({"holder_name": r["holder_name"], "firm_name": r["firm_name"],
                                     "pan": r["pan"] or None, "mobile": r["mobile"], "email": r["email"],
                                     "remarks": r["remarks"], "status": "Active"})
        return len(rows)

    def update_client(self, client_id, data):
        c = self._clean_client(data, client_id)
        with self.conn:
            self.conn.execute(
                "UPDATE clients SET holder_name = ?, firm_name = ?, pan = ?, mobile = ?, email = ?, remarks = ?, "
                "status = ?, updated_at = datetime('now', 'localtime') WHERE client_id = ?",
                (c["holder_name"], c["firm_name"], c["pan"], c["mobile"], c["email"], c["remarks"],
                 c["status"], client_id))

    def set_client_status(self, client_id, status):
        if status not in ("Active", "Inactive"):
            raise ValidationError("Status must be Active or Inactive.")
        with self.conn:
            self.conn.execute("UPDATE clients SET status = ?, updated_at = datetime('now', 'localtime') "
                              "WHERE client_id = ?", (status, client_id))

    def client_has_transactions(self, client_id):
        return bool(self._scalar(
            "SELECT (SELECT COUNT(*) FROM tokens WHERE client_id = :c) + "
            "(SELECT COUNT(*) FROM inward WHERE client_id = :c) + "
            "(SELECT COUNT(*) FROM expected_dscs WHERE client_id = :c)", {"c": client_id}))

    def delete_client(self, client_id):
        if self.client_has_transactions(client_id):
            raise ValidationError("This client has DSC tokens or transactions and cannot be deleted. "
                                  "Mark the client Inactive instead.")
        with self.conn:
            self.conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))

    def get_client(self, client_id):
        return self._one("SELECT * FROM clients WHERE client_id = ?", (client_id,))

    def find_client_by_pan(self, pan):
        return self._one("SELECT * FROM clients WHERE pan = ?", (_clean(pan).upper(),))

    def list_clients(self, search="", status="All"):
        sql = """
            SELECT c.*,
                   (SELECT COUNT(*) FROM tokens t WHERE t.client_id = c.client_id) AS token_count,
                   (SELECT COUNT(DISTINCT token_id) FROM v_open_inward i WHERE i.client_id = c.client_id)
                       AS in_custody
            FROM clients c WHERE 1 = 1"""
        params = []
        if status in ("Active", "Inactive"):
            sql += " AND c.status = ?"
            params.append(status)
        elif status == "PAN pending":
            sql += " AND (c.pan IS NULL OR c.pan = '')"
        if _clean(search):
            like = f"%{search.strip()}%"
            sql += (" AND (c.holder_name LIKE ? OR c.firm_name LIKE ? OR c.client_code LIKE ? OR c.pan LIKE ?"
                    " OR c.client_id = ?)")
            params += [like, like, like, like, search.strip()]
        sql += " ORDER BY c.holder_name COLLATE NOCASE"
        return self._all(sql, params)

    # ------------------------------------------------------------------ tokens
    def get_token(self, token_id):
        return self._one("SELECT t.*, c.client_code FROM tokens t JOIN clients c USING (client_id) "
                         "WHERE t.token_id = ?", (token_id,))

    def find_token(self, token_serial):
        serial = _clean(token_serial).upper()
        if not serial:
            return None
        return self._one("SELECT t.*, c.client_code, c.holder_name AS client_holder FROM tokens t "
                         "JOIN clients c USING (client_id) WHERE t.token_serial = ?", (serial,))

    def tokens_for_client(self, client_id, as_of=None, active_only=False):
        rows = self._all("""
            SELECT t.*, cert.cert_serial, cert.expiry_date, cert.issuer, cert.admin_status,
                   EXISTS (SELECT 1 FROM v_open_inward i WHERE i.token_id = t.token_id) AS in_custody
            FROM tokens t
            LEFT JOIN certificates cert ON cert.token_id = t.token_id AND cert.is_current = 1
            WHERE t.client_id = ? ORDER BY t.status, t.token_serial""", (client_id,))
        out = []
        for r in rows:
            if active_only and r["status"] != "Active":
                continue
            r["days"], r["expiry_status"] = classify_expiry(r["expiry_date"], as_of)
            r["custody_status"] = "In Custody" if r["in_custody"] else "Returned / Not Held"
            r["status_text"] = r["status"] if r["status"] == "Active" else f"Inactive - {r['inactive_reason'] or ''}"
            out.append(r)
        return out

    def _log_token_status(self, token_id, status, reason, at, is_sample=0):
        self.conn.execute("INSERT INTO token_status_log (token_id, status, reason, changed_at, is_sample) "
                          "VALUES (?, ?, ?, ?, ?)", (token_id, status, reason, at, is_sample))

    def _deactivate_token(self, token, reason, at, replaced_by=None, is_sample=0):
        """Mark a token Inactive inside the caller's transaction. A token still in the firm's
        custody (with the custodian, a staff member or a consultant) leaves custody, recorded
        as an outward entry 'closed as inactive' naming who had it."""
        open_inw = self.open_inward_for_token(token["token_id"])
        if open_inw:
            holder = self.holder_of(open_inw["inward_id"])
            self.conn.execute(
                "INSERT INTO outward (outward_date, inward_id, token_id, client_id, holder_name, returned_to, "
                "returned_by, purpose, remarks, closed_as, is_sample, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'inactive', ?, ?)",
                (at[:10], open_inw["inward_id"], token["token_id"], open_inw["client_id"], open_inw["holder_name"],
                 "(token made inactive)", holder["holder_name"], open_inw["purpose"], reason, is_sample, at))
        self.conn.execute("UPDATE tokens SET status = 'Inactive', inactive_reason = ?, status_changed_at = ?, "
                          "replaced_by = ? WHERE token_id = ?", (reason, at, replaced_by, token["token_id"]))
        self._log_token_status(token["token_id"], "Inactive", reason, at, is_sample)

    def set_token_inactive(self, token_id, reason, at=None, is_sample=0):
        """Inactive = lost, replaced, damaged, surrendered... (reason recorded). Leaves expiry alerts."""
        token = self.get_token(token_id)
        reason = _clean(reason)
        if not token:
            raise ValidationError("Token not found.")
        if token["status"] == "Inactive":
            raise ValidationError(f"Token {token['token_serial']} is already Inactive.")
        if not reason:
            raise ValidationError("Please give the reason (for example: Lost, Replaced by a new token).")
        at = _datetime(at, "Time") if at else dates.now_iso()
        with self.conn:
            self._deactivate_token(token, reason, at, is_sample=is_sample)

    def set_token_active(self, token_id, reason, at=None):
        token = self.get_token(token_id)
        reason = _clean(reason)
        if not token:
            raise ValidationError("Token not found.")
        if token["status"] == "Active":
            raise ValidationError(f"Token {token['token_serial']} is already Active.")
        if not reason:
            raise ValidationError("Please give the reason for making the token Active again (e.g. Found).")
        at = _datetime(at, "Time") if at else dates.now_iso()
        with self.conn:
            self.conn.execute("UPDATE tokens SET status = 'Active', inactive_reason = NULL, status_changed_at = ?, "
                              "replaced_by = NULL WHERE token_id = ?", (at, token_id))
            self._log_token_status(token_id, "Active", reason, at)

    def _get_or_create_token(self, client_id, serial, holder, is_sample=0):
        t = self.find_token(serial)
        if t:
            if t["client_id"] != client_id:
                raise ValidationError(
                    f"Token {serial} is already registered to another client "
                    f"({t['client_code']} - {t['client_holder']}). Please check the token number.")
            return t["token_id"]
        cur = self.conn.execute("INSERT INTO tokens (client_id, token_serial, holder_name, is_sample) "
                                "VALUES (?, ?, ?, ?)", (client_id, serial, holder, is_sample))
        return cur.lastrowid

    def open_inward_for_token(self, token_id):
        return self._one("SELECT i.*, t.token_serial FROM v_open_inward i JOIN tokens t USING (token_id) "
                         "WHERE i.token_id = ? ORDER BY i.inward_id DESC LIMIT 1", (token_id,))

    # ------------------------------------------------------------------ who holds a token
    def _holders(self, inward_id=None):
        """One row per open inward entry with the token's current holder inside the firm."""
        sql = """
            SELECT i.inward_id, i.token_id, i.created_at AS inward_recorded, i.inward_date,
                   m.movement_id, m.kind, m.moved_at, m.to_name, m.consultant_id, m.expected_return, m.purpose
            FROM v_open_inward i LEFT JOIN v_last_movement m ON m.inward_id = i.inward_id"""
        params = ()
        if inward_id is not None:
            sql += " WHERE i.inward_id = ?"
            params = (inward_id,)
        custodian = self.current_custodian()
        rows = []
        for r in self._all(sql, params):
            if r["kind"] == "issue_staff":
                r["holder_type"], r["holder_name"] = "staff", r["to_name"]
            elif r["kind"] == "to_consultant":
                r["holder_type"], r["holder_name"] = "consultant", r["to_name"]
            else:
                r["holder_type"] = "custodian"
                r["holder_name"] = custodian["name"] if custodian else "(no custodian)"
                r["expected_return"] = None
            r["holder_since"] = r["moved_at"] or (
                r["inward_recorded"] if r["inward_recorded"][:10] == r["inward_date"] else r["inward_date"])
            rows.append(r)
        return rows

    def holder_of(self, inward_id):
        rows = self._holders(inward_id)
        return rows[0] if rows else None

    def _open_entry(self, inward_id):
        inw = self._one("SELECT i.*, t.token_serial FROM v_open_inward i JOIN tokens t USING (token_id) "
                        "WHERE i.inward_id = ?", (inward_id,))
        if not inw:
            raise ValidationError("This DSC is not in the firm's custody (it was returned or the entry cancelled).")
        return inw, self.holder_of(inward_id)

    # ------------------------------------------------------------------ certificates
    def get_current_certificate(self, token_id):
        return self._one("SELECT * FROM certificates WHERE token_id = ? AND is_current = 1", (token_id,))

    def certificate_history(self, token_id):
        return self._all("SELECT * FROM certificates WHERE token_id = ? ORDER BY cert_id DESC", (token_id,))

    def _clean_cert(self, data):
        c = {
            "cert_serial": _clean(data.get("cert_serial")),
            "issue_date": _datetime(data.get("issue_date"), "Certificate Issue Date"),
            "expiry_date": _datetime(data.get("expiry_date"), "Certificate Expiry Date"),
            "issuer": _clean(data.get("issuer")),
            "admin_status": _clean(data.get("admin_status")) or "Active",
            "remarks": _clean(data.get("remarks")),
            "followup": _clean(data.get("followup")),
        }
        if c["admin_status"] not in CERT_STATUSES:
            raise ValidationError("Invalid certificate administrative status.")
        if c["issue_date"] and c["expiry_date"] and \
                dates.iso_to_datetime(c["issue_date"]) > dates.iso_to_datetime(c["expiry_date"]):
            raise ValidationError("Certificate Issue Date cannot be after the Expiry Date.")
        return c

    @staticmethod
    def _cert_conflicts(current, new):
        """True when the new serial/expiry would overwrite a different, already recorded value."""
        cs, ns = (current["cert_serial"] or "").upper(), (new["cert_serial"] or "").upper()
        return bool((ns and cs and ns != cs) or not _same_moment(current["expiry_date"], new["expiry_date"]))

    def _insert_cert(self, token_id, c, is_sample=0):
        t = self.get_token(token_id)
        cur = self.conn.execute(
            "INSERT INTO certificates (token_id, client_id, holder_name, cert_serial, issue_date, expiry_date, "
            "issuer, admin_status, is_current, remarks, followup, is_sample) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (token_id, t["client_id"], t["holder_name"], c["cert_serial"], c["issue_date"], c["expiry_date"],
             c["issuer"], c["admin_status"], c["remarks"], c["followup"], is_sample or t["is_sample"]))
        return cur.lastrowid

    def _renew_cert(self, current, c, is_sample=0):
        """Close the current certificate and record the new one (history preserved)."""
        self.conn.execute("UPDATE certificates SET is_current = 0, updated_at = datetime('now', 'localtime') "
                          "WHERE cert_id = ?", (current["cert_id"],))
        new_id = self._insert_cert(current["token_id"], c, is_sample)
        self.conn.execute("UPDATE certificates SET replaced_by = ? WHERE cert_id = ?", (new_id, current["cert_id"]))
        return new_id

    def _apply_inward_cert(self, token_id, cert, action, is_sample=0):
        """Certificate details captured on the inward form.

        action: 'auto' (raise CertificateConflict if details differ), 'renew'
        (record as a new certificate) or 'keep' (leave the current one alone).
        Returns the certificate id now current for the token (or None).
        """
        current = self.get_current_certificate(token_id)
        c = self._clean_cert(cert or {})
        if not (c["cert_serial"] or c["issue_date"] or c["expiry_date"]):
            return current["cert_id"] if current else None
        if current is None:
            return self._insert_cert(token_id, c, is_sample)
        if not self._cert_conflicts(current, c):
            # Same certificate - only fill in details that were missing (or add the time of day).
            self.conn.execute(
                "UPDATE certificates SET cert_serial = ?, issue_date = ?, expiry_date = ?, issuer = ?, "
                "updated_at = datetime('now', 'localtime') WHERE cert_id = ?",
                (current["cert_serial"] or c["cert_serial"] or None,
                 _more_precise(current["issue_date"], c["issue_date"]),
                 _more_precise(current["expiry_date"], c["expiry_date"]),
                 current["issuer"] or c["issuer"] or None, current["cert_id"]))
            return current["cert_id"]
        if action == "keep":
            return current["cert_id"]
        if action == "renew":
            return self._renew_cert(current, c, is_sample)
        raise CertificateConflict(current)

    def save_certificate(self, token_id, data, action="auto"):
        """Add or update the current certificate of a token.

        action: 'auto' raises CertificateConflict when the serial number or
        expiry of an existing certificate would change; 'renew' records a
        new certificate and keeps the old one as history; 'correct' fixes the
        existing record and appends a correction note to its remarks.
        """
        if not self.get_token(token_id):
            raise ValidationError("Token not found.")
        c = self._clean_cert(data)
        with self.conn:
            current = self.get_current_certificate(token_id)
            if current is None:
                return self._insert_cert(token_id, c)
            if action == "renew":
                return self._renew_cert(current, c)
            conflict = self._cert_conflicts(current, c)
            if conflict and action != "correct":
                raise CertificateConflict(current)
            remarks = c["remarks"]
            if conflict:
                note = (f"[{dates.to_display(dates.today_iso())}] Corrected from serial "
                        f"'{current['cert_serial'] or '-'}', expiry "
                        f"'{dates.to_display_dt(current['expiry_date']) or '-'}'.")
                remarks = f"{remarks} {note}".strip()
            self.conn.execute(
                "UPDATE certificates SET cert_serial = ?, issue_date = ?, expiry_date = ?, issuer = ?, "
                "admin_status = ?, remarks = ?, followup = ?, updated_at = datetime('now', 'localtime') "
                "WHERE cert_id = ?",
                (c["cert_serial"], c["issue_date"], c["expiry_date"], c["issuer"] or current["issuer"],
                 c["admin_status"], remarks, c["followup"], current["cert_id"]))
            return current["cert_id"]

    # ------------------------------------------------------------------ expected DSCs
    def add_expected(self, data, is_sample=0):
        client_id = data.get("client_id")
        client = self.get_client(client_id) if client_id else None
        if not client:
            raise ValidationError("Please select a client.")
        holder = _clean(data.get("holder_name")) or client["holder_name"]
        purpose = _clean(data.get("purpose"))
        if purpose not in PURPOSES:
            raise ValidationError("Please select the Purpose/Assignment.")
        expected_date = _date(data.get("expected_date"), "Expected By date")
        serial = _clean(data.get("token_serial")).upper()
        if serial:
            t = self.find_token(serial)
            if t and t["client_id"] != client_id:
                raise ValidationError(f"Token {serial} belongs to another client ({t['client_code']}).")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO expected_dscs (client_id, holder_name, token_serial, purpose, expected_date, "
                "followup_staff, remarks, is_sample) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (client_id, holder, serial or None, purpose, expected_date, _clean(data.get("followup_staff")),
                 _clean(data.get("remarks")), is_sample))
            self._ensure_staff(data.get("followup_staff"))
            return cur.lastrowid

    def cancel_expected(self, expected_id, reason):
        reason = _clean(reason)
        if not reason:
            raise ValidationError("Please give a reason for cancelling.")
        e = self._one("SELECT * FROM v_awaited WHERE expected_id = ?", (expected_id,))
        if not e:
            raise ValidationError("Only DSCs that are still awaited can be cancelled.")
        with self.conn:
            self.conn.execute("UPDATE expected_dscs SET status = 'Cancelled', status_note = ? WHERE expected_id = ?",
                              (reason, expected_id))

    def awaited_for_client(self, client_id):
        return self._all("SELECT * FROM v_awaited WHERE client_id = ? ORDER BY expected_date, expected_id",
                         (client_id,))

    # ------------------------------------------------------------------ inward
    def _clean_inward(self, data):
        client_id = data.get("client_id")
        client = self.get_client(client_id) if client_id else None
        if not client:
            raise ValidationError("Please select a client.")
        if client["status"] != "Active":
            raise ValidationError(f"Client {client['client_code']} is Inactive. Mark the client Active first.")
        d = {
            "client_id": client_id,
            "inward_date": _date(data.get("inward_date"), "Inward Date", required=True),
            "holder_name": _clean(data.get("holder_name")),
            "token_serial": _clean(data.get("token_serial")).upper(),
            "received_from": _clean(data.get("received_from")),
            "purpose": _clean(data.get("purpose")),
            "expected_return_date": _date(data.get("expected_return_date"), "Expected Return Date"),
            "remarks": _clean(data.get("remarks")),
            "expected_id": data.get("expected_id") or None,
        }
        if d["inward_date"] > dates.today_iso():
            raise ValidationError("Inward Date cannot be in the future.")
        for key, label in (("holder_name", "DSC Holder Name"), ("token_serial", "Token Serial Number"),
                           ("received_from", "Received From")):
            if not d[key]:
                raise ValidationError(f"{label} is required.")
        if d["purpose"] not in PURPOSES:
            raise ValidationError("Please select the Purpose/Assignment.")
        if d["expected_return_date"] and d["expected_return_date"] < d["inward_date"]:
            raise ValidationError("Expected Return Date cannot be before the Inward Date.")
        if d["expected_id"]:
            e = self._one("SELECT * FROM v_awaited WHERE expected_id = ?", (d["expected_id"],))
            if not e or e["client_id"] != client_id:
                raise ValidationError("The selected awaited DSC request is not pending for this client.")
        return d

    def save_inward(self, data, allow_duplicate=False, cert=None, cert_action="auto", is_sample=0,
                    reactivate=False, replaces=()):
        """Record a DSC received from a client; it goes to the custodian automatically.

        Raises DuplicateCustodyError if the token is already in custody and
        allow_duplicate is False; CertificateConflict if cert details differ
        from the current certificate and cert_action is 'auto'; InactiveTokenError
        if the token is marked Inactive and reactivate is False. replaces = ids of
        the client's older tokens this new token replaces (they become Inactive).
        Everything runs in one transaction, so a failure saves nothing.
        """
        d = self._clean_inward(data)
        custodian = self._require_custodian()
        existing = self.find_token(d["token_serial"])
        if existing and existing["status"] == "Inactive" and not reactivate:
            raise InactiveTokenError(existing)
        old_tokens = []
        for tid in replaces:
            old = self.get_token(tid)
            if not old or old["client_id"] != d["client_id"]:
                raise ValidationError("A token being replaced must belong to the same client.")
            if existing and old["token_id"] == existing["token_id"]:
                raise ValidationError("A token cannot replace itself.")
            if old["status"] == "Active":
                old_tokens.append(old)
        now = dates.now_iso()
        with self.conn:
            if existing and existing["status"] == "Inactive":
                self.conn.execute("UPDATE tokens SET status = 'Active', inactive_reason = NULL, status_changed_at = ?, "
                                  "replaced_by = NULL WHERE token_id = ?", (now, existing["token_id"]))
                self._log_token_status(existing["token_id"], "Active", "Received again from client", now, is_sample)
            token_id = self._get_or_create_token(d["client_id"], d["token_serial"], d["holder_name"], is_sample)
            open_inw = self.open_inward_for_token(token_id)
            if open_inw and not allow_duplicate:
                raise DuplicateCustodyError(open_inw)
            cert_id = self._apply_inward_cert(token_id, cert, cert_action, is_sample)
            expected_id = d["expected_id"]
            if not expected_id:  # auto-link an awaited request for this exact token
                e = self._one("SELECT expected_id FROM v_awaited WHERE client_id = ? AND token_serial = ? "
                              "ORDER BY expected_id LIMIT 1", (d["client_id"], d["token_serial"]))
                expected_id = e["expected_id"] if e else None
            cur = self.conn.execute(
                "INSERT INTO inward (inward_date, client_id, token_id, holder_name, received_from, received_by, "
                "purpose, expected_return_date, remarks, expected_id, cert_id, custodian_id, is_sample) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (d["inward_date"], d["client_id"], token_id, d["holder_name"], d["received_from"],
                 custodian["name"], d["purpose"], d["expected_return_date"], d["remarks"], expected_id,
                 cert_id, custodian["custodian_id"], is_sample))
            new_id = cur.lastrowid
            if open_inw:
                self.conn.execute(
                    "UPDATE inward SET status = 'Superseded', superseded_by = ?, status_note = ? "
                    "WHERE token_id = ? AND inward_id <> ? AND inward_id IN (SELECT inward_id FROM v_open_inward)",
                    (new_id, f"Token received again - superseded by Inward #{new_id}", token_id, new_id))
            for old in old_tokens:
                self._deactivate_token(old, f"Replaced by new token {d['token_serial']} (Inward #{new_id})", now,
                                       replaced_by=token_id, is_sample=is_sample)
        return new_id

    def cancel_inward(self, inward_id, reason):
        reason = _clean(reason)
        if not reason:
            raise ValidationError("Please give a reason for cancelling the entry.")
        inw = self._one("SELECT * FROM inward WHERE inward_id = ?", (inward_id,))
        if not inw:
            raise ValidationError("Inward entry not found.")
        if inw["status"] != "Active":
            raise ValidationError(f"Inward #{inward_id} is already {inw['status']}.")
        if self._scalar("SELECT COUNT(*) FROM outward WHERE inward_id = ? AND status = 'Active'", (inward_id,)):
            raise ValidationError("This DSC has already been returned. Cancel the outward entry first.")
        holder = self.holder_of(inward_id)
        if holder and holder["holder_type"] != "custodian":
            raise ValidationError(f"The token is with {HOLDER_LABELS[holder['holder_type']].lower()} "
                                  f"{holder['holder_name']}. Record its return to the custodian first.")
        with self.conn:
            self.conn.execute("UPDATE inward SET status = 'Cancelled', status_note = ? WHERE inward_id = ?",
                              (f"Cancelled: {reason}", inward_id))
            # Restore any receipt this entry had superseded.
            self.conn.execute("UPDATE inward SET status = 'Active', superseded_by = NULL, status_note = NULL "
                              "WHERE superseded_by = ? AND status = 'Superseded'", (inward_id,))

    # ------------------------------------------------------------------ internal movements
    def _clean_expected_return(self, value, at):
        value = _datetime(value, "Expected return")
        if value and dates.iso_to_datetime(value) < dates.iso_to_datetime(at):
            raise ValidationError("Expected return cannot be earlier than now.")
        return value

    def _insert_movement(self, inw, kind, at, from_name, to_name, custodian_id, consultant_id=None,
                         purpose=None, expected_return=None, remarks=None, is_sample=0):
        cur = self.conn.execute(
            "INSERT INTO movements (inward_id, token_id, kind, moved_at, from_name, to_name, custodian_id, "
            "consultant_id, purpose, expected_return, remarks, is_sample) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inw["inward_id"], inw["token_id"], kind, at, from_name, to_name, custodian_id, consultant_id,
             purpose, expected_return, _clean(remarks), is_sample))
        return cur.lastrowid

    @staticmethod
    def _need_custodian_holder(holder, inw, action):
        if holder["holder_type"] == "staff":
            raise ValidationError(
                f"Token {inw['token_serial']} is with staff member {holder['holder_name']}. "
                f"Staff-to-staff transfers are not allowed: record its return to the custodian before {action}.")
        if holder["holder_type"] == "consultant":
            raise ValidationError(
                f"Token {inw['token_serial']} is with consultant {holder['holder_name']}. "
                f"Record its return to the custodian before {action}.")

    def issue_to_staff(self, inward_id, staff, purpose="", expected_return=None, remarks="", at=None, is_sample=0):
        """Custodian -> staff member. Time = system time; expected return defaults to end of today."""
        custodian = self._require_custodian()
        inw, holder = self._open_entry(inward_id)
        staff = _clean(staff)
        if not staff:
            raise ValidationError("Please select the staff member receiving the token.")
        if staff.lower() == custodian["name"].lower():
            raise ValidationError("The token is already with the custodian.")
        self._need_custodian_holder(holder, inw, "issuing it again")
        at = _datetime(at, "Time") if at else dates.now_iso()
        expected_return = self._clean_expected_return(expected_return or f"{at[:10]} 23:59:00", at)
        with self.conn:
            mid = self._insert_movement(inw, "issue_staff", at, custodian["name"], staff, custodian["custodian_id"],
                                        purpose=_clean(purpose) or inw["purpose"], expected_return=expected_return,
                                        remarks=remarks, is_sample=is_sample)
            self._ensure_staff(staff)
        return mid

    def return_from_staff(self, inward_id, remarks="", at=None, is_sample=0):
        custodian = self._require_custodian()
        inw, holder = self._open_entry(inward_id)
        if holder["holder_type"] != "staff":
            raise ValidationError(f"Token {inw['token_serial']} is not with a staff member "
                                  f"(it is with the {holder['holder_type']}).")
        at = _datetime(at, "Time") if at else dates.now_iso()
        with self.conn:
            return self._insert_movement(inw, "return_staff", at, holder["holder_name"], custodian["name"],
                                         custodian["custodian_id"], remarks=remarks, is_sample=is_sample)

    def hand_to_consultant(self, inward_id, consultant_id, purpose="", expected_return=None, remarks="",
                           at=None, is_sample=0):
        """Custodian -> outside consultant (e.g. a CS for ROC filing)."""
        custodian = self._require_custodian()
        inw, holder = self._open_entry(inward_id)
        consultant = self.get_consultant(consultant_id) if consultant_id else None
        if not consultant:
            raise ValidationError("Please select the consultant.")
        if not consultant["active"]:
            raise ValidationError(f"Consultant {consultant['name']} is marked inactive.")
        self._need_custodian_holder(holder, inw, "handing it to a consultant")
        at = _datetime(at, "Time") if at else dates.now_iso()
        expected_return = self._clean_expected_return(expected_return, at)
        with self.conn:
            return self._insert_movement(inw, "to_consultant", at, custodian["name"], consultant["name"],
                                         custodian["custodian_id"], consultant["consultant_id"],
                                         purpose=_clean(purpose) or inw["purpose"],
                                         expected_return=expected_return, remarks=remarks, is_sample=is_sample)

    def return_from_consultant(self, inward_id, remarks="", at=None, is_sample=0):
        custodian = self._require_custodian()
        inw, holder = self._open_entry(inward_id)
        if holder["holder_type"] != "consultant":
            raise ValidationError(f"Token {inw['token_serial']} is not with a consultant "
                                  f"(it is with the {holder['holder_type']}).")
        at = _datetime(at, "Time") if at else dates.now_iso()
        with self.conn:
            return self._insert_movement(inw, "return_consultant", at, holder["holder_name"], custodian["name"],
                                         custodian["custodian_id"], holder["consultant_id"], remarks=remarks,
                                         is_sample=is_sample)

    def client_collected_from_consultant(self, inward_id, collected_by, remarks="", at=None, is_sample=0):
        """The client took the token back from the consultant: ends the firm's custody."""
        inw, holder = self._open_entry(inward_id)
        if holder["holder_type"] != "consultant":
            raise ValidationError(f"Token {inw['token_serial']} is not with a consultant.")
        collected_by = _clean(collected_by)
        if not collected_by:
            raise ValidationError("Please enter who collected the token from the consultant.")
        at = _datetime(at, "Time") if at else dates.now_iso()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO outward (outward_date, inward_id, token_id, client_id, holder_name, returned_to, "
                "returned_by, purpose, remarks, via_consultant_id, collected_by, is_sample, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (at[:10], inward_id, inw["token_id"], inw["client_id"], inw["holder_name"], collected_by,
                 holder["holder_name"], inw["purpose"], _clean(remarks), holder["consultant_id"], collected_by,
                 is_sample, at))
            return cur.lastrowid

    def cancel_movement(self, movement_id, reason):
        reason = _clean(reason)
        if not reason:
            raise ValidationError("Please give a reason for cancelling the movement.")
        m = self._one("SELECT * FROM movements WHERE movement_id = ?", (movement_id,))
        if not m:
            raise ValidationError("Movement not found.")
        if m["status"] != "Active":
            raise ValidationError("This movement is already cancelled.")
        if m["kind"] == "handover":
            raise ValidationError("Custodian hand-over entries are created automatically and cannot be cancelled.")
        if not self._one("SELECT 1 FROM v_open_inward WHERE inward_id = ?", (m["inward_id"],)):
            raise ValidationError("The token is no longer in custody. Cancel its outward entry first.")
        last = self._one("SELECT movement_id FROM v_last_movement WHERE inward_id = ?", (m["inward_id"],))
        if last["movement_id"] != movement_id:
            raise ValidationError("Only the latest movement of a token can be cancelled.")
        with self.conn:
            self.conn.execute("UPDATE movements SET status = 'Cancelled', status_note = ? WHERE movement_id = ?",
                              (f"Cancelled: {reason}", movement_id))

    # ------------------------------------------------------------------ outward
    def save_outward(self, data, is_sample=0):
        """Record the custodian returning a DSC to the client. Returns outward_id."""
        inward_id = data.get("inward_id")
        if not inward_id:
            raise ValidationError("Please select the DSC being returned from the custody list.")
        inw = self._one("SELECT * FROM inward WHERE inward_id = ?", (inward_id,))
        if not inw:
            raise ValidationError("Inward entry not found.")
        if self._scalar("SELECT COUNT(*) FROM outward WHERE inward_id = ? AND status = 'Active'", (inward_id,)):
            raise ValidationError("This DSC has already been returned (an outward entry exists).")
        if inw["status"] != "Active":
            raise ValidationError(f"Inward #{inward_id} is {inw['status']} and is not in custody.")
        custodian = self._require_custodian()
        holder = self.holder_of(inward_id)
        if holder["holder_type"] == "staff":
            raise ValidationError(f"The token is with staff member {holder['holder_name']}. "
                                  "Record its return to the custodian before returning it to the client.")
        if holder["holder_type"] == "consultant":
            raise ValidationError(f"The token is with consultant {holder['holder_name']}. Record its return to "
                                  "the custodian, or record that the client collected it from the consultant.")
        out_date = _date(data.get("outward_date"), "Outward Date", required=True)
        returned_to = _clean(data.get("returned_to"))
        if out_date > dates.today_iso():
            raise ValidationError("Outward Date cannot be in the future.")
        if out_date < inw["inward_date"]:
            raise ValidationError(f"Outward Date cannot be before the Inward Date "
                                  f"({dates.to_display(inw['inward_date'])}).")
        if not returned_to:
            raise ValidationError("Returned To is required.")
        purpose = _clean(data.get("purpose")) or inw["purpose"]
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO outward (outward_date, inward_id, token_id, client_id, holder_name, returned_to, "
                    "returned_by, purpose, remarks, is_sample) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (out_date, inward_id, inw["token_id"], inw["client_id"], inw["holder_name"], returned_to,
                     custodian["name"], purpose, _clean(data.get("remarks")), is_sample))
                return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError("This DSC has already been returned (an outward entry exists).") from None

    def cancel_outward(self, outward_id, reason):
        reason = _clean(reason)
        if not reason:
            raise ValidationError("Please give a reason for cancelling the entry.")
        out = self._one("SELECT * FROM outward WHERE outward_id = ?", (outward_id,))
        if not out:
            raise ValidationError("Outward entry not found.")
        if out["status"] != "Active":
            raise ValidationError(f"Outward #{outward_id} is already cancelled.")
        if out["closed_as"] == "inactive":
            raise ValidationError("This entry ended custody because the token was made Inactive. If the token is "
                                  "back, mark it Active again and record a new inward entry.")
        if self.open_inward_for_token(out["token_id"]):
            raise ValidationError("This token has since been received again and is in custody under a newer "
                                  "inward entry, so this return cannot be cancelled.")
        with self.conn:
            self.conn.execute("UPDATE outward SET status = 'Cancelled', status_note = ? WHERE outward_id = ?",
                              (f"Cancelled: {reason}", outward_id))

    # ------------------------------------------------------------------ corrections
    def correct_inward(self, inward_id, data, reason, at=None):
        """Correct an inward entry's date, Received From, purpose, expected return date or remarks.
        The client and token cannot be changed (cancel and re-enter). Returns [(label, old, new), ...]."""
        inw = self._one("SELECT * FROM inward WHERE inward_id = ?", (inward_id,))
        if not inw:
            raise ValidationError("Inward entry not found.")
        if inw["status"] == "Cancelled":
            raise ValidationError("A cancelled entry cannot be corrected.")
        new = {
            "inward_date": _date(data.get("inward_date", inw["inward_date"]), "Inward Date", required=True),
            "received_from": _clean(data.get("received_from", inw["received_from"])),
            "purpose": _clean(data.get("purpose", inw["purpose"])),
            "expected_return_date": _date(data.get("expected_return_date", inw["expected_return_date"]),
                                          "Expected Return Date"),
            "remarks": _clean(data.get("remarks", inw["remarks"])),
        }
        day = new["inward_date"]
        if day > dates.today_iso():
            raise ValidationError("Inward Date cannot be in the future.")
        if not new["received_from"]:
            raise ValidationError("Received From is required.")
        if new["purpose"] not in PURPOSES:
            raise ValidationError("Please select the Purpose/Assignment.")
        if new["expected_return_date"] and new["expected_return_date"] < day:
            raise ValidationError("Expected Return Date cannot be before the Inward Date.")
        first_move = self._scalar("SELECT MIN(substr(moved_at, 1, 10)) FROM movements WHERE inward_id = ? "
                                  "AND status = 'Active'", (inward_id,))
        if first_move and day > first_move:
            raise ValidationError(f"Inward Date cannot be after the token was first handed over "
                                  f"({dates.to_display(first_move)}).")
        returned = self._scalar("SELECT outward_date FROM outward WHERE inward_id = ? AND status = 'Active'",
                                (inward_id,))
        if returned and day > returned:
            raise ValidationError(f"Inward Date cannot be after the token was returned "
                                  f"({dates.to_display(returned)}).")
        earlier = self._scalar("SELECT MAX(outward_date) FROM outward WHERE token_id = ? AND status = 'Active' "
                               "AND inward_id < ?", (inw["token_id"], inward_id))
        if earlier and day < earlier:
            raise ValidationError(f"Inward Date cannot be before the token's previous return "
                                  f"({dates.to_display(earlier)}).")
        return self._apply_correction("inward", inw, new, reason, at)

    def correct_outward(self, outward_id, data, reason, at=None):
        """Correct an outward entry's date, Returned To, purpose or remarks. Returns [(label, old, new), ...]."""
        out = self._one("SELECT * FROM outward WHERE outward_id = ?", (outward_id,))
        if not out:
            raise ValidationError("Outward entry not found.")
        if out["status"] == "Cancelled":
            raise ValidationError("A cancelled entry cannot be corrected.")
        new = {
            "outward_date": _date(data.get("outward_date", out["outward_date"]), "Outward Date", required=True),
            "returned_to": _clean(data.get("returned_to", out["returned_to"])),
            "purpose": _clean(data.get("purpose", out["purpose"])),
            "remarks": _clean(data.get("remarks", out["remarks"])),
        }
        day = new["outward_date"]
        if day != out["outward_date"]:
            if out["closed_as"] == "inactive" or out["via_consultant_id"] is not None:
                raise ValidationError("The date of this entry was taken from the system clock and cannot be "
                                      "changed.")
            if day > dates.today_iso():
                raise ValidationError("Outward Date cannot be in the future.")
            inward_date = self._scalar("SELECT inward_date FROM inward WHERE inward_id = ?", (out["inward_id"],))
            if day < inward_date:
                raise ValidationError(f"Outward Date cannot be before the Inward Date "
                                      f"({dates.to_display(inward_date)}).")
            last_move = self._scalar("SELECT MAX(substr(moved_at, 1, 10)) FROM movements WHERE inward_id = ? "
                                     "AND status = 'Active'", (out["inward_id"],))
            if last_move and day < last_move:
                raise ValidationError(f"Outward Date cannot be before the token came back to the custodian "
                                      f"({dates.to_display(last_move)}).")
            later = self._scalar("SELECT MIN(inward_date) FROM inward WHERE token_id = ? AND inward_id > ? "
                                 "AND status <> 'Cancelled'", (out["token_id"], out["inward_id"]))
            if later and day > later:
                raise ValidationError(f"Outward Date cannot be after the token was received again "
                                      f"({dates.to_display(later)}).")
        if not new["returned_to"]:
            raise ValidationError("Returned To is required.")
        return self._apply_correction("outward", out, new, reason, at)

    def _apply_correction(self, kind, entry, new, reason, at=None):
        reason = _clean(reason)
        if not reason:
            raise ValidationError("Please give the reason for the correction.")
        changes = [(k, entry[k], v) for k, v in new.items() if (entry[k] or "") != (v or "")]
        if not changes:
            raise ValidationError("Nothing was changed.")
        at = at or dates.now_iso()
        entry_id = entry[f"{kind}_id"]
        with self.conn:
            self.conn.execute(f"UPDATE {kind} SET " + ", ".join(f"{k} = ?" for k, _, _ in changes)
                              + f" WHERE {kind}_id = ?", [v for _, _, v in changes] + [entry_id])
            for field, old, value in changes:
                self.conn.execute(
                    "INSERT INTO corrections (entry_type, entry_id, token_id, field, old_value, new_value, reason, "
                    "corrected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (kind, entry_id, entry["token_id"], field, old, value, reason, at))
        return [self.correction_text(f, old, value) for f, old, value in changes]

    def corrections_for(self, kind, entry_id):
        return self._all("SELECT * FROM corrections WHERE entry_type = ? AND entry_id = ? ORDER BY correction_id",
                         (kind, entry_id))

    @staticmethod
    def correction_text(field, old, new):
        """'Purpose: ITR Filing -> Tax Audit', with dates as DD-MM-YYYY."""
        label = {**INWARD_CORRECTABLE, **OUTWARD_CORRECTABLE}.get(field, field)
        if field in DATE_FIELDS:
            old, new = dates.to_display(old) if old else "", dates.to_display(new) if new else ""
        return f"{label}: {old or '(blank)'} -> {new or '(blank)'}"

    # ------------------------------------------------------------------ restore
    def restore_from(self, path):
        """Replace all the data with a backup file's. A copy of the current data is saved first, next to the
        database (DSC_BeforeRestore_<date-time>.db), so a restore can itself be undone. Returns that copy's
        path. Reopen the database afterwards (an older backup is brought up to date on opening)."""
        path = os.path.abspath(path)
        if os.path.normcase(path) == os.path.normcase(self.path):
            raise ValidationError("That is the database in use, not a backup.")
        if not is_valid_database(path):
            raise ValidationError(f"{path}\nis not a DSC Management Tool backup, or the file is damaged.")
        safety = self.backup_to(os.path.dirname(self.path),
                                f"DSC_BeforeRestore_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")
        self.conn.commit()
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            src.backup(self.conn)
        finally:
            src.close()
        return safety

    # ------------------------------------------------------------------ reports
    @staticmethod
    def _filters(sql, params, f, date_col, staff_col, alias):
        if f.get("from_date"):
            sql += f" AND {date_col} >= ?"
            params.append(f["from_date"])
        if f.get("to_date"):
            sql += f" AND {date_col} <= ?"
            # Timestamp columns hold a time too, so the whole of the last day counts.
            params.append(f["to_date"] + " 23:59:59" if date_col.endswith(("moved_at", "created_at"))
                          else f["to_date"])
        if f.get("client_id"):
            sql += f" AND {alias}.client_id = ?"
            params.append(f["client_id"])
        if f.get("staff") and staff_col:
            sql += f" AND {staff_col} = ?"
            params.append(f["staff"])
        if f.get("purpose"):
            sql += f" AND {alias}.purpose = ?"
            params.append(f["purpose"])
        if _clean(f.get("search")):
            like = f"%{f['search'].strip()}%"
            # Report searches match names people remember: the DSC holder and the client (holder or firm).
            sql += f" AND ({alias}.holder_name LIKE ? OR c.holder_name LIKE ? OR c.firm_name LIKE ?)"
            params += [like] * 3
        return sql, params

    def inward_register(self, f=None):
        f = f or {}
        sql = """
            SELECT i.inward_id, i.inward_date, i.created_at, c.client_code, c.firm_name, i.holder_name,
                   t.token_serial, COALESCE(ce.cert_serial, cur.cert_serial) AS cert_serial,
                   COALESCE(ce.expiry_date, cur.expiry_date) AS expiry_date,
                   i.purpose, i.received_from, i.received_by, i.expected_return_date, i.remarks, i.status,
                   i.status_note, i.token_id, i.client_id,
                   (SELECT o.outward_date FROM outward o WHERE o.inward_id = i.inward_id AND o.status = 'Active')
                       AS returned_on,
                   (SELECT COUNT(*) FROM corrections x WHERE x.entry_type = 'inward' AND x.entry_id = i.inward_id)
                       AS corrections
            FROM inward i
            JOIN clients c ON c.client_id = i.client_id
            JOIN tokens t ON t.token_id = i.token_id
            LEFT JOIN certificates ce ON ce.cert_id = i.cert_id
            LEFT JOIN certificates cur ON cur.token_id = i.token_id AND cur.is_current = 1
            WHERE 1 = 1"""
        params = []
        if not f.get("include_cancelled"):
            sql += " AND i.status <> 'Cancelled'"
        sql, params = self._filters(sql, params, f, "i.inward_date", "i.received_by", "i")
        sql += " ORDER BY i.inward_date DESC, i.inward_id DESC"
        rows = self._all(sql, params)
        for r in rows:
            if r["status"] == "Active":
                r["custody"] = f"Returned {dates.to_display(r['returned_on'])}" if r["returned_on"] else "In Custody"
            else:
                r["custody"] = r["status"]
            if r["corrections"] and r["status"] != "Cancelled":
                r["custody"] += " (corrected)"
        return rows

    def outward_register(self, f=None):
        f = f or {}
        sql = """
            SELECT o.outward_id, o.outward_date, o.created_at, o.inward_id, i.inward_date, c.client_code,
                   c.firm_name, o.holder_name, t.token_serial, o.purpose, o.returned_to, o.returned_by, o.remarks,
                   o.status, o.status_note, o.token_id, o.client_id, o.via_consultant_id, o.collected_by,
                   CASE WHEN o.closed_as = 'inactive' THEN 'Token made inactive'
                        WHEN o.via_consultant_id IS NULL THEN 'Custodian' ELSE 'Collected from consultant' END
                       AS returned_via,
                   (SELECT COUNT(*) FROM corrections x WHERE x.entry_type = 'outward' AND x.entry_id = o.outward_id)
                       AS corrections
            FROM outward o
            JOIN inward i ON i.inward_id = o.inward_id
            JOIN clients c ON c.client_id = o.client_id
            JOIN tokens t ON t.token_id = o.token_id
            WHERE 1 = 1"""
        params = []
        if not f.get("include_cancelled"):
            sql += " AND o.status <> 'Cancelled'"
        sql, params = self._filters(sql, params, f, "o.outward_date", "o.returned_by", "o")
        sql += " ORDER BY o.outward_date DESC, o.outward_id DESC"
        rows = self._all(sql, params)
        for r in rows:
            r["status_text"] = r["status"] + (" (corrected)" if r["corrections"] and r["status"] == "Active" else "")
        return rows

    def custody_register(self, f=None, as_of=None):
        """Live custody: one row per token currently held by the firm, with its current holder."""
        f = f or {}
        now = dates.iso_to_datetime(as_of) if as_of else dates.now()
        today = now.date()
        sql = """
            SELECT i.inward_id, i.inward_date, i.client_id, c.client_code, c.firm_name, i.holder_name,
                   t.token_id, t.token_serial, cur.cert_serial, cur.expiry_date, cur.admin_status, i.purpose,
                   i.received_from, i.received_by, i.expected_return_date, i.remarks
            FROM v_open_inward i
            JOIN clients c ON c.client_id = i.client_id
            JOIN tokens t ON t.token_id = i.token_id
            LEFT JOIN certificates cur ON cur.token_id = i.token_id AND cur.is_current = 1
            WHERE i.inward_id = (SELECT MAX(j.inward_id) FROM v_open_inward j WHERE j.token_id = i.token_id)"""
        params = []
        sql, params = self._filters(sql, params, f, "i.inward_date", None, "i")
        sql += " ORDER BY i.inward_date, i.inward_id"
        holders = {h["inward_id"]: h for h in self._holders()}
        rows = []
        for r in self._all(sql, params):
            h = holders[r["inward_id"]]
            # who has the token right now ("with_*"; holder_name stays the DSC holder)
            r["with_type"], r["with_name"] = h["holder_type"], h["holder_name"]
            r["with_label"] = f"{HOLDER_LABELS[h['holder_type']]}: {h['holder_name']}"
            r["with_since"], r["with_due"] = h["holder_since"], h["expected_return"]
            r["with_purpose"] = h["purpose"]
            r["with_movement_id"], r["with_kind"] = h["movement_id"], h["kind"]
            r["internal_overdue"] = bool(h["expected_return"] and dates.iso_to_datetime(h["expected_return"]) < now)
            r["days_in_custody"] = dates.days_between(r["inward_date"], today)
            due = dates.days_between(today.isoformat(), dates.iso_to_date(r["expected_return_date"])) \
                if r["expected_return_date"] else None
            r["days_to_return"] = due
            if due is None:
                r["custody_status"], r["overdue_flag"] = "In Custody", "none"
            elif due < 0:
                r["custody_status"], r["overdue_flag"] = f"Overdue by {-due} day(s)", "overdue"
            elif due == 0:
                r["custody_status"], r["overdue_flag"] = "Return Due Today", "soon"
            elif due <= DUE_SOON_DAYS:
                r["custody_status"], r["overdue_flag"] = f"Return Due in {due} day(s)", "soon"
            else:
                r["custody_status"], r["overdue_flag"] = "In Custody", "ok"
            if r["internal_overdue"]:
                r["with_status"] = f"Overdue back to custodian (due {dates.to_display_dt(r['with_due'])})"
            elif r["with_due"]:
                r["with_status"] = f"Due back {dates.to_display_dt(r['with_due'])}"
            else:
                r["with_status"] = ""
            _, r["expiry_status"] = classify_expiry(r["expiry_date"], now)
            ov = f.get("overdue")
            if ov == "overdue" and r["overdue_flag"] != "overdue":
                continue
            if ov == "soon" and r["overdue_flag"] != "soon":
                continue
            if ov == "not_overdue" and r["overdue_flag"] == "overdue":
                continue
            hf = f.get("holder")
            if hf in HOLDER_LABELS and r["with_type"] != hf:
                continue
            if hf == "internal_overdue" and not r["internal_overdue"]:
                continue
            if f.get("with_name") and r["with_name"] != f["with_name"]:
                continue
            rows.append(r)
        return rows

    def movement_register(self, f=None):
        """Every internal/external movement, plus 'client collected from consultant' entries."""
        f = f or {}
        sql = """
            SELECT m.movement_id AS entry_id, m.moved_at, m.kind, m.from_name, m.to_name, m.purpose,
                   m.expected_return, m.remarks, m.status, m.status_note, m.inward_id, m.token_id,
                   t.token_serial, i.holder_name, c.client_code, i.client_id
            FROM movements m
            JOIN inward i ON i.inward_id = m.inward_id
            JOIN tokens t ON t.token_id = m.token_id
            JOIN clients c ON c.client_id = i.client_id
            WHERE 1 = 1"""
        params = []
        if not f.get("include_cancelled"):
            sql += " AND m.status <> 'Cancelled'"
        if f.get("kind") and f["kind"] not in OUTWARD_KINDS:
            sql += " AND m.kind = ?"
            params.append(f["kind"])
        if f.get("person"):
            sql += " AND (m.from_name = ? OR m.to_name = ?)"
            params += [f["person"], f["person"]]
        sql, params = self._filters(sql, params, {k: f.get(k) for k in ("from_date", "to_date", "client_id",
                                                                        "search")},
                                    "m.moved_at", None, "i")
        rows = [] if f.get("kind") in OUTWARD_KINDS else self._all(sql, params)
        if not f.get("kind") or f["kind"] in OUTWARD_KINDS:
            osql = """
                SELECT o.outward_id AS entry_id, o.created_at AS moved_at,
                       CASE WHEN o.closed_as = 'inactive' THEN 'token_inactive' ELSE 'client_collected' END AS kind,
                       o.returned_by AS from_name, COALESCE(o.collected_by, o.returned_to) AS to_name, o.purpose,
                       NULL AS expected_return, o.remarks, o.status, o.status_note, o.inward_id, o.token_id,
                       t.token_serial, o.holder_name, c.client_code, o.client_id
                FROM outward o JOIN tokens t ON t.token_id = o.token_id JOIN clients c ON c.client_id = o.client_id
                WHERE (o.via_consultant_id IS NOT NULL OR o.closed_as = 'inactive')"""
            oparams = []
            if f.get("kind") == "client_collected":
                osql += " AND o.closed_as IS NULL"
            elif f.get("kind") == "token_inactive":
                osql += " AND o.closed_as = 'inactive'"
            if not f.get("include_cancelled"):
                osql += " AND o.status <> 'Cancelled'"
            if f.get("person"):
                osql += " AND (o.returned_by = ? OR o.collected_by = ?)"
                oparams += [f["person"], f["person"]]
            osql, oparams = self._filters(osql, oparams, {k: f.get(k) for k in ("from_date", "to_date",
                                                                                "client_id", "search")},
                                          "o.created_at", None, "o")
            rows += self._all(osql, oparams)
        for r in rows:
            r["kind_label"] = MOVEMENT_LABELS[r["kind"]]
        # Newest first; a client collection always follows the hand-over it ends, even in the same second.
        rows.sort(key=lambda r: (r["moved_at"], r["kind"] in OUTWARD_KINDS, r["entry_id"]), reverse=True)
        return rows

    def token_history(self, token_id):
        """The full chain of custody of one token, oldest first."""
        events = []

        def when(day, recorded):
            # Entries carry a date the user chose plus the system time they were recorded.
            return recorded if recorded and recorded[:10] == day else day

        for i in self._all("SELECT * FROM inward WHERE token_id = ?", (token_id,)):
            events.append({"at": when(i["inward_date"], i["created_at"]), "event": "Inward (received from client)",
                           "from": i["received_from"], "to": f"Custodian: {i['received_by']}",
                           "details": f"Inward #{i['inward_id']} - {i['purpose']}", "status": i["status"],
                           "order": (i["inward_id"], 0, 0)})
        for m in self._all("SELECT * FROM movements WHERE token_id = ?", (token_id,)):
            details = m["purpose"] or m["remarks"] or ""
            if m["expected_return"]:
                details += f" (due back {dates.to_display_dt(m['expected_return'])})"
            events.append({"at": m["moved_at"], "event": MOVEMENT_LABELS[m["kind"]], "from": m["from_name"],
                           "to": m["to_name"], "details": details.strip(), "status": m["status"],
                           "order": (m["inward_id"], 1, m["movement_id"])})
        for o in self._all("SELECT * FROM outward WHERE token_id = ?", (token_id,)):
            if o["closed_as"] == "inactive":
                at, event, details = o["created_at"], "Custody ended - token made inactive", o["remarks"] or ""
            elif o["via_consultant_id"] is not None:
                at, event, details = o["created_at"], "Client collected from consultant", f"Outward #{o['outward_id']}"
            else:
                at = when(o["outward_date"], o["created_at"])
                event, details = "Outward (returned to client)", f"Outward #{o['outward_id']}"
            events.append({"at": at, "event": event, "from": o["returned_by"], "to": o["returned_to"],
                           "details": details, "status": o["status"], "order": (o["inward_id"], 2, o["outward_id"])})
        batches = {}   # one history line per correction (all the fields changed at once)
        for x in self._all("SELECT * FROM corrections WHERE token_id = ? ORDER BY correction_id", (token_id,)):
            b = batches.setdefault((x["entry_type"], x["entry_id"], x["corrected_at"]),
                                   {"reason": x["reason"], "changes": []})
            b["changes"].append(self.correction_text(x["field"], x["old_value"], x["new_value"]))
        for (kind, entry_id, at), b in batches.items():
            events.append({"at": at, "event": f"{kind.title()} #{entry_id} corrected", "from": "", "to": "",
                           "details": "; ".join(b["changes"]) + f". Reason: {b['reason']}", "status": "Corrected",
                           "order": None})
        for log in self._all("SELECT * FROM token_status_log WHERE token_id = ?", (token_id,)):
            events.append({"at": log["changed_at"], "event": f"Token made {log['status']}", "from": "", "to": "",
                           "details": log["reason"] or "", "status": log["status"], "order": None})
        # Custody events follow their inward entries; status changes slot in by time.
        custody = sorted((e for e in events if e["order"]), key=lambda e: e["order"])
        for e in sorted((e for e in events if not e["order"]), key=lambda e: e["at"]):
            pos = next((i for i, c in enumerate(custody) if c["at"] > e["at"]), len(custody))
            custody.insert(pos, e)
        return custody

    def awaited_list(self, f=None, as_of=None):
        f = f or {}
        today = dates.iso_to_date(as_of) if as_of else dates.today()
        sql = """
            SELECT e.expected_id, e.client_id, c.client_code, c.firm_name, e.holder_name, e.token_serial,
                   e.purpose, e.expected_date, e.followup_staff, e.remarks, e.created_at
            FROM v_awaited e JOIN clients c ON c.client_id = e.client_id WHERE 1 = 1"""
        params = []
        if f.get("client_id"):
            sql += " AND e.client_id = ?"
            params.append(f["client_id"])
        if f.get("staff"):
            sql += " AND e.followup_staff = ?"
            params.append(f["staff"])
        if f.get("purpose"):
            sql += " AND e.purpose = ?"
            params.append(f["purpose"])
        if _clean(f.get("search")):
            like = f"%{f['search'].strip()}%"
            sql += " AND (e.holder_name LIKE ? OR c.holder_name LIKE ? OR c.firm_name LIKE ?)"
            params += [like] * 3
        sql += " ORDER BY e.expected_date IS NULL, e.expected_date, e.expected_id"
        rows = []
        for r in self._all(sql, params):
            due = dates.days_between(today.isoformat(), dates.iso_to_date(r["expected_date"])) \
                if r["expected_date"] else None
            if due is None:
                r["await_status"], r["overdue_flag"] = "Awaited", "none"
            elif due < 0:
                r["await_status"], r["overdue_flag"] = f"Overdue by {-due} day(s)", "overdue"
            elif due <= DUE_SOON_DAYS:
                r["await_status"], r["overdue_flag"] = ("Due Today" if due == 0 else f"Due in {due} day(s)"), "soon"
            else:
                r["await_status"], r["overdue_flag"] = "Awaited", "ok"
            if f.get("overdue") == "overdue" and r["overdue_flag"] != "overdue":
                continue
            rows.append(r)
        return rows

    def expiry_alerts(self, flt="all", f=None, as_of=None):
        """One row per token with its *current* certificate (never duplicated)."""
        f = f or {}
        now = dates.iso_to_datetime(as_of) if as_of else dates.now()
        sql = """
            SELECT t.token_id, t.token_serial, t.client_id, c.client_code, c.firm_name,
                   t.status AS token_status, t.inactive_reason,
                   COALESCE(cur.holder_name, t.holder_name) AS holder_name,
                   cur.cert_id, cur.cert_serial, cur.issue_date, cur.expiry_date, cur.issuer, cur.admin_status,
                   cur.remarks, cur.followup,
                   (SELECT i.inward_id FROM v_open_inward i WHERE i.token_id = t.token_id
                    ORDER BY i.inward_id DESC LIMIT 1) AS open_inward_id,
                   EXISTS (SELECT 1 FROM outward o WHERE o.token_id = t.token_id AND o.status = 'Active')
                       AS ever_returned,
                   (SELECT COUNT(*) FROM certificates h WHERE h.token_id = t.token_id) AS cert_count
            FROM tokens t
            JOIN clients c ON c.client_id = t.client_id
            LEFT JOIN certificates cur ON cur.token_id = t.token_id AND cur.is_current = 1
            WHERE 1 = 1"""
        params = []
        if f.get("client_id"):
            sql += " AND t.client_id = ?"
            params.append(f["client_id"])
        if _clean(f.get("search")):
            like = f"%{f['search'].strip()}%"
            sql += " AND (t.holder_name LIKE ? OR c.holder_name LIKE ? OR c.firm_name LIKE ?)"
            params += [like] * 3
        holders = {h["inward_id"]: h for h in self._holders()}
        rows = []
        for r in self._all(sql, params):
            r["days"], r["expiry_status"] = classify_expiry(r["expiry_date"], now)
            r["admin_status"] = r["admin_status"] or "Not Recorded"
            if r["open_inward_id"]:
                r["custody"] = "In Custody"
                h = holders[r["open_inward_id"]]
                r["with_label"] = f"{HOLDER_LABELS[h['holder_type']]}: {h['holder_name']}"
            else:
                r["custody"] = "Returned" if r["ever_returned"] else "Not in Custody"
                r["with_label"] = "-"
            if f.get("custody") and r["custody"] != f["custody"]:
                continue
            if r["token_status"] == "Inactive":  # lost / replaced tokens appear only under "All tokens"
                if flt != "all":
                    continue
                r["custody"] = f"Inactive - {r['inactive_reason'] or ''}"
            if not matches_expiry_filter(flt, r["days"], r["expiry_status"], r["admin_status"]):
                continue
            r["days_text"] = days_text(r["days"], r["expiry_status"], r["expiry_date"])
            r["followup_text"] = " | ".join(x for x in (r["followup"], r["remarks"]) if x)
            rows.append(r)
        rows.sort(key=lambda r: (r["expiry_date"] is None, dates.iso_to_datetime(r["expiry_date"]) or now,
                                 r["holder_name"]))
        return rows

    def dashboard_counts(self, from_date=None, to_date=None, as_of=None):
        now = dates.iso_to_datetime(as_of) if as_of else dates.now()
        rng, params = "", []
        if from_date:
            rng += " AND {col} >= ?"
            params.append(from_date)
        if to_date:
            rng += " AND {col} <= ?"
            params.append(to_date)
        counts = {
            "inward": self._scalar("SELECT COUNT(*) FROM inward WHERE status <> 'Cancelled'"
                                   + rng.format(col="inward_date"), params),
            "outward": self._scalar("SELECT COUNT(*) FROM outward WHERE status = 'Active'"
                                    + rng.format(col="outward_date"), params),
            "custody": self._scalar("SELECT COUNT(DISTINCT token_id) FROM v_open_inward"),
            "awaited": self._scalar("SELECT COUNT(*) FROM v_awaited"),
        }
        custody = self.custody_register(as_of=now)
        counts["overdue"] = sum(1 for r in custody if r["overdue_flag"] == "overdue")
        for kind in HOLDER_LABELS:
            counts[f"with_{kind}"] = sum(1 for r in custody if r["with_type"] == kind)
            counts[f"{kind}_overdue"] = sum(1 for r in custody if r["with_type"] == kind and r["internal_overdue"])
        alerts = self.expiry_alerts("all", as_of=now)
        for key in ("7", "15", "30", "expired", "unknown", "renewal", "today"):
            counts[f"exp_{key}"] = sum(1 for r in alerts if r["token_status"] == "Active" and matches_expiry_filter(
                key, r["days"], r["expiry_status"], r["admin_status"]))
        return counts

    def today_summary(self, as_of=None):
        """Counts for the dashboard's 'Today' strip."""
        now = dates.iso_to_datetime(as_of) if as_of else dates.now()
        today = now.date().isoformat()
        custody = self.custody_register(as_of=now)
        return {
            "received": self._scalar("SELECT COUNT(*) FROM inward WHERE status <> 'Cancelled' AND inward_date = ?",
                                     (today,)),
            "returned": self._scalar("SELECT COUNT(*) FROM outward WHERE status = 'Active' AND outward_date = ?",
                                     (today,)),
            "due_back": sum(1 for r in custody if (r["with_due"] or "")[:10] == today),
            "expiring": sum(1 for r in self.expiry_alerts("today", as_of=now) if r["token_status"] == "Active"),
            "awaited": sum(1 for r in self.awaited_list(as_of=now) if r["expected_date"] == today),
        }

    def search_index(self):
        """Everything the search box at the top can find: clients (name, firm, client ID, PAN, mobile)
        and tokens (serial, holder, certificate serial). [{kind, id, label, text}, ...]"""
        items = []
        for c in self._all("SELECT client_id, client_code, holder_name, firm_name, pan, mobile, status FROM clients "
                           "ORDER BY holder_name COLLATE NOCASE"):
            firm = f" ({c['firm_name']})" if c["firm_name"] else ""
            inactive = " - inactive" if c["status"] != "Active" else ""
            items.append({"kind": "client", "id": c["client_id"],
                          "label": f"Client  {c['client_code']} - {c['holder_name']}{firm}  {c['mobile'] or ''}{inactive}",
                          "text": " ".join(str(v or "") for v in (c["client_code"], c["holder_name"], c["firm_name"],
                                                                   c["pan"], c["mobile"]))})
        for t in self._all("""SELECT t.token_id, t.token_serial, t.holder_name, t.status, c.client_code,
                                     cur.cert_serial
                              FROM tokens t JOIN clients c USING (client_id)
                              LEFT JOIN certificates cur ON cur.token_id = t.token_id AND cur.is_current = 1
                              ORDER BY t.token_serial"""):
            inactive = " - inactive" if t["status"] != "Active" else ""
            items.append({"kind": "token", "id": t["token_id"],
                          "label": f"Token  {t['token_serial']} - {t['holder_name']} ({t['client_code']}){inactive}",
                          "text": " ".join(str(v or "") for v in (t["token_serial"], t["holder_name"],
                                                                   t["cert_serial"], t["client_code"]))})
        return items

    def person_names(self):
        """Everyone who can receive or return a token: custodians, staff and consultants."""
        names = {r["name"] for r in self._all("SELECT name FROM custodians")}
        names |= set(self.list_staff())
        names |= {r["name"] for r in self._all("SELECT name FROM consultants")}
        return sorted(names, key=str.lower)

    def recent_inwards(self, limit=10):
        return self.inward_register()[:limit]

    # ------------------------------------------------------------------ backup & sample data
    def backup_to(self, folder, name=None):
        """Write a dated copy of the database into folder. Returns the file path."""
        if not folder or not os.path.isdir(folder):
            raise ValidationError("Please choose an existing folder for the backup.")
        name = name or f"DSC_Backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db"
        dest = os.path.join(folder, name)
        if os.path.abspath(dest) == self.path:
            raise ValidationError("Backup cannot overwrite the live database.")
        target = sqlite3.connect(dest)
        try:
            with target:
                self.conn.backup(target)
        finally:
            target.close()
        self.set_meta("last_backup", f"{datetime.now().strftime('%d-%m-%Y %H:%M')} -> {dest}")
        self.set_meta("last_backup_at", dates.now_iso())
        return dest

    AUTO_PREFIX = "DSC_AutoBackup_"

    def auto_backup(self, folder, keep=30):
        """The automatic daily backup: one file per day (DSC_AutoBackup_YYYY-MM-DD.db); only the
        latest `keep` of them are kept so the folder does not fill up. Returns the path."""
        dest = self.backup_to(folder, f"{self.AUTO_PREFIX}{dates.today_iso()}.db")
        self.set_meta("last_auto_backup_at", dates.now_iso())
        old = sorted(f for f in os.listdir(folder) if f.startswith(self.AUTO_PREFIX) and f.endswith(".db"))
        for f in old[:-keep]:
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass
        return dest

    def days_since_backup(self, as_of=None):
        """Whole days since the last backup (manual or automatic); None if there has never been one."""
        last = self.get_meta("last_backup_at")
        if not last:
            return None
        now = dates.iso_to_datetime(as_of) if as_of else dates.now()
        return (now.date() - dates.iso_to_date(last)).days

    def attention_summary(self, as_of=None):
        """What needs attention today, for the message shown when the app opens.

        Returns [(text, screen, options), ...] - empty when everything is in order.
        """
        c = self.dashboard_counts(as_of=as_of)
        items = []
        if not self.current_custodian():
            items.append(("No custodian has been appointed.", "settings", {"tab": 0}))
        if c["exp_expired"]:
            items.append((f"{c['exp_expired']} certificate(s) have already expired.", "alerts", {"flt": "expired"}))
        if c["exp_7"]:
            today = f" ({c['exp_today']} today)" if c["exp_today"] else ""
            items.append((f"{c['exp_7']} certificate(s) expire within 7 days{today}.", "alerts", {"flt": "7"}))
        back = c["staff_overdue"] + c["consultant_overdue"]
        if back:
            items.append((f"{back} token(s) are overdue back to the custodian from staff or consultants.",
                          "custody", {"view": "custody", "holder": "internal_overdue"}))
        if c["overdue"]:
            items.append((f"{c['overdue']} token(s) are overdue for return to clients.", "custody",
                          {"view": "custody", "overdue": "Overdue"}))
        awaited = sum(1 for r in self.awaited_list(as_of=as_of) if r["overdue_flag"] == "overdue")
        if awaited:
            items.append((f"{awaited} DSC(s) awaited from clients are past their expected date.", "custody",
                          {"view": "awaited"}))
        days = self.days_since_backup(as_of)
        if days is None:
            items.append(("No backup of the database has been taken yet.", "backup", {}))
        elif days > 7:
            items.append((f"The last backup was {days} days ago.", "backup", {}))
        return items

    def has_sample_data(self):
        return bool(self._scalar("SELECT COUNT(*) FROM clients WHERE is_sample = 1"))

    def remove_sample_data(self):
        """Delete demonstration rows only (all are flagged is_sample = 1)."""
        blockers = self._scalar("""
            SELECT (SELECT COUNT(*) FROM inward WHERE is_sample = 0 AND (client_id IN
                        (SELECT client_id FROM clients WHERE is_sample = 1) OR custodian_id IN
                        (SELECT custodian_id FROM custodians WHERE is_sample = 1)))
                 + (SELECT COUNT(*) FROM outward WHERE is_sample = 0 AND (client_id IN
                        (SELECT client_id FROM clients WHERE is_sample = 1) OR via_consultant_id IN
                        (SELECT consultant_id FROM consultants WHERE is_sample = 1)))
                 + (SELECT COUNT(*) FROM movements WHERE is_sample = 0 AND (custodian_id IN
                        (SELECT custodian_id FROM custodians WHERE is_sample = 1) OR consultant_id IN
                        (SELECT consultant_id FROM consultants WHERE is_sample = 1)))
                 + (SELECT COUNT(*) FROM expected_dscs WHERE is_sample = 0 AND client_id IN
                        (SELECT client_id FROM clients WHERE is_sample = 1))
                 + (SELECT COUNT(*) FROM tokens WHERE is_sample = 0 AND client_id IN
                        (SELECT client_id FROM clients WHERE is_sample = 1))""")
        if blockers:
            raise ValidationError("Real transactions have been recorded against sample clients, custodians or "
                                  "consultants, so sample data cannot be removed automatically.")
        with self.conn:
            self.conn.execute("UPDATE inward SET superseded_by = NULL WHERE is_sample = 1")
            self.conn.execute("UPDATE tokens SET replaced_by = NULL WHERE is_sample = 1")
            self.conn.execute("DELETE FROM token_status_log WHERE is_sample = 1 OR token_id IN "
                              "(SELECT token_id FROM tokens WHERE is_sample = 1)")
            self.conn.execute("UPDATE certificates SET replaced_by = NULL WHERE is_sample = 1")
            for table in ("movements", "outward", "inward", "expected_dscs", "certificates", "tokens", "clients",
                          "consultants", "custodians"):
                self.conn.execute(f"DELETE FROM {table} WHERE is_sample = 1")
