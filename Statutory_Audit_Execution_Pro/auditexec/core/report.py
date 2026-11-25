"""Builds the complete audit working-paper file (Word) with adverse remarks highlighted."""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from . import database as db
from .progress import (TOPICS, ASSERTIONS, STEP_STATUS, CONCLUSION_TYPES, ADVERSE_TYPES, OVERALL_TYPES,
                       ADVERSE_PATTERN, NEGATED, load_engagement, area_progress, adverse_register)

NAVY = RGBColor(0x12, 0x2B, 0x4A); GOLD = RGBColor(0xB8, 0x86, 0x2B); RED = RGBColor(0xB4, 0x1E, 0x1E)
GREY = RGBColor(0x5B, 0x67, 0x78); GREEN = RGBColor(0x1E, 0x7A, 0x4C)
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
TAB_EXT = {".xlsx", ".xlsm", ".xls", ".csv"}
KIND = {".pdf": "PDF", ".doc": "Word", ".docx": "Word", ".xls": "Excel", ".xlsx": "Excel", ".xlsm": "Excel", ".csv": "CSV",
        ".jpg": "Image", ".jpeg": "Image", ".png": "Image", ".gif": "Image", ".bmp": "Image", ".webp": "Image",
        ".txt": "Text", ".ppt": "PowerPoint", ".pptx": "PowerPoint", ".msg": "Email", ".eml": "Email", ".zip": "Archive"}


def kind_of(name: str) -> str: return KIND.get(Path(name).suffix.lower(), "File")


def shade(cell, hex_fill: str):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill); tcPr.append(shd)


def set_cell(cell, text, bold=False, size=9, color=None, align=None, highlight=False):
    cell.text = ""; p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(1)
    if align: p.alignment = align
    if highlight: add_hl(p, "" if text is None else str(text), size=size, bold=bold)
    else:
        r = p.add_run("" if text is None else str(text)); r.bold = bold; r.font.size = Pt(size)
        if color: r.font.color.rgb = color


def add_hl(par, text: str, size=10, bold=False, force=False):
    """Write text, highlighting negative / disclaimer wording in yellow (whole text if force)."""
    text = text or ""
    if force:
        r = par.add_run(text); r.font.size = Pt(size); r.bold = bold
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED; return
    pos = 0
    for m in ADVERSE_PATTERN.finditer(text):
        if NEGATED.search(text[max(0, m.start() - 18):m.start()]): continue
        if m.start() > pos:
            r = par.add_run(text[pos:m.start()]); r.font.size = Pt(size); r.bold = bold
        r = par.add_run(m.group(0)); r.font.size = Pt(size); r.bold = True
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED
        pos = m.end()
    if pos < len(text):
        r = par.add_run(text[pos:]); r.font.size = Pt(size); r.bold = bold


def table(doc, headers, widths, header_fill="122B4A"):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for c, h, w in zip(t.rows[0].cells, headers, widths):
        set_cell(c, h, bold=True, size=9, color=RGBColor(255, 255, 255)); shade(c, header_fill); c.width = Inches(w)
    for col, w in zip(t.columns, widths): col.width = Inches(w)
    return t


def add_row(t, values, widths, fills=None, opts=None):
    kw = opts or {}
    cells = t.add_row().cells
    for i, (c, v, w) in enumerate(zip(cells, values, widths)):
        c.width = Inches(w)
        set_cell(c, v, **kw.get(i, {}))
        if fills and fills[i]: shade(c, fills[i])
    return cells


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs: r.font.color.rgb = NAVY; r.font.name = "Calibri"
    return h


def page_number_footer(section, label):
    p = section.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{label}  |  Page "); r.font.size = Pt(8); r.font.color.rgb = GREY
    for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        run = p.add_run(); run.font.size = Pt(8); run.font.color.rgb = GREY
        if t:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), t); run._r.append(el)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt; run._r.append(el)


