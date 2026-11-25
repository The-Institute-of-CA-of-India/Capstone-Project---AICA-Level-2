"""SQLite persistence layer for Statutory Audit Execution Pro (standard library only)."""
from __future__ import annotations
import hashlib, hmac, json, secrets, shutil, sqlite3, zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"
DB_PATH = RUNTIME / "auditexec.db"
EVIDENCE_DIR = RUNTIME / "evidence"
EXPORT_DIR = RUNTIME / "exports"


def now() -> str:
    return datetime.now().strftime("%d-%b-%Y %H:%M")


LEGACY_SALT = b"AuditExecPro-local-salt"


def password_hash(password: str, salt: str | None = None) -> str:
    """New format: 'pbkdf2$<salt>$<hash>' with a random per-user salt. Legacy hashes (no prefix) still verify."""
    if salt is None:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), LEGACY_SALT, 200_000).hex()
    return f"pbkdf2${salt}${hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200_000).hex()}"


def new_hash(password: str) -> str:
    return password_hash(password, secrets.token_hex(16))


def verify(password: str, stored: str) -> bool:
    if stored and stored.startswith("pbkdf2$"):
        _, salt, _h = stored.split("$", 2)
        return hmac.compare_digest(password_hash(password, salt), stored)
    return hmac.compare_digest(password_hash(password), stored or "")


