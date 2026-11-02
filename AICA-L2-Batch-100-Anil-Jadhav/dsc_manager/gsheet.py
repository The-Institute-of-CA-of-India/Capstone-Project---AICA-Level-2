"""Google Sheet for the partners: the reports, one tab each, plus a dashboard.

The custodian's PC sends every report to a Google Sheet so the partners can see
them from their own desks (with Viewer access). The sheet holds a small Google
Apps Script (assets/google_sheet_script.gs) deployed as a web app; the app
posts all the reports to that web app's link as JSON, and the script writes
the tabs, filters and dashboard. One-way: nothing comes back from the sheet.

The link and a secret key (also written into the script) are kept in the
firm's database. PAN and mobile numbers are masked in the sheet.
"""
import json
import secrets
import urllib.error
import urllib.request

from . import config, dates, firm_info
from .database import HOLDER_LABELS

META_URL = "gsheet_url"
META_KEY = "gsheet_key"
META_LAST_OK = "gsheet_last_ok_at"
META_LAST_ERROR = "gsheet_last_error"
TIMEOUT = 60

# Row colours in the sheet, as on screen.
TAG_COLORS = {"red": "#fbe9e7", "orange": "#fdf0e3", "yellow": "#fdf8e1", "green": "#eaf5ee",
              "grey": "#f1f3f5", "cancelled": "#f1f3f5"}

# (key, heading, kind) - kind as in the app's tables: text, date, datetime or num.
CUSTODY = [
    ("client_code", "Client", "text"), ("holder_name", "DSC Holder Name", "text"),
    ("token_serial", "Token Serial", "text"), ("with_label", "Currently With", "text"),
    ("with_since", "Since", "datetime"), ("with_status", "Back to Custodian", "text"),
    ("expiry_date", "Cert Expiry", "datetime"), ("expiry_status", "Certificate Status", "text"),
    ("inward_date", "Inward Date", "date"), ("purpose", "Purpose", "text"), ("received_by", "Received By", "text"),
    ("expected_return_date", "Expected Return", "date"), ("days_in_custody", "Days in Custody", "num"),
    ("custody_status", "Current Custody Status", "text"),
]
AWAITED = [
    ("client_code", "Client", "text"), ("holder_name", "DSC Holder Name", "text"),
    ("firm_name", "Firm/Company", "text"), ("token_serial", "Token Serial", "text"), ("purpose", "Purpose", "text"),
    ("expected_date", "Expected By", "date"), ("await_status", "Status", "text"),
    ("followup_staff", "Follow-up Staff", "text"), ("remarks", "Remarks", "text"),
]
EXPIRY = [
    ("client_code", "Client", "text"), ("holder_name", "DSC Holder Name", "text"),
    ("token_serial", "Token Serial", "text"), ("cert_serial", "Certificate Serial", "text"),
    ("expiry_date", "Expiry", "datetime"), ("days_text", "Days Remaining / Overdue", "text"),
    ("expiry_status", "Expiry Status", "text"), ("admin_status", "Renewal Status", "text"),
    ("custody", "Physical Custody", "text"), ("with_label", "Currently With", "text"),
    ("issuer", "Certifying Authority", "text"), ("followup_text", "Remarks / Follow-up", "text"),
]
INWARD = [
    ("inward_id", "Inward ID", "num"), ("inward_date", "Inward Date", "date"), ("client_code", "Client", "text"),
    ("holder_name", "DSC Holder Name", "text"), ("token_serial", "Token Serial", "text"),
    ("expiry_date", "Cert Expiry", "datetime"), ("purpose", "Purpose", "text"),
    ("received_from", "Received From", "text"), ("received_by", "Received By (Custodian)", "text"),
    ("expected_return_date", "Expected Return", "date"), ("custody", "Status", "text"), ("remarks", "Remarks", "text"),
]
OUTWARD = [
    ("outward_id", "Outward ID", "num"), ("outward_date", "Outward Date", "date"), ("client_code", "Client", "text"),
    ("holder_name", "DSC Holder Name", "text"), ("token_serial", "Token Serial", "text"),
    ("purpose", "Purpose", "text"), ("returned_to", "Returned To", "text"), ("returned_by", "Returned By", "text"),
    ("returned_via", "Returned Via", "text"), ("inward_id", "Inward ID", "num"),
    ("inward_date", "Inward Date", "date"), ("remarks", "Remarks", "text"),
]
MOVEMENTS = [
    ("moved_at", "Date / Time", "datetime"), ("kind_label", "Movement", "text"),
    ("token_serial", "Token Serial", "text"), ("holder_name", "DSC Holder", "text"), ("client_code", "Client", "text"),
    ("from_name", "From", "text"), ("to_name", "To", "text"), ("purpose", "Purpose", "text"),
    ("expected_return", "Due Back", "datetime"), ("remarks", "Remarks", "text"),
]
HOLDINGS = [
    ("role", "Role", "text"), ("name", "Name", "text"), ("token_serial", "Token Serial", "text"),
    ("holder_name", "DSC Holder", "text"), ("client_code", "Client", "text"), ("with_since", "Since", "datetime"),
    ("with_due", "Due Back", "datetime"), ("with_purpose", "Purpose", "text"),
    ("with_status", "Back to Custodian", "text"), ("expiry_status", "Certificate", "text"),
]
# The two short lists on the dashboard.
OUT_NOW = [
    ("role", "Role", "text"), ("name", "Name", "text"), ("holder_name", "DSC Holder", "text"),
    ("client_code", "Client", "text"), ("with_due", "Due Back", "datetime"),
    ("with_status", "Back to Custodian", "text"),
]
EXPIRING = [
    ("holder_name", "DSC Holder Name", "text"), ("token_serial", "Token Serial", "text"),
    ("expiry_date", "Expiry", "datetime"), ("days_text", "Days Remaining", "text"),
    ("custody", "Physical Custody", "text"), ("with_label", "Currently With", "text"),
]
CLIENTS = [
    ("client_code", "Client ID", "text"), ("holder_name", "DSC Holder Name", "text"),
    ("firm_name", "Firm/Company Name", "text"), ("pan", "PAN (masked)", "text"), ("mobile", "Mobile (masked)", "text"),
    ("email", "Email", "text"), ("status", "Status", "text"), ("token_count", "Tokens", "num"),
    ("in_custody", "In Custody", "num"), ("remarks", "Remarks", "text"),
]