def build_working_paper(eng_id: int, out_path: Path) -> dict:
    eng = db.one("SELECT * FROM engagements WHERE id=?", (eng_id,)); eng = dict(eng)
    data = load_engagement(eng_id)
    areas = [area_progress(c, data) for c in data["codes"]]
    register = adverse_register(eng_id, data)
    users = {u["id"]: u["name"] for u in db.query("SELECT id,name FROM users")}

    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.8); sec.top_margin = Inches(0.8); sec.bottom_margin = Inches(0.8)
    page_number_footer(sec, f"{eng['client_name']} – Statutory Audit Working Papers FY {eng['financial_year']} – Khare Deshmukh & Co.")

    # ---------- cover ----------
    for _ in range(4): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("KHARE DESHMUKH & CO."); r.bold = True; r.font.size = Pt(15); r.font.color.rgb = GOLD
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Chartered Accountants, Pune"); r.font.size = Pt(10); r.font.color.rgb = GREY
    for _ in range(3): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("AUDIT WORKING PAPERS"); r.bold = True; r.font.size = Pt(30); r.font.color.rgb = NAVY
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(eng["client_name"]); r.bold = True; r.font.size = Pt(20)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Financial year {eng['financial_year']}"); r.font.size = Pt(13); r.font.color.rgb = GREY
    for _ in range(3): doc.add_paragraph()
    t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in [("Type of entity", eng["entity_type"]), ("Reporting framework", eng["framework"]),
                 ("Overall materiality (₹)", f"{eng['materiality']:,.0f}" if eng["materiality"] else "Not yet determined"),
                 ("Target completion date", eng["deadline"] or "—"), ("File generated on", db.now()),
                 ("Partner review status", f"{sum(1 for a in areas if a['workflow'] == 'Reviewed' or a['na'])} of {len(areas)} modules reviewed")]:
        c = t.add_row().cells; set_cell(c[0], k, bold=True, size=10); shade(c[0], "EEF2F7"); set_cell(c[1], v, size=10)
        c[0].width = Inches(2.2); c[1].width = Inches(3.8)
    doc.add_page_break()

    # ---------- summary ----------
    heading(doc, "1. Executive summary", 1)
    live = [a for a in areas if not a["na"]]
    n_done = sum(1 for a in live if a["state"] == "Complete"); n_na = len(areas) - len(live)
    overall_pct = round(sum(a["pct"] for a in areas) / len(areas))
    n_high = sum(1 for r in register if r["severity"] == "High"); n_med = len(register) - n_high
    p = doc.add_paragraph()
    p.add_run(f"Audit file completion: {overall_pct}%.  ").bold = True
    p.add_run(f"{n_done} of {len(live)} applicable audit areas are fully complete; {n_na} area(s) marked not applicable. "
              f"{sum(a['open_queries'] for a in areas)} audit quer(ies) remain open.")
    p = doc.add_paragraph()
    r = p.add_run(f"Adverse / negative remarks: {n_high} high-priority and {n_med} for attention. ")
    r.bold = True; r.font.color.rgb = RED if register else GREEN
    p.add_run("These are listed in Section 2 and highlighted wherever they appear in the file." if register else "None were noted.")

    heading(doc, "Overall audit conclusion", 2)
    otype = eng.get("overall_type") or ""
    p = doc.add_paragraph(); p.add_run("Proposed basis: ").bold = True
    if otype:
        r = p.add_run(OVERALL_TYPES.get(otype, otype)); r.bold = True
        if otype != "Unmodified": r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED
    else:
        r = p.add_run("NOT YET RECORDED"); r.bold = True; r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED
    if (eng.get("overall_conclusion") or "").strip():
        add_hl(doc.add_paragraph(), eng["overall_conclusion"])
    if (eng.get("basis_of_conclusion") or "").strip():
        p = doc.add_paragraph(); p.add_run("Basis for the conclusion: ").bold = True; add_hl(p, eng["basis_of_conclusion"])
    p = doc.add_paragraph(); r = p.add_run("The conclusion above is the engagement team’s proposal and is subject to review and approval by the Partner. "
                                         "It is not an audit report."); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = GREY

    heading(doc, "Status of all audit areas", 2)
    W = [0.4, 1.8, 0.6, 0.6, 0.55, 1.0, 1.0, 1.0]
    t = table(doc, ["Ref", "Audit area", "Done", "Steps", "Files", "Conclusion", "Compiled by", "Reviewed by"], W)
    for a in areas:
        ct = "Not applicable" if a["na"] else (CONCLUSION_TYPES.get(a["conclusion_type"], "— pending —").split(" – ")[0])
        bad = a["conclusion_type"] in ADVERSE_TYPES
        pend = (not a["na"]) and a["state"] != "Complete"
        fills = [None, None, "FDECEC" if pend else None, None, None, "FDECEC" if (bad or not a["conclusion_type"] and not a["na"]) else None]
        fills = fills + ["FDECEC" if (not a["na"] and not a["compiled_by"]) else None, "FDECEC" if (not a["na"] and not a["reviewed_by"]) else None]
        add_row(t, [a["no"], a["title"], f"{a['pct']}%", f"{a['steps_done']}/{a['steps_total']}", a["files"], ct,
                    "n/a" if a["na"] else (a["compiled_by"] or "— pending —"), "n/a" if a["na"] else (a["reviewed_by"] or "— pending —")], W, fills)

    # ---------- adverse register ----------
    doc.add_page_break()
    heading(doc, "2. Register of adverse / negative / disclaimer remarks", 1)
    if not register:
        doc.add_paragraph("No exceptions, qualifications, disclaimers, adverse wording or open queries were recorded.")
    else:
        p = doc.add_paragraph("Red shading = high priority (exception identified, or conclusion qualified / disclaimer). "
                              "Amber shading = observation or wording that needs partner attention. Offending words are highlighted in yellow.")
        p.runs[0].font.size = Pt(9); p.runs[0].font.color.rgb = GREY
        W = [0.55, 1.35, 1.2, 2.6, 0.9]
        t = table(doc, ["Ref", "Audit area", "Where written", "Remark", "Priority"], W, header_fill="8E1B1B")
        for r in register:
            fill = "FBD5D5" if r["severity"] == "High" else "FFF1CC"
            c = add_row(t, [r["ref"], r["area"], r["where"], r["text"] or "(no remark text – see reason)", f"{r['severity']}\n{r['reason']}"], W,
                        [fill] * 5, opts={3: {"highlight": True}})

    # ---------- index ----------
    doc.add_page_break()
    heading(doc, "3. Index of working papers", 1)
    W = [0.6, 3.0, 1.3, 1.9]
    t = table(doc, ["WP Ref", "Audit area", "Status", "Sign-off"], W)
    for a in areas:
        wp = data["wps"].get(a["code"], {})
        sign = "Not applicable" if a["na"] else ({"Reviewed": f"Reviewed by {a['reviewed_by']}", "Compiled": f"Compiled by {a['compiled_by']}; awaiting review"}.get(a["workflow"], a["workflow"]))
        add_row(t, [f"WP {a['no']}", a["title"], a["state"], sign], W)

    # ---------- per-area working papers ----------
    for a in areas:
        code = a["code"]; topic = TOPICS[code]; wp = data["wps"].get(code, {})
        doc.add_page_break()
        heading(doc, f"WP {a['no']}  {topic['title']}", 1)
        meta = doc.add_paragraph()
        r = meta.add_run(f"Status: {a['state']} ({a['pct']}%)   |   Sign-off: {a['workflow']}"); r.font.size = Pt(9); r.font.color.rgb = GREY
        if a["na"]:
            p = doc.add_paragraph(); r = p.add_run("Marked NOT APPLICABLE to this engagement. "); r.bold = True
            p.add_run("Reason: " + (a.get("na_reason") or "not stated")); 
            if not a.get("na_reason"): p.runs[-1].font.highlight_color = WD_COLOR_INDEX.YELLOW
            continue
        if a.get("undecided"):
            p = doc.add_paragraph(); r = p.add_run("Applicability of this module to the entity has NOT been decided."); r.bold = True
            r.font.color.rgb = RED; r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            continue
        p = doc.add_paragraph(); p.add_run("Audit objective: ").bold = True; p.add_run(wp.get("objective") or topic["objective"])

        heading(doc, "A. Audit procedures performed", 2)
        W = [0.35, 2.55, 1.15, 1.05, 1.9]
        t = table(doc, ["#", "Audit step", "Checking", "Result", "Remarks / evidence examined"], W)
        srows = data["steps"].get(code, {})
        for i, (proc, asr) in enumerate(topic["procedures"], 1):
            s = srows.get(i, {}); stt = s.get("status", "")
            exp = ", ".join(ASSERTIONS.get(x.strip(), x.strip()) for x in asr.split(","))
            fill = "FBD5D5" if stt == "Exception" else ("FFF1CC" if find_hit(s.get("remarks")) else ("FDECEC" if not stt else None))
            col = RED if stt == "Exception" else (GREEN if stt == "Completed" else GREY)
            who = ""
            if stt and s.get("checked_by"):
                try: wd = datetime.strptime(s.get("work_date") or "", "%Y-%m-%d").strftime("%d-%b-%Y")
                except ValueError: wd = (s.get("checked_at") or "")[:11]
                who = f"\n{users.get(s['checked_by'], '')}, {wd}"
            add_row(t, [i, proc, exp, (STEP_STATUS[stt] if stt else "NOT DONE") + who, s.get("remarks", "")], W,
                    [fill] * 5, opts={3: {"bold": True, "color": col}, 4: {"highlight": True}})

        heading(doc, "B. Audit evidence attached", 2)
        files = data["files"].get(code, [])
        if not files:
            p = doc.add_paragraph()
            if wp.get("evidence_na"):
                p.add_run("Evidence marked as not required. Reason: " + (wp.get("evidence_na_reason") or "not stated"))
            else:
                r = p.add_run("No evidence uploaded."); r.bold = True; r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED
        else:
            W = [0.4, 2.2, 0.7, 2.6, 1.1]
            t = table(doc, ["#", "File name", "Type", "What it shows / relates to", "Uploaded"], W)
            for n, f in enumerate(files, 1):
                sl = [x for x in (f.get("step_list") or "").split(",") if x.strip()] or ([str(f["step_no"])] if f.get("step_no") else [])
                step = ("Steps " + ", ".join(sl) + ": ") if sl else ""
                add_row(t, [n, f["source_name"], kind_of(f["source_name"]), step + (f.get("description") or ""),
                            f"{users.get(f['uploaded_by'], '')}\n{f['uploaded_at']}"], W)
            for n, f in enumerate(files, 1):
                ext = Path(f["source_name"]).suffix.lower(); path = Path(f["stored_path"])
                if not path.exists(): continue
                if ext in IMG_EXT:
                    p = doc.add_paragraph(); r = p.add_run(f"Evidence {n}: {f['source_name']}"); r.bold = True; r.font.size = Pt(9)
                    try: doc.add_picture(str(path), width=Inches(4.8))
                    except Exception: doc.add_paragraph("(image could not be embedded – see original file)")
                elif ext in TAB_EXT:
                    try:
                        df = pd.read_csv(path, nrows=12) if ext == ".csv" else pd.read_excel(path, nrows=12)
                        df = df.iloc[:, :8]
                        p = doc.add_paragraph(); r = p.add_run(f"Evidence {n}: {f['source_name']} (first {len(df)} rows extract)"); r.bold = True; r.font.size = Pt(9)
                        tt = doc.add_table(rows=1, cols=len(df.columns)); tt.style = "Table Grid"
                        for c, h in zip(tt.rows[0].cells, df.columns): set_cell(c, h, bold=True, size=7); shade(c, "E2EAF3")
                        for _, row in df.iterrows():
                            cells = tt.add_row().cells
                            for c, v in zip(cells, row): set_cell(c, "" if pd.isna(v) else v, size=7)
                    except Exception: pass

        heading(doc, "C. Audit queries", 2)
        qs = data["aqms"].get(code, [])
        if not qs: doc.add_paragraph("No audit queries were raised.")
        else:
            W = [0.4, 1.6, 2.0, 1.9, 0.8]
            t = table(doc, ["#", "Query", "Detail", "Management response", "Status"], W)
            for q in qs:
                openq = q["status"] != "Closed"
                add_row(t, [q["id"], q["title"], q["description"], q["management_response"] or ("NO RESPONSE YET" if openq else ""), q["status"]], W,
                        ["FFF1CC" if openq else None] * 5, opts={2: {"highlight": True}, 3: {"highlight": True}})

        heading(doc, "D. Conclusion", 2)
        ctype = wp.get("conclusion_type", "")
        p = doc.add_paragraph(); p.add_run("Conclusion type: ").bold = True
        if ctype:
            r = p.add_run(CONCLUSION_TYPES[ctype]); r.bold = True
            if ctype != "Satisfactory": r.font.highlight_color = WD_COLOR_INDEX.YELLOW if ctype == "Observations" else WD_COLOR_INDEX.RED
            if ctype in ADVERSE_TYPES: r.font.color.rgb = RGBColor(255, 255, 255)
        else:
            r = p.add_run("NOT SELECTED"); r.bold = True; r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED
        c = wp.get("conclusion") or ""
        if c.strip(): add_hl(doc.add_paragraph(), c, size=10)
        else:
            r = doc.add_paragraph().add_run("Conclusion not written."); r.bold = True; r.font.highlight_color = WD_COLOR_INDEX.YELLOW; r.font.color.rgb = RED

        W = [1.7, 2.6, 2.6]
        t = table(doc, ["Sign-off", "Name", "Date / time"], W)
        for lbl, b, at in (("Compiled by", "prepared_by", "prepared_at"), ("Reviewed by (Partner)", "reviewed_by", "reviewed_at")):
            add_row(t, [lbl, users.get(wp.get(b), "— pending —"), wp.get(at) or "— pending —"], W,
                    ["FDECEC" if not wp.get(b) else None] * 3)
        rn = data["notes"].get(code, [])
        if rn:
            heading(doc, "E. Partner / senior review notes", 2)
            W2 = [0.4, 2.6, 2.6, 1.3]
            t = table(doc, ["#", "Review note", "Response by staff", "Status"], W2)
            for n in rn:
                add_row(t, [n["id"], n["note"], n["response"] or "—", n["status"]], W2, ["FFF1CC" if n["status"] == "Open" else None] * 4, opts={1: {"highlight": True}})

    # ---------- pending annex ----------
    pend = [a for a in areas if a["pending"]]
    doc.add_page_break()
    heading(doc, "4. Pending work at the time of generating this file", 1)
    if not pend:
        doc.add_paragraph("All applicable audit areas are complete.")
    else:
        p = doc.add_paragraph("The following items were still outstanding. This file should not be treated as final until they are cleared.")
        p.runs[0].font.color.rgb = RED
        W = [0.6, 2.0, 4.3]
        t = table(doc, ["Ref", "Audit area", "What is pending"], W)
        for a in pend: add_row(t, [a["no"], a["title"], "\n".join("• " + x for x in a["pending"])], W, ["FDECEC"] * 3)

    heading(doc, "Notes", 2)
    p = doc.add_paragraph("This working-paper file is a documentation aid generated from information entered by the engagement team. Professional judgement on materiality, "
                          "risk, accounting treatment and sufficiency of audit evidence remains with the engagement team and the Partner. Highlighted wording is flagged "
                          "automatically for attention and is not by itself an audit conclusion.")
    p.runs[0].font.size = Pt(8.5); p.runs[0].font.color.rgb = GREY
    doc.save(out_path)
    return {"pct": overall_pct, "adverse": len(register), "high": n_high, "pending_areas": len(pend)}


