"""
Bank statement transaction table (CSV) from a redacted PDF.

Works on the text rows of the redacted output (so only redacted text ever reaches the table) and
handles the common Indian layouts:
  * separate Withdrawal / Deposit columns (HDFC, ICICI, SBI, Axis, ...), with or without 0.00 fillers;
  * one Amount column marked Dr / Cr, either attached ("1,850.00(Dr)") or in its own column (Kotak, Axis);
  * a serial-number column before the date (ICICI), a value date after it, narrations wrapping onto
    the following lines, headers on two lines, tables running over several pages;
  * dates such as 01/04/25, 01-04-2025, 01.04.2025, 1 Apr 2025, 01-Apr-25, 2025-04-01.

Which amount is a debit and which a credit is decided first from the running balance
(previous balance - debit + credit = balance), then from an explicit Dr/Cr mark, and only then from
the column positions under the header. Every row says whether its balance was verified.
"""

from __future__ import annotations

import re

from . import pdf

_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*"
_DATE_PAT = (rf"\d{{1,2}}[-/.]\d{{1,2}}[-/.](?:\d{{4}}|\d{{2}})"
             rf"|\d{{1,2}}[-/. ]?{_MON}[-/., ]{{0,2}}(?:\d{{4}}|\d{{2}})"
             rf"|\d{{4}}-\d{{2}}-\d{{2}}")
DATE = re.compile(rf"(?i)(?<![\w/.-])(?:{_DATE_PAT})(?![\w/])")
LEAD = re.compile(rf"(?i)^\s*(?:(\d{{1,5}})\.?\s+)?((?:{_DATE_PAT}))(?![\w/])")
AMT = re.compile(r"(?<![\w.,/:-])(-)?(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{2})(?![\d,]|\.\d)"
                 r"\s?(?:\(?\s?(Dr|Cr|DR|CR|dr|cr)\.?\s?\)?(?![A-Za-z]))?")
DRCR = re.compile(r"(?<![A-Za-z])(Dr|Cr|DR|CR)\.?(?![A-Za-z])")

HDR = {
    "debit": re.compile(r"(?i)\b(?:withdrawals?|debits?|paid\s*out)"),
    "credit": re.compile(r"(?i)\b(?:deposits?|credits?|paid\s*in)"),
    "balance": re.compile(r"(?i)\bbalance\b"),
    "amount": re.compile(r"(?i)\bamount\b"),
}
# text columns: used to split the value date and cheque/reference number out of the narration
TXT_HDR = {
    "narr": re.compile(r"(?i)\b(?:narration|particulars|description|transaction\s+remarks|remarks|details)\b"),
    "ref": re.compile(r"(?i)(?:\bchq\b|\bcheque\b|\bref(?:erence)?\b)"),
    "vdate": re.compile(r"(?i)\bvalue\s*(?:dt|date)?\b"),
}
DATE_HDR = re.compile(r"(?i)\b(?:date|dt\.?|txn|tran)\b")
STOP = re.compile(r"(?i)\b(?:closing\s+balance|statement\s+summary|grand\s+total|total\b|page\s+\d+(?:\s+of\s+\d+)?"
                  r"|computer\s+generated|end\s+of\s+statement|abbreviations)")
OPENING = re.compile(r"(?i)\b(?:opening\s+balance|balance\s+(?:b/?f|brought\s+forward|as\s+on)|brought\s+forward|b/f)\b")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _span_x(boxes, s, e):
    bs = [b for b in boxes[s:e] if b]
    return (min(b[0] for b in bs), max(b[2] for b in bs)) if bs else None


def _header(rows, i):
    """Column positions if row i (alone or with the next row) is a table header."""
    page, text, boxes = rows[i]
    cand = [(text, boxes)]
    if i + 1 < len(rows) and rows[i + 1][0] == page and not LEAD.match(rows[i + 1][1]) and not AMT.search(rows[i + 1][1]):
        cand.append((rows[i + 1][1], rows[i + 1][2]))
    if AMT.search(text) or LEAD.match(text):
        return None
    cols: dict[str, tuple[float, float]] = {}
    has_date = False
    for t, b in cand:
        has_date |= bool(DATE_HDR.search(t))
        for k, rx in list(HDR.items()) + list(TXT_HDR.items()):
            for m in rx.finditer(t):
                x = _span_x(b, m.start(), m.end())
                if x and k not in cols:
                    cols[k] = x
    if "debit" in cols and "credit" in cols:
        # "Withdrawal Amount"/"Deposit Amount": 'amount' is part of those headers, not its own column
        cols.pop("amount", None)
        # one combined header such as "Withdrawal (Dr)/ Deposit (Cr)" is a single amount column
        if abs(cols["debit"][0] - cols["credit"][0]) < 1 or _overlap_words(cand, cols):
            x0 = min(cols["debit"][0], cols["credit"][0])
            x1 = max(cols["debit"][1], cols["credit"][1])
            cols.pop("debit")
            cols.pop("credit")
            cols["amount"] = (x0, x1)
    n_amount_cols = sum(k in cols for k in ("debit", "credit", "amount"))
    if has_date and "balance" in cols and n_amount_cols >= 1:
        return cols
    if has_date and "debit" in cols and "credit" in cols:
        return cols
    return None