def mask_pan(pan):
    """ABCPX1234F -> ABCPX****F: enough to recognise the client, not enough to use."""
    pan = (pan or "").strip().upper()
    return pan[:5] + "****" + pan[9:] if len(pan) == 10 else ("*" * len(pan))


def mask_mobile(mobile):
    """9876543210 -> 98XXXXXX10."""
    digits = "".join(ch for ch in (mobile or "") if ch.isdigit())
    if len(digits) < 4:
        return "X" * len(digits)
    return digits[:2] + "X" * (len(digits) - 4) + digits[-2:]


def _cell(row, key, kind):
    v = row.get(key)
    if v is None:
        return ""
    if kind == "num" and isinstance(v, (int, float)):
        return v
    if kind in ("date", "datetime"):
        # Sent as YYYY-MM-DD [HH:MM] so the sheet stores real dates (sortable); the script formats them
        # as DD-MM-YYYY, with the time only where one is recorded.
        v = str(v).replace("T", " ")
        return v[:10] if kind == "date" else v[:16]
    return str(v)


def _custody_tag(r):
    if r.get("internal_overdue"):
        return "red"
    return {"overdue": "red", "soon": "orange", "ok": "green"}.get(r.get("overdue_flag"))


def _expiry_tag(r):
    d = r.get("days")
    if r.get("admin_status") in ("Revoked", "Inactive") or r.get("token_status") == "Inactive":
        return "grey"
    if d is None:
        return "grey"
    if r.get("expiry_status") == "Expired":
        return "red"
    return "orange" if d <= 7 else ("yellow" if d <= 30 else "green")


def _tab(name, title, columns, rows, tag=None):
    return {"name": name, "title": title, "headings": [c[1] for c in columns], "kinds": [c[2] for c in columns],
            "rows": [[_cell(r, k, kind) for k, _, kind in columns] for r in rows],
            "colors": [TAG_COLORS.get(tag(r), "") if tag else "" for r in rows]}