def find_hit(text):
    from .progress import find_adverse
    return bool(find_adverse(text or ""))


# ====================================================================
#  Draft reporting paragraphs, observations list and printable HTML report
# ====================================================================
def draft_paragraphs(eng_id: int) -> str:
    """Draft text from the adverse register. It is a starting point for the Partner, not an audit report."""
    eng = dict(db.one("SELECT * FROM engagements WHERE id=?", (eng_id,)))
    reg = adverse_register(eng_id)
    areas = {}
    for r in reg: areas.setdefault(r["code"], []).append(r)
    nums = {r["code"]: r["no"] for r in reg}
    data = load_engagement(eng_id)

    def cite(code):
        rs = areas[code]; txt = next((x["text"] for x in rs if x["where"] == "Conclusion" and x["text"]), None) or next((x["text"] for x in rs if x["text"]), "")
        return f"(WP {nums[code]}) {TOPICS[code]['title']}: {txt.strip()}".replace("\n", " ")
    hard = [c for c in areas if any(x["severity"] == "High" for x in areas[c])]
    soft = [c for c in areas if c not in hard]
    ctypes = {c: (data["wps"].get(c) or {}).get("conclusion_type", "") for c in areas}
    disclaim = [c for c in hard if ctypes.get(c) == "Disclaimer"]
    otype = eng.get("overall_type") or ""
    out = [f"DRAFT – for Partner's consideration only. Entity: {eng['client_name']}, year {eng['financial_year']}.", ""]
    if not reg:
        out.append("No exceptions, qualified / disclaimer conclusions or open queries are recorded. Unmodified opinion language would ordinarily be considered, subject to completion of all modules and the Partner's judgement.")
        return "\n".join(out)
    if hard:
        head = {"Adverse": "Basis for Adverse Opinion", "Disclaimer": "Basis for Disclaimer of Opinion"}.get(otype, "Basis for Qualified Opinion")
        out.append(head.upper()); out.append("")
        if otype == "Disclaimer" or (disclaim and not otype):
            out.append("We were unable to obtain sufficient appropriate audit evidence to provide a basis for an audit opinion in respect of the matters described below.")
        else:
            out.append("We conducted our audit in accordance with the Standards on Auditing. Our qualification arises from the following matter(s), which in our judgement are material:")
        for i, c in enumerate(hard, 1): out.append(f"  ({i}) {cite(c)}")
        out.append(""); out.append("Reference: SA 705 (Revised), Modifications to the Opinion in the Independent Auditor's Report. Quantify the effect where practicable, and state whether the matter is pervasive.")
    if soft:
        out.append(""); out.append("EMPHASIS OF MATTER / OTHER MATTERS – candidates for consideration"); out.append("")
        for i, c in enumerate(soft, 1): out.append(f"  ({i}) {cite(c)}")
        out.append(""); out.append("Reference: SA 706 (Revised). Include only matters that are appropriately presented or disclosed in the financial statements and are fundamental to users' understanding.")
    pend = sum(1 for a in [area_progress(c, data) for c in data["codes"]] if a["workflow"] != "Reviewed" and not a["na"])
    if pend: out.append(""); out.append(f"NOTE: {pend} module(s) have not yet been reviewed by the Partner; these paragraphs may change.")
    return "\n".join(out)


