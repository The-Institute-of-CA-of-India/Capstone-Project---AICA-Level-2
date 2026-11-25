"""Completion tracking and adverse-remark detection for Statutory Audit Execution Pro."""
from __future__ import annotations
import json, re
from pathlib import Path
from . import database as db

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = json.loads((ROOT / "auditexec/data/programs.json").read_text(encoding="utf-8"))
TOPICS = {t["code"]: t for t in PROGRAM["topics"]}
GROUPS = PROGRAM["groups"]


def codes_for(entity_type: str) -> list[str]:
    """Audit areas applicable to the entity type, in display order (some areas are Company-only)."""
    order = {g: i for i, g in enumerate(GROUPS)}
    ts = [t for t in PROGRAM["topics"] if not t.get("entities") or entity_type in t["entities"]]
    return [t["code"] for t in sorted(ts, key=lambda t: (order.get(t["group"], 99), [int(x) for x in t["code"].split(".")]))]


def wp_numbers(codes: list[str]) -> dict[str, int]:
    """Logical sequential working-paper numbers (1, 2, 3 ...) in display order; internal codes stay unchanged."""
    return {c: i + 1 for i, c in enumerate(codes)}


ASSERTIONS = {
    "A": "Accuracy", "C": "Completeness", "E": "Existence", "RO": "Rights & Obligations", "CO": "Cut-off",
    "PD": "Presentation & Disclosure", "Cl": "Classification", "O": "Occurrence", "V": "Valuation", "Al": "Allocation",
}

STEP_STATUS = {"": "Pending", "Completed": "Completed – no issue noted", "Exception": "Exception identified", "NA": "Not applicable"}
CONCLUSION_TYPES = {
    "Satisfactory": "Satisfactory – audit objective achieved, no issues",
    "Observations": "Satisfactory with observations",
    "Qualified": "Qualified / Adverse – material issue noted",
    "Disclaimer": "Disclaimer – unable to obtain sufficient evidence",
}
ADVERSE_TYPES = {"Qualified", "Disclaimer"}
WEIGHTS = {"steps": 55, "evidence": 20, "conclusion": 25}

# Words / phrases in remarks or conclusions that signal a negative or limiting remark
ADVERSE_PATTERN = re.compile(
    r"(qualif\w*|disclaim\w*|adverse\w*|unable to|not able to|could not|cannot be|not provided|not received|not confirmed|not furnished|"
    r"not available|not produced|not submitted|not obtained|non[- ]?compliance|not complied|not in compliance|"
    r"violat\w*|breach\w*|misstate\w*|discrepanc\w*|shortfall|short provision|under[- ]?provi\w*|"
    r"scope (limitation|restriction)|limitation of scope|fraud\w*|irregular\w*|overdue|not reconciled|unreconciled|"
    r"material (weakness|uncertainty|misstatement)|deficien\w*|doubt\w*|emphasis of matter|"
    r"subject to|disagree\w*|not satisfactory|unsatisfactory|exception\w*|not recorded|not accounted|"
    r"not disclosed|non[- ]?disclosure|penalt\w*|default\w*|lapse\w*|delay\w*)", re.I)


NEGATED = re.compile(r"\b(no|nil|without|zero|not any|none)\s+(\w+\s+)?$", re.I)


def find_adverse(text: str) -> list[str]:
    """Adverse words found in the text, ignoring negated uses such as 'no exceptions noted'."""
    text = text or ""; hits = set()
    for m in ADVERSE_PATTERN.finditer(text):
        if NEGATED.search(text[max(0, m.start() - 18):m.start()]): continue
        hits.add(m.group(0).lower())
    return sorted(hits)


def load_engagement(eng_id: int) -> dict:
    """Everything needed to compute progress for every audit area of an engagement."""
    wps = {r["topic_code"]: dict(r) for r in db.query("SELECT * FROM workpapers WHERE engagement_id=?", (eng_id,))}
    steps: dict[str, dict[int, dict]] = {}
    for r in db.query("""SELECT c.*, w.topic_code FROM checklist_status c JOIN workpapers w ON w.id=c.workpaper_id
                         WHERE w.engagement_id=?""", (eng_id,)):
        steps.setdefault(r["topic_code"], {})[r["row_no"]] = dict(r)
    files: dict[str, list] = {}
    for r in db.query("SELECT * FROM uploads WHERE engagement_id=? ORDER BY id", (eng_id,)):
        files.setdefault(r["topic_code"], []).append(dict(r))
    aqms: dict[str, list] = {}
    for r in db.query("SELECT * FROM aqms WHERE engagement_id=? ORDER BY id", (eng_id,)):
        aqms.setdefault(r["topic_code"], []).append(dict(r))
    notes: dict[str, list] = {}
    for r in db.query("SELECT * FROM review_notes WHERE engagement_id=? ORDER BY id", (eng_id,)):
        notes.setdefault(r["topic_code"], []).append(dict(r))
    eng = dict(db.one("SELECT * FROM engagements WHERE id=?", (eng_id,)))
    users = {u["id"]: u["name"] for u in db.query("SELECT id,name FROM users")}
    return {"wps": wps, "steps": steps, "files": files, "aqms": aqms, "notes": notes, "eng": eng, "users": users,
            "codes": codes_for(eng.get("entity_type") or "")}


