"""Background IMAP poller: turns emailed invoices into Invoice records."""
import email
import imaplib
import logging
import re
import threading
import time
from datetime import timedelta
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr

from sqlalchemy.exc import SQLAlchemyError

from ..invoices.service import ingest_file
from ..models import Client, EmailConfig, Vendor, db, utcnow
from ..utils import audit
from .config import (ALLOWED_ATTACHMENT_SUFFIXES, IMAP_TIMEOUT_SECONDS, MAX_MESSAGES_PER_POLL, POLL_TICK_SECONDS,
                     PUBLIC_MAIL_DOMAINS, decrypt_password)

log = logging.getLogger("ktap.email")
_started = False


def _decode(value):
    try:
        return str(make_header(decode_header(value or "")))
    except (LookupError, ValueError):
        return value or ""


def connect(server, port, address, password):
    connection = imaplib.IMAP4_SSL(server, int(port or 993), timeout=IMAP_TIMEOUT_SECONDS)
    connection.login(address, password)
    return connection


def test_connection(server, port, address, password):
    """Returns (ok, message) for the admin 'Test connection' button."""
    try:
        connection = connect(server, port, address, password)
        status, data = connection.select("INBOX", readonly=True)
        connection.logout()
        return True, f"Connected. INBOX holds {int(data[0])} message(s)." if status == "OK" else "Connected, but INBOX could not be opened."
    except (imaplib.IMAP4.error, OSError) as exc:
        return False, f"Connection failed: {exc}"


def resolve_client(message, default_client):
    """Plus-address tag (knowtaxxap+c0001@gmail.com) or alias local part decides the client."""
    headers = []
    for name in ("Delivered-To", "X-Original-To", "To", "Cc"):
        headers.extend(message.get_all(name, []))
    for _, address in getaddresses(headers):
        local = address.split("@")[0].lower()
        tag = local.split("+", 1)[1] if "+" in local else local
        client = Client.query.filter_by(email_alias=tag, is_archived=False).first()
        if client:
            return client
    return default_client


def match_sender(client_id, sender_address):
    """Vendor with this exact contact email, else the same non-public email domain."""
    address = (sender_address or "").lower()
    if "@" not in address:
        return None
    vendors = Vendor.query.filter(Vendor.client_id == client_id, Vendor.status != "archived", Vendor.contact_email.isnot(None)).all()
    exact = next((v for v in vendors if (v.contact_email or "").lower() == address), None)
    if exact:
        return exact
    domain = address.split("@")[1]
    if domain in PUBLIC_MAIL_DOMAINS:
        return None
    return next((v for v in vendors if (v.contact_email or "").lower().endswith("@" + domain)), None)


def iter_attachments(message):
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = _decode(part.get_filename() or "")
        if filename and filename.lower().endswith(ALLOWED_ATTACHMENT_SUFFIXES):
            payload = part.get_payload(decode=True)
            if payload:
                yield filename, payload


def process_message(raw_bytes, default_client):
    """Create invoices from one email. Returns how many were created. The caller commits."""
    message = email.message_from_bytes(raw_bytes)
    client = resolve_client(message, default_client)
    sender_name, sender_address = parseaddr(message.get("From", ""))
    meta = {"subject": _decode(message.get("Subject")), "from": sender_address or sender_name, "date": message.get("Date", "")}
    created = 0
    for filename, payload in iter_attachments(message):
        try:
            invoice = ingest_file(client, payload, filename, source="email", email_meta=meta)
        except ValueError as exc:
            log.warning("Skipped attachment %s: %s", re.sub(r"[\r\n]", " ", filename), exc)
            continue
        if invoice.vendor_id is None:
            vendor = match_sender(client.id, sender_address)
            if vendor:
                invoice.vendor_id = vendor.id
        audit("upload", "invoice", invoice.id, {"source": "email", "from": meta["from"], "subject": meta["subject"]})
        created += 1
    return created


def poll_mailbox(config):
    """Read unread mail, ingest it and mark it read. Mail is marked read only after a successful commit."""
    password = decrypt_password(config.email_password_encrypted)
    if not password:
        raise ValueError("The stored password cannot be decrypted. Please re-enter it.")
    connection = connect(config.imap_server, config.imap_port, config.email_address, password)
    total = 0
    try:
        connection.select("INBOX")
        status, data = connection.search(None, "UNSEEN")
        if status != "OK":
            raise imaplib.IMAP4.error("UNSEEN search failed")
        for number in data[0].split()[:MAX_MESSAGES_PER_POLL]:
            status, parts = connection.fetch(number, "(BODY.PEEK[])")  # PEEK leaves it unread for now
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            total += process_message(parts[0][1], config.client)
            db.session.commit()
            connection.store(number, "+FLAGS", "\\Seen")
    finally:
        try:
            connection.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
    return total


def _is_due(config, now):
    return config.last_poll_at is None or now - config.last_poll_at >= timedelta(minutes=config.poll_interval_minutes or 5)


def poll_due_mailboxes():
    now = utcnow()
    for config in EmailConfig.query.filter_by(is_active=True).all():
        if not _is_due(config, now):
            continue
        try:
            count = poll_mailbox(config)
            config.last_error = None
            if count:
                log.info("Client %s: %s invoice(s) captured from email", config.client.code, count)
        except (imaplib.IMAP4.error, OSError, ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            log.warning("Email poll failed for client %s: %s", config.client.code, exc)
            config.last_error = str(exc)[:500]
        config.last_poll_at = utcnow()
        db.session.commit()


def _loop(app):
    while True:
        time.sleep(POLL_TICK_SECONDS)
        with app.app_context():
            try:
                poll_due_mailboxes()
            except Exception:  # the thread must outlive any single bad poll
                log.exception("Email listener tick failed")
                db.session.rollback()
            finally:
                db.session.remove()


def start_listener(app):
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, args=(app,), name="ktap-email-listener", daemon=True).start()
