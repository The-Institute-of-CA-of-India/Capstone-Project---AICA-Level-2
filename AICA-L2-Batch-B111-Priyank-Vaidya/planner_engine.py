"""Raw Material Purchase & Production Planner - calculation engine.

A Python port of the logic inside Purchase_Plan_Dashboard.html:

    compute_mrp()              Sales Plan -> Production Required -> Blend -> Raw Material purchase
    read_line_config()         Lines, SKUs and cases/day from the Line_Production sheet
    compute_production_plan()  Week-wise schedule driven by available days per line

Nothing here depends on Streamlit, so it can be used and tested on its own.
"""
from __future__ import annotations

import io
import math
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import openpyxl

PLAN_WEEKS = 4
MAX_DAYS_PER_WEEK = 6            # 1 weekly holiday
MAX_DAYS_PER_MONTH = PLAN_WEEKS * MAX_DAYS_PER_WEEK
REQUIRED_SHEETS = ["Sales Plan", "FG_BOM", "Blend_BOM", "RM_OpeningStock", "FG_OpeningStock"]
# Production priority (Line_Production "Important Points"): first entry is scheduled first.
PRIORITY_BRANDS = ["Brand A", "Brand B"]
ENA_CODE = "9300001"
DASH = "—"
_EPS = 1e-9

