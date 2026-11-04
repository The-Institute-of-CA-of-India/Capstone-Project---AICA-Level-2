"""First-run registration of the licensee and the administrator.

Licence checking comes later; for now the licence number is stored and "valid upto" is one
year from registration (to be replaced by the date in the licence).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import date, datetime

FIELDS = [  # key, label, required
    ("name", "Name", True), ("organisation", "Name of Organisation", False), ("email", "Email Address", True),
    ("mobile", "Mobile No.", True), ("whatsapp", "WhatsApp No.", False), ("city", "City", True),
    ("pin", "PIN", False), ("state", "State", False), ("country", "Country", True),
    ("admin_name", "Name of Administrator", True), ("admin_user", "User Id of Administrator", True),
    ("licence_no", "Licence No.", False),
]
SCHEMA = "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);"


def load(store) -> dict:
    store.db.executescript(SCHEMA)
    r = store.db.execute("SELECT value FROM app_settings WHERE key='registration'").fetchone()
    return json.loads(r["value"]) if r else {}


def registered(store) -> bool:
    return bool(load(store).get("name"))


def _hash(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def check_password(store, pw: str) -> bool:
    h = load(store).get("admin_pw", "")
    try:
        _, salt, dk = h.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(_hash(pw, base64.b64decode(salt)), h)


def validate(data: dict, password: str | None, confirm: str | None, new: bool) -> list[str]:
    errs = []
    for key, label, req in FIELDS:
        if req and not (data.get(key) or "").strip():
            errs.append(f"{label} is required")
    e = (data.get("email") or "").strip()
    if e and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", e):
        errs.append("Email Address is not valid")
    for key, label in (("mobile", "Mobile No."), ("whatsapp", "WhatsApp No.")):
        v = re.sub(r"[\s()+-]", "", data.get(key) or "")
        if v and not re.fullmatch(r"\d{10,13}", v):
            errs.append(f"{label} should have 10 to 13 digits")
    pin = (data.get("pin") or "").strip()
    if pin and (data.get("country") or "").strip().lower() in ("india", "in") and not re.fullmatch(r"\d{6}", pin):
        errs.append("PIN should have 6 digits")
    if new or password:
        if len(password or "") < 6:
            errs.append("Password of the Administrator should have at least 6 characters")
        elif password != confirm:
            errs.append("The two passwords do not match")
    return errs


def save(store, data: dict, password: str | None):
    old = load(store)
    rec = {k: (data.get(k) or "").strip() for k, _, _ in FIELDS}
    rec["registered_at"] = old.get("registered_at") or datetime.now().isoformat(timespec="seconds")
    if not old.get("valid_upto"):
        d = date.today()
        try:
            rec["valid_upto"] = d.replace(year=d.year + 1).isoformat()
        except ValueError:
            rec["valid_upto"] = d.replace(year=d.year + 1, day=28).isoformat()
    else:
        rec["valid_upto"] = old["valid_upto"]
    rec["admin_pw"] = _hash(password) if password else old.get("admin_pw", "")
    store.db.executescript(SCHEMA)
    store.db.execute("INSERT OR REPLACE INTO app_settings VALUES ('registration', ?)", (json.dumps(rec),))
    store.db.commit()
    store.log(rec["organisation"] or rec["name"], "Registration saved", f"licence {rec['licence_no'] or '(not yet)'}")


def licensee(store) -> tuple[str, str]:
    """(licensee name, valid upto as DD MMM YYYY)"""
    r = load(store)
    if not r:
        return "", ""
    vu = r.get("valid_upto", "")
    try:
        vu = date.fromisoformat(vu).strftime("%d %b %Y")
    except ValueError:
        pass
    return r.get("organisation") or r.get("name", ""), vu


# --------------------------------------------------------------------------- administrator password and users

USERS = "CREATE TABLE IF NOT EXISTS app_users (user_id TEXT PRIMARY KEY, name TEXT, role TEXT, pw TEXT, created_at TEXT);"
ROLES = ["Accountant", "Data entry", "Viewer"]


def change_admin_password(store, current: str, new: str, confirm: str) -> None:
    if not check_password(store, current):
        raise ValueError("the present password of the Administrator is not correct")
    if len(new or "") < 6:
        raise ValueError("the new password should have at least 6 characters")
    if new != confirm:
        raise ValueError("the two new passwords do not match")
    rec = load(store)
    rec["admin_pw"] = _hash(new)
    store.db.execute("INSERT OR REPLACE INTO app_settings VALUES ('registration', ?)", (json.dumps(rec),))
    store.db.commit()
    store.log(rec.get("admin_user", "Administrator"), "Administrator password changed", "")


def users(store) -> list[dict]:
    store.db.executescript(USERS)
    return [dict(r) for r in store.query("SELECT user_id, name, role, created_at FROM app_users ORDER BY name")]


def save_user(store, user_id: str, name: str, role: str, password: str | None, new: bool) -> None:
    store.db.executescript(USERS)
    user_id, name = (user_id or "").strip(), (name or "").strip()
    if not user_id or not name:
        raise ValueError("name and user id are both needed")
    if user_id.lower() == (load(store).get("admin_user") or "").lower():
        raise ValueError("this user id belongs to the Administrator")
    exists = store.query("SELECT 1 FROM app_users WHERE user_id=?", (user_id,))
    if new and exists:
        raise ValueError(f"user id '{user_id}' already exists")
    if new and len(password or "") < 6:
        raise ValueError("the password should have at least 6 characters")
    if password and len(password) < 6:
        raise ValueError("the password should have at least 6 characters")
    pw = _hash(password) if password else (store.query("SELECT pw FROM app_users WHERE user_id=?", (user_id,))
                                            or [{"pw": ""}])[0]["pw"]
    store.db.execute("INSERT OR REPLACE INTO app_users VALUES (?,?,?,?,COALESCE((SELECT created_at FROM app_users "
                     "WHERE user_id=?), ?))", (user_id, name, role, pw, user_id,
                                               datetime.now().isoformat(timespec="seconds")))
    store.db.commit()
    store.log(user_id, "User added" if new else "User changed", f"{name}, {role}")


def delete_user(store, user_id: str) -> None:
    store.db.executescript(USERS)
    store.db.execute("DELETE FROM app_users WHERE user_id=?", (user_id,))
    store.db.commit()
    store.log(user_id, "User deleted", "")