def connection() -> sqlite3.Connection:
    for d in (RUNTIME, EVIDENCE_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT, password_hash TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS engagements(id INTEGER PRIMARY KEY, client_name TEXT, financial_year TEXT, entity_type TEXT, framework TEXT, materiality REAL, deadline TEXT, status TEXT DEFAULT 'Planning', created_by INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS workpapers(id INTEGER PRIMARY KEY, engagement_id INTEGER, topic_code TEXT, objective TEXT, conclusion TEXT, workflow TEXT DEFAULT 'Not Started', prepared_by INTEGER, prepared_at TEXT, reviewed_by INTEGER, reviewed_at TEXT, approved_by INTEGER, approved_at TEXT, UNIQUE(engagement_id,topic_code));
CREATE TABLE IF NOT EXISTS checklist_status(id INTEGER PRIMARY KEY, workpaper_id INTEGER, row_no INTEGER, status TEXT DEFAULT '', remarks TEXT DEFAULT '', checked_by INTEGER, checked_at TEXT, UNIQUE(workpaper_id,row_no));
CREATE TABLE IF NOT EXISTS uploads(id INTEGER PRIMARY KEY, engagement_id INTEGER, topic_code TEXT, source_name TEXT, stored_path TEXT, kind TEXT, uploaded_by INTEGER, uploaded_at TEXT);
CREATE TABLE IF NOT EXISTS aqms(id INTEGER PRIMARY KEY, engagement_id INTEGER, topic_code TEXT, title TEXT, description TEXT, status TEXT DEFAULT 'Open', management_response TEXT DEFAULT '', raised_by INTEGER, raised_at TEXT, closed_by INTEGER, closed_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, engagement_id INTEGER, topic_code TEXT, user_id INTEGER, action TEXT, detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS review_notes(id INTEGER PRIMARY KEY, engagement_id INTEGER, topic_code TEXT, step_no INTEGER DEFAULT 0, note TEXT, raised_by INTEGER, raised_at TEXT, status TEXT DEFAULT 'Open', response TEXT DEFAULT '', cleared_by INTEGER, cleared_at TEXT);
CREATE TABLE IF NOT EXISTS login_attempts(username TEXT PRIMARY KEY, fails INTEGER DEFAULT 0, locked_until REAL DEFAULT 0);
"""

# (table, column, definition) - added on start-up so older databases keep working
MIGRATIONS = [
    ("workpapers", "conclusion_type", "TEXT DEFAULT ''"),
    ("workpapers", "not_applicable", "INTEGER DEFAULT 0"),
    ("workpapers", "na_reason", "TEXT DEFAULT ''"),
    ("workpapers", "evidence_na", "INTEGER DEFAULT 0"),
    ("workpapers", "evidence_na_reason", "TEXT DEFAULT ''"),
    ("uploads", "description", "TEXT DEFAULT ''"),
    ("uploads", "step_no", "INTEGER DEFAULT 0"),
    ("uploads", "size_bytes", "INTEGER DEFAULT 0"),
    ("engagements", "overall_type", "TEXT DEFAULT ''"),
    ("engagements", "overall_conclusion", "TEXT DEFAULT ''"),
    ("engagements", "basis_of_conclusion", "TEXT DEFAULT ''"),
    ("engagements", "programme", "TEXT DEFAULT 'GEN'"),
    ("engagements", "prior_engagement_id", "INTEGER DEFAULT 0"),
    ("workpapers", "rev", "INTEGER DEFAULT 0"),
    ("workpapers", "applicability", "TEXT DEFAULT ''"),
    ("workpapers", "applicability_by", "INTEGER DEFAULT 0"),
    ("workpapers", "applicability_at", "TEXT DEFAULT ''"),
    ("checklist_status", "work_date", "TEXT DEFAULT ''"),
    ("workpapers", "assigned_to", "INTEGER DEFAULT 0"),
    ("workpapers", "due_date", "TEXT DEFAULT ''"),
    ("workpapers", "py_conclusion", "TEXT DEFAULT ''"),
    ("workpapers", "py_type", "TEXT DEFAULT ''"),
    ("workpapers", "returned_note", "TEXT DEFAULT ''"),
    ("uploads", "step_list", "TEXT DEFAULT ''"),
    ("uploads", "file_modified", "TEXT DEFAULT ''"),
    ("users", "must_change", "INTEGER DEFAULT 0"),
]


def init_db() -> None:
    con = connection()
    con.executescript(SCHEMA)
    for table, col, ddl in MIGRATIONS:
        cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    # applicability: carry earlier choices forward (N/A stays N/A; modules already worked on count as Applicable)
    con.execute("UPDATE workpapers SET applicability='NA' WHERE not_applicable=1 AND IFNULL(applicability,'')=''")
    con.execute("""UPDATE workpapers SET applicability='Applicable' WHERE IFNULL(applicability,'')='' AND (
        IFNULL(conclusion,'')<>'' OR IFNULL(conclusion_type,'')<>'' OR evidence_na=1 OR workflow IN ('Compiled','Reviewed','Returned')
        OR id IN (SELECT workpaper_id FROM checklist_status WHERE IFNULL(status,'')<>'' OR IFNULL(remarks,'')<>'')
        OR EXISTS(SELECT 1 FROM uploads u WHERE u.engagement_id=workpapers.engagement_id AND u.topic_code=workpapers.topic_code))""")
    # first run: the Partner login. Old sample accounts with their published passwords are switched off.
    if not con.execute("SELECT 1 FROM users WHERE username='vivek'").fetchone():
        con.execute("INSERT INTO users(username,name,role,password_hash,must_change) VALUES (?,?,?,?,1)",
                    ("vivek", "Vivek", "Partner", new_hash("kdc@123")))
    for un, pw in (("partner", "Partner@123"), ("senior", "Senior@123"), ("junior", "Junior@123")):
        r = con.execute("SELECT id,password_hash FROM users WHERE username=?", (un,)).fetchone()
        if r and verify(pw, r["password_hash"]): con.execute("UPDATE users SET active=0 WHERE id=?", (r["id"],))
    con.commit(); con.close()


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    con = connection(); rows = con.execute(sql, params).fetchall(); con.close(); return rows


def one(sql: str, params: tuple = ()):
    rows = query(sql, params); return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    con = connection(); cur = con.execute(sql, params); con.commit(); ident = cur.lastrowid; con.close(); return ident


def login(username: str, password: str):
    """Returns (user_row_or_None, message). Locks a username for 5 minutes after 5 failures."""
    import time
    un = (username or "").strip().lower()
    att = one("SELECT * FROM login_attempts WHERE username=?", (un,))
    if att and att["locked_until"] > time.time():
        return None, "Too many failed attempts. Please try again in a few minutes, or ask the Partner to reset your password."
    row = one("SELECT * FROM users WHERE lower(username)=? AND active=1", (un,))
    if row and verify(password, row["password_hash"]):
        execute("DELETE FROM login_attempts WHERE username=?", (un,))
        if not row["password_hash"].startswith("pbkdf2$"):
            execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash(password), row["id"]))
        return row, ""
    fails = (att["fails"] if att else 0) + 1
    execute("INSERT INTO login_attempts(username,fails,locked_until) VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET fails=excluded.fails,locked_until=excluded.locked_until",
            (un, 0 if fails >= 5 else fails, time.time() + 300 if fails >= 5 else 0))
    return None, "The username or password is incorrect."


def backup_now(keep: int = 14) -> Path:
    """Zip a consistent copy of the database plus all evidence into runtime/backups."""
    bdir = RUNTIME / "backups"; bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S"); tmp = bdir / f"_tmp_{stamp}.db"
    src = connection(); dst = sqlite3.connect(tmp); src.backup(dst); dst.close(); src.close()
    out = bdir / f"AuditExec_backup_{stamp}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, "auditexec.db")
        if EVIDENCE_DIR.exists():
            for f in EVIDENCE_DIR.rglob("*"):
                if f.is_file(): z.write(f, "evidence/" + f.relative_to(EVIDENCE_DIR).as_posix())
    tmp.unlink(missing_ok=True)
    for old in sorted(bdir.glob("AuditExec_backup_*.zip"))[:-keep]: old.unlink(missing_ok=True)
    return out


def restore_backup(zpath: Path) -> None:
    """Replace the live database and evidence with the contents of a backup zip (after backing up the current state)."""
    backup_now()
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if "auditexec.db" not in names: raise ValueError("This is not an AUDIT EXECUTION Pro backup file.")
        z.extract("auditexec.db", RUNTIME)
        for n in ("auditexec.db-wal", "auditexec.db-shm"): (RUNTIME / n).unlink(missing_ok=True)
        if EVIDENCE_DIR.exists(): shutil.rmtree(EVIDENCE_DIR)
        for n in names:
            if n.startswith("evidence/") and not n.endswith("/"):
                target = (RUNTIME / n).resolve()
                if RUNTIME.resolve() not in target.parents: continue
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(z.read(n))
    init_db()


def log(engagement_id, topic_code, user_id, action: str, detail: str = ""):
    execute("INSERT INTO audit_log(engagement_id,topic_code,user_id,action,detail,created_at) VALUES(?,?,?,?,?,?)",
            (engagement_id, topic_code, user_id, action, detail, now()))


def save_json(value: Any) -> str: return json.dumps(value, default=str)
def load_json(value: str) -> Any: return json.loads(value) if value else {}