_NUM_RE = re.compile(r"^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
_TAPE_RE = re.compile(r"SEALING[\s-]*TAPE|BOPP.*TAPE|TAPE.*BOPP", re.I)


# ----------------------------------------------------------------- helpers
def _num(x) -> float:
    """Numeric value of a cell, 0 when blank / text."""
    if x is None or isinstance(x, bool):
        return 0.0
    if isinstance(x, (int, float)):
        return 0.0 if (isinstance(x, float) and math.isnan(x)) else float(x)
    m = _NUM_RE.match(str(x).replace("\xa0", " "))
    return float(m.group(0)) if m else 0.0


def _clean_code(x) -> str | None:
    """Item code as a clean string ('\\xa08200006' -> '8200006'); None when not numeric."""
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        v = float(x)
    else:
        m = _NUM_RE.match(str(x).replace("\xa0", " "))
        if not m:
            return None
        v = float(m.group(0))
    if math.isnan(v) or math.isinf(v):
        return None
    return str(int(math.floor(v + 0.5)))


def _s(x) -> str:
    return "" if x is None else str(x).replace("\xa0", " ").strip()


def _rnd(x: float, d: int = 2) -> float:
    """Round half-up to d decimals (same behaviour as JavaScript toFixed)."""
    return float(Decimal(float(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _round_int(x: float) -> int:
    return int(math.floor(x + 0.5))


def _rows(wb, name):
    if name not in wb.sheetnames:
        return None
    return [list(r) for r in wb[name].iter_rows(values_only=True)]


def _find_header_row(rows, keys) -> int:
    for i in range(min(len(rows), 5)):
        cells = [_s(c).lower() for c in rows[i]]
        if all(any(k in c for c in cells) for k in keys):
            return i
    return 0


def _col(header, sub) -> int:
    for i, c in enumerate(header):
        if sub in _s(c).lower():
            return i
    return -1


def _col_exact(header, text) -> int:
    for i, c in enumerate(header):
        if _s(c).lower() == text:
            return i
    return -1


def _col_re(header, pattern, exclude=None) -> int:
    for i, c in enumerate(header):
        t = "" if c is None else str(c)
        if re.search(pattern, t, re.I) and not (exclude and re.search(exclude, t, re.I)):
            return i
    return -1


def _get(row, idx):
    return row[idx] if 0 <= idx < len(row) else None


def _code_order(codes):
    return sorted(codes, key=lambda c: (int(c) if c.isdigit() else float("inf"), c))


def load_workbook(source):
    """Open a planner workbook from a path or from uploaded bytes (cached formula values)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    return openpyxl.load_workbook(source, data_only=True)


def missing_sheets(wb):
    return [n for n in REQUIRED_SHEETS if n not in wb.sheetnames]


# ----------------------------------------------------------------- readers
def _read_month(wb) -> str:
    rows = _rows(wb, "Sales Plan")
    month = None
    if rows:
        for row in rows[:4]:
            for j, cell in enumerate(row):
                if re.search(r"planning month", _s(cell), re.I):
                    for v in row[j + 1:]:
                        if isinstance(v, (datetime, date)):
                            month = v.strftime("%B %Y")
                            break
                        t = _s(v)
                        if t and not re.search(r"set the month", t, re.I):
                            month = t
                            break
                if month:
                    break
            if month:
                break
        if not month:
            hr = _find_header_row(rows, ["fg code", "finished goods"])
            for c in rows[hr]:
                if re.search(r"sales target", _s(c), re.I):
                    m = re.search(r"([A-Za-z]+\s*\d{4})", _s(c))
                    if m:
                        month = m.group(1)
                    break
    month = re.sub(r"^[\s`'\"~^*\-–—:]+", "", month or "")
    month = re.sub(r"[\s`'\"]+$", "", month).strip()
    return month or "New Month"


def _read_closing_by_name(wb, sheet):
    rows = _rows(wb, sheet)
    if not rows:
        return {}
    h = _find_header_row(rows, ["finished goods"])
    hh = rows[h]
    n = _col_exact(hh, "finished goods")
    if n < 0:
        n = _col(hh, "finished goods")
    cc = _col_re(hh, r"closing|required")
    if cc < 0:
        cc = len(hh) - 1
    out = {}
    for row in rows[h + 1:]:
        nm = _s(_get(row, n))
        if nm:
            out[nm] = out.get(nm, 0) + _num(_get(row, cc))
    return out


def _read_closing_by_code(wb, sheet):
    rows = _rows(wb, sheet)
    if not rows:
        return {}
    h = _find_header_row(rows, ["code"])
    hh = rows[h]
    c = _col(hh, "code")
    cc = _col_re(hh, r"closing|required")
    if cc < 0:
        cc = len(hh) - 1
    out = {}
    for row in rows[h + 1:]:
        code = _clean_code(_get(row, c))
        if code:
            out[code] = out.get(code, 0) + _num(_get(row, cc))
    return out


def _rm_closing_fallback(wb, rows, h_idx, c_item):
    """RM_Closing column K is an Excel formula (Qty per case x Salience FG cases).
    If the file was saved without calculated values, recompute it here."""
    hh = rows[h_idx]
    c_fg = _col(hh, "fg code")
    sal = _rows(wb, "Salience")
    fb = _rows(wb, "FG_BOM")
    if c_fg < 0 or not sal or not fb:
        return {}
    total = 0.0
    for row in sal[:3]:
        for j, cell in enumerate(row):
            if re.search(r"total fg stock", _s(cell), re.I):
                total = next((_num(v) for v in row[j + 1:] if isinstance(v, (int, float))), 0.0)
    sh = _find_header_row(sal, ["fg code", "sale"])
    s_code, s_pct = _col(sal[sh], "fg code"), _col(sal[sh], "% sale")
    fg_cases = {}
    for row in sal[sh + 1:]:
        code = _clean_code(_get(row, s_code))
        if code:
            fg_cases[code] = total * _num(_get(row, s_pct)) / 100.0
    bh = _find_header_row(fb, ["fg code", "bom item code"])
    b = fb[bh]
    b_fg, b_item, b_qty, b_fgqty = _col(b, "fg code"), _col(b, "bom item code"), _col(b, "bom qty"), _col(b, "fgqty")
    per_case, last, fgqty = {}, None, 1000.0
    for row in fb[bh + 1:]:
        fg = _clean_code(_get(row, b_fg))
        if fg:
            last = fg
            fgqty = _num(_get(row, b_fgqty)) or 1000.0
        item = _clean_code(_get(row, b_item))
        if item and last:
            per_case.setdefault((last, item), []).append(_num(_get(row, b_qty)) / fgqty)
    out, last = {}, None
    for row in rows[h_idx + 1:]:
        fg = _clean_code(_get(row, c_fg))
        if fg:
            last = fg
        item = _clean_code(_get(row, c_item))
        if not item or not last:
            continue
        lst = per_case.get((last, item))
        if not lst:
            continue
        q = (lst.pop(0) if len(lst) > 1 else lst[0]) * fg_cases.get(last, 0.0)
        if q:
            out[item] = out.get(item, 0) + q
    return out


def _read_rm_closing(wb):
    """Required raw-material closing stock, summed per item. Blend codes (82*) are kept apart."""
    out = {"rm": {}, "blend": {}}
    rows = _rows(wb, "RM_Closing")
    if not rows:
        return out
    h_idx = _find_header_row(rows, ["rm item code"])
    hh = rows[h_idx]
    c_item = _col_re(hh, r"rm\s*item\s*code")
    if c_item < 0:
        c_item = _col_re(hh, r"item\s*code", exclude=r"fg")
    c_qty = _col_re(hh, r"closing\s*stock\s*qty")
    if c_qty < 0:
        c_qty = _col_re(hh, r"closing")
    if c_item < 0 or c_qty < 0:
        return out
    totals, any_value = {}, False
    for row in rows[h_idx + 1:]:
        code = _clean_code(_get(row, c_item))
        if not code:
            continue
        v = _get(row, c_qty)
        if isinstance(v, (int, float)):
            any_value = True
        q = _num(v)
        if q:
            totals[code] = totals.get(code, 0) + q
    if not any_value:
        totals = _rm_closing_fallback(wb, rows, h_idx, c_item)
    for code, q in totals.items():
        bucket = out["blend"] if code.startswith("82") else out["rm"]
        bucket[code] = bucket.get(code, 0) + q
    return out


# ----------------------------------------------------------------- MRP
def compute_mrp(wb) -> dict:
    month = _read_month(wb)

    # --- Sales Plan ---
    sp = _rows(wb, "Sales Plan")
    sp_h = _find_header_row(sp, ["fg code", "finished goods"])
    sh = sp[sp_h]
    c_code = _col(sh, "fg code")
    c_name = _col_exact(sh, "finished goods")
    if c_name < 0:
        c_name = _col(sh, "finished goods")
    c_sales = _col_re(sh, r"sales target")
    sales = []
    for row in sp[sp_h + 1:]:
        code = _clean_code(_get(row, c_code))
        nm = _s(_get(row, c_name))
        if not code or not nm or nm.upper() == "TOTAL":
            continue
        sales.append({"code": code, "name": nm, "sales": _num(_get(row, c_sales))})

    # --- FG_Master: brand (Item Category) + pack size (SKUs) ---
    cat_by_code, cat_by_name, sku_by_code, sku_by_name, sku_order = {}, {}, {}, {}, []
    fm = _rows(wb, "FG_Master")
    if fm:
        fm_h = _find_header_row(fm, ["item category"])
        mh = fm[fm_h]
        m_code = _col_re(mh, r"item\s*code|fg code")
        m_code = m_code if m_code >= 0 else 0
        m_name = _col_exact(mh, "finished goods")
        m_cat = _col_re(mh, r"item category")
        m_sku = _col_re(mh, r"^\s*skus?\s*$")
        if m_cat >= 0:
            for row in fm[fm_h + 1:]:
                code = _clean_code(_get(row, m_code))
                cat = _s(_get(row, m_cat))
                nm = _s(_get(row, m_name)) if m_name >= 0 else ""
                sk = _s(_get(row, m_sku)) if m_sku >= 0 else ""
                if code and cat:
                    cat_by_code[code] = cat
                if nm and cat:
                    cat_by_name[nm] = cat
                if sk:
                    if code:
                        sku_by_code[code] = sk
                    if nm:
                        sku_by_name[nm] = sk
                    if sk not in sku_order:
                        sku_order.append(sk)

    def cat_of(s):
        return cat_by_code.get(s["code"]) or cat_by_name.get(s["name"]) or "Uncategorised"

    def sku_of(s):
        return sku_by_code.get(s["code"]) or sku_by_name.get(s["name"]) or DASH

    def _vol(k):
        m = re.search(r"\d+", k)
        return float(m.group(0)) if m else 0.0

    sku_list = sorted(sku_order, key=lambda k: (_vol(k), k.lower(), k))

    # --- FG opening (by name) and required closing ---
    fo = _rows(wb, "FG_OpeningStock")
    fo_h = _find_header_row(fo, ["finished goods", "opening"])
    fh = fo[fo_h]
    fc_name = _col_exact(fh, "finished goods")
    if fc_name < 0:
        fc_name = _col(fh, "finished goods")
    fc_open = _col_re(fh, r"opening")
    open_by_name = {}
    for row in fo[fo_h + 1:]:
        nm = _s(_get(row, fc_name))
        if nm:
            open_by_name[nm] = open_by_name.get(nm, 0) + _num(_get(row, fc_open))
    close_by_name = _read_closing_by_name(wb, "FG_ClosingStock")

    prod_by_code = {}
    for s in sales:
        s["opening"] = open_by_name.get(s["name"], 0)
        s["closing"] = close_by_name.get(s["name"], 0)
        s["prod"] = max(s["sales"] + s["closing"] - s["opening"], 0)
        s["cat"] = cat_of(s)
        s["sku"] = sku_of(s)
        prod_by_code[s["code"]] = s["prod"]

    # --- RM opening stock ---
    rm_rows = _rows(wb, "RM_OpeningStock")
    rm_h = _find_header_row(rm_rows, ["item code", "stock"])
    rh = rm_rows[rm_h]
    r_code, r_desc = _col(rh, "item code"), _col(rh, "item description")
    r_type, r_grp = _col(rh, "item type"), _col(rh, "item group")
    r_uom, r_qty = _col(rh, "base uom"), _col_re(rh, r"stock qty")
    open_stock, meta = {}, {}
    for row in rm_rows[rm_h + 1:]:
        code = _clean_code(_get(row, r_code))
        if not code:
            continue
        open_stock[code] = open_stock.get(code, 0) + _num(_get(row, r_qty))
        meta.setdefault(code, {"desc": _s(_get(row, r_desc)), "type": _s(_get(row, r_type)),
                               "group": _s(_get(row, r_grp)), "uom": _s(_get(row, r_uom))})

    # --- required closing stock of raw materials and blends ---
    close_stock = _read_closing_by_code(wb, "RM_ClosingStock")
    blend_close = _read_closing_by_code(wb, "Blend_ClosingStock")
    rmc = _read_rm_closing(wb)
    for c, q in rmc["rm"].items():
        close_stock[c] = close_stock.get(c, 0) + q
    for c, q in rmc["blend"].items():
        blend_close[c] = blend_close.get(c, 0) + q

    # --- FG_BOM (per 1000 cases) -> blend demand + direct packing material ---
    fb = _rows(wb, "FG_BOM")
    fb_h = _find_header_row(fb, ["fg code", "bom item code"])
    bh = fb[fb_h]
    b_fg, b_item = _col(bh, "fg code"), _col(bh, "bom item code")
    b_desc, b_uom, b_qty = _col(bh, "bom item description"), _col(bh, "bom uom"), _col(bh, "bom qty")
    last_fg = None
    blend_demand, blend_demand_fg = {}, {}
    direct_req, direct_req_fg, bom_lines = {}, {}, []
    for row in fb[fb_h + 1:]:
        fg = _clean_code(_get(row, b_fg))
        if fg:
            last_fg = fg
        item = _clean_code(_get(row, b_item))
        if not item:
            continue
        per1000 = _num(_get(row, b_qty))
        gross = per1000 * prod_by_code.get(last_fg, 0) / 1000
        desc = _s(_get(row, b_desc))
        if last_fg and per1000 > 0:
            bom_lines.append({"fg": last_fg, "item": item, "per1000": per1000, "desc": desc})
        if item.startswith("82"):
            blend_demand[item] = blend_demand.get(item, 0) + gross
            d = blend_demand_fg.setdefault(item, {})
            d[last_fg] = d.get(last_fg, 0) + gross
        else:
            o = direct_req.setdefault(item, {"req": 0, "desc": desc, "uom": _s(_get(row, b_uom))})
            o["req"] += gross
            d = direct_req_fg.setdefault(item, {})
            d[last_fg] = d.get(last_fg, 0) + gross

    blend_net = {c: max(blend_demand[c] + blend_close.get(c, 0) - open_stock.get(c, 0), 0)
                 for c in blend_demand}

    # --- Blend_BOM (per 1000 BL) -> spirits / flavours ---
    bb = _rows(wb, "Blend_BOM")
    bb_h = _find_header_row(bb, ["blend code", "bom item code"])
    zh = bb[bb_h]
    z_bl, z_bn, z_item = _col(zh, "blend code"), _col(zh, "blend name"), _col(zh, "bom item code")
    z_desc, z_uom, z_qty = _col(zh, "bom item description"), _col(zh, "bom uom"), _col(zh, "bom qty")
    last_blend, blend_name = None, {}
    spirit_req, spirit_req_fg = {}, {}
    for row in bb[bb_h + 1:]:
        bc = _clean_code(_get(row, z_bl))
        if bc:
            last_blend = bc
            if _s(_get(row, z_bn)):
                blend_name[bc] = _s(_get(row, z_bn))
        item = _clean_code(_get(row, z_item))
        if not item:
            continue
        req = _num(_get(row, z_qty)) * blend_net.get(last_blend, 0) / 1000
        o = spirit_req.setdefault(item, {"req": 0, "desc": _s(_get(row, z_desc)), "uom": _s(_get(row, z_uom))})
        o["req"] += req
        shares = blend_demand_fg.get(last_blend, {})
        tot = sum(shares.values()) or 1
        d = spirit_req_fg.setdefault(item, {})
        for fgc, bl in shares.items():
            d[fgc] = d.get(fgc, 0) + req * (bl / tot)

    blends = [{"code": c,
               "name": blend_name.get(c) or meta.get(c, {}).get("desc") or c,
               "gross": _rnd(blend_demand[c], 1), "opening": _rnd(open_stock.get(c, 0), 1),
               "closing": _rnd(blend_close.get(c, 0), 1), "net": _rnd(blend_net[c], 1)}
              for c in _code_order(blend_demand)]

    # --- combine all raw materials ---
    combined, by_fg = {}, {}

    def add(code, o, fgmap):
        c = combined.setdefault(code, {"req": 0, "desc": o["desc"], "uom": o["uom"]})
        c["req"] += o["req"]
        if not c["desc"]:
            c["desc"] = o["desc"]
        d = by_fg.setdefault(code, {})
        for f, v in (fgmap or {}).items():
            d[f] = d.get(f, 0) + v

    for c, o in direct_req.items():
        add(c, o, direct_req_fg.get(c))
    for c, o in spirit_req.items():
        add(c, o, spirit_req_fg.get(c))
    for c in close_stock:                 # closing-stock-only items still need buying
        if c not in combined:
            add(c, {"req": 0, "desc": "", "uom": ""}, None)

    rm = []
    for code in _code_order(combined):
        o = combined[code]
        opening, close = open_stock.get(code, 0), close_stock.get(code, 0)
        m = meta.get(code, {})
        need = o["req"] + close
        fgmap, catmap = {}, {}
        for f in _code_order(by_fg.get(code, {})):
            v = by_fg[code][f]
            fgmap[f] = _rnd(v, 2)
            cat = cat_by_code.get(f, "Uncategorised")
            catmap[cat] = _rnd(catmap.get(cat, 0) + v, 2)
        rm.append({"code": code, "desc": o["desc"] or m.get("desc") or code,
                   "uom": o["uom"] or m.get("uom") or "",
                   "type": m.get("type") or "Unmapped", "group": m.get("group") or "Unmapped",
                   "gross": _rnd(o["req"], 2), "close": _rnd(close, 2), "req": _rnd(need, 2),
                   "open": _rnd(opening, 2), "buy": _rnd(max(need - opening, 0), 2),
                   "surplus": _rnd(max(opening - need, 0), 2), "byFG": fgmap, "byCat": catmap})
    rm.sort(key=lambda r: -r["buy"])

    ena = sum(r["buy"] for r in rm if r["code"] == ENA_CODE)
    prod_cats = sorted({s["cat"] for s in sales if s["prod"] > 0})

    # --- possible production from opening raw-material stock ---
    def unlimited(item, desc):
        return item.startswith("82") or bool(_TAPE_RE.search(desc or ""))

    item_users, lines_by_fg = {}, {}
    for l in bom_lines:
        lines_by_fg.setdefault(l["fg"], []).append(l)
        if not unlimited(l["item"], l["desc"]):
            item_users.setdefault(l["item"], set()).add(l["fg"])
    possible = []
    for s in sales:
        min_c, binding, bind_sh = math.inf, None, 1
        max_c, max_item, max_sh = -math.inf, None, 1
        for l in lines_by_fg.get(s["code"], []):
            if unlimited(l["item"], l["desc"]) or l["per1000"] <= 0:
                continue
            n_users = len(item_users.get(l["item"], ())) or 1
            cases = open_stock.get(l["item"], 0) / n_users / l["per1000"] * 1000
            if cases < min_c:
                min_c, binding, bind_sh = cases, l["desc"] or l["item"], n_users
            if cases > max_c:
                max_c, max_item, max_sh = cases, l["desc"] or l["item"], n_users
        if not math.isfinite(min_c):
            min_c = 0
        if not math.isfinite(max_c):
            max_c = 0
        possible.append({"code": s["code"], "name": s["name"], "cat": s["cat"],
                         "cases": math.floor(min_c * 100) / 100, "binding": binding or DASH, "shared": bind_sh,
                         "maxCases": math.floor(max_c * 100) / 100, "maxItem": max_item or DASH,
                         "maxShared": max_sh})

    return {
        "month": month,
        "sales": [{k: s[k] for k in ("code", "name", "cat", "sku", "sales", "opening", "closing", "prod")}
                  for s in sales],
        "skuList": sku_list,
        "fgList": [{"code": s["code"], "name": s["name"], "cat": s["cat"]} for s in sales],
        "catList": prod_cats,
        "blends": blends, "rm": rm, "possible": possible,
        "kpi": {"totalSales": sum(s["sales"] for s in sales), "totalProd": sum(s["prod"] for s in sales),
                "rmItems": len(rm), "buyItems": sum(1 for r in rm if r["buy"] > 0),
                "enaLtr": _round_int(ena)},
    }


# ----------------------------------------------------------------- lines
def read_line_config(wb) -> dict:
    """{line name: {SKU name: max cases per day}} from the Line_Production sheet."""
    rows = _rows(wb, "Line_Production")
    if not rows:
        return {}
    line_re = re.compile(r"^line\s*\d+$", re.I)
    head, cols = None, []
    for i, row in enumerate(rows[:10]):
        found = [(j, _s(c)) for j, c in enumerate(row) if line_re.match(_s(c))]
        if found:
            head, cols = i, found
            break
    if head is None:
        return {}
    config = {name: {} for _, name in cols}
    for row in rows[head + 1:]:
        if any(re.search(r"important points", _s(c), re.I) for c in row):
            break
        for j, name in cols:
            sku, cap = _get(row, j), _get(row, j + 1)
            if isinstance(sku, str) and sku.strip() and isinstance(cap, (int, float)) \
                    and not isinstance(cap, bool) and cap > 0:
                config[name][_s(sku)] = float(cap)
    return config


def days_per_week(monthly_days: float) -> float:
    """Monthly available days spread evenly over the weeks, at most 6 working days a week."""
    return max(0.0, min(_num(monthly_days) / PLAN_WEEKS, MAX_DAYS_PER_WEEK))


def brand_tier(name: str) -> int:
    for i, b in enumerate(PRIORITY_BRANDS):
        if re.search(re.escape(b), name, re.I):
            return i
    return len(PRIORITY_BRANDS)


def _brand_of(n: str) -> str:
    m = re.match(r"^(.*?)\s+(?:PET\s+)?\d+\s*ML\b", n, re.I)
    return (m.group(1) if m else re.split(r"\s+\d", n)[0]).strip()


def _g(x: float) -> str:
    return f"{x:g}"


# ----------------------------------------------------------------- production plan
def compute_production_plan(data: dict, line_config: dict, monthly_days: dict | None = None,
                            week_days: dict | None = None) -> dict:
    """Week-wise production schedule.

    monthly_days : {line: available days in the month}; split evenly over 4 weeks (max 6 a week).
                   Lines not listed get the full 24 days.
    week_days    : optional {line: days per week} that bypasses the split/cap (used for checks).
    """
    monthly_days = monthly_days or {}
    lines = list(line_config)
    dpw = {ln: (float(week_days[ln]) if week_days and ln in week_days
                else days_per_week(monthly_days.get(ln, MAX_DAYS_PER_MONTH))) for ln in lines}
    days_avail = {ln: _rnd(dpw[ln] * PLAN_WEEKS, 2) for ln in lines}

    def cap_of(ln, sku):
        return line_config.get(ln, {}).get(sku, 0)

    def line_of(sku):
        return next((ln for ln in lines if sku in line_config[ln]), None)

    possible_by = {p["name"]: max(math.floor(p["cases"]), 0) for p in data.get("possible", [])}
    rem, poss_left = {}, {}
    for s in data.get("sales", []):
        if s["prod"] > 0:
            rem[s["name"]] = s["prod"]
            poss_left[s["name"]] = possible_by.get(s["name"], 0)

    plan = []
    for wk in range(1, PLAN_WEEKS + 1):
        if wk == 1:     # prefer FGs whose raw material is already in opening stock
            key = lambda s: (brand_tier(s), -possible_by.get(s, 0), -rem.get(s, 0))
        else:           # lead time has passed: largest remaining demand first within a tier
            key = lambda s: (brand_tier(s), -rem.get(s, 0))
        for ln in lines:
            days_left = dpw[ln]
            while days_left > _EPS:
                day_size = min(1.0, days_left)          # last day of the week may be a part-day
                cand = sorted((s for s in line_config[ln] if rem.get(s, 0) > 0), key=key)
                if not cand:
                    break
                used, progressed = 0.0, False
                for s in cand:
                    if used >= day_size - _EPS:
                        break
                    cap = cap_of(ln, s)
                    if cap <= 0:
                        continue
                    allow = rem[s]
                    if wk == 1:                          # 5-day purchase lead time
                        allow = min(allow, poss_left.get(s, 0))
                    if allow <= 0:
                        continue
                    q = min(cap * (day_size - used), allow)
                    if q > 0:
                        plan.append((wk, ln, s, q))
                        rem[s] -= q
                        used += q / cap
                        progressed = True
                        if wk == 1:
                            poss_left[s] = max(poss_left.get(s, 0) - q, 0)
                if not progressed:
                    break
                days_left -= day_size

    agg = {}
    for wk, ln, s, q in plan:
        agg[(wk, ln, s)] = agg.get((wk, ln, s), 0) + q
    consolidated = [{"week": wk, "line": ln, "sku": s, "rate": cap_of(ln, s), "cases": q,
                     "days": _rnd(q / (cap_of(ln, s) or 1), 2)}
                    for (wk, ln, s), q in sorted(agg.items())]

    demand_by = {s["name"]: s["prod"] for s in data.get("sales", []) if s["prod"] > 0}

    def line_days(ln):
        return sum(demand_by[s] / (cap_of(ln, s) or 1) for s in line_config[ln] if demand_by.get(s, 0) > 0)

    def tier_name(t):
        return PRIORITY_BRANDS[t] if t < len(PRIORITY_BRANDS) else "other brands"

    def reason_for(sku):
        ln = line_of(sku)
        if not ln:
            return "Not mapped to any production line — add it to the Line_Production sheet."
        my_tier, need, avail = brand_tier(sku), line_days(ln), days_avail[ln]
        cap_txt = f"{cap_of(ln, sku):,.0f}"
        comp = [s for s in line_config[ln] if s != sku and demand_by.get(s, 0) > 0 and brand_tier(s) < my_tier]
        higher = " & ".join(tier_name(t) for t in sorted({brand_tier(s) for s in comp}))
        lead = ("" if possible_by.get(sku, 0) > 0 else
                " Its raw material is not in opening stock, so it could not start until purchased "
                "material arrived (5-day lead time).")
        if avail <= 0:
            return f"{ln} has no available days this month."
        if need > avail:
            if comp:
                return (f"{ln} is over capacity — needs {need:.1f} days vs {_g(avail)} available. "
                        f"Higher-priority {higher} on the same line is scheduled first, leaving too few days "
                        f"for this SKU (its rate is {cap_txt} cases/day).{lead}")
            return (f"{ln} is over capacity — needs {need:.1f} days vs {_g(avail)} available at "
                    f"{cap_txt} cases/day, so the full quantity cannot be produced this month.{lead}")
        if comp:
            return (f"Days on {ln} ran out for this SKU — higher-priority {higher} is scheduled first "
                    f"(line needs {need:.1f} of {_g(avail)} days; this SKU runs at {cap_txt} cases/day).{lead}")
        return (f"Could not be fully scheduled within {ln}'s {_g(avail)} available days at "
                f"{cap_txt} cases/day.{lead}")

    shortfall = sorted(({"sku": s, "line": line_of(s) or DASH, "cases": _round_int(q), "reason": reason_for(s)}
                        for s, q in rem.items() if q > 0.5), key=lambda r: -r["cases"])
    scheduled = sum(r["cases"] for r in consolidated)
    short_total = sum(r["cases"] for r in shortfall)

    short_by = {r["sku"]: r["cases"] for r in shortfall}
    sched_by, days_by = {}, {}
    for r in consolidated:
        sched_by[r["sku"]] = sched_by.get(r["sku"], 0) + r["cases"]
        days_by[r["sku"]] = days_by.get(r["sku"], 0) + r["days"]
    sku_analysis = []
    for ln in lines:
        for sku, cap in line_config[ln].items():
            dem = demand_by.get(sku, 0)
            if dem <= 0:
                continue
            cap = cap or 1
            sku_analysis.append({"line": ln, "sku": sku, "cap": cap, "demand": dem,
                                 "daysNeeded": _rnd(dem / cap, 2),
                                 "scheduled": _round_int(sched_by.get(sku, 0)),
                                 "daysUsed": _rnd(days_by.get(sku, 0), 2),
                                 "short": _round_int(short_by.get(sku, 0)),
                                 "shortDays": _rnd(short_by.get(sku, 0) / cap, 2)})

    line_analysis = []
    for ln in lines:
        rws = [r for r in sku_analysis if r["line"] == ln]
        need = sum(r["daysNeeded"] for r in rws)
        line_analysis.append({"line": ln, "demand": sum(r["demand"] for r in rws),
                              "daysNeeded": _rnd(need, 2), "daysAvail": days_avail[ln],
                              "daysPerWeek": _rnd(dpw[ln], 2),
                              "balance": _rnd(days_avail[ln] - need, 2),
                              "scheduled": sum(r["scheduled"] for r in rws),
                              "short": sum(r["short"] for r in rws)})

    bmap = {}
    for r in sku_analysis:
        g = bmap.setdefault(_brand_of(r["sku"]), {"brand": _brand_of(r["sku"]), "demand": 0, "daysNeeded": 0,
                                                  "scheduled": 0, "daysUsed": 0, "short": 0, "shortDays": 0,
                                                  "lines": set(), "skus": []})
        for k in ("demand", "daysNeeded", "scheduled", "daysUsed", "short", "shortDays"):
            g[k] += r[k]
        g["lines"].add(r["line"])
        g["skus"].append(r)
    brand_analysis = sorted(({**g, "daysNeeded": _rnd(g["daysNeeded"], 2), "daysUsed": _rnd(g["daysUsed"], 2),
                              "shortDays": _rnd(g["shortDays"], 2), "lines": sorted(g["lines"]),
                              "skus": sorted(g["skus"], key=lambda r: -r["daysNeeded"])}
                             for g in bmap.values()), key=lambda g: -g["demand"])

    return {"plan": consolidated, "shortfall": shortfall,
            "scheduled": _round_int(scheduled), "shortTotal": _round_int(short_total),
            "demand": _round_int(sum(demand_by.values())), "weeks": PLAN_WEEKS,
            "lineAnalysis": line_analysis, "brandAnalysis": brand_analysis,
            "daysAvail": days_avail, "daysPerWeek": dpw,
            "totalDays": _rnd(sum(days_avail.values()), 2)}


if __name__ == "__main__":
    import sys

    book = load_workbook(sys.argv[1] if len(sys.argv) > 1 else "Purchase_Plan_Standard_Revised.xlsx")
    D = compute_mrp(book)
    P = compute_production_plan(D, read_line_config(book))
    print(D["month"], D["kpi"])
    print("scheduled", P["scheduled"], "shortfall", P["shortTotal"], "days/week", P["daysPerWeek"])