def build_observations(eng_id: int, out_path: Path):
    eng = dict(db.one("SELECT * FROM engagements WHERE id=?", (eng_id,))); reg = adverse_register(eng_id)
    doc = Document(); doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(10)
    s = doc.sections[0]; s.orientation = WD_ORIENT.LANDSCAPE; s.page_width, s.page_height = s.page_height, s.page_width
    s.left_margin = s.right_margin = Inches(0.7)
    p = doc.add_paragraph(); r = p.add_run("KHARE DESHMUKH & CO. – CHARTERED ACCOUNTANTS"); r.bold = True; r.font.color.rgb = GOLD
    heading(doc, f"Audit observations – {eng['client_name']} – FY {eng['financial_year']}", 1)
    doc.add_paragraph("List of exceptions, adverse remarks and open queries noted during the audit, for discussion with management.")
    W = [0.5, 1.7, 1.3, 3.6, 1.3, 1.3]
    t = table(doc, ["Sr.", "Audit area", "Where noted", "Observation", "Management response", "Action / date"], W)
    for i, r in enumerate(reg, 1):
        add_row(t, [i, r["area"], r["where"], r["text"], "", ""], W, ["FBD5D5" if r["severity"] == "High" else "FFF1CC"] * 6, opts={3: {"highlight": True}})
    if not reg: doc.add_paragraph("No observations were recorded.")
    doc.save(out_path)


