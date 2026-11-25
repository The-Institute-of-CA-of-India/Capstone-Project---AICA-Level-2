"""Multi-user web server for Statutory Audit Execution Pro (Khare Deshmukh & Co.)."""
from __future__ import annotations
import json, re, secrets, tempfile, uuid
from datetime import datetime, date
from pathlib import Path
from functools import wraps
import pandas as pd
from flask import Flask, jsonify, request, session, send_file, send_from_directory, abort, Response
from .core import database as db
from .core.progress import (TOPICS, GROUPS, ASSERTIONS, STEP_STATUS, CONCLUSION_TYPES, OVERALL_TYPES, ADVERSE_TYPES,
                            codes_for, load_engagement, area_progress, engagement_progress, adverse_register)
from .core.report import build_working_paper, build_observations, build_html_report, draft_paragraphs, kind_of
from .core.analytics import findings as run_checks

STATIC = Path(__file__).resolve().parent / "static"
ALLOWED = {".xlsx", ".xlsm", ".xls", ".csv", ".doc", ".docx", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
           ".txt", ".ppt", ".pptx", ".msg", ".eml", ".zip"}
INLINE = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".txt"}
ROLES = ("Partner", "Senior", "Junior")
ROLE_LABEL = {"Partner": "Partner", "Senior": "Sr Staff", "Junior": "Jr Staff"}
ENTITY_TYPES = ["Company", "LLP", "Partnership Firm", "Proprietorship", "HUF", "Trust / Society", "Other"]


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "_", s)[:120]


def next_fy(fy: str) -> str | None:
    m = re.fullmatch(r"\s*(\d{4})\s*[-–/]\s*(\d{2,4})\s*", fy or "")
    if not m: return None
    a = int(m.group(1)) + 1
    return f"{a}-{str(a + 1)[-2:]}"


def fy_start(fy: str) -> date | None:
    m = re.match(r"\s*(\d{4})", fy or "")
    return date(int(m.group(1)), 4, 1) if m else None


