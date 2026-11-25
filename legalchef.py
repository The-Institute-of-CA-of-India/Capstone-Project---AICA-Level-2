"""LegalChef Work Organiser. Run with Python 3.10+ or the bundled executable."""
import argparse
import base64
import hashlib
import hmac
import secrets
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template_string, request, send_file, session, url_for
from waitress import serve

SERVICES = ("Income tax", "GST", "Appeals", "Bookkeeping", "Other")
STATUSES = ("Open", "Running", "Ready for review", "Completed")
ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
DB = ROOT / "LegalChef Data" / "legalchef.sqlite3"
app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=64_000, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(hours=10))

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
 password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 version INTEGER NOT NULL DEFAULT 1, temporary INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clients (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS client_services (
 client INTEGER REFERENCES clients(id), service TEXT NOT NULL, PRIMARY KEY(client, service)
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, client INTEGER NOT NULL REFERENCES clients(id), service TEXT NOT NULL,
 title TEXT NOT NULL, details TEXT NOT NULL, assignee INTEGER REFERENCES users(id),
 due TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Open',
 urgent INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY, task INTEGER NOT NULL REFERENCES tasks(id), actor INTEGER NOT NULL REFERENCES users(id),
 message TEXT NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

def connect(path):
    conn = sqlite3.connect(path, timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init(path):
    global DB
    DB = Path(path)
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(DB)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        with conn:
            conn.execute("INSERT OR IGNORE INTO config VALUES ('secret', ?)", (secrets.token_hex(32),))
        app.secret_key = conn.execute("SELECT value FROM config WHERE key='secret'").fetchone()[0]
    finally:
        conn.close()

def db():
    if "db" not in g:
        g.db = connect(DB)
    return g.db

@app.teardown_appcontext
def close_db(error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()

def password_matches(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(":")[0]), stored)

def field(name, limit=200, required=False):
    value = request.form.get(name, "").strip()
    if len(value) > limit or (required and not value):
        raise ValueError(f"Enter a valid {name.replace('_', ' ')} (up to {limit} characters).")
    return value

def new_password():
    value = request.form.get("password", "")
    if not 12 <= len(value) <= 128:
        raise ValueError("Use a password of 12 to 128 characters.")
    return hash_password(value)

def number(name, default=0):
    return int(request.form.get(name) or default)

def one(sql, params=()):
    return db().execute(sql, params).fetchone()

def query(sql, params=()):
    return db().execute(sql, params).fetchall()

@app.before_request
def prepare():
    g.user = one("SELECT * FROM users WHERE id=? AND active=1 AND version=?",
                 (session.get("user"), session.get("version")))
    if request.method == "POST":
        expected = session.get("csrf", "")
        if not expected or not hmac.compare_digest(expected.encode(), request.form.get("csrf", "").encode()):
            abort(400, "This form expired. Reload the page and try again.")
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    g.admin = bool(g.user and g.user["role"] == "admin")
    if request.endpoint in {"login", "logo", "setup"}:
        return
    if not g.user:
        return redirect(url_for("login"))
    if g.user["temporary"] and request.endpoint not in {"password", "logout"}:
        return redirect(url_for("password"))

@app.after_request
def headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    return response

def require_admin():
    if not g.admin:
        abort(403)

def create_user(role, *, temporary=False):
    name = field("name", 100, True)
    username = field("username", 60, True)
    if not all(c.isalnum() or c in "._-" for c in username):
        raise ValueError("Use letters, numbers, dots, hyphens or underscores in the username.")
    db().execute("INSERT INTO users(username,name,password,role,temporary) VALUES (?,?,?,?,?)",
                 (username, name, new_password(), role, int(temporary)))

def sign_in(user):
    session.clear()
    session.permanent = True
    session.update(user=user["id"], version=user["version"])

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if one("SELECT id FROM users LIMIT 1"):
        return redirect(url_for("login"))
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(403, "Open http://127.0.0.1 on the server to create the super admin.")
    if request.method == "POST":
        try:
            db().execute("BEGIN IMMEDIATE")
            if not one("SELECT id FROM users LIMIT 1"):
                create_user("admin")
            db().commit()
            return redirect(url_for("login"))
        except (ValueError, sqlite3.IntegrityError) as error:
            db().rollback()
            flash(str(error), "error")
    return page("Set up LegalChef", AUTH, mode="setup")

@app.route("/login", methods=["GET", "POST"])
def login():
    if not one("SELECT id FROM users LIMIT 1"):
        return redirect(url_for("setup"))
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")[:60].strip()
        password = request.form.get("password", "")
        user = one("SELECT * FROM users WHERE username=? AND active=1", (username,))
        if len(password) <= 128 and password_matches(password, user["password"] if user else DUMMY_PASSWORD) and user:
            sign_in(user)
            return redirect(url_for("dashboard"))
        flash("Check your username and password.", "error")
    return page("Sign in", AUTH, mode="login")

DUMMY_PASSWORD = hash_password(secrets.token_hex(16))

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/password", methods=["GET", "POST"])
def password():
    if request.method == "POST":
        try:
            current = request.form.get("current", "")
            if len(current) > 128 or not password_matches(current, g.user["password"]):
                raise ValueError("The current password is incorrect.")
            with db():
                result = db().execute("UPDATE users SET password=?,temporary=0,version=version+1 WHERE id=? AND version=?",
                                      (new_password(), g.user["id"], g.user["version"]))
                if not result.rowcount:
                    raise ValueError("Your account changed. Sign in again.")
            sign_in(one("SELECT * FROM users WHERE id=?", (g.user["id"],)))
            flash("Password updated.")
            return redirect(url_for("dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    return page("Change password", AUTH, mode="password")

TASK_SELECT = """SELECT t.*, c.name AS client_name, u.name AS staff_name
FROM tasks t JOIN clients c ON c.id=t.client LEFT JOIN users u ON u.id=t.assignee"""

def scope():
    return ("1=1", ()) if g.admin else ("t.assignee=?", (g.user["id"],))

@app.get("/")
def dashboard():
    service = request.args.get("service", "")
    state = request.args.get("state", "")
    search = request.args.get("q", "").strip()[:100]
    if service and service not in SERVICES:
        abort(404)
    where, params = scope()
    if service:
        where += " AND t.service=?"
        params += (service,)
    tasks = query(TASK_SELECT + " WHERE " + where +
                  " ORDER BY t.urgent DESC, t.status='Completed', t.due='', t.due, t.id DESC", params)
    today = date.today().isoformat()
    def overdue(task):
        return bool(task["due"] and task["due"] < today and task["status"] != "Completed")
    counts = {status: sum(t["status"] == status for t in tasks) for status in STATUSES}
    counts["Overdue"] = sum(overdue(t) for t in tasks)
    counts["Flagged"] = sum(t["urgent"] and t["status"] != "Completed" for t in tasks)
    tasks = [t for t in tasks if (not state or t["status"] == state or
             (state == "Overdue" and overdue(t)) or
             (state == "Flagged" and t["urgent"] and t["status"] != "Completed"))
             and search.casefold() in f'{t["title"]} {t["client_name"]} {t["staff_name"] or ""}'.casefold()]
    clients = []
    if service:
        if g.admin:
            clients = query("SELECT c.* FROM clients c JOIN client_services s ON s.client=c.id WHERE s.service=? ORDER BY c.name", (service,))
        else:
            clients = query("SELECT DISTINCT c.* FROM clients c JOIN tasks t ON t.client=c.id WHERE t.service=? AND t.assignee=? ORDER BY c.name",
                            (service, g.user["id"]))
    return page(service or "Overview", DASHBOARD, tasks=tasks, clients=clients, counts=counts,
                service=service, state=state, search=search, overdue=overdue)

@app.route("/clients", methods=["GET", "POST"])
def clients():
    require_admin()
    client_id = request.args.get("edit", 0, type=int)
    editing = one("SELECT * FROM clients WHERE id=?", (client_id,)) if client_id else None
    if client_id and not editing:
        abort(404)
    if request.method == "POST":
        try:
            name = field("name", 150, True)
            contact = field("contact", 200)
            services = set(request.form.getlist("services"))
            if not services or not services.issubset(SERVICES):
                raise ValueError("Select at least one service.")
            db().execute("BEGIN IMMEDIATE")
            if editing:
                existing = {row["service"] for row in query("SELECT DISTINCT service FROM tasks WHERE client=?", (client_id,))}
                if existing - services:
                    raise ValueError("Keep services that already have tasks attached.")
                db().execute("UPDATE clients SET name=?,contact=? WHERE id=?", (name, contact, client_id))
                db().execute("DELETE FROM client_services WHERE client=?", (client_id,))
            else:
                client_id = db().execute("INSERT INTO clients(name,contact) VALUES(?,?)", (name, contact)).lastrowid
            db().executemany("INSERT INTO client_services VALUES (?,?)",
                             [(client_id, service) for service in services])
            db().commit()
            flash("Client saved.")
            return redirect(url_for("clients"))
        except ValueError as error:
            db().rollback()
            flash(str(error), "error")
    records = query("""SELECT c.*, group_concat(s.service, ' · ') AS services
                     FROM clients c JOIN client_services s ON s.client=c.id GROUP BY c.id ORDER BY c.name""")
    selected = {row["service"] for row in query("SELECT service FROM client_services WHERE client=?", (client_id,))}
    return page("Clients", CLIENTS, records=records, editing=editing, selected=selected)

@app.route("/staff", methods=["GET", "POST"])
def staff():
    require_admin()
    if request.method == "POST":
        try:
            with db():
                action = request.form.get("action")
                if action == "add":
                    create_user("staff", temporary=True)
                elif action == "add_admin":
                    create_user("admin", temporary=True)
                elif action == "reset":
                    result = db().execute("UPDATE users SET password=?,temporary=1,version=version+1 WHERE id=? AND role='staff'",
                                          (new_password(), number("user")))
                    if not result.rowcount:
                        abort(404)
                elif action == "toggle":
                    result = db().execute("UPDATE users SET active=1-active,version=version+1 WHERE id=? AND role='staff'", (number("user"),))
                    if not result.rowcount:
                        abort(404)
                else:
                    abort(400)
            flash("Super admin added. They will choose a new password when they sign in."
                  if action == "add_admin" else "Staff account updated.")
            return redirect(url_for("staff"))
        except ValueError as error:
            flash(str(error), "error")
        except sqlite3.IntegrityError:
            flash("That username is already in use.", "error")
    return page("Staff & super admins", STAFF,
                staff=query("SELECT * FROM users WHERE role='staff' ORDER BY name"),
                admins=query("SELECT id, name, username FROM users WHERE role='admin' ORDER BY name"))

def log(task_id, message):
    db().execute("INSERT INTO activity(task,actor,message) VALUES (?,?,?)",
                 (task_id, g.user["id"], message))

@app.route("/task/new", methods=["GET", "POST"])
def new_task():
    require_admin()
    if request.method == "POST":
        try:
            client, service = field("client_service", 50, True).split("|", 1)
            client_id = int(client)
            title, details, assignee, due = task_fields()
            db().execute("BEGIN IMMEDIATE")
            if not one("SELECT 1 FROM client_services WHERE client=? AND service=?", (client_id, service)):
                raise ValueError("Choose a service listed for the client.")
            check_assignee(assignee)
            task_id = db().execute("""INSERT INTO tasks(client,service,title,details,assignee,due)
                                   VALUES (?,?,?,?,?,?)""", (client_id, service, title, details, assignee, due)).lastrowid
            log(task_id, "Task created")
            db().commit()
            return redirect(url_for("task", task_id=task_id))
        except ValueError as error:
            db().rollback()
            flash(str(error), "error")
    choices = query("""SELECT c.id,c.name,s.service FROM clients c JOIN client_services s ON s.client=c.id
                     ORDER BY c.name,s.service""")
    return page("New task", NEW_TASK, choices=choices, employees=employees(),
                chosen_client=request.args.get("client", 0, type=int),
                chosen_service=request.args.get("service", ""))

def task_fields():
    title = field("title", 160, True)
    details = field("details", 4000)
    assignee = number("assignee") or None
    due = field("due", 10)
    if due:
        try:
            if date.fromisoformat(due).isoformat() != due:
                raise ValueError
        except ValueError:
            raise ValueError("Enter a valid due date.") from None
    return title, details, assignee, due

def check_assignee(assignee, previous=None):
    if assignee and assignee != previous and not one("SELECT 1 FROM users WHERE id=? AND role='staff' AND active=1", (assignee,)):
        raise ValueError("Choose an active member of staff.")

def employees():
    return query("SELECT id,name,active FROM users WHERE role='staff' ORDER BY name")

@app.route("/task/<int:task_id>", methods=["GET", "POST"])
def task(task_id):
    where, params = scope()
    item = one(TASK_SELECT + " WHERE t.id=? AND " + where, (task_id, *params))
    if not item:
        abort(404)
    if request.method == "POST":
        try:
            status = field("status", 30, True)
            if status not in STATUSES:
                raise ValueError("Choose a valid status.")
            urgent = int(request.form.get("urgent") == "yes")
            note = field("note", 2000)
            submitted_version = number("version")
            fields = task_fields() if g.admin else tuple(item[key] for key in ("title", "details", "assignee", "due"))
            title, details, assignee, due = fields
            db().execute("BEGIN IMMEDIATE")
            if g.admin:
                check_assignee(assignee, item["assignee"])
            result = db().execute(
                """UPDATE tasks SET status=?,urgent=?,title=?,details=?,assignee=?,due=?,version=version+1
                   WHERE id=? AND version=? AND """ + ("1=1" if g.admin else "assignee=?"),
                (status, urgent, title, details, assignee, due, task_id, submitted_version, *params))
            if not result.rowcount or item["version"] != submitted_version:
                raise ValueError("Someone changed this task. Reload it before saving your update.")
            updates = []
            if status != item["status"]:
                updates.append(f'Status changed to {status}')
            if urgent != item["urgent"]:
                updates.append("Red flag added" if urgent else "Red flag cleared")
            if fields != tuple(item[key] for key in ("title", "details", "assignee", "due")):
                updates.append("Task details updated")
            for message in updates + ([note] if note else []):
                log(task_id, message)
            db().commit()
            flash("Task saved.")
            return redirect(url_for("task", task_id=task_id))
        except ValueError as error:
            db().rollback()
            flash(str(error), "error")
    history = query("""SELECT a.*,u.name FROM activity a JOIN users u ON u.id=a.actor
                     WHERE a.task=? ORDER BY a.id DESC""", (task_id,))
    return page(item["title"], TASK, item=item, history=history, employees=employees() if g.admin else [])

@app.get("/backup")
def backup():
    require_admin()
    from io import BytesIO
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(dir=DB.parent) as folder:
        snapshot = Path(folder) / "backup.sqlite3"
        destination = sqlite3.connect(snapshot)
        try:
            db().backup(destination)
            destination.execute("UPDATE config SET value=? WHERE key='secret'", (secrets.token_hex(32),))
            destination.commit()
        finally:
            destination.close()
        data = BytesIO(snapshot.read_bytes())
    return send_file(data, as_attachment=True, download_name=f"LegalChef-{date.today()}.sqlite3")

@app.get("/logo")
def logo():
    from io import BytesIO
    return send_file(BytesIO(base64.b64decode(LOGO)), mimetype="image/png")


BASE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} · LegalChef</title><style>
:root{color-scheme:dark;--gold:#e8cb81;--line:#3b3428;--muted:#c0b8a9}*{box-sizing:border-box}body{margin:0;background:#121212;color:#f8f1e3;font:15px/1.5 system-ui,sans-serif}
a{color:var(--gold);text-decoration:none}a:hover{text-decoration:underline}:focus-visible{outline:2px solid var(--gold);outline-offset:3px}
.shell{display:grid;grid-template-columns:230px minmax(0,1fr);min-height:100vh}aside{padding:25px 17px;display:flex;flex-direction:column;background:#181717;border-right:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:25px}.brand img{width:51px;border-radius:7px}.brand strong{display:block;font:24px Georgia,serif}small,.muted{color:var(--muted)}
nav{display:grid;gap:3px}nav a{padding:8px 11px;border-radius:7px;color:#e8dfcf}nav a:hover,nav a.current{background:#342b1d;color:var(--gold)}nav small{margin:10px 11px 2px}.account{margin-top:auto;padding:18px 10px 0}
main{padding:37px clamp(17px,4vw,58px);width:100%;max-width:1540px;margin:0 auto}
header,.actions{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}header{margin-bottom:22px}
h1,h2{font:normal 44px/1.15 Georgia,serif;margin:0}h2{font-size:24px;margin:0 0 14px}p{margin:0 0 12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:12px;margin-bottom:20px}
.stat,.panel{background:#1c1b19;border:1px solid var(--line);border-radius:12px}.stat{padding:13px 14px;color:var(--muted)}.stat strong{display:block;font:32px Georgia,serif;color:var(--gold)}.stat:hover,.stat.current{border-color:var(--gold);text-decoration:none}
.panel{padding:18px;margin-bottom:15px}.split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.scroll{overflow:auto}
table{border-collapse:collapse;width:100%;text-align:left}td,th{padding:10px;border-top:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:12px}td:first-child{min-width:140px}.tag{display:inline-block;border-radius:15px;padding:2px 8px;background:#3b3120;color:#f4da94;white-space:nowrap;font-size:12px}.danger{color:#ffaaa5}.flag{background:#492a28;color:#ffaaa5}.done{background:#23382b;color:#bbe7c8}
label{display:block;margin-bottom:12px}input,button,select,textarea{font:inherit}input:not([type=checkbox]),select,textarea{width:100%;padding:8px 10px;border:1px solid #62563e;border-radius:7px;margin-top:4px;background:#131313;color:#f8f1e3}textarea{min-height:85px;resize:vertical}
fieldset{border:1px solid var(--line);border-radius:7px;margin:0 0 12px}fieldset label{display:inline-block;margin:4px 10px 4px 0}input[type=checkbox]{accent-color:var(--gold)}
button,.button{display:inline-block;background:var(--gold);color:#241b0a;font-weight:650;border:1px solid transparent;border-radius:7px;padding:7px 12px;cursor:pointer}.secondary{background:#292318;color:var(--gold);border-color:#5b4a2c}button:hover,.button:hover{filter:brightness(1.15);text-decoration:none}
.record{padding:10px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}.pre{white-space:pre-wrap;overflow-wrap:anywhere}.stack{margin-top:10px}
.notice{background:#322a1b;padding:9px 12px;border-radius:7px;margin-bottom:12px}.error{background:#452c28;color:#ffbbb1}
.auth{max-width:445px;margin:7vh auto;padding:16px}.auth header{display:grid;justify-items:center;justify-content:center;text-align:center}.auth img{width:110px}.auth h1{font-size:33px}.search{display:flex;gap:8px;align-items:baseline;margin-bottom:12px;max-width:460px}
@media(max-width:800px){.shell,.split{grid-template-columns:1fr}aside{border:0;border-bottom:1px solid var(--line);padding:12px}.brand{margin-bottom:8px}nav{display:flex;flex-wrap:wrap}nav small{display:none}main{padding-top:19px}}
</style>
{% macro csrf() %}<input type="hidden" name="csrf" value="{{ session.csrf }}">{% endmacro %}
{% macro user_fields() %}
<label>Display name<input name="name" required maxlength="100"></label><label>Username<input name="username" required maxlength="60"></label>
<label>Password <small>(at least 12 characters)</small><input name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label>
{% endmacro %}
{% macro task_fields(item) %}
<label>Task title<input name="title" required maxlength="160" value="{{ item.title|default('') }}"></label>
<label>Instructions<textarea name="details" maxlength="4000">{{ item.details|default('') }}</textarea></label>
<label>Assigned to<select name="assignee"><option value="">Unassigned</option>{% for e in employees %}{% if e.active or e.id==item.assignee %}<option value="{{ e.id }}"{% if e.id==item.assignee %} selected{% endif %}>{{ e.name }}{% if not e.active %} (inactive){% endif %}</option>{% endif %}{% endfor %}</select></label>
<label>Due date <small>(optional)</small><input name="due" type="date" value="{{ item.due|default('') }}"></label>
{% endmacro %}
<body>{% if g.user and not g.user.temporary %}
<div class="shell"><aside><a class="brand" href="{{ url_for('dashboard') }}"><img src="/logo" alt=""><span><strong>LegalChef</strong><small>Work Organiser</small></span></a>
<nav aria-label="Workspace"><a href="/" class="{{ 'current' if title=='Overview' }}">Overview</a><small>Services</small>
{% for category in services %}<a href="{{ url_for('dashboard',service=category) }}" class="{{ 'current' if service==category }}">{{ category }}</a>{% endfor %}
{% if g.admin %}<small>Administration</small><a href="/clients">Clients</a><a href="/staff">Staff &amp; super admins</a><a href="/backup">Download backup</a>{% endif %}</nav>
<div class="account"><strong>{{ g.user.name }}</strong><br><small>{{ 'Super admin' if g.admin else 'Staff' }}</small><br><a href="/password">Change password</a>
<form method="post" action="/logout" class="stack">{{ csrf() }}<button class="secondary">Sign out</button></form></div></aside><main>
<header><h1>{{ title }}</h1>{% if g.admin and request.endpoint=='dashboard' %}<a class="button" href="{{ url_for('new_task',service=service) }}">New task</a>{% endif %}</header>
{% else %}<div class="auth"><header><img src="/logo" alt="LegalChef"><h1>{{ title }}</h1></header><div class="panel">{% endif %}
{% for category,message in get_flashed_messages(with_categories=true) %}<div role="status" class="notice {{ category }}">{{ message }}</div>{% endfor %}
__CONTENT__
{% if g.user and not g.user.temporary %}</main></div>{% else %}</div></div>{% endif %}</body></html>"""

AUTH = """
<form method="post">{{ csrf() }}
{% if mode=='setup' %}<p class="muted">Create the super admin account on this server.</p>{{ user_fields() }}
{% elif mode=='login' %}<label>Username<input name="username" autocomplete="username" maxlength="60" required autofocus></label><label>Password<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
{% else %}{% if g.user.temporary %}<p class="muted">Choose your own password to activate your account.</p>{% endif %}<label>Current password<input name="current" type="password" autocomplete="current-password" required></label><label>New password<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label>{% endif %}
<button>{{ {'setup':'Create super admin','login':'Sign in','password':'Save password'}[mode] }}</button></form>
{% if mode=='password' and g.user.temporary %}<form class="stack" method="post" action="/logout">{{ csrf() }}<button class="secondary">Sign out</button></form>{% endif %}
"""
DASHBOARD = """
<section class="stats" aria-label="Task totals">{% for label,total in counts.items() %}<a class="stat {{ 'current' if state==label }}" href="{{ url_for('dashboard',service=service,state='' if state==label else label,q=search) }}"><strong>{{ total }}</strong>{{ label }}</a>{% endfor %}</section>
<section class="panel"><div class="actions"><h2>{{ state or 'Tasks' }}</h2><form class="search" method="get">
<input type="hidden" name="service" value="{{ service }}"><input type="hidden" name="state" value="{{ state }}"><input name="q" aria-label="Search tasks" placeholder="Task, client or staff" maxlength="100" value="{{ search }}"><button class="secondary">Search</button>{% if state or search %}<a href="{{ url_for('dashboard',service=service) }}">Clear</a>{% endif %}</form></div>
{% if tasks %}<div class="scroll"><table><thead><tr><th>Task</th><th>Client</th><th>Service</th><th>Assigned to</th><th>Due date</th><th>Status</th></tr></thead><tbody>
{% for t in tasks %}<tr><td><a href="{{ url_for('task',task_id=t.id) }}">{{ t.title }}</a>{% if t.urgent %}<br><span class="tag flag">Red flag</span>{% endif %}</td>
<td>{{ t.client_name }}</td><td>{{ t.service }}</td><td>{{ t.staff_name or 'Unassigned' }}</td><td class="{{ 'danger' if overdue(t) }}">{{ t.due or '—' }}{% if overdue(t) %}<br>Overdue{% endif %}</td><td><span class="tag {{ 'done' if t.status=='Completed' }}">{{ t.status }}</span></td></tr>{% endfor %}
</tbody></table></div>{% else %}<p class="muted">No tasks to show.</p>{% endif %}</section>
{% if service %}<section class="panel"><h2>Clients</h2>{% for c in clients %}<div class="record actions"><div><strong>{{ c.name }}</strong>{% if g.admin and c.contact %}<br><small>{{ c.contact }}</small>{% endif %}</div>
{% if g.admin %}<a class="button secondary" href="{{ url_for('new_task',client=c.id,service=service) }}">Add task</a>{% endif %}</div>
{% else %}<p class="muted">No clients to show.{% if g.admin %} <a href="/clients">Manage clients</a>{% endif %}</p>{% endfor %}</section>{% endif %}
"""
CLIENTS = """
<div class="split"><section class="panel"><h2>{{ 'Edit client' if editing else 'Add client' }}</h2><form method="post">{{ csrf() }}
<label>Client name<input name="name" required maxlength="150" value="{{ editing.name if editing else '' }}"></label><label>Contact <small>(optional)</small><input name="contact" maxlength="200" value="{{ editing.contact if editing else '' }}"></label>
<fieldset><legend>Services</legend>{% for category in services %}<label><input type="checkbox" name="services" value="{{ category }}"{% if category in selected %} checked{% endif %}> {{ category }}</label>{% endfor %}</fieldset>
<button>Save client</button>{% if editing %} <a href="/clients">Cancel</a>{% endif %}</form></section>
<section class="panel"><h2>Client directory</h2>{% for c in records %}<div class="record actions"><div><strong>{{ c.name }}</strong><br><small>{{ c.services }}</small>{% if c.contact %}<br><small>{{ c.contact }}</small>{% endif %}</div><a href="{{ url_for('clients',edit=c.id) }}">Edit</a></div>{% else %}<p class="muted">No clients added yet.</p>{% endfor %}</section></div>
"""
STAFF = """
<div class="split"><section class="panel"><h2>Add staff account</h2><form method="post">{{ csrf() }}<input type="hidden" name="action" value="add">{{ user_fields() }}<button>Add staff member</button></form></section>
<section class="panel"><h2>Add super admin</h2>
<p class="muted">A super admin can manage all clients, tasks, accounts and backups.</p>
<form method="post">{{ csrf() }}<input type="hidden" name="action" value="add_admin">{{ user_fields() }}<button>Add super admin</button></form></section>
<section class="panel"><h2>Staff accounts</h2>{% for member in staff %}<div class="record"><div class="actions"><div><strong>{{ member.name }}</strong><br><small>{{ member.username }} · {{ 'Active' if member.active else 'Inactive' }}</small></div>
<form method="post">{{ csrf() }}<input type="hidden" name="user" value="{{ member.id }}"><button name="action" value="toggle" class="secondary">{{ 'Deactivate' if member.active else 'Reactivate' }}</button></form></div>
<details class="stack"><summary>Reset password</summary><form method="post" class="stack">{{ csrf() }}<input type="hidden" name="user" value="{{ member.id }}"><label>Temporary password<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label><button name="action" value="reset">Reset password</button></form></details></div>{% else %}<p class="muted">No staff accounts added yet.</p>{% endfor %}</section>
<section class="panel"><h2>Super admin accounts</h2>
{% for admin in admins %}<div class="record"><strong>{{ admin.name }}</strong>{% if admin.id==g.user.id %} <small>(you)</small>{% endif %}<br><small>{{ admin.username }}</small></div>{% endfor %}
</section></div>
"""
NEW_TASK = """
<section class="panel">{% if choices %}<form method="post">{{ csrf() }}
<label>Client and service<select name="client_service" required><option value="">Choose a client and service</option>{% for c in choices %}{% if not chosen_service or c.service==chosen_service %}<option value="{{ c.id }}|{{ c.service }}"{% if c.id==chosen_client and c.service==chosen_service %} selected{% endif %}>{{ c.name }} · {{ c.service }}</option>{% endif %}{% endfor %}</select></label>
{{ task_fields({}) }}<button>Create task</button></form>
{% else %}<p>Add a client before creating a task.</p><a href="/clients" class="button">Add client</a>{% endif %}</section>
"""
TASK = """
<p class="muted">{{ item.client_name }} · <a href="{{ url_for('dashboard',service=item.service) }}">{{ item.service }}</a> · Task #{{ item.id }}</p>
<div class="split"><section class="panel"><h2>Update task</h2><form method="post">{{ csrf() }}<input type="hidden" name="version" value="{{ item.version }}">
{% if g.admin %}{{ task_fields(item) }}{% else %}<p class="pre">{{ item.details or 'No instructions added.' }}</p><p class="muted">Due {{ item.due or '—' }}</p>{% endif %}
<label>Status<select name="status">{% for status in statuses %}<option{% if item.status==status %} selected{% endif %}>{{ status }}</option>{% endfor %}</select></label>
<label class="danger"><input type="checkbox" name="urgent" value="yes"{% if item.urgent %} checked{% endif %}> Red flag for urgent review</label>
<label>Progress note <small>(optional)</small><textarea name="note" maxlength="2000"></textarea></label><button>Save update</button></form></section>
<section class="panel"><h2>Activity</h2>{% for entry in history %}<div class="record"><strong>{{ entry.name }}</strong> <small>{{ entry.at }}</small><div class="pre">{{ entry.message }}</div></div>{% endfor %}</section></div>
"""

def page(title, content, **context):
    return render_template_string(BASE.replace("__CONTENT__", content), title=title,
                                  services=SERVICES, statuses=STATUSES, **context)

def main():
    parser = argparse.ArgumentParser(description="Run LegalChef Work Organiser on the office network.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=DB.parent)
    parser.add_argument("--secure-cookie", action="store_true", help="Require HTTPS for session cookies")
    options = parser.parse_args()
    init(options.data_dir / DB.name)
    app.config["SESSION_COOKIE_SECURE"] = options.secure_cookie
    print(f"LegalChef Work Organiser: http://127.0.0.1:{options.port}", flush=True)
    print(f"Office network: http://<server-IP>:{options.port}", flush=True)
    print(f"Database: {DB}", flush=True)
    print("Leave this window open. Press Ctrl+C to stop.", flush=True)
    serve(app, host=options.host, port=options.port, threads=8,
          channel_timeout=30, max_request_body_size=64_000)

LOGO = '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'

if __name__ == "__main__":
    main()