def _overlap_words(cand, cols):
    """True when the debit and credit keywords sit in one header cell ('Withdrawal (Dr)/ Deposit (Cr)')."""
    for t, _ in cand:
        if re.search(r"(?i)(withdrawal|debit)\s*(\(dr\))?\s*/\s*(deposit|credit)", t):
            return True
    return False


def _nearest_col(cols, x):
    """Column for an amount occupying x = (x0, x1): numbers are usually right-aligned under their header."""
    best, bd = None, None
    for k, (c0, c1) in cols.items():
        if x[0] <= c1 + 2 and x[1] >= c0 - 2:            # overlaps the header word
            d = 0.0
        else:
            d = min(abs(x[1] - c1), abs((x[0] + x[1]) / 2 - (c0 + c1) / 2))
        if bd is None or d < bd:
            best, bd = k, d
    return best


# --------------------------------------------------------------------------
# Rows with geometry
# --------------------------------------------------------------------------
FOOTER = re.compile(r"(?i)(?:www\.|https?://|toll[\s-]*free|\bdial\b|customer\s+care|never\s+share|registered\s+mobile"
                    r"|call\s+us|system\s+generated|computer\s+generated|\bdisclaimer\b|\blegends?\b|abbreviations"
                    r"|end\s+of\s+statement|statement\s+summary|\bpage\s+\d+(?:\s+of\s+\d+)?\b|^\s*\*{2,})")
SUMMARY = re.compile(r"(?i)\b(?:closing\s+balance|grand\s+total|total\s+(?:debits?|credits?|withdrawals?|deposits?)"
                     r"|dr\s+count|cr\s+count)\b")