def build_html_report(eng_id: int, part: str = "full") -> str:
    from html import escape as E
    eng = dict(db.one("SELECT * FROM engagements WHERE id=?", (eng_id,))); data = load_engagement(eng_id)
    areas = [area_progress(c, data) for c in data["codes"]]; reg = adverse_register(eng_id, data)
    users = data["users"]; live = [a for a in areas if not a["na"]]

    def hl(text):
        text = text or ""; out, pos = "", 0
        for m in ADVERSE_PATTERN.finditer(text):
            if NEGATED.search(text[max(0, m.start() - 18):m.start()]): continue
            out += E(text[pos:m.start()]) + "<mark>" + E(m.group(0)) + "</mark>"; pos = m.end()
        return (out + E(text[pos:])).replace("\n", "<br>")
    reviewed = sum(1 for a in live if a["workflow"] == "Reviewed")
    h = [f"""<!doctype html><html><head><meta charset="utf-8"><title>Statutory Audit Working Papers – {E(eng['client_name'])}</title><style>
@page{{size:A4;margin:16mm 14mm}}*{{box-sizing:border-box}}body{{font-family:Calibri,'Segoe UI',Arial,sans-serif;color:#1c2a3f;font-size:11.5px;margin:0;background:#eef1f6}}
.page{{background:#fff;max-width:900px;margin:18px auto;padding:34px 40px;box-shadow:0 2px 14px rgba(0,0,0,.1)}}
h1{{color:#0d1f3a;font-size:22px;margin:0 0 6px}}h2{{color:#0d1f3a;font-size:15px;border-bottom:2px solid #c9a24b;padding-bottom:3px;margin:22px 0 8px}}h3{{font-size:12.5px;color:#16315a;margin:14px 0 4px}}
table{{border-collapse:collapse;width:100%;margin:6px 0 10px}}th{{background:#0d1f3a;color:#fff;text-align:left;padding:5px 7px;font-size:10.5px}}td{{border:1px solid #d9e0ea;padding:5px 7px;vertical-align:top}}
tr.hi td{{background:#fbd5d5}}tr.me td{{background:#fff1cc}}td.pend{{background:#fdecec}}mark{{background:#ffe14d;color:#9b1c1c;font-weight:700}}
.muted{{color:#6b7a90}}.cover{{text-align:center;padding:90px 0 60px}}.cover .f{{letter-spacing:.25em;color:#b8862b;font-weight:700}}.cover h1{{font-size:34px;margin:50px 0 8px}}
.bar{{display:flex;gap:10px;margin:10px 0}}.kpi{{flex:1;border:1px solid #d9e0ea;border-radius:8px;padding:8px 10px}}.kpi b{{font-size:20px;display:block}}
.stamp{{display:inline-block;padding:3px 10px;border-radius:12px;font-weight:700;font-size:10.5px}}.s-ok{{background:#e3f5ec;color:#17895a}}.s-no{{background:#fde8e6;color:#c0392b}}
.noprint{{position:fixed;top:12px;right:16px}}.noprint button{{background:#c9a24b;color:#fff;border:0;border-radius:8px;padding:9px 16px;font-weight:700;cursor:pointer}}
@media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0;padding:0;max-width:none}}.noprint{{display:none}}.pb{{page-break-before:always}}tr{{page-break-inside:avoid}}}}</style></head><body>
<div class="noprint"><button onclick="window.print()">Print / Save as PDF</button></div>"""]
    if part != "summary":
        h.append(f"""<div class="page cover"><div class="f">KHARE DESHMUKH &amp; CO.</div><div class="muted">Chartered Accountants</div><h1>AUDIT WORKING PAPERS</h1>
<div style="font-size:20px;font-weight:700">{E(eng['client_name'])}</div><div class="muted" style="margin-top:6px">Financial year {E(eng['financial_year'])} · {E(eng['entity_type'])} · {E(eng['framework'])}</div>
<div style="margin-top:50px">Modules reviewed by Partner: <b>{reviewed} of {len(live)}</b></div><div class="muted">Generated {E(db.now())}</div></div>""")
    # partner summary
    h.append(f"""<div class="page {'pb' if part != 'summary' else ''}"><h1>Partner summary – {E(eng['client_name'])} FY {E(eng['financial_year'])}</h1>
<div class="bar"><div class="kpi"><b>{round(sum(a['pct'] for a in areas)/len(areas))}%</b>file complete</div><div class="kpi"><b>{sum(1 for a in live if a['workflow'] in ('Compiled','Reviewed'))}/{len(live)}</b>compiled</div>
<div class="kpi"><b>{reviewed}/{len(live)}</b>reviewed by Partner</div><div class="kpi"><b>{sum(1 for r in reg if r['severity']=='High')}</b>high-priority adverse</div><div class="kpi"><b>{sum(a['open_queries'] for a in areas)}</b>open queries</div></div>
<p><b>Proposed overall basis:</b> {E(OVERALL_TYPES.get(eng.get('overall_type') or '', 'NOT YET RECORDED'))}</p>{('<p>'+hl(eng['overall_conclusion'])+'</p>') if eng.get('overall_conclusion') else ''}
{('<p><b>Basis:</b> '+hl(eng['basis_of_conclusion'])+'</p>') if eng.get('basis_of_conclusion') else ''}
<h2>Adverse / negative / disclaimer remarks</h2>""")
    if reg:
        h.append("<table><tr><th>Ref</th><th>Audit area</th><th>Where written</th><th>Remark</th><th>Priority</th></tr>" + "".join(
            f"<tr class='{'hi' if r['severity']=='High' else 'me'}'><td>{E(r['ref'])}</td><td>{E(r['area'])}</td><td>{E(r['where'])}</td><td>{hl(r['text'])}</td><td><b>{r['severity']}</b><br>{E(r['reason'])}</td></tr>" for r in reg) + "</table>")
    else: h.append("<p>None recorded.</p>")
    h.append("<h2>Status of audit modules</h2><table><tr><th>Ref</th><th>Audit area</th><th>Done</th><th>Conclusion</th><th>Compiled by</th><th>Reviewed by Partner</th></tr>")
    for a in areas:
        ct = "Not applicable" if a["na"] else CONCLUSION_TYPES.get(a["conclusion_type"], "— pending —").split(" – ")[0]
        h.append(f"<tr><td>{a['no']}</td><td>{E(a['title'])}</td><td>{a['pct']}%</td><td>{E(ct)}</td><td class='{'pend' if not a['na'] and not a['compiled_by'] else ''}'>{E('n/a' if a['na'] else a['compiled_by'] or '— pending —')}</td>"
                 f"<td class='{'pend' if not a['na'] and not a['reviewed_by'] else ''}'>{E('n/a' if a['na'] else (a['reviewed_by'] + ' · ' + a['reviewed_at']) if a['reviewed_by'] else '— pending —')}</td></tr>")
    h.append("</table></div>")
    if part != "summary":
        for a in areas:
            code = a["code"]; topic = TOPICS[code]; wp = data["wps"].get(code, {})
            h.append(f"<div class='page pb'><h2 style='margin-top:0'>WP {a['no']} · {E(topic['title'])}</h2><p class='muted'>{E(topic['objective'])}</p>")
            if a["na"]: h.append(f"<p><b>Not applicable.</b> Reason: {hl(a['na_reason']) or '<mark>not stated</mark>'}</p></div>"); continue
            if a.get("undecided"): h.append("<p><mark>Applicability of this module has not been decided.</mark></p></div>"); continue
            h.append("<h3>A. Procedures performed</h3><table><tr><th>#</th><th>Audit step</th><th>Result</th><th>Remarks / evidence examined</th></tr>")
            sr = data["steps"].get(code, {})
            for i, (proc, _) in enumerate(topic["procedures"], 1):
                s = sr.get(i, {}); st = s.get("status", ""); cls = "hi" if st == "Exception" else ("" if st else "")
                h.append(f"<tr class='{cls}'><td>{i}</td><td>{E(proc)}</td><td><b>{E(STEP_STATUS[st]) if st else '<mark>NOT DONE</mark>'}</b>{('<br><span class="muted">' + E(users.get(s.get('checked_by'), '')) + ', ' + E(s.get('work_date') or '') + '</span>') if st and s.get('checked_by') else ''}</td><td>{hl(s.get('remarks'))}</td></tr>")
            h.append("</table><h3>B. Evidence</h3>")
            fl = data["files"].get(code, [])
            if fl:
                h.append("<table><tr><th>#</th><th>File</th><th>Type</th><th>Description</th><th>By</th></tr>" + "".join(
                    f"<tr><td>{n}</td><td>{E(f['source_name'])}</td><td>{kind_of(f['source_name'])}</td><td>{E(f.get('description') or '')}</td><td>{E(users.get(f['uploaded_by'], ''))}<br>{E(f['uploaded_at'])}</td></tr>" for n, f in enumerate(fl, 1)) + "</table>")
            else: h.append("<p><mark>No evidence uploaded.</mark></p>" if not wp.get("evidence_na") else f"<p>Not required: {E(wp.get('evidence_na_reason') or '')}</p>")
            qs = data["aqms"].get(code, [])
            if qs:
                h.append("<h3>C. Audit queries</h3><table><tr><th>#</th><th>Query</th><th>Management response</th><th>Status</th></tr>" + "".join(
                    f"<tr class='{'me' if q['status']!='Closed' else ''}'><td>{q['id']}</td><td><b>{E(q['title'])}</b><br>{hl(q['description'])}</td><td>{hl(q['management_response']) or '<mark>NO RESPONSE</mark>'}</td><td>{q['status']}</td></tr>" for q in qs) + "</table>")
            rn = data["notes"].get(code, [])
            if rn:
                h.append("<h3>Review notes</h3><table><tr><th>Note</th><th>Response</th><th>Status</th></tr>" + "".join(f"<tr class='{'me' if n['status']=='Open' else ''}'><td>{hl(n['note'])}</td><td>{E(n['response'] or '—')}</td><td>{n['status']}</td></tr>" for n in rn) + "</table>")
            ct = wp.get("conclusion_type", "")
            h.append(f"<h3>D. Conclusion</h3><p><b>{E(CONCLUSION_TYPES.get(ct, 'NOT SELECTED'))}</b></p><p>{hl(wp.get('conclusion')) or '<mark>Conclusion not written.</mark>'}</p>")
            h.append(f"<table><tr><th>Compiled by</th><th>Reviewed by (Partner)</th></tr><tr><td class='{'pend' if not a['compiled_by'] else ''}'>{E(a['compiled_by'] or '— pending —')}<br><span class='muted'>{E(a['compiled_at'])}</span></td>"
                     f"<td class='{'pend' if not a['reviewed_by'] else ''}'>{E(a['reviewed_by'] or '— pending —')}<br><span class='muted'>{E(a['reviewed_at'])}</span></td></tr></table></div>")
    h.append("</body></html>")
    return "".join(h)
