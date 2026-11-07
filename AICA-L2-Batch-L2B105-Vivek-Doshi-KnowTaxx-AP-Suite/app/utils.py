"""Shared helpers: validators, access control, audit logging, formatting, file storage."""
import hashlib
import json
import re
import socket
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

from flask import abort, current_app, request
from flask_login import current_user
from werkzeug.utils import secure_filename

from .models import AuditLog, Client, db, utcnow

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")
_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def valid_pan(pan):
    return bool(pan and PAN_RE.match(pan))


def gstin_check_digit(first_14):
    """GSTN mod-36 check digit for the first 14 characters of a GSTIN."""
    total = 0
    for i, ch in enumerate(first_14):
        product = _B36.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _B36[(36 - total % 36) % 36]


def valid_gstin(gstin):
    if not gstin or not GSTIN_RE.match(gstin):
        return False
    if not 1 <= int(gstin[:2]) <= 38 and gstin[:2] not in ("97", "99"):
        return False
    return gstin_check_digit(gstin[:14]) == gstin[14]


def password_problem(password):
    """Return a message if the password breaks policy, else None."""
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must contain at least one letter and one digit."
    return None


def to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except InvalidOperation:
        return None


def sanitize_cell(value):
    """Stop spreadsheet formula injection from vendor-supplied or OCR text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def inr(value, symbol=True, decimals=2):
    """Format with Indian digit grouping, e.g. ₹12,34,567.00."""
    if value is None or value == "":
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.{decimals}f}".split(".") if decimals else (f"{abs(value):.0f}", "")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    text = whole + ("." + frac if frac else "")
    return f"{sign}{'₹' if symbol else ''}{text}"


def ist(value, fmt="%d %b %Y %H:%M"):
    """Display a stored UTC datetime in IST."""
    if not value:
        return "-"
    return (value + timedelta(hours=5, minutes=30)).strftime(fmt)


def fmt_date(value):
    return value.strftime("%d-%m-%Y") if value else "-"


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def get_client_or_403(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        abort(404)
    if not current_user.can_access_client(client_id):
        abort(403)
    return client


def can_view_invoice(user, invoice):
    if user.role in ("admin", "manager"):
        return True
    if user.role == "accountant":
        return user.can_access_client(invoice.client_id)
    if user.role == "approver":
        return invoice.current_approver_id == user.id or any(l.actor_id == user.id for l in invoice.logs)
    return invoice.uploaded_by == user.id


def audit(action, entity_type=None, entity_id=None, details=None, user_id=None):
    """Add an audit row to the session. The caller's commit persists it."""
    if user_id is None and current_user and current_user.is_authenticated:
        user_id = current_user.id
    has_request = bool(request)
    db.session.add(AuditLog(
        user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id,
        details=json.dumps(details, default=str) if details is not None else None,
        ip_address=request.remote_addr if has_request else None,
        user_agent=(request.user_agent.string or "")[:255] if has_request else None,
        timestamp=utcnow(),
    ))


def next_code(prefix, existing_codes):
    numbers = [int(c[len(prefix):]) for c in existing_codes if c and c[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers) if numbers else 0) + 1:04d}"


def sniff_extension(data):
    """Identify an allowed document from its leading bytes, ignoring its claimed name."""
    if data[:5] == b"%PDF-":
        return ".pdf"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return None


def store_file(data, original_name, client_code, subfolder):
    """Validate and store document bytes. Returns (safe_name, path_relative_to_FILES_ROOT, sha256)."""
    max_bytes = current_app.config["MAX_FILE_BYTES"]
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    ext = sniff_extension(data)
    if ext is None:
        raise ValueError("Only PDF, JPG and PNG files are accepted.")
    stem = Path(secure_filename(original_name or "") or "document").stem[:80] or "document"
    safe_name = stem + ext
    rel_dir = Path(client_code) / subfolder
    if subfolder in ("invoices", "expenses"):
        rel_dir = rel_dir / utcnow().strftime("%Y-%m")
    full_dir = Path(current_app.config["FILES_ROOT"]) / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    (full_dir / stored).write_bytes(data)
    return safe_name, (rel_dir / stored).as_posix(), hashlib.sha256(data).hexdigest()


def absolute_file_path(relative):
    root = Path(current_app.config["FILES_ROOT"]).resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        abort(404)
    return path


def lan_base_url():
    """Base URL other devices can reach: swaps localhost for this machine's LAN IP."""
    base = request.host_url.rstrip("/")
    if request.host.split(":")[0] in ("localhost", "127.0.0.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            port = request.host.split(":")[1] if ":" in request.host else ""
            return f"{request.scheme}://{ip}{':' + port if port else ''}"
        except OSError:
            pass
    return base


def paginate(query, per_page=None):
    per_page = per_page or current_app.config["ITEMS_PER_PAGE"]
    return query.paginate(page=request.args.get("page", 1, type=int), per_page=per_page, error_out=False)