def area_progress(code: str, data: dict) -> dict:
    topic = TOPICS[code]; wp = data["wps"].get(code) or {}
    total = len(topic["procedures"]); srows = data["steps"].get(code, {})
    done = sum(1 for i in range(1, total + 1) if srows.get(i, {}).get("status") in ("Completed", "Exception", "NA"))
    exc = sum(1 for i in range(1, total + 1) if srows.get(i, {}).get("status") == "Exception")
    nfiles = len(data["files"].get(code, []))
    qs = data["aqms"].get(code, []); open_q = sum(1 for q in qs if q["status"] != "Closed")
    has_c = bool((wp.get("conclusion") or "").strip()); has_t = bool(wp.get("conclusion_type"))
    ev_na = bool(wp.get("evidence_na"))
    open_notes = sum(1 for n in data["notes"].get(code, []) if n["status"] == "Open")
    wf = wp.get("workflow") or "Not Started"
    names = data["users"]
    no = wp_numbers(data["codes"]).get(code, 0)
    appl = wp.get("applicability") or ("NA" if wp.get("not_applicable") else "")
    extra = {"no": no, "applicability": appl, "group": topic["group"], "workflow": wf, "open_notes": open_notes,
             "compiled_by": names.get(wp.get("prepared_by"), ""), "compiled_at": wp.get("prepared_at") or "",
             "reviewed_by": names.get(wp.get("reviewed_by"), ""), "reviewed_at": wp.get("reviewed_at") or "",
             "assigned_to": wp.get("assigned_to") or 0, "assigned_name": names.get(wp.get("assigned_to"), ""), "due_date": wp.get("due_date") or ""}

    if appl == "":
        return {"code": code, "title": topic["title"], "na": False, "undecided": True, "pct": 0, "state": "Not decided",
                "tabs": {k: "empty" for k in ("steps", "evidence", "queries", "conclusion")},
                "pending": ["Confirm whether this module is applicable to the entity"], "steps_done": 0, "steps_total": total,
                "files": nfiles, "open_queries": 0, "exceptions": 0, "conclusion_type": "", **extra}
    if appl == "NA":
        return {"code": code, "undecided": False, "title": topic["title"], "na": True, "pct": 100, "state": "Not applicable",
                "tabs": {k: "na" for k in ("steps", "evidence", "queries", "conclusion")},
                "pending": [], "steps_done": total, "steps_total": total, "files": nfiles,
                "open_queries": 0, "exceptions": 0,
                "conclusion_type": "", "na_reason": wp.get("na_reason", ""), **extra}

    tabs = {
        "steps": "complete" if done == total else ("partial" if done else "empty"),
        "evidence": "complete" if (nfiles or ev_na) else "empty",
        "queries": "complete" if open_q == 0 else "partial",
        "conclusion": "complete" if (has_c and has_t) else ("partial" if (has_c or has_t) else "empty"),
    }
    frac = {
        "steps": done / total if total else 1,
        "evidence": 1 if (nfiles or ev_na) else 0,
        "queries": ((len(qs) - open_q) / len(qs)) if qs else 1,
        "conclusion": (0.5 if has_c else 0) + (0.5 if has_t else 0),
    }
    pct = round(sum(WEIGHTS[k] * frac[k] for k in WEIGHTS))
    if open_q and pct >= 100: pct = 95   # open audit queries stop an area showing 100%
    pending = []
    if done < total: pending.append(f"{total - done} of {total} audit steps not yet completed")
    if not (nfiles or ev_na): pending.append("No audit evidence uploaded (or marked as not required)")
    if not has_c: pending.append("Conclusion not written")
    if not has_t: pending.append("Conclusion type not selected")
    if open_q: pending.append(f"{open_q} audit quer{'y' if open_q == 1 else 'ies'} still open")
    if open_notes: pending.append(f"{open_notes} review note{'s' if open_notes != 1 else ''} to be cleared")
    state = "Complete" if (all(v == "complete" for v in tabs.values()) and not open_notes) else ("Not started" if pct == 0 else "In progress")
    return {"code": code, "title": topic["title"], "na": False, "undecided": False, "pct": pct, "state": state, "tabs": tabs,
            "pending": pending, "steps_done": done, "steps_total": total, "files": nfiles, "open_queries": open_q,
            "exceptions": exc, "conclusion_type": wp.get("conclusion_type", ""), **extra}