def create_app() -> Flask:
    db.init_db()
    app = Flask(__name__, static_folder=None)
    key = db.RUNTIME / "secret.key"
    if not key.exists(): key.write_text(secrets.token_hex(32))
    app.secret_key = key.read_text()
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 10

    def current_user():
        uid = session.get("uid")
        return db.one("SELECT * FROM users WHERE id=? AND active=1", (uid,)) if uid else None

    def auth(fn=None, *, roles=None):
        def deco(f):
            @wraps(f)
            def wrapper(*a, **k):
                u = current_user()
                if not u: return jsonify(error="Please sign in."), 401
                if roles and u["role"] not in roles:
                    return jsonify(error="You do not have permission for this action."), 403
                return f(u, *a, **k)
            return wrapper
        return deco(fn) if fn else deco

    def bad(msg, code=400): return jsonify(error=msg), code
    def names(): return {x["id"]: x["name"] for x in db.query("SELECT id,name FROM users")}

    def get_wp(eid, code):
        row = db.one("SELECT * FROM workpapers WHERE engagement_id=? AND topic_code=?", (eid, code))
        if row: return dict(row)
        db.execute("INSERT OR IGNORE INTO workpapers(engagement_id,topic_code,objective,conclusion) VALUES(?,?,?,?)",
                   (eid, code, TOPICS[code]["objective"], ""))
        return dict(db.one("SELECT * FROM workpapers WHERE engagement_id=? AND topic_code=?", (eid, code)))

    def locked(wp): return wp.get("workflow") in ("Compiled", "Reviewed")

    def guard(wp):
        if wp.get("workflow") == "Reviewed": return bad("This module has been reviewed by the Partner and is locked. The Partner can send it back for changes.", 423)
        if wp.get("workflow") == "Compiled": return bad("This module is compiled and awaiting Partner review. It is locked unless the Partner sends it back.", 423)
        if (g := gate(wp)): return g

    def gate(wp):
        if (wp.get("applicability") or ("NA" if wp.get("not_applicable") else "")) != "Applicable":
            return bad("Please confirm first whether this module is applicable to the entity.", 409)

    def iso_to_disp(v):
        """Date typed by the user (YYYY-MM-DD) -> '24-Nov-2026'; blank/invalid -> today."""
        try: return datetime.strptime((v or "")[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
        except ValueError: return datetime.now().strftime("%d-%b-%Y")

    def valid_area(eid, code):
        e = db.one("SELECT * FROM engagements WHERE id=?", (eid,))
        return bool(e) and code in codes_for(e["entity_type"])

    # ================= pages =================
    @app.get("/")
    def index(): return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name): return send_from_directory(STATIC, name)

    # ================= auth =================
    @app.post("/api/login")
    def login():
        b = request.get_json(force=True)
        u, msg = db.login(b.get("username") or "", b.get("password") or "")
        if not u: return bad(msg, 401)
        session.permanent = True; session["uid"] = u["id"]
        db.log(None, None, u["id"], "Signed in")
        return jsonify(id=u["id"], name=u["name"], role=u["role"], must_change=bool(u["must_change"]))

    @app.post("/api/logout")
    def logout(): session.clear(); return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        u = current_user()
        return jsonify(user=None if not u else {"id": u["id"], "name": u["name"], "role": u["role"], "must_change": bool(u["must_change"])},
                       meta={"step_status": STEP_STATUS, "conclusion_types": CONCLUSION_TYPES, "overall_types": OVERALL_TYPES,
                             "assertions": ASSERTIONS, "role_label": ROLE_LABEL, "entity_types": ENTITY_TYPES, "groups": GROUPS})

    @app.get("/api/people")
    @auth
    def people(u):
        return jsonify([{"id": r["id"], "name": r["name"], "role": r["role"]} for r in db.query("SELECT * FROM users WHERE active=1 ORDER BY name")])

    # ================= users (Partner only) =================
    def valid_pw(pw): return len(pw or "") >= 6

    @app.post("/api/me/password")
    @auth
    def change_my_password(u):
        b = request.get_json(force=True)
        if not db.verify(b.get("old") or "", u["password_hash"]): return bad("Your current password is incorrect.")
        if not valid_pw(b.get("new")): return bad("The new password must be at least 6 characters.")
        if b["new"] == b.get("old"): return bad("Choose a password different from the current one.")
        db.execute("UPDATE users SET password_hash=?, must_change=0 WHERE id=?", (db.new_hash(b["new"]), u["id"]))
        db.log(None, None, u["id"], "Changed own password"); return jsonify(ok=True)

    @app.get("/api/users")
    @auth(roles=("Partner",))
    def list_users(u):
        return jsonify([{k: r[k] for k in ("id", "username", "name", "role", "active")} for r in db.query("SELECT * FROM users ORDER BY active DESC, role, name")])

    @app.post("/api/users")
    @auth(roles=("Partner",))
    def add_user(u):
        b = request.get_json(force=True); un = (b.get("username") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9._-]{3,30}", un): return bad("Username: 3–30 letters / numbers (no spaces).")
        if b.get("role") not in ROLES: return bad("Choose a role.")
        if not (b.get("name") or "").strip(): return bad("Enter the person's name.")
        if not valid_pw(b.get("password")): return bad("Password must be at least 6 characters.")
        if db.one("SELECT 1 FROM users WHERE lower(username)=?", (un,)): return bad("That username already exists.")
        db.execute("INSERT INTO users(username,name,role,password_hash,must_change) VALUES (?,?,?,?,1)", (un, b["name"].strip(), b["role"], db.new_hash(b["password"])))
        db.log(None, None, u["id"], "Created login", un); return jsonify(ok=True)

    @app.put("/api/users/<int:uid>")
    @auth(roles=("Partner",))
    def edit_user(u, uid):
        b = request.get_json(force=True)
        if not db.one("SELECT 1 FROM users WHERE id=?", (uid,)): return bad("User not found.", 404)
        if "password" in b:
            if not valid_pw(b["password"]): return bad("Password must be at least 6 characters.")
            db.execute("UPDATE users SET password_hash=?, must_change=? WHERE id=?", (db.new_hash(b["password"]), 0 if uid == u["id"] else 1, uid))
            db.execute("DELETE FROM login_attempts WHERE username=(SELECT lower(username) FROM users WHERE id=?)", (uid,))
            db.log(None, None, u["id"], "Reset password", str(uid))
        if "active" in b:
            if uid == u["id"] and not b["active"]: return bad("You cannot disable your own account.")
            db.execute("UPDATE users SET active=? WHERE id=?", (int(bool(b["active"])), uid))
        if (b.get("name") or "").strip(): db.execute("UPDATE users SET name=? WHERE id=?", (b["name"].strip(), uid))
        if b.get("role") in ROLES:
            if uid == u["id"] and b["role"] != "Partner":
                if not db.one("SELECT 1 FROM users WHERE role='Partner' AND active=1 AND id<>?", (uid,)): return bad("There must be at least one active Partner.")
            db.execute("UPDATE users SET role=? WHERE id=?", (b["role"], uid))
        return jsonify(ok=True)

    # ================= engagements =================
    @app.get("/api/engagements")
    @auth
    def engagements(u):
        out = []
        for e in db.query("SELECT * FROM engagements ORDER BY id DESC"):
            pr = engagement_progress(e["id"])
            out.append({**dict(e), "pct": pr["overall_pct"], "complete": pr["complete"], "total_areas": pr["total_areas"],
                        "open_queries": pr["open_queries"], "reviewed": pr["reviewed"], "compiled": pr["compiled"], "live_areas": pr["live_areas"]})
        return jsonify(out)

    @app.get("/api/my-work")
    @auth
    def my_work(u):
        rows = db.query("""SELECT w.topic_code, w.workflow, w.due_date, e.id eid, e.client_name, e.financial_year FROM workpapers w
                           JOIN engagements e ON e.id=w.engagement_id WHERE w.assigned_to=? AND w.workflow<>'Reviewed' AND w.not_applicable=0
                           ORDER BY CASE WHEN w.due_date='' THEN 1 ELSE 0 END, w.due_date""", (u["id"],))
        return jsonify([{**dict(r), "title": TOPICS[r["topic_code"]]["title"]} for r in rows if r["topic_code"] in TOPICS])

    @app.post("/api/engagements")
    @auth(roles=("Partner", "Senior"))
    def new_engagement(u):
        b = request.get_json(force=True)
        if not (b.get("client_name") or "").strip(): return bad("Please enter the client / entity name.")
        if b.get("entity_type") not in ENTITY_TYPES: return bad("Choose the type of entity.")
        try: m = float(str(b.get("materiality") or 0).replace(",", ""))
        except ValueError: return bad("Enter materiality as a number.")
        i = db.execute("INSERT INTO engagements(client_name,financial_year,entity_type,framework,materiality,deadline,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       (b["client_name"].strip(), b.get("financial_year", "").strip(), b["entity_type"], b.get("framework", ""), m, b.get("deadline", ""), u["id"], db.now()))
        db.log(i, None, u["id"], "Created engagement", b["client_name"]); return jsonify(id=i)

    @app.post("/api/engagements/<int:eid>/rollover")
    @auth(roles=("Partner",))
    def rollover(u, eid):
        e = db.one("SELECT * FROM engagements WHERE id=?", (eid,))
        if not e: return bad("Engagement not found.", 404)
        fy = (request.get_json(force=True) or {}).get("financial_year") or next_fy(e["financial_year"])
        if not fy: return bad("Enter the new financial year (e.g. 2026-27).")
        if db.one("SELECT 1 FROM engagements WHERE client_name=? AND financial_year=?", (e["client_name"], fy)): return bad("An engagement for that client and year already exists.")
        nid = db.execute("INSERT INTO engagements(client_name,financial_year,entity_type,framework,materiality,deadline,created_by,created_at,prior_engagement_id) VALUES(?,?,?,?,?,?,?,?,?)",
                         (e["client_name"], fy, e["entity_type"], e["framework"], e["materiality"], "", u["id"], db.now(), eid))
        for w in db.query("SELECT * FROM workpapers WHERE engagement_id=?", (eid,)):
            db.execute("INSERT INTO workpapers(engagement_id,topic_code,objective,conclusion,py_conclusion,py_type,not_applicable,na_reason,assigned_to,applicability) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (nid, w["topic_code"], w["objective"], "", w["conclusion"], w["conclusion_type"], 1 if w["applicability"] == "NA" else 0, w["na_reason"] if w["applicability"] == "NA" else "", w["assigned_to"], w["applicability"] or ""))
        n = 0
        for q in db.query("SELECT * FROM aqms WHERE engagement_id=? AND status<>'Closed'", (eid,)):
            db.execute("INSERT INTO aqms(engagement_id,topic_code,title,description,raised_by,raised_at) VALUES(?,?,?,?,?,?)",
                       (nid, q["topic_code"], "Carried forward: " + q["title"], f"{q['description']}\n[Prior-year response: {q['management_response'] or 'none'}]", u["id"], db.now())); n += 1
        db.log(nid, None, u["id"], "Rolled over from previous year", f"from engagement {eid}; {n} open queries carried forward")
        return jsonify(id=nid, carried_queries=n)

    @app.get("/api/engagements/<int:eid>")
    @auth
    def engagement(u, eid):
        e = db.one("SELECT * FROM engagements WHERE id=?", (eid,))
        if not e: return bad("Engagement not found.", 404)
        data = load_engagement(eid)
        return jsonify(engagement=dict(e), progress=engagement_progress(eid), adverse=adverse_register(eid, data), groups=GROUPS)

    @app.put("/api/engagements/<int:eid>/conclusion")
    @auth(roles=("Partner", "Senior"))
    def overall_conclusion(u, eid):
        b = request.get_json(force=True)
        db.execute("UPDATE engagements SET overall_type=?, overall_conclusion=?, basis_of_conclusion=? WHERE id=?",
                   (b.get("overall_type", ""), b.get("overall_conclusion", ""), b.get("basis_of_conclusion", ""), eid))
        db.log(eid, None, u["id"], "Updated overall conclusion"); return jsonify(ok=True)

    @app.put("/api/engagements/<int:eid>/materiality")
    @auth(roles=("Partner", "Senior"))
    def materiality(u, eid):
        try: m = float(str(request.get_json(force=True).get("materiality") or 0).replace(",", ""))
        except ValueError: return bad("Enter materiality as a number.")
        db.execute("UPDATE engagements SET materiality=? WHERE id=?", (m, eid)); db.log(eid, None, u["id"], "Changed materiality", str(m)); return jsonify(ok=True)

    @app.get("/api/engagements/<int:eid>/draft-paragraphs")
    @auth(roles=("Partner", "Senior"))
    def draft(u, eid): return jsonify(text=draft_paragraphs(eid))

    @app.get("/api/engagements/<int:eid>/log")
    @auth
    def activity_log(u, eid):
        nm = names(); rows = db.query("SELECT * FROM audit_log WHERE engagement_id=? ORDER BY id DESC LIMIT 400", (eid,))
        return jsonify([{"when": r["created_at"], "who": nm.get(r["user_id"], ""), "area": (TOPICS.get(r["topic_code"]) or {}).get("title", ""),
                         "code": r["topic_code"] or "", "action": r["action"], "detail": r["detail"] or ""} for r in rows])

    # ================= audit area =================
    @app.get("/api/engagements/<int:eid>/areas/<code>")
    @auth
    def area(u, eid, code):
        if code not in TOPICS or not valid_area(eid, code): return bad("Unknown audit area.", 404)
        wp = get_wp(eid, code); data = load_engagement(eid); topic = TOPICS[code]; nm = data["users"]
        srows = data["steps"].get(code, {}); notes = data["notes"].get(code, [])
        steps = []
        for i, (proc, asr) in enumerate(topic["procedures"], 1):
            s = srows.get(i, {})
            steps.append({"no": i, "procedure": proc, "assertions": [ASSERTIONS.get(x.strip(), x.strip()) for x in asr.split(",")],
                          "status": s.get("status", ""), "remarks": s.get("remarks", ""), "checked_at": s.get("checked_at", ""),
                          "checked_by": nm.get(s.get("checked_by"), ""),
                          "work_date": s.get("work_date") or "",
                          "notes": [{**n, "raised_by_name": nm.get(n["raised_by"], ""), "cleared_by_name": nm.get(n["cleared_by"], "")} for n in notes if n["step_no"] == i]})
        start = fy_start(data["eng"]["financial_year"]); files = []
        for f in data["files"].get(code, []):
            stale = False
            try: stale = bool(f.get("file_modified")) and bool(start) and datetime.strptime(f["file_modified"][:10], "%Y-%m-%d").date() < start
            except ValueError: pass
            sl = [int(x) for x in (f.get("step_list") or "").split(",") if x.strip().isdigit()] or ([f["step_no"]] if f.get("step_no") else [])
            files.append({k: v for k, v in f.items() if k != "stored_path"} | {"kind": kind_of(f["source_name"]), "uploaded_by_name": nm.get(f["uploaded_by"], ""), "steps": sl, "stale": stale})
        qs = [{**q, "raised_by_name": nm.get(q["raised_by"], "")} for q in data["aqms"].get(code, [])]
        wp_out = {k: wp.get(k) for k in ("objective", "conclusion", "conclusion_type", "workflow", "applicability", "na_reason", "evidence_na", "evidence_na_reason",
                                         "prepared_at", "reviewed_at", "rev", "due_date", "py_conclusion", "py_type", "assigned_to")}
        for k in ("prepared_by", "reviewed_by"): wp_out[k] = nm.get(wp.get(k), "")
        wp_out["assigned_name"] = nm.get(wp.get("assigned_to"), "")
        wp_out["applicability"] = wp.get("applicability") or ("NA" if wp.get("not_applicable") else "")
        wp_out["applicability_by"] = nm.get(wp.get("applicability_by"), ""); wp_out["applicability_at"] = wp.get("applicability_at") or ""
        return jsonify(topic={"code": code, "no": area_progress(code, data)["no"], "title": topic["title"], "objective": topic["objective"], "group": topic["group"]}, wp=wp_out, steps=steps,
                       evidence=files, queries=qs, notes=[{**n, "raised_by_name": nm.get(n["raised_by"], ""), "cleared_by_name": nm.get(n["cleared_by"], "")} for n in notes],
                       progress=area_progress(code, data), locked=locked(wp))

    def prog(eid, code): return area_progress(code, load_engagement(eid))

    @app.put("/api/engagements/<int:eid>/areas/<code>/step/<int:no>")
    @auth
    def save_step(u, eid, code, no):
        if code not in TOPICS or no < 1 or no > len(TOPICS[code]["procedures"]): return bad("Unknown step.", 404)
        wp = get_wp(eid, code)
        if (g := guard(wp)): return g
        b = request.get_json(force=True); status = b.get("status", ""); remarks = (b.get("remarks") or "").strip()
        if status not in ("", "Completed", "Exception", "NA"): return bad("Invalid status.")
        if status in ("Exception", "NA") and not remarks:
            return bad("Please record a remark – describe the exception, or give the reason this step is not applicable.")
        wd = (b.get("work_date") or "")[:10]
        try: datetime.strptime(wd, "%Y-%m-%d")
        except ValueError: wd = datetime.now().strftime("%Y-%m-%d")
        db.execute("""INSERT INTO checklist_status(workpaper_id,row_no,status,remarks,checked_by,checked_at,work_date) VALUES(?,?,?,?,?,?,?)
                      ON CONFLICT(workpaper_id,row_no) DO UPDATE SET status=excluded.status,remarks=excluded.remarks,checked_by=excluded.checked_by,checked_at=excluded.checked_at,work_date=excluded.work_date""",
                   (wp["id"], no, status, remarks, u["id"], db.now(), wd))
        db.log(eid, code, u["id"], "Step updated", f"Step {no}: {status or 'Pending'}")
        return jsonify(progress=prog(eid, code))

    @app.put("/api/engagements/<int:eid>/areas/<code>/workpaper")
    @auth
    def save_wp(u, eid, code):
        if code not in TOPICS: return bad("Unknown audit area.", 404)
        wp = get_wp(eid, code)
        if (g := guard(wp)): return g
        b = request.get_json(force=True)
        if b.get("rev") is not None and int(b["rev"]) != int(wp.get("rev") or 0):
            return bad("Someone else has just changed this module. Please reload the page and re-apply your edit.", 409)
        ctype = b.get("conclusion_type", "")
        if ctype and ctype not in CONCLUSION_TYPES: return bad("Invalid conclusion type.")
        if b.get("evidence_na") and not (b.get("evidence_na_reason") or "").strip(): return bad("Please give the reason evidence is not required.")
        db.execute("""UPDATE workpapers SET objective=?,conclusion=?,conclusion_type=?,evidence_na=?,evidence_na_reason=?,rev=rev+1 WHERE id=?""",
                   (b.get("objective", ""), (b.get("conclusion") or "").strip(), ctype,
                    int(bool(b.get("evidence_na"))), b.get("evidence_na_reason", ""), wp["id"]))
        db.log(eid, code, u["id"], "Conclusion / settings saved")
        return jsonify(progress=prog(eid, code), rev=int(wp.get("rev") or 0) + 1)

    @app.put("/api/engagements/<int:eid>/areas/<code>/applicability")
    @auth
    def set_applicability(u, eid, code):
        if code not in TOPICS or not valid_area(eid, code): return bad("Unknown audit area.", 404)
        wp = get_wp(eid, code); b = request.get_json(force=True); val = b.get("value")
        if val not in ("Applicable", "NA"): return bad("Choose Applicable or Not applicable.")
        if wp.get("workflow") in ("Compiled", "Reviewed"):
            return bad("This module is compiled / reviewed. Ask the Partner to send it back before changing applicability.", 423)
        reason = (b.get("reason") or "").strip()
        if val == "NA" and not reason: return bad("Please record why this module is not applicable to the entity.")
        db.execute("UPDATE workpapers SET applicability=?, not_applicable=?, na_reason=?, applicability_by=?, applicability_at=?, rev=rev+1 WHERE id=?",
                   (val, 1 if val == "NA" else 0, reason if val == "NA" else "", u["id"], db.now(), wp["id"]))
        db.log(eid, code, u["id"], "Marked " + ("applicable" if val == "Applicable" else "not applicable"), reason)
        return jsonify(progress=prog(eid, code))

    @app.put("/api/engagements/<int:eid>/areas/<code>/assign")
    @auth(roles=("Partner", "Senior"))
    def assign(u, eid, code):
        wp = get_wp(eid, code); b = request.get_json(force=True)
        db.execute("UPDATE workpapers SET assigned_to=?, due_date=? WHERE id=?", (int(b.get("user_id") or 0), b.get("due_date", ""), wp["id"]))
        db.log(eid, code, u["id"], "Assigned", names().get(int(b.get("user_id") or 0), "nobody")); return jsonify(ok=True)

    # ---- compile / review workflow ----
    @app.post("/api/engagements/<int:eid>/areas/<code>/workflow")
    @auth
    def workflow(u, eid, code):
        wp = get_wp(eid, code); b = request.get_json(force=True); action = b.get("action"); state = wp.get("workflow") or "Not Started"
        pr = prog(eid, code)
        if action == "compile":
            if state not in ("Not Started", "Returned"): return bad("This module is already compiled.")
            if pr.get("undecided"): return bad("Please confirm first whether this module is applicable to the entity.")
            if pr["state"] not in ("Complete", "Not applicable"):
                return bad("This module is not fully complete yet:\n• " + "\n• ".join(pr["pending"]))
            db.execute("UPDATE workpapers SET workflow='Compiled', prepared_by=?, prepared_at=?, reviewed_by=NULL, reviewed_at=NULL WHERE id=?", (u["id"], iso_to_disp(b.get("date")), wp["id"]))
            db.log(eid, code, u["id"], "Compiled"); return jsonify(ok=True)
        if u["role"] != "Partner": return bad("Only a Partner can review, return or reopen a module.", 403)
        if action == "review":
            if state != "Compiled": return bad("Only a compiled module can be reviewed.")
            if pr["open_notes"]: return bad(f"{pr['open_notes']} review note(s) are still open. Ask staff to clear them, or delete the notes, before completing the review.")
            db.execute("UPDATE workpapers SET workflow='Reviewed', reviewed_by=?, reviewed_at=? WHERE id=?", (u["id"], iso_to_disp(b.get("date")), wp["id"]))
            db.log(eid, code, u["id"], "Review complete"); return jsonify(ok=True)
        if action in ("return", "reopen"):
            reason = (b.get("reason") or "").strip()
            if not reason: return bad("Please state what needs to be corrected.")
            if state not in ("Compiled", "Reviewed"): return bad("Only a compiled or reviewed module can be sent back.")
            db.execute("UPDATE workpapers SET workflow='Returned', reviewed_by=NULL, reviewed_at=NULL, returned_note=? WHERE id=?", (reason, wp["id"]))
            db.execute("INSERT INTO review_notes(engagement_id,topic_code,step_no,note,raised_by,raised_at) VALUES(?,?,?,?,?,?)", (eid, code, 0, "Returned: " + reason, u["id"], db.now()))
            db.log(eid, code, u["id"], "Returned to staff", reason); return jsonify(ok=True)
        return bad("Unknown action.")

    # ---- review notes ----
    @app.post("/api/engagements/<int:eid>/areas/<code>/notes")
    @auth(roles=("Partner", "Senior"))
    def add_note(u, eid, code):
        b = request.get_json(force=True)
        if not (b.get("note") or "").strip(): return bad("Write the review note.")
        i = db.execute("INSERT INTO review_notes(engagement_id,topic_code,step_no,note,raised_by,raised_at) VALUES(?,?,?,?,?,?)",
                       (eid, code, int(b.get("step_no") or 0), b["note"].strip(), u["id"], db.now()))
        db.log(eid, code, u["id"], "Review note raised", b["note"][:80]); return jsonify(id=i)

    @app.put("/api/notes/<int:nid>")
    @auth
    def update_note(u, nid):
        n = db.one("SELECT * FROM review_notes WHERE id=?", (nid,))
        if not n: abort(404)
        b = request.get_json(force=True); act = b.get("action")
        if act == "clear":
            resp = (b.get("response") or "").strip()
            if not resp: return bad("Write how the note was addressed before clearing it.")
            db.execute("UPDATE review_notes SET status='Cleared', response=?, cleared_by=?, cleared_at=? WHERE id=?", (resp, u["id"], db.now(), nid))
        elif act == "reopen" and u["role"] in ("Partner", "Senior"):
            db.execute("UPDATE review_notes SET status='Open', cleared_by=NULL, cleared_at=NULL WHERE id=?", (nid,))
        elif act == "delete" and u["role"] == "Partner":
            db.execute("DELETE FROM review_notes WHERE id=?", (nid,))
        else: return bad("Not allowed.", 403)
        db.log(n["engagement_id"], n["topic_code"], u["id"], "Review note " + act); return jsonify(ok=True)

    # ================= evidence =================
    def save_upload(eid, code, f, u, desc="", steps="", modified=""):
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED: return None
        folder = db.EVIDENCE_DIR / str(eid) / code.replace(".", "_"); folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{uuid.uuid4().hex[:10]}_{safe_name(f.filename)}"; f.save(dest)
        first = int(steps.split(",")[0]) if steps and steps.split(",")[0].isdigit() else 0
        db.execute("INSERT INTO uploads(engagement_id,topic_code,source_name,stored_path,kind,uploaded_by,uploaded_at,description,step_no,step_list,size_bytes,file_modified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (eid, code, f.filename, str(dest), kind_of(f.filename), u["id"], db.now(), desc, first, steps, dest.stat().st_size, modified))
        return f.filename

    def parse_modified(raw):
        try: return datetime.fromtimestamp(int(raw) / 1000).strftime("%Y-%m-%d")
        except (TypeError, ValueError): return ""

    @app.post("/api/engagements/<int:eid>/areas/<code>/evidence")
    @auth
    def upload(u, eid, code):
        if code not in TOPICS: return bad("Unknown audit area.", 404)
        wp = get_wp(eid, code)
        if (g := guard(wp)): return g
        files = request.files.getlist("files")
        if not files: return bad("Choose one or more files to upload.")
        desc = (request.form.get("description") or "").strip(); steps = ",".join(x for x in (request.form.get("steps") or "").split(",") if x.strip().isdigit())
        mods = json.loads(request.form.get("modified") or "[]"); saved, rejected = [], []
        for i, f in enumerate(files):
            r = save_upload(eid, code, f, u, desc, steps, parse_modified(mods[i] if i < len(mods) else None))
            (saved if r else rejected).append(r or f.filename)
        db.log(eid, code, u["id"], "Evidence uploaded", ", ".join(saved))
        if rejected and not saved: return bad("File type not allowed: " + ", ".join(rejected))
        return jsonify(saved=saved, rejected=rejected)

    @app.post("/api/engagements/<int:eid>/bulk-evidence")
    @auth
    def bulk_upload(u, eid):
        """Files named like '8 bank statement.pdf' or 'WP8_...' (the working-paper number) go to that area; others are matched on area title words."""
        e = db.one("SELECT * FROM engagements WHERE id=?", (eid,)); codes = codes_for(e["entity_type"])
        files = request.files.getlist("files"); mods = json.loads(request.form.get("modified") or "[]")
        result = {"placed": {}, "unmatched": [], "rejected": [], "locked": [], "not_applicable": []}
        for i, f in enumerate(files):
            n = f.filename.replace("\\", "/").split("/")[-1]; f.filename = n; hay = (n + " " + (request.form.get("paths") or "")).lower()
            code = None; m = re.match(r"\s*(?:wp[ _-]?)?(\d{1,2})(?![\d]|\.\d)", n, re.I)
            if m and 1 <= int(m.group(1)) <= len(codes): code = codes[int(m.group(1)) - 1]
            if not code:
                for c in codes:
                    words = [w for w in re.split(r"[^a-z]+", TOPICS[c]["title"].lower()) if len(w) > 4]
                    if words and all(w in hay for w in words[:2]): code = c; break
            if not code: result["unmatched"].append(n); continue
            w_ = get_wp(eid, code)
            if locked(w_): result["locked"].append(n); continue
            if (w_.get("applicability") or "") != "Applicable": result["not_applicable"].append(n); continue
            ok = save_upload(eid, code, f, u, "Bulk upload", "", parse_modified(mods[i] if i < len(mods) else None))
            if not ok: result["rejected"].append(n); continue
            result["placed"].setdefault(code, []).append(n)
        db.log(eid, None, u["id"], "Bulk evidence upload", f"{sum(len(v) for v in result['placed'].values())} placed, {len(result['unmatched'])} unmatched")
        return jsonify(result)

    def evidence_row(fid):
        r = db.one("SELECT * FROM uploads WHERE id=?", (fid,))
        if not r: abort(404)
        return r

    @app.get("/api/evidence/<int:fid>/file")
    @auth
    def evidence_file(u, fid):
        r = evidence_row(fid); p = Path(r["stored_path"])
        if not p.exists(): abort(404)
        inline = p.suffix.lower() in INLINE and not request.args.get("download")
        return send_file(p, as_attachment=not inline, download_name=r["source_name"])

    @app.put("/api/evidence/<int:fid>")
    @auth
    def evidence_update(u, fid):
        r = evidence_row(fid)
        if (g := guard(get_wp(r["engagement_id"], r["topic_code"]))): return g
        b = request.get_json(force=True); steps = ",".join(str(int(x)) for x in b.get("steps", []))
        db.execute("UPDATE uploads SET description=?, step_list=?, step_no=? WHERE id=?", (b.get("description", ""), steps, int(b["steps"][0]) if b.get("steps") else 0, fid))
        return jsonify(ok=True)

    @app.delete("/api/evidence/<int:fid>")
    @auth
    def evidence_delete(u, fid):
        r = evidence_row(fid)
        if (g := guard(get_wp(r["engagement_id"], r["topic_code"]))): return g
        Path(r["stored_path"]).unlink(missing_ok=True)
        db.execute("DELETE FROM uploads WHERE id=?", (fid,)); db.log(r["engagement_id"], r["topic_code"], u["id"], "Evidence removed", r["source_name"])
        return jsonify(ok=True)

    @app.get("/api/evidence/<int:fid>/table")
    @auth
    def evidence_table(u, fid):
        r = evidence_row(fid); p = Path(r["stored_path"]); ext = p.suffix.lower()
        if ext not in (".xlsx", ".xlsm", ".xls", ".csv"): return bad("Preview is available for Excel and CSV files only.")
        try: df = pd.read_csv(p) if ext == ".csv" else pd.read_excel(p)
        except Exception as e: return bad(f"Could not read this file: {e}")
        eng = db.one("SELECT materiality FROM engagements WHERE id=?", (r["engagement_id"],)); checks = []
        if request.args.get("checks"):
            try: checks = run_checks(df, r["topic_code"], eng["materiality"] or 0)
            except Exception as e: return bad(f"Data checks could not run: {e}")
        head = df.head(100).fillna("").astype(str)
        return jsonify(rows=len(df), cols=[str(c) for c in df.columns], data=head.values.tolist(), checks=checks[:200])

    # ================= audit queries =================
    @app.post("/api/engagements/<int:eid>/areas/<code>/queries")
    @auth
    def add_query(u, eid, code):
        b = request.get_json(force=True)
        if not (b.get("title") or "").strip(): return bad("Please enter a short title for the query.")
        i = db.execute("INSERT INTO aqms(engagement_id,topic_code,title,description,raised_by,raised_at) VALUES(?,?,?,?,?,?)",
                       (eid, code, b["title"].strip(), b.get("description", ""), u["id"], db.now()))
        db.log(eid, code, u["id"], "Audit query raised", b["title"]); return jsonify(id=i)

    @app.put("/api/queries/<int:qid>")
    @auth
    def update_query(u, qid):
        q = db.one("SELECT * FROM aqms WHERE id=?", (qid,))
        if not q: abort(404)
        b = request.get_json(force=True); resp = (b.get("management_response") or "").strip(); close = bool(b.get("close"))
        if close and not resp: return bad("Record the management response before closing the query.")
        if close and u["role"] == "Junior": return bad("A Sr Staff or Partner must close the query after evaluating the response.", 403)
        status = "Closed" if close else ("Responded" if resp else "Open")
        db.execute("UPDATE aqms SET management_response=?, status=?, closed_by=?, closed_at=? WHERE id=?", (resp, status, u["id"] if close else None, db.now() if close else None, qid))
        db.log(q["engagement_id"], q["topic_code"], u["id"], "Audit query " + status.lower(), q["title"]); return jsonify(ok=True)

    # ================= exports =================
    def eng_or_404(eid):
        e = db.one("SELECT * FROM engagements WHERE id=?", (eid,))
        if not e: abort(404)
        return e

    @app.get("/api/engagements/<int:eid>/export/working-paper")
    @auth
    def export_wp(u, eid):
        e = eng_or_404(eid); db.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        name = safe_name(f"Audit_Working_Papers_{e['client_name']}_{e['financial_year']}").replace(" ", "_") + ".docx"
        build_working_paper(eid, db.EXPORT_DIR / name); db.log(eid, None, u["id"], "Generated working-paper file")
        return send_file(db.EXPORT_DIR / name, as_attachment=True, download_name=name)

    @app.get("/api/engagements/<int:eid>/export/observations")
    @auth
    def export_obs(u, eid):
        e = eng_or_404(eid); db.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        name = safe_name(f"Audit_Observations_{e['client_name']}_{e['financial_year']}").replace(" ", "_") + ".docx"
        build_observations(eid, db.EXPORT_DIR / name)
        return send_file(db.EXPORT_DIR / name, as_attachment=True, download_name=name)

    @app.get("/report/<int:eid>")
    @auth
    def html_report(u, eid):
        eng_or_404(eid); part = request.args.get("part", "full")
        db.log(eid, None, u["id"], "Opened printable report", part)
        return Response(build_html_report(eid, part), mimetype="text/html")

    @app.get("/api/engagements/<int:eid>/export/queries")
    @auth
    def export_queries(u, eid):
        rows = [{"No.": q["id"], "Audit area": TOPICS[q["topic_code"]]["title"], "Query": q["title"], "Detail": q["description"], "Status": q["status"],
                 "Management response": q["management_response"], "Raised on": q["raised_at"]} for q in db.query("SELECT * FROM aqms WHERE engagement_id=? ORDER BY id", (eid,))]
        e = eng_or_404(eid); db.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        name = safe_name(f"Audit_Query_Tracker_{e['client_name']}_{e['financial_year']}").replace(" ", "_") + ".xlsx"
        pd.DataFrame(rows, columns=["No.", "Audit area", "Query", "Detail", "Status", "Management response", "Raised on"]).to_excel(db.EXPORT_DIR / name, index=False)
        return send_file(db.EXPORT_DIR / name, as_attachment=True, download_name=name)

    # ================= backup / restore (Partner) =================
    @app.get("/api/backups")
    @auth(roles=("Partner",))
    def backups(u):
        bdir = db.RUNTIME / "backups"; bdir.mkdir(parents=True, exist_ok=True)
        return jsonify([{"name": p.name, "mb": round(p.stat().st_size / 1048576, 1)} for p in sorted(bdir.glob("AuditExec_backup_*.zip"), reverse=True)])

    @app.post("/api/backups")
    @auth(roles=("Partner",))
    def make_backup(u):
        p = db.backup_now(); db.log(None, None, u["id"], "Backup created", p.name); return jsonify(name=p.name)

    @app.get("/api/backups/<name>")
    @auth(roles=("Partner",))
    def get_backup(u, name):
        p = db.RUNTIME / "backups" / Path(name).name
        if not p.exists(): abort(404)
        return send_file(p, as_attachment=True, download_name=p.name)

    @app.post("/api/restore")
    @auth(roles=("Partner",))
    def restore(u):
        f = request.files.get("file")
        if not f: return bad("Choose a backup (.zip) file.")
        if (request.form.get("confirm") or "") != "RESTORE": return bad("Type RESTORE to confirm.")
        tmp = Path(tempfile.mkdtemp()) / "restore.zip"; f.save(tmp)
        try: db.restore_backup(tmp)
        except Exception as e: return bad(f"Restore failed: {e}")
        session.clear(); return jsonify(ok=True)

    return app
