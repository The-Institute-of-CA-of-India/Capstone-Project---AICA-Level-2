"""SQLite database layer for the Work Tracker."""
import sqlite3, hashlib, os, secrets
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worktracker.db")

STATUSES = ["Not Started", "In Progress", "Submitted for Review", "Rework", "Approved", "Completed"]
EMPLOYEE_STATUSES = ["Not Started", "In Progress", "Submitted for Review"]
PRIORITIES = ["High", "Medium", "Low"]


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def check_pw(password, stored):
    salt, _ = stored.split("$")
    return hash_pw(password, salt) == stored


def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','employee')),
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            client TEXT,
            category TEXT,
            priority TEXT DEFAULT 'Medium',
            assigned_to INTEGER REFERENCES users(id),
            assigned_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Not Started',
            review_comments TEXT,
            employee_remarks TEXT,
            completed_date TEXT
        );
        CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER REFERENCES tasks(id),
            file_path TEXT,
            uploaded_on TEXT
        );
        CREATE TABLE IF NOT EXISTS activity_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            who TEXT,
            what TEXT,
            at TEXT
        );
        """)
        if not c.execute("SELECT 1 FROM users").fetchone():
            c.execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)",
                      ("Administrator", "admin", hash_pw("admin123"), "admin"))


# ---------- users ----------
def login(username, password):
    with conn() as c:
        u = c.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    if u and check_pw(password, u["password"]):
        return dict(u)
    return None


def list_users(only_employees=False, include_inactive=False):
    q = "SELECT id,name,username,role,active FROM users"
    cond = []
    if not include_inactive:
        cond.append("active=1")
    if only_employees:
        cond.append("role='employee'")
    if cond:
        q += " WHERE " + " AND ".join(cond)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY name")]


def add_user(name, username, password, role="employee"):
    with conn() as c:
        c.execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)",
                  (name, username, hash_pw(password), role))


def set_user_active(user_id, active):
    with conn() as c:
        c.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))


def change_password(user_id, new_password):
    with conn() as c:
        c.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new_password), user_id))


# ---------- tasks ----------
def log(task_id, who, what):
    with conn() as c:
        c.execute("INSERT INTO activity_log(task_id,who,what,at) VALUES(?,?,?,?)",
                  (task_id, who, what, datetime.now().strftime("%Y-%m-%d %H:%M")))


def create_task(title, description, client, category, priority, assigned_to, due_date, who="admin"):
    with conn() as c:
        cur = c.execute(
            """INSERT INTO tasks(title,description,client,category,priority,assigned_to,
               assigned_date,due_date,status) VALUES(?,?,?,?,?,?,?,?,'Not Started')""",
            (title, description, client, category, priority, assigned_to,
             date.today().isoformat(), str(due_date) if due_date else None))
        tid = cur.lastrowid
    log(tid, who, "Task created and assigned")
    return tid


def update_task(task_id, who="admin", **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
    log(task_id, who, "Updated: " + ", ".join(fields.keys()))


def delete_task(task_id, who="admin"):
    with conn() as c:
        c.execute("DELETE FROM attachments WHERE task_id=?", (task_id,))
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    log(task_id, who, "Task deleted")


def set_status(task_id, status, who):
    extra = {}
    if status == "Completed":
        extra["completed_date"] = date.today().isoformat()
    update_task(task_id, who=who, status=status, **extra)


def get_tasks(user_id=None):
    q = """SELECT t.*, u.name AS assignee FROM tasks t
           LEFT JOIN users u ON u.id=t.assigned_to"""
    params = ()
    if user_id is not None:          # employees only ever get their own tasks
        q += " WHERE t.assigned_to=?"
        params = (user_id,)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY t.due_date IS NULL, t.due_date", params)]


def add_attachment(task_id, path):
    with conn() as c:
        c.execute("INSERT INTO attachments(task_id,file_path,uploaded_on) VALUES(?,?,?)",
                  (task_id, path, date.today().isoformat()))


def get_attachments(task_id):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM attachments WHERE task_id=?", (task_id,))]


def get_log(task_id):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM activity_log WHERE task_id=? ORDER BY id DESC", (task_id,))]


def is_overdue(t):
    return bool(t["due_date"]) and t["status"] not in ("Completed", "Approved") \
        and t["due_date"] < date.today().isoformat()