def engagement_progress(eng_id: int) -> dict:
    data = load_engagement(eng_id)
    areas = [area_progress(c, data) for c in data["codes"]]
    n = len(areas)
    live = [a for a in areas if not a["na"]]
    return {
        "areas": areas,
        "overall_pct": round(sum(a["pct"] for a in areas) / n) if n else 0,
        "complete": sum(1 for a in areas if a["state"] in ("Complete", "Not applicable")),
        "in_progress": sum(1 for a in areas if a["state"] == "In progress"),
        "undecided": sum(1 for a in areas if a.get("undecided")),
        "not_started": sum(1 for a in areas if a["state"] in ("Not started", "Not decided")),
        "total_areas": n,
        "compiled": sum(1 for a in live if a["workflow"] == "Compiled"),
        "reviewed": sum(1 for a in live if a["workflow"] == "Reviewed"),
        "returned": sum(1 for a in live if a["workflow"] == "Returned"),
        "live_areas": len(live),
        "steps_done": sum(a["steps_done"] for a in areas), "steps_total": sum(a["steps_total"] for a in areas),
        "files": sum(a["files"] for a in areas), "open_queries": sum(a["open_queries"] for a in areas),
        "open_notes": sum(a["open_notes"] for a in areas),
        "pending_total": sum(len(a["pending"]) for a in areas),
    }


def adverse_register(eng_id: int, data: dict | None = None) -> list[dict]:
    """Every negative / qualifying / disclaimer-type remark across the file, with where it was written."""
    data = data or load_engagement(eng_id); out = []; nums = wp_numbers(data["codes"])
    for code in data["codes"]:
        topic = TOPICS[code]; wp = data["wps"].get(code) or {}
        if wp.get("not_applicable") or wp.get("applicability") == "NA": continue
        title = topic["title"]
        for i, (proc, _) in enumerate(topic["procedures"], 1):
            s = data["steps"].get(code, {}).get(i)
            if not s: continue
            hits = find_adverse(s.get("remarks", ""))
            if s["status"] == "Exception":
                out.append({"code": code, "no": nums[code], "area": title, "where": f"Audit step {i}", "text": s.get("remarks", ""),
                            "severity": "High", "reason": "Marked as exception", "ref": f"{nums[code]}.{i}"})
            elif hits:
                out.append({"code": code, "no": nums[code], "area": title, "where": f"Audit step {i} remarks", "text": s.get("remarks", ""),
                            "severity": "Medium", "reason": "Wording: " + ", ".join(hits), "ref": f"{nums[code]}.{i}"})
        ctype = wp.get("conclusion_type", "")
        hits = find_adverse(wp.get("conclusion", ""))
        if ctype in ADVERSE_TYPES:
            out.append({"code": code, "no": nums[code], "area": title, "where": "Conclusion", "text": wp.get("conclusion", ""),
                        "severity": "High", "reason": CONCLUSION_TYPES[ctype].split(" – ")[0], "ref": f"{nums[code]}.C"})
        elif ctype == "Observations" or hits:
            out.append({"code": code, "no": nums[code], "area": title, "where": "Conclusion", "text": wp.get("conclusion", ""),
                        "severity": "Medium", "reason": "Observations noted" if ctype == "Observations" else "Wording: " + ", ".join(hits),
                        "ref": f"{nums[code]}.C"})
        for q in data["aqms"].get(code, []):
            if q["status"] != "Closed":
                out.append({"code": code, "no": nums[code], "area": title, "where": f"Audit query #{q['id']} (open)", "text": f"{q['title']} – {q['description']}",
                            "severity": "Medium", "reason": "Query unresolved", "ref": f"{nums[code]}.Q{q['id']}"})
    out.sort(key=lambda r: (r["severity"] != "High", r["no"]))
    return out


OVERALL_TYPES = {
    "Unmodified": "Unmodified – financial statements give a true and fair view",
    "Qualified": "Qualified – except for the matters described below",
    "Adverse": "Adverse – financial statements do not give a true and fair view",
    "Disclaimer": "Disclaimer – unable to obtain sufficient appropriate audit evidence",
}