def build_payload(db, key="", as_of=None):
    """Everything the sheet shows, as one JSON-ready dict."""
    now = dates.iso_to_datetime(as_of) if as_of else dates.now()
    custody = db.custody_register(as_of=now)
    alerts = db.expiry_alerts("all", as_of=now)
    holdings = sorted(custody, key=lambda r: ({"custodian": 0, "staff": 1, "consultant": 2}[r["with_type"]],
                                              (r["with_name"] or "").lower()))
    for r in holdings:
        r["role"], r["name"] = HOLDER_LABELS[r["with_type"]], r["with_name"]
    clients = [dict(c, pan=mask_pan(c["pan"]), mobile=mask_mobile(c["mobile"]))
               for c in db.list_clients(status="All")]
    c = db.dashboard_counts(as_of=now)
    out_now = [r for r in holdings if r["with_type"] != "custodian"]
    soon = sorted((r for r in alerts if r["token_status"] == "Active" and r["days"] is not None
                   and r["expiry_status"] != "Expired" and r["days"] <= 30), key=lambda r: r["days"])
    return {
        "key": key,
        "firm": firm_info.FIRM_NAME,
        "address": firm_info.address_lines(),
        "updated": dates.to_display_dt(now.strftime("%Y-%m-%d %H:%M")),
        "dashboard": {
            "cards": [
                ["DSC in custody", c["custody"], "tokens the firm holds now"],
                ["With the custodian", c["with_custodian"], ""],
                ["With staff", c["with_staff"], f"{c['staff_overdue']} late back" if c["staff_overdue"] else "",
                 c["staff_overdue"] > 0],
                ["With consultants", c["with_consultant"],
                 f"{c['consultant_overdue']} late back" if c["consultant_overdue"] else "", c["consultant_overdue"] > 0],
                ["Overdue to clients", c["overdue"], "past the expected return date", c["overdue"] > 0],
                ["DSC awaited from clients", c["awaited"], ""],
                ["Expired (still active)", c["exp_expired"], "", c["exp_expired"] > 0],
                ["Expiring within 7 days", c["exp_7"], "", c["exp_7"] > 0],
                ["Expiring within 15 days", c["exp_15"], ""],
                ["Expiring within 30 days", c["exp_30"], ""],
                ["Expiry date unknown", c["exp_unknown"], ""],
            ],
            "holders": [["Custodian", c["with_custodian"]], ["Staff", c["with_staff"]],
                        ["Consultants", c["with_consultant"]]],
            "out_now": _tab("", "Tokens out with staff and consultants", OUT_NOW, out_now, _custody_tag),
            "expiring": _tab("", "Certificates expiring in the next 30 days", EXPIRING, soon, _expiry_tag),
        },
        "tabs": [
            _tab("DSC in Custody", "DSC in Custody - who holds each token now", CUSTODY, custody, _custody_tag),
            _tab("DSC Awaited", "DSC Awaited from Clients", AWAITED, db.awaited_list(as_of=now),
                 lambda r: {"overdue": "red", "soon": "orange", "ok": "green"}.get(r.get("overdue_flag"))),
            _tab("Expiry Alerts", "Expiry Alerts - certificate validity of every token", EXPIRY, alerts, _expiry_tag),
            _tab("Inward Register", "DSC Inward Register", INWARD, db.inward_register()),
            _tab("Outward Register", "DSC Outward Register", OUTWARD, db.outward_register()),
            _tab("Movement Register", "Movement Register (staff and consultants)", MOVEMENTS, db.movement_register()),
            _tab("Holdings by Person", "Holdings by Person - what each person holds now", HOLDINGS, holdings,
                 _custody_tag),
            _tab("Clients", "Clients (PAN and mobile masked)", CLIENTS, clients),
        ],
    }


# ---------------------------------------------------------------- settings kept in the firm's database
def get_url(db):
    return (db.get_meta(META_URL) or "").strip()


def set_url(db, url):
    url = (url or "").strip()
    if url and not url.startswith("https://script.google.com/"):
        raise ValueError("The link should start with https://script.google.com/ - copy the 'Web app' URL "
                         "shown after deploying the script.")
    db.set_meta(META_URL, url)


def get_key(db):
    """The secret key the script checks, made the first time it is needed."""
    key = db.get_meta(META_KEY)
    if not key:
        key = secrets.token_urlsafe(18)
        db.set_meta(META_KEY, key)
    return key


def script_text(db):
    """The Apps Script to paste into the Google Sheet, with this firm's key written in."""
    with open(config.asset("google_sheet_script.gs"), encoding="utf-8") as fh:
        return fh.read().replace("PUT-KEY-HERE", get_key(db))


def status(db):
    return {"url": get_url(db), "last_ok": db.get_meta(META_LAST_OK) or "",
            "last_error": db.get_meta(META_LAST_ERROR) or ""}


# ---------------------------------------------------------------- sending
def post(url, payload, timeout=TIMEOUT):
    """Send the payload to the sheet's web app. Returns the script's reply; raises RuntimeError with a
    plain-English message if the sheet could not be updated. Safe to call from a background thread."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "text/plain; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # Google redirects to the reply
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google refused the request (HTTP {exc.code}). Check that the script is deployed "
                           "as a web app with access for 'Anyone'.") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Could not reach Google - no internet? ({getattr(exc, 'reason', exc)})") from exc
    try:
        reply = json.loads(body)
    except ValueError:
        raise RuntimeError("The link did not answer like the DSC Manager script. Check the link, and that "
                           "the script was deployed as a web app.") from None
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error") or "The sheet did not accept the update.")
    return reply


def record_result(db, error=None):
    """Remember the outcome for the Settings screen (main thread only - the database)."""
    if error:
        db.set_meta(META_LAST_ERROR, f"{dates.to_display_dt(dates.now_iso())}: {error}")
    else:
        db.set_meta(META_LAST_OK, dates.now_iso())
        db.set_meta(META_LAST_ERROR, "")
