"""Email connection settings: password encryption and the listener's constants."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

POLL_TICK_SECONDS = 30       # how often the thread checks whether a mailbox is due
IMAP_TIMEOUT_SECONDS = 30
MAX_MESSAGES_PER_POLL = 50
ALLOWED_ATTACHMENT_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png")
# Sender domains shared by unrelated businesses: never used to identify a vendor.
PUBLIC_MAIL_DOMAINS = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "icloud.com"}


def _fernet():
    digest = hashlib.sha256(("email-config:" + current_app.config["SECRET_KEY"]).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_password(plain):
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_password(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, AttributeError):
        return None