def _geometry(output_pdf: bytes):
    rows = []
    for page, text, boxes in pdf.page_rows(output_pdf):
        bs = [b for b in boxes if b]
        if not bs or not text.strip():
            continue
        ys = sorted((b[1] + b[3]) / 2 for b in bs)
        rows.append({"page": page, "text": text, "boxes": boxes, "y": ys[len(ys) // 2],
                     "y0": min(b[1] for b in bs), "y1": max(b[3] for b in bs),
                     "x0": min(b[0] for b in bs), "x1": max(b[2] for b in bs)})
    return rows


def _hrules(output_pdf: bytes) -> dict:
    """y positions of horizontal lines drawn across the table (row separators), per page."""
    import pymupdf
    out = {}
    try:
        with pymupdf.open(stream=output_pdf, filetype="pdf") as d:
            for page in d:
                ys = []
                for dr in page.get_drawings():
                    for it in dr["items"]:
                        if it[0] == "l" and abs(it[1].y - it[2].y) < 1 and abs(it[1].x - it[2].x) > 60:
                            ys.append(it[1].y)
                        elif it[0] == "re" and it[1].height < 2 and it[1].width > 60:
                            ys.append(it[1].y0)
                ys = sorted(ys)
                merged = []
                for y in ys:
                    if not merged or y - merged[-1] > 2:
                        merged.append(y)
                out[page.number + 1] = merged
    except Exception:
        pass
    return out


def _cells(text, start=0, end=None):
    """Cells of a row: runs of text separated by two or more spaces."""
    end = len(text) if end is None else end
    for m in re.finditer(r"\S+(?: \S+)*", text[start:end]):
        yield start + m.start(), start + m.end(), m.group(0)


INT_AMT = re.compile(r"(?<![\w.,/:-])(-)?(\d{1,9})(?![\w.,/:-])\s?(?:\(?(Dr|Cr|DR|CR)\.?\)?(?![A-Za-z]))?")


def _amounts(text, boxes, start=0, cols=None):
    amts = []
    for m in AMT.finditer(text, start):
        x = _span_x(boxes, m.start(2), m.end(2)) or (0.0, 0.0)
        amts.append({"v": _num(m.group(2)), "neg": bool(m.group(1)), "mark": (m.group(3) or "").lower(),
                     "x": x, "s": m.start(), "e": m.end(), "text": m.group(2)})
    if cols:
        # whole-rupee amounts ('500') are accepted only when they sit under an amount column
        amount_cols = [v for k, v in cols.items() if k in ("debit", "credit", "balance", "amount")]
        for m in INT_AMT.finditer(text, start):
            if any(a["s"] <= m.start() < a["e"] for a in amts):
                continue
            x = _span_x(boxes, m.start(2), m.end(2))
            if not x or not any(x[1] >= c0 - 12 and x[0] <= c1 + 12 for c0, c1 in amount_cols):
                continue
            amts.append({"v": float(m.group(2)), "neg": bool(m.group(1)), "mark": (m.group(3) or "").lower(),
                         "x": x, "s": m.start(), "e": m.end(), "text": m.group(2)})
        amts.sort(key=lambda a: a["s"])
    for d in DRCR.finditer(text, start):                  # stand-alone Dr / Cr column
        if any(a["s"] <= d.start() < a["e"] for a in amts):
            continue
        before = [a for a in amts if a["e"] <= d.start()]
        if before and not before[-1]["mark"]:
            before[-1]["mark"] = d.group(1).lower()
    return amts


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def extract(output_pdf: bytes, strict: bool = False) -> list[dict]:
    rows = _geometry(output_pdf)
    rules = _hrules(output_pdf)
    cols: dict = {}
    seen_header = False
    opening = None
    mode = None                      # "top": date on a transaction's first line; "middle": date inside its cell
    txns: list[dict] = []
    narr_left = None
    by_page: dict = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)

    for page in sorted(by_page):
        prs = by_page[page]
        # header(s) on this page
        start_y = None
        skip = set()
        for i, r in enumerate(prs):
            if i in skip:
                continue
            tup = [(x["page"], x["text"], x["boxes"]) for x in prs]
            own = DATE_HDR.search(r["text"]) or any(rx.search(r["text"]) for rx in HDR.values())
            h = _header(tup, i) if own else None
            if h:
                cols, seen_header = h, True
                hy = r["y1"]
                skip.add(i)
                for j in (i + 1, i + 2):                    # header continued on one or two more lines
                    if j < len(prs) and _header_tail(prs[j]["text"]) and prs[j]["y"] - prs[j - 1]["y"] < 3 * (r["y1"] - r["y0"] + 2):
                        skip.add(j)
                        hy = prs[j]["y1"]
                    else:
                        break
                start_y = hy
        # opening balance, anchors and candidate lines
        anchors, lines = [], []
        for i, r in enumerate(prs):
            if i in skip:
                continue
            t = r["text"]
            om = OPENING.search(t)
            if om and not LEAD.match(t):                    # opening balance, also when printed above the table
                m = AMT.search(t, om.end())
                if m and opening is None:
                    opening = _signed(m)
                continue
            if start_y is not None and r["y"] <= start_y and not LEAD.match(t):
                continue
            lead = LEAD.match(t)
            if lead and (cols or AMT.search(t)):
                anchors.append(r)
                r["lead"] = lead
            else:
                lines.append(r)
        if not anchors:
            if txns and cols and mode == "top":
                _continuation(txns[-1], lines, narr_left, cols)
            continue
        # typical line pitch in the table
        ys = sorted(x["y"] for x in anchors + lines if x["y"] >= anchors[0]["y"] - 60)
        dys = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > 1)
        pitch = dys[len(dys) // 4] if dys else 10.0          # lower quartile = the line height
        if narr_left is None:
            narr_left = _narr_left(anchors, cols)
        top_a, bot_a = anchors[0]["y"], anchors[-1]["y"]
        # keep lines inside the table: above the first anchor only close to it, below the last only until a gap
        inside = []
        for r in sorted(lines, key=lambda x: x["y"]):
            if FOOTER.search(r["text"]) or SUMMARY.search(r["text"]):
                continue
            if narr_left is not None and r["x1"] < narr_left - 3:
                continue                                   # left of the narration (date / serial columns)
            inside.append(r)
        kept = [r for r in inside if top_a - 3.2 * pitch <= r["y"] <= bot_a]
        last_y = bot_a
        for r in [x for x in inside if x["y"] > bot_a]:
            if r["y"] - last_y > 2.2 * pitch:
                break
            kept.append(r)
            last_y = r["y"]
        if mode is None:
            pre = [r for r in kept if r["y"] < top_a - 0.5 and (start_y is None or r["y"] > start_y)]
            mode = "middle" if pre else "top"
        page_rules = [y for y in rules.get(page, []) if top_a - 4 * pitch <= y <= last_y + 2 * pitch]
        use_rules = len(page_rules) >= max(2, len(anchors) // 2)
        groups = {id(a): [] for a in anchors}
        orphans = []
        for r in kept:
            target = None
            if use_rules:
                k = sum(1 for y in page_rules if y < r["y"])
                same = [a for a in anchors if sum(1 for y in page_rules if y < a["y"]) == k]
                if same:
                    target = same[0]
            if target is None:
                if mode == "top":
                    above = [a for a in anchors if a["y"] <= r["y"] + 1]
                    target = above[-1] if above else None
                else:
                    target = min(anchors, key=lambda a: (abs(a["y"] - r["y"]), a["y"] < r["y"]))
            if target is None:
                orphans.append(r)
            else:
                groups[id(target)].append(r)
        if orphans and txns:                               # narration carried over from the previous page
            _continuation(txns[-1], orphans, narr_left, cols)
        for a in anchors:
            txns.append(_build(a, sorted(groups[id(a)] + [a], key=lambda x: x["y"]), cols, narr_left))
    return _finish(txns, cols, opening, seen_header, strict)


def _narr_left(anchors, cols):
    xs = []
    for a in anchors:
        t, boxes, lead = a["text"], a["boxes"], a["lead"]
        pos = lead.end()
        vd = DATE.match(t[pos:].lstrip())
        if vd:
            pos += (len(t[pos:]) - len(t[pos:].lstrip())) + vd.end()
        for s, e, cell in _cells(t, pos):
            if AMT.fullmatch(cell.strip()):
                break
            x = _span_x(boxes, s, e)
            if x and not _in_col(cols, "ref", x):
                xs.append(x[0])
                break
    xs.sort()
    return xs[len(xs) // 2] if xs else None


def _in_col(cols, key, x, pad=8):
    if key not in cols or not x:
        return False
    c0, c1 = cols[key]
    mid = (x[0] + x[1]) / 2
    return c0 - pad <= mid <= c1 + pad


def _row_text(r, cols, narr_left, txn, start=0, amts=()):
    """Narration text of one row (amount cells left out, wherever the narration column is); cheque/ref numbers
    and value dates under their own headers go to their columns."""
    t, boxes = r["text"], r["boxes"]
    parts = []
    for s, e, cell in _cells(t, start):
        if any(a["s"] < e and s < a["e"] for a in amts):
            rest = cell
            for a in sorted(amts, key=lambda a: -a["s"]):          # drop the amount, keep any words around it
                if a["s"] < e and s < a["e"]:
                    rest = rest[:max(0, a["s"] - s)] + " " + rest[max(0, a["e"] - s):]
            rest = re.sub(r"(?<![A-Za-z])(?:Dr|Cr|DR|CR)\.?(?![A-Za-z])", " ", rest).strip(" .")
            if not rest or not re.search(r"[A-Za-z]{2}", rest):
                continue
            cell = rest
        x = _span_x(boxes, s, e)
        if cell in ("Dr", "Cr", "DR", "CR", "(Dr)", "(Cr)"):
            continue
        if x and _in_col(cols, "vdate", x, 10) and DATE.fullmatch(cell) and not txn["value_date"]:
            txn["value_date"] = cell
            continue
        if x and _in_col(cols, "ref", x) and not (narr_left is not None and x[0] <= narr_left + 2 <= x[1]):
            if cell not in ("-", "--"):
                txn["ref"] = (txn["ref"] + " " + cell).strip()
            continue
        if x and narr_left is not None and x[1] < narr_left - 3:
            continue
        parts.append(cell)
    return " ".join(parts)


def _build(anchor, group, cols, narr_left):
    t, boxes, lead = anchor["text"], anchor["boxes"], anchor["lead"]
    txn = {"page": anchor["page"], "date": lead.group(2).strip(), "value_date": "", "ref": "", "narr": [], "amts": [],
           "sno": lead.group(1) or ""}
    pos = lead.end()
    vd = DATE.match(t[pos:].lstrip())
    if vd:
        txn["value_date"] = vd.group(0)
        pos += (len(t[pos:]) - len(t[pos:].lstrip())) + vd.end()
    txn["amts"] = _amounts(t, boxes, pos, cols)
    for r in group:
        if r is anchor:
            txt = _row_text(r, cols, narr_left, txn, pos, txn["amts"])
        else:
            amts = _amounts(r["text"], r["boxes"], 0, cols)
            if amts and not txn["amts"]:
                txn["amts"] = amts                      # amounts printed on another line of the row
            txt = _row_text(r, cols, narr_left, txn, 0, amts)
        if txt:
            txn["narr"].append(txt)
    return txn


def _continuation(txn, lines, narr_left, cols):
    for r in sorted(lines, key=lambda x: x["y"]):
        if FOOTER.search(r["text"]) or SUMMARY.search(r["text"]) or AMT.search(r["text"]):
            continue
        if narr_left is not None and not (narr_left - 3 <= r["x0"] <= narr_left + 40):
            continue
        txt = _row_text(r, cols, narr_left, txn)
        if txt:
            txn["narr"].append(txt)


_TAIL_WORDS = re.compile(r"(?i)(?:\b(?:date|dt|no|number|amount|amt|inr|rs|balance|value|details|particulars|remarks"
                         r"|narration|description|withdrawals?|deposits?|debit|credit|cheque|chq|ref|txn|tran)\b|\()")


def _header_tail(text):
    """Second header line such as 'Date   Number   (INR )   (INR )' (heading words only, no data)."""
    if not (re.fullmatch(r"(?i)[\s()A-Za-z./]*", text) and len(text.strip()) < 120 and not LEAD.match(text)):
        return False
    words = re.findall(r"[A-Za-z]+|\(", text)
    hits = len(_TAIL_WORDS.findall(text))
    return hits >= 1 and hits >= len(words) / 2


def _signed(m) -> float:
    v = _num(m.group(2))
    if m.group(1) or (m.group(3) or "").lower() == "dr":
        v = -v
    return v


def _finish(txns, cols, opening, seen_header, strict):
    out = []
    prev_bal = opening
    for t in txns:
        amts = t["amts"]
        if not amts:
            continue
        rec = {"Page": t["page"], "S No.": t.get("sno", ""), "Date": t["date"], "Value date": t["value_date"],
               "Narration": re.sub(r"\s+", " ", " ".join(n for n in t["narr"] if n)).strip(" -"),
               "Chq / Ref no.": t.get("ref", ""),
               "Debit": "", "Credit": "", "Balance": "", "Balance check": "Not checked", "_amount": ""}
        # 1. which amount is the balance
        bal_a = None
        if len(amts) >= 2:
            bal_a = amts[-1]
        elif cols and "balance" in cols and _nearest_col(cols, amts[0]["x"]) == "balance":
            bal_a = amts[0]
        bal = None
        if bal_a is not None:
            bal = -bal_a["v"] if (bal_a["neg"] or bal_a["mark"] == "dr") else bal_a["v"]
            rec["Balance"] = f"{bal:.2f}"
        movers = [a for a in amts if a is not bal_a and a["v"] != 0]     # ICICI prints 0.00 in the empty column
        if not movers and bal_a is not None and len(amts) >= 2:
            movers = []
        # 2. debit or credit
        for a in movers:
            kind = None
            if prev_bal is not None and bal is not None and len(movers) == 1:
                delta = round(bal - prev_bal, 2)
                if abs(delta - a["v"]) < 0.011:
                    kind, rec["Balance check"] = "Credit", "OK"
                elif abs(delta + a["v"]) < 0.011:
                    kind, rec["Balance check"] = "Debit", "OK"
                else:
                    rec["Balance check"] = "Mismatch"
            if kind is None and a["mark"] in ("dr", "cr"):
                kind = "Debit" if a["mark"] == "dr" else "Credit"
            if kind is None and a["neg"]:
                kind = "Debit"
            if kind is None and cols:
                c = _nearest_col({k: v for k, v in cols.items() if k in ("debit", "credit")}, a["x"]) \
                    if ("debit" in cols and "credit" in cols) else None
                kind = {"debit": "Debit", "credit": "Credit"}.get(c)
            if kind:
                rec[kind] = f"{a['v']:.2f}"
            else:
                rec["_amount"] = f"{a['v']:.2f}"
        if bal is not None:
            prev_bal = bal
        out.append(rec)
    if strict and not seen_header and not any(r["Balance check"] == "OK" for r in out):
        return []
    has_unknown = any(r["_amount"] for r in out)
    has_vd = any(r["Value date"] for r in out)
    has_ref = any(r["Chq / Ref no."] for r in out)
    has_sno = sum(1 for r in out if r["S No."]) >= max(1, len(out) // 2)
    clean = []
    for r in out:
        r = dict(r)
        if has_unknown:
            r["Amount (debit/credit not identified)"] = r.pop("_amount")
        else:
            r.pop("_amount")
        if not has_vd:
            r.pop("Value date")
        if not has_ref:
            r.pop("Chq / Ref no.")
        if not has_sno:
            r.pop("S No.")
        clean.append(r)
    return clean
