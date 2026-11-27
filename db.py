"""SQLite storage, demo users and seed data for Mini CFO (demo / dummy data only)."""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
DATA = BASE / "data"
DB_PATH = DATA / "minicfo.db"

CLIENTS = [
    dict(id="sharma", name="Sharma Traders", owner_name="Rakesh Sharma", opening_cash=400000,
         fixed_costs=160000, sales_target=800000, profit_target=150000, language="English",
         sample="sharma_traders.csv"),
    dict(id="verma", name="Verma Foods", owner_name="Sunita Verma", opening_cash=50000,
         fixed_costs=60000, sales_target=300000, profit_target=40000, language="English",
         sample="verma_foods.csv"),
]
USERS = [  # email, password, role, client_id
    ("ca@demo.com", "Demo@12345", "ca", None),
    ("owner@demo.com", "Demo@12345", "owner", "sharma"),
    ("owner2@demo.com", "Demo@12345", "owner", "verma"),
]


def _hash(pw: str) -> str:
    return hashlib.sha256(("minicfo-demo-salt" + pw).encode()).hexdigest()


def conn() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, name TEXT, owner_name TEXT,
            opening_cash REAL, fixed_costs REAL, sales_target REAL, profit_target REAL,
            language TEXT, uploaded_at TEXT);
        CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY, pw_hash TEXT, role TEXT,
            client_id TEXT, consent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT,
            email TEXT, question TEXT, answer TEXT, status TEXT, reply TEXT, faq INTEGER DEFAULT 0, ts TEXT);
        CREATE TABLE IF NOT EXISTS notes(client_id TEXT, month TEXT, text TEXT, status TEXT,
            approved_on TEXT, PRIMARY KEY(client_id, month));
        CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, email TEXT, action TEXT);
        """)
        if c.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
            now = datetime.now().strftime("%d %b %Y")
            for cl in CLIENTS:
                c.execute("INSERT INTO clients VALUES(?,?,?,?,?,?,?,?,?)",
                          (cl["id"], cl["name"], cl["owner_name"], cl["opening_cash"], cl["fixed_costs"],
                           cl["sales_target"], cl["profit_target"], cl["language"], now))
                shutil.copy(BASE / "sample" / cl["sample"], DATA / f"{cl['id']}.csv")
            for email, pw, role, cid in USERS:
                c.execute("INSERT INTO users(email,pw_hash,role,client_id) VALUES(?,?,?,?)",
                          (email, _hash(pw), role, cid))


def login(email: str, pw: str):
    with conn() as c:
        r = c.execute("SELECT * FROM users WHERE email=? AND pw_hash=?",
                      (email.strip().lower(), _hash(pw))).fetchone()
    return dict(r) if r else None


def set_consent(email: str):
    with conn() as c:
        c.execute("UPDATE users SET consent=1 WHERE email=?", (email,))


def log(email: str, action: str):
    with conn() as c:
        c.execute("INSERT INTO log(ts,email,action) VALUES(?,?,?)",
                  (datetime.now().strftime("%d %b %Y %H:%M"), email, action))


def get_clients() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clients ORDER BY name")]


def get_client(cid: str) -> dict:
    with conn() as c:
        return dict(c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone())


def update_client(cid: str, **fields):
    keys = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE clients SET {keys} WHERE id=?", (*fields.values(), cid))


def load_txns(cid: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{cid}.csv", parse_dates=["Date", "Due_Date"])
    return df


def save_txns(cid: str, new: pd.DataFrame):
    """Months present in the new file replace the same months already stored."""
    path = DATA / f"{cid}.csv"
    new = new.copy()
    if path.exists():
        old = pd.read_csv(path, parse_dates=["Date", "Due_Date"])
        months = set(new["Date"].dt.to_period("M"))
        old = old[~old["Date"].dt.to_period("M").isin(months)]
        new = pd.concat([old, new], ignore_index=True)
    new = new.sort_values("Date")
    new.to_csv(path, index=False)
    update_client(cid, uploaded_at=datetime.now().strftime("%d %b %Y"))


# questions ---------------------------------------------------------------
def add_question(cid, email, question, answer, status="Answered by app"):
    with conn() as c:
        c.execute("INSERT INTO questions(client_id,email,question,answer,status,ts) VALUES(?,?,?,?,?,?)",
                  (cid, email, question, answer, status, datetime.now().strftime("%d %b %Y %H:%M")))


def forward_to_ca(qid: int):
    with conn() as c:
        c.execute("UPDATE questions SET status='Sent to CA' WHERE id=?", (qid,))


def questions_for(cid: str):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM questions WHERE client_id=? ORDER BY id", (cid,))]


def inbox():
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT q.*, cl.name AS client FROM questions q JOIN clients cl ON cl.id=q.client_id "
            "WHERE q.status IN ('Sent to CA','Replied by CA') ORDER BY q.id DESC")]


def reply(qid: int, text: str, faq: bool):
    with conn() as c:
        c.execute("UPDATE questions SET reply=?, faq=?, status='Replied by CA' WHERE id=?",
                  (text, 1 if faq else 0, qid))


def faq_lookup(cid: str, question: str):
    with conn() as c:
        r = c.execute("SELECT reply FROM questions WHERE client_id=? AND faq=1 AND lower(question)=lower(?) "
                      "ORDER BY id DESC LIMIT 1", (cid, question.strip())).fetchone()
    return r["reply"] if r else None


def question_counts():
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT lower(question) AS q, COUNT(*) AS times FROM questions GROUP BY lower(question) "
            "ORDER BY times DESC LIMIT 10")]


# notes ---------------------------------------------------------------
def get_note(cid, month):
    with conn() as c:
        r = c.execute("SELECT * FROM notes WHERE client_id=? AND month=?", (cid, month)).fetchone()
    return dict(r) if r else None


def save_note(cid, month, text, status="Draft", approved_on=None):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO notes VALUES(?,?,?,?,?)", (cid, month, text, status, approved_on))


def get_log(limit=200):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT ts,email,action FROM log ORDER BY id DESC LIMIT ?", (limit,))]
