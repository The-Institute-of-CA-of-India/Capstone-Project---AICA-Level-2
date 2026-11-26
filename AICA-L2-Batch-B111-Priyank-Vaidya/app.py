"""Raw Material Purchase & Production Planner - Streamlit app.

Start it with run_app.bat (or:  python -m streamlit run app.py)
"""
from __future__ import annotations

import html
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

import planner_engine as pe

APP_DIR = Path(__file__).parent
DEFAULT_FILES = ["Purchase_Plan_Standard_Revised.xlsx", "Purchase_Plan_Standard_Template.xlsx"]
DASH = "—"

st.set_page_config(page_title="RM Purchase & FG Production Planner", page_icon="\U0001F4E6", layout="wide")

st.markdown("""
<style>
:root{--ink:#1a1410;--paper:#f4efe6;--card:#fffdf8;--line:#d8cdb8;--amber:#b8742a;--amber-dk:#8a4f17;
      --gold:#c9a227;--green:#3f7d3f;--red:#a8392b;--blue:#2a5d8a;--muted:#7a6f5f;--shadow:rgba(60,40,15,.12)}
.stApp{background:radial-gradient(circle at 12% 8%,rgba(201,162,39,.10),transparent 40%),
       radial-gradient(circle at 88% 92%,rgba(184,116,42,.10),transparent 42%),var(--paper)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#efe6d4;border-right:1px solid var(--line)}
.block-container{padding-top:2.2rem;max-width:1280px}
.top{border-bottom:3px double var(--amber-dk);padding-bottom:16px;margin-bottom:6px;display:flex;
     justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:16px}
.top .h1{font-family:Georgia,'Times New Roman',serif;font-size:30px;letter-spacing:-.5px;font-weight:700;
         color:var(--amber-dk);line-height:1.2}
.top .sub{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:3px;text-transform:uppercase;
          color:var(--muted);margin-top:6px}
.top .period{text-align:right}
.top .lbl{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:2px;text-transform:uppercase;
          color:var(--muted)}
.top .val{font-family:Georgia,'Times New Roman',serif;font-size:26px;font-weight:700;color:var(--ink);line-height:1.2}
.stTabs [data-baseweb="tab-list"]{gap:8px;border-bottom:2px solid var(--line)}
.stTabs [data-baseweb="tab"]{padding:10px 26px;color:var(--muted)}
.stTabs [data-baseweb="tab"] p{font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;font-weight:700;
                               letter-spacing:.3px}
.stTabs [aria-selected="true"]{color:var(--amber-dk)}
.sec-h{display:flex;align-items:center;gap:12px;margin:22px 0 12px 0;min-width:0}
.sec-h .h2{font-family:Georgia,'Times New Roman',serif;font-size:20px;color:var(--amber-dk);font-weight:700;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;line-height:1.4}
.sec-h .rule{flex:1 1 20px;height:1px;background:var(--line)}
.sec-h .tag{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:1px;text-transform:uppercase;
            color:var(--muted);border:1px solid var(--line);border-radius:20px;padding:3px 11px;white-space:nowrap}
.pp{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;
    box-shadow:0 2px 12px var(--shadow);margin-bottom:.3rem}
.pp table{width:100%;border-collapse:collapse;font-family:'Helvetica Neue',Arial,sans-serif;font-size:13px;
          color:var(--ink);margin:0}
.pp th{background:var(--amber-dk);color:#fff;text-align:left;padding:11px 14px;font-size:11px;letter-spacing:.6px;
       text-transform:uppercase;font-weight:600;white-space:nowrap;border:none}
.pp td{padding:9px 14px;border:none;border-bottom:1px solid #ece3d2;vertical-align:top}
.pp tbody tr:nth-child(even){background:#faf6ee}
.pp tbody tr:hover{background:#f3ead6}
.pp .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pp tr.head td{font-weight:700;border-top:1px solid var(--line)}
.pp tr.total td{font-weight:700;border-top:2px solid var(--amber-dk);background:#fbf3e0;color:var(--amber-dk)}
.pp tr.subtotal td{font-weight:700;border-top:1px solid var(--line);background:#f7f1e6;color:var(--muted)}
.pp tr.group td{font-weight:700;background:#efe6d4;color:var(--amber-dk);font-size:12px;letter-spacing:.5px}
.pp tr.detail td{background:#faf7f0;font-size:12px}
.pp tr.detail td:first-child{padding-left:26px;color:var(--muted)}
.pp tr.main td{font-weight:700;color:var(--amber-dk);border-top:1px solid var(--line)}
.pp .neg{color:var(--red);font-weight:700}
.pp .pos{color:var(--green);font-weight:700}
.pp .muted{color:#c9bfae}
.pp .reason{display:inline-block;font-size:11.5px;color:var(--muted);line-height:1.45;min-width:300px;max-width:440px;
            white-space:normal}
.pp .pill{display:inline-block;font-size:9.5px;font-weight:700;color:var(--blue);background:#e3edf5;
          border-radius:10px;padding:1px 6px;margin-left:4px}
.pp.compact table{font-size:11.5px}
.pp.compact table{font-size:11px}
.pp.compact th,.pp.compact td{padding:6px 3px}
.pp.compact th{font-size:10px;letter-spacing:.2px}
.pp.compact table{table-layout:fixed;min-width:430px}
.pp.compact th:first-child,.pp.compact td:first-child{padding-left:10px;white-space:normal;width:25%}
.pp.compact th:last-child,.pp.compact td:last-child{padding-right:10px}
.pp th.num{line-height:1.25;vertical-align:bottom}
.pp th .sub{display:block;font-size:9.5px;font-weight:600;color:#e6cfa8;letter-spacing:.2px}
.pp.week{border-radius:0 0 8px 8px;box-shadow:none;border-top:none}
.pp.week table{font-size:11.5px}
.pp.week th,.pp.week td{padding:6px 9px}
.weekhead{display:flex;justify-content:space-between;align-items:center;padding:10px 13px;background:#efe6d4;
          border:1px solid var(--line);border-radius:8px 8px 0 0;font-family:'Helvetica Neue',Arial,sans-serif;
          font-size:12.5px;font-weight:700;color:var(--amber-dk);margin-top:.5rem}
.weekhead span:last-child{color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
.weekempty{padding:14px 16px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:12.5px;color:var(--muted);
           background:var(--card);border:1px solid var(--line);border-top:none;border-radius:0 0 8px 8px}
.kpis{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:14px;margin:.6rem 0 1rem 0}
@media (max-width:760px){.kpis{grid-auto-flow:row;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}}
.kpi{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--amber);border-radius:9px;
     padding:14px 16px;box-shadow:0 2px 10px var(--shadow);min-width:0}
.kpi:nth-child(2){border-left-color:var(--gold)}
.kpi:nth-child(3){border-left-color:var(--blue)}
.kpi:nth-child(4){border-left-color:var(--green)}
.kpi:nth-child(5){border-left-color:var(--red)}
.kpi .l{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10.5px;letter-spacing:1.5px;text-transform:uppercase;
        color:var(--muted)}
.kpi .l{min-height:2.9em;line-height:1.45}
.kpi .v{font-family:Georgia,'Times New Roman',serif;font-size:clamp(20px,2.1vw,30px);font-weight:700;margin-top:4px;letter-spacing:-.5px;
        color:var(--ink);line-height:1.25}
.kpi .u{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;color:var(--muted);margin-top:2px}
.legend{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;color:var(--muted);padding:4px 4px 0 4px;
        margin-bottom:.6rem;line-height:1.5}
.note{background:#fbf3e0;border:1px solid var(--gold);border-radius:8px;padding:13px 16px;
      font-family:'Helvetica Neue',Arial,sans-serif;font-size:12.5px;color:#6b5618;margin:26px 0 10px 0}
.note b{color:var(--amber-dk)}
.foot{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;color:var(--muted);border-top:1px solid var(--line);
      padding-top:14px;margin-top:18px;line-height:1.7}
.stDownloadButton button{background:transparent;color:var(--amber-dk);border:1.5px solid var(--amber-dk);
                         border-radius:7px;font-weight:600}
.stDownloadButton button:hover{background:var(--amber-dk);color:#fff;border-color:var(--amber-dk)}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- formatting
def fmt(n, d: int = 0) -> str:
    """Indian-style number formatting (12,34,567.89), like the HTML dashboard."""
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "-"
    q = Decimal(float(n)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    whole, _, frac = f"{abs(q):f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return sign + whole + ("." + frac if frac else "")


def fmt_c(n) -> str:
    """Up to one decimal, dropped for whole numbers."""
    s = fmt(n, 1)
    return s[:-2] if s.endswith(".0") else s


def cell(v) -> str:
    return fmt_c(v) if v else f'<span class="muted">{DASH}</span>'


def esc(x) -> str:
    return html.escape(str(x))


def table(headers, rows, cls: str = "") -> str:
    """headers: [(label, is_numeric)], rows: [(css_class, [cell html, ...])]."""
    th = "".join(f'<th class="{"num" if n else ""}">{h}</th>' for h, n in headers)
    body = []
    for row_cls, cells in rows:
        tds = "".join(f'<td class="{"num" if headers[i][1] else ""}">{c}</td>' for i, c in enumerate(cells))
        body.append(f'<tr class="{row_cls}">{tds}</tr>')
    return f'<div class="pp {cls}"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def show(html_text: str):
    st.markdown(html_text, unsafe_allow_html=True)


def kpis(items):
    """items: [(label, value, unit)]"""
    show('<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="l">{esc(l)}</div><div class="v">{esc(v)}</div><div class="u">{esc(u)}</div></div>'
        for l, v, u in items) + "</div>")


def sec(title: str, tag: str = ""):
    """Section heading: title, hairline rule and an optional tag (always one line)."""
    tag_html = f'<span class="tag">{esc(tag)}</span>' if tag else ""
    show(f'<div class="sec-h"><div class="h2" title="{esc(title)}">{esc(title)}</div>'
         f'<span class="rule"></span>{tag_html}</div>')


def legend(text: str):
    show(f'<div class="legend">{text}</div>')


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def month_slug(month: str) -> str:
    return "_".join(str(month or "Month").split())


# ----------------------------------------------------------------- data
@st.cache_data(show_spinner="Reading workbook and calculating…")
def load_plan(file_bytes: bytes):
    wb = pe.load_workbook(file_bytes)
    miss = pe.missing_sheets(wb)
    if miss:
        return None, None, miss
    return pe.compute_mrp(wb), pe.read_line_config(wb), []


with st.sidebar:
    st.header("Monthly input file")
    upload = st.file_uploader("Load New Month's File", type=["xlsx", "xlsm"])
    default_path = next((APP_DIR / f for f in DEFAULT_FILES if (APP_DIR / f).exists()), None)
    if upload is not None:
        file_bytes, file_name = upload.getvalue(), upload.name
    elif default_path is not None:
        file_bytes, file_name = default_path.read_bytes(), default_path.name
    else:
        file_bytes, file_name = None, None
    if file_name:
        st.caption(f"Using: **{file_name}**")
    st.caption("Keep sheet names and column headings as in the standard template. "
               "Everything is calculated on this computer; nothing is uploaded anywhere.")

if file_bytes is None:
    st.title("RM Purchase & FG Production Planner")
    st.info("Upload the monthly Excel template from the sidebar to begin.")
    st.stop()

try:
    DATA, LINES, missing = load_plan(file_bytes)
except Exception as err:  # unreadable / unexpected workbook
    st.error(f"Could not read **{file_name}**: {err}")
    st.stop()
if missing:
    st.error("Missing sheet(s) in the workbook: " + ", ".join(missing))
    st.stop()

show(f'''<div class="top"><div><div class="h1">RM Purchase &amp; FG Production Planner</div>
<div class="sub">Two-Level MRP · Sales → Blend → Raw Material</div></div>
<div class="period"><div class="lbl">Planning Period</div><div class="val">{esc(DATA["month"])}</div></div></div>''')

SALES = DATA["sales"]
POSS_BY_NAME = {p["name"]: max(math.floor(p["cases"]), 0) for p in DATA["possible"]}
tab_sales, tab_purchase, tab_prod = st.tabs(["Sales Plan", "Purchase Plan", "Production Plan"])


# ================================================================= SALES PLAN
def sku_head(k: str) -> str:
    """Pack-size heading on two lines: size on top, material below (as in the HTML)."""
    m = re.match(r"^(\d+\s*ml)\s*(.*)$", str(k).strip(), re.I)
    if not m:
        return esc(k)
    return esc(m.group(1)).replace(" ", "&nbsp;") + f'<span class="sub">{esc(m.group(2)) or "&nbsp;"}</span>'


def pivot_table(G, sku_cols, field, expand=None, cls: str = "") -> str:
    def val(b, k, f):
        return G[b].get(k, {}).get(f, 0)

    brands = sorted(b for b in G if any(G[b].get(k, {}).get("sales", 0) > 0 or G[b].get(k, {}).get("prod", 0) > 0
                                        for k in sku_cols))
    headers = [("Brand", False)] + [(sku_head(k), True) for k in sku_cols] + [("Total", True)]
    rows = []
    for b in brands:
        tot = sum(val(b, k, field) for k in sku_cols)
        rows.append(("head", [esc(b)] + [cell(val(b, k, field)) for k in sku_cols] + [fmt_c(tot)]))
        for label, f in (expand or []):
            t = sum(val(b, k, f) for k in sku_cols)
            rows.append(("detail main" if f == field else "detail",
                         [label] + [cell(val(b, k, f)) for k in sku_cols] + [fmt_c(t)]))
    col_tot = [sum(val(b, k, field) for b in brands) for k in sku_cols]
    rows.append(("total", ["TOTAL"] + [fmt_c(v) if v else DASH for v in col_tot] + [fmt_c(sum(col_tot))]))
    return table(headers, rows, cls)


with tab_sales:
    k = DATA["kpi"]
    kpis([("FG Sales Plan", fmt(k["totalSales"]), "cases · sales target"),
          ("FG Opening Stock", fmt(sum(s["opening"] for s in SALES)), "cases · at month start"),
          ("Possible Production from Opening RM", fmt(sum(POSS_BY_NAME.get(s["name"], 0) for s in SALES)),
           "cases · without purchasing"),
          ("Closing FG Cases", fmt(sum(s["closing"] for s in SALES)), "cases · required at month end"),
          ("Production Required", fmt(k["totalProd"]), "cases (after opening FG)")])

    # ---- brand summary
    sec("Brand Summary", "Cases")
    bs = {}
    for s in SALES:
        g = bs.setdefault(s["cat"] or "Uncategorised", {"sales": 0, "poss": 0, "prod": 0, "close": 0})
        g["sales"] += s["sales"]
        g["poss"] += POSS_BY_NAME.get(s["name"], 0)
        g["prod"] += s["prod"]
        g["close"] += s["closing"]
    rows, tot = [], {"sales": 0, "poss": 0, "prod": 0, "close": 0}
    for b in sorted(b for b, g in bs.items() if any(v > 0 for v in g.values())):
        g = bs[b]
        for f in tot:
            tot[f] += g[f]
        rows.append(("head", [esc(b), cell(g["sales"]), cell(g["poss"]), cell(g["prod"]), cell(g["close"])]))
    rows.append(("total", ["TOTAL"] + [fmt_c(tot[f]) for f in ("sales", "poss", "prod", "close")]))
    show(table([("Brand", False), ("FG Sales Plan", True), ("FG Production from Opening RM", True),
                ("Production Required", True), ("Closing FG Cases", True)], rows))
    legend("Brand-wise totals (cases). <b>FG Production from Opening RM</b> is the maximum producible from opening "
           "raw-material stock without purchasing; <b>Production Required</b> = Sales Plan + Closing FG "
           "− Opening FG (floored at zero per SKU).")

    # ---- brand x pack-size pivots
    G = {}
    for s in SALES:
        c = G.setdefault(s["cat"] or "Uncategorised", {}).setdefault(
            s["sku"] or DASH, {"sales": 0, "closing": 0, "opening": 0, "prod": 0, "poss": 0})
        for f in ("sales", "closing", "opening", "prod"):
            c[f] += s[f]
        c["poss"] += POSS_BY_NAME.get(s["name"], 0)
    all_sku = DATA["skuList"] or list(dict.fromkeys(s["sku"] or DASH for s in SALES))
    active = [x for x in all_sku if any(G[b].get(x) and (G[b][x]["sales"] > 0 or G[b][x]["prod"] > 0
                                                         or G[b][x]["poss"] > 0) for b in G)]
    sku_cols = active or all_sku

    pair = st.columns(2)
    with pair[0]:
        sec("Finished Goods Sales Plan", "Cases")
        show(pivot_table(G, sku_cols, "sales", cls="compact"))
        legend("Sales plan quantity (cases) by brand and pack size.")
    with pair[1]:
        sec("Possible Production from Opening Stock", "Cases")
        show(pivot_table(G, sku_cols, "poss", cls="compact"))
        legend("Maximum cases producible from <b>opening raw-material stock only</b>. Blend and sealing tape are "
               "treated as unlimited; shared bottles/caps are split equally.")

    sec("Production Required", "Cases")
    build_up = st.toggle("Show build-up (Sales + Closing − Opening)", key="prod_buildup")
    show(pivot_table(G, sku_cols, "prod", [("Sales Plan Qty", "sales"), ("Add: Req. Closing Stock", "closing"),
                                           ("Less: Opening Stock", "opening"),
                                           ("= Production Required", "prod")] if build_up else None))
    legend("Sales Plan Qty + Required Closing Stock − Opening Stock = Production Required (floored at zero).")

    # ---- blend
    sec("Blend (Sub-Product) Requirement", "Bulk Litres")
    show(table([("Blend Code", False), ("Blend (Sub-Product)", False), ("Gross Demand (BL)", True),
                ("Opening Blend (BL)", True), ("Req. Closing (BL)", True), ("Net to Produce (BL)", True)],
               [("", [b["code"], esc(b["name"]), fmt(b["gross"]), fmt(b["opening"]), fmt(b["closing"]),
                      f"<b>{fmt(b['net'])}</b>"]) for b in DATA["blends"]]))
    legend("Net Blend to Produce = Gross Blend Demand + Required Closing Blend Stock − Opening Blend Stock. "
           "Only the net is exploded into spirits &amp; flavours.")

    # ---- possible production detail
    sec("Possible Production — Item Detail & Limiting Material", "Cases")
    detail = sorted((r for r in DATA["possible"] if r["binding"] and r["binding"] != DASH),
                    key=lambda r: (r["cat"] or "", r["name"]))
    rows, export, grand, grand_max = [], [], 0, 0
    for cat in sorted({r["cat"] for r in detail}):
        rows.append(("group", [esc(cat), "", "", "", "", ""]))
        sub = sub_max = 0
        for r in (x for x in detail if x["cat"] == cat):
            lo, hi = math.floor(r["cases"]), math.floor(r["maxCases"])
            sub += lo
            sub_max += hi
            pill = f'<span class="pill">÷{r["shared"]}</span>' if r["shared"] > 1 else ""
            pill_max = f'<span class="pill">÷{r["maxShared"]}</span>' if r["maxShared"] > 1 else ""
            rows.append(("", [r["code"], esc(r["name"]), f"<b>{fmt(lo)}</b>", esc(r["binding"]) + pill,
                              fmt(hi), esc(r["maxItem"]) + pill_max]))
            export.append({"Brand (Category)": cat, "FG Code": r["code"], "Finished Good": r["name"],
                           "Min Possible Cases": lo, "Min Shared Among": max(r["shared"], 1),
                           "Limited By (scarcest raw material)": r["binding"],
                           "Max Possible Cases": hi, "Max Shared Among": max(r["maxShared"], 1),
                           "Enabled By (best-stocked raw material)": r["maxItem"]})
        rows.append(("subtotal", ["", f"{esc(cat)} subtotal", fmt(sub), "", fmt(sub_max), ""]))
        grand += sub
        grand_max += sub_max
    rows.append(("total", ["", "GRAND TOTAL", fmt(grand), "", fmt(grand_max), ""]))
    st.download_button("Export CSV", csv_bytes(pd.DataFrame(export)),
                       f"Possible_Production_{month_slug(DATA['month'])}.csv", "text/csv", key="dl_poss")
    show(table([("FG Code", False), ("Finished Good", False), ("Min Possible Cases", True),
                ("Limited By (scarcest raw material)", False), ("Max Possible Cases", True),
                ("Enabled By (best-stocked raw material)", False)], rows))
    legend("<b>Min Possible Cases</b> is what you can actually build — each SKU capped by its scarcest raw "
           "material. <b>Max Possible Cases</b> is the ceiling implied by the best-stocked raw material. "
           "÷N marks stock shared equally among N finished goods. Figures are per-SKU and are not "
           "simultaneously achievable across SKUs that share a material.")


# ================================================================= PURCHASE PLAN
with tab_purchase:
    k = DATA["kpi"]
    kpis([("Raw Material Items", fmt(k["rmItems"]), "distinct items in plan"),
          ("Items to Purchase", fmt(k["buyItems"]), "net shortfall > 0"),
          ("ENA Spirit to Buy", fmt(k["enaLtr"]), "litres")])

    sec("Raw Material Purchase Plan")
    RM = DATA["rm"]
    f1 = st.columns(3) + st.columns(3)
    q = f1[0].text_input("Search item / code", key="rm_q").strip().lower()
    cat = f1[1].selectbox("Item Category", ["All Item Categories"] + sorted(DATA["catList"]), key="rm_cat")
    cat = "" if cat.startswith("All ") else cat
    fgs = sorted((f for f in DATA["fgList"] if not cat or f["cat"] == cat), key=lambda f: f["name"])
    fg_names = {f["code"]: f["name"] for f in fgs}
    fg = f1[2].selectbox("Finished Good", [""] + list(fg_names), key="rm_fg",
                         format_func=lambda c: fg_names.get(c, "All FGs in category" if cat else "All Finished Goods"))
    typ = f1[3].selectbox("Type", ["All Types"] + sorted({r["type"] for r in RM}), key="rm_type")
    grp = f1[4].selectbox("Group", ["All Groups"] + sorted({r["group"] for r in RM}), key="rm_group")
    mode = f1[5].selectbox("Show", ["Need to Purchase", "All Items", "Surplus / Covered"], key="rm_show",
                           disabled=bool(fg or cat))

    picked = []
    for r in RM:
        if q and not (q in r["desc"].lower() or q in r["code"]):
            continue
        if typ != "All Types" and r["type"] != typ:
            continue
        if grp != "All Groups" and r["group"] != grp:
            continue
        if fg:
            if r["byFG"].get(fg, 0) <= 0:
                continue
        elif cat:
            if r["byCat"].get(cat, 0) <= 0:
                continue
        elif mode == "Need to Purchase" and r["buy"] <= 0:
            continue
        elif mode == "Surplus / Covered" and r["surplus"] <= 0:
            continue
        picked.append(r)
    picked.sort(key=lambda r: r["desc"].lower())

    base = {"Item Code": [r["code"] for r in picked], "Raw Material": [r["desc"] for r in picked],
            "UOM": [r["uom"] for r in picked], "Type": [r["type"] for r in picked],
            "Group": [r["group"] for r in picked]}
    if fg or cat:
        label = f"Requirement for {fg_names[fg]}" if fg else f"Requirement for category {cat}"
        df = pd.DataFrame({**base, label: [(r["byFG"].get(fg, 0) if fg else r["byCat"].get(cat, 0)) for r in picked]})
        num_cols, suffix = [label], ("_byFG" if fg else "_byCategory")
        st.caption(f"**{fg_names[fg] if fg else cat + ' (category)'}** — {len(df)} materials "
                   "(share of shared materials shown pro-rata)")
    else:
        df = pd.DataFrame({**base,
                           "Gross Requirement": [r["gross"] for r in picked],
                           "Required Closing Stock": [r["close"] for r in picked],
                           "Total Requirement": [r["req"] for r in picked],
                           "Opening Stock": [r["open"] for r in picked],
                           "To Purchase": [r["buy"] for r in picked],
                           "Surplus": [r["surplus"] for r in picked]})
        num_cols, suffix = list(df.columns[5:]), ""
        st.caption(f"**{k['buyItems']} items to buy** · showing {len(df)} rows · click a column heading to sort")

    st.download_button("Export CSV", csv_bytes(df), f"RM_Purchase_Plan_{month_slug(DATA['month'])}{suffix}.csv",
                       "text/csv", key="dl_rm")
    styler = df.style.format({c: (lambda v: fmt(v, 2)) for c in num_cols})
    if "To Purchase" in df.columns:
        styler = styler.map(lambda v: "color:#c0392b;font-weight:600" if v > 0 else "color:#2e8b57",
                            subset=["To Purchase"])
    st.dataframe(styler, hide_index=True, width="stretch", height=560)
    legend("To Purchase = Gross Requirement + <b>Required Closing Stock</b> − Opening Stock (floored at zero). "
           "Required closing stock is read from the <i>RM_Closing</i> sheet (summed per material across all "
           "finished goods). Surplus = Opening Stock in excess of total requirement. Select an <b>Item Category</b> "
           "or a <b>Finished Good</b> to see the raw-material quantity that category / good consumes.")


# ================================================================= PRODUCTION PLAN
with tab_prod:
    if not LINES:
        st.warning("The workbook has no readable **Line_Production** sheet, so a production schedule cannot be built.")
        st.stop()
    line_names = list(LINES)

    sec("Available Days per Line", "New")
    st.caption(f"Enter the days each line is available this month (0 – {pe.MAX_DAYS_PER_MONTH}). They are spread "
               f"evenly over {pe.PLAN_WEEKS} weeks, with one weekly holiday (maximum {pe.MAX_DAYS_PER_WEEK} working "
               "days a week).")
    monthly_days = {}
    day_cols = st.columns(len(line_names))
    for col, ln in zip(day_cols, line_names):
        monthly_days[ln] = col.number_input(f"{ln} – days in month", min_value=0.0,
                                            max_value=float(pe.MAX_DAYS_PER_MONTH),
                                            value=float(pe.MAX_DAYS_PER_MONTH), step=1.0, format="%g",
                                            key=f"days_{ln}")
    P = pe.compute_production_plan(DATA, LINES, monthly_days)
    for col, ln in zip(day_cols, line_names):
        col.caption(f"{P['daysPerWeek'][ln]:g} days / week")

    pct = round(P["scheduled"] / P["demand"] * 100) if P["demand"] else 0
    kpis([("Production Required", fmt(P["demand"]), "cases this month"),
          (f"Scheduled ({P['weeks']} weeks)", fmt(P["scheduled"]), f"{pct}% of requirement"),
          ("Shortfall", fmt(P["shortTotal"]), "needs management action"),
          ("Line-days Available", f"{P['totalDays']:g}", "sum of available days, all lines")])

    # ---- weekly plan
    sec("Weekly Production Plan", "Cases · 4 weeks")
    top = st.columns([3, 1])
    sku_detail = top[0].toggle("Show SKU detail under each line", value=True, key="wk_detail")
    plan_df = pd.DataFrame([{"Week": f"Week {r['week']}", "Line": r["line"], "SKU": r["sku"],
                             "Rate per day": r["rate"], "Cases": round(r["cases"], 2), "Days": r["days"]}
                            for r in P["plan"]], columns=["Week", "Line", "SKU", "Rate per day", "Cases", "Days"])
    top[1].download_button("Export CSV", csv_bytes(plan_df), f"Production_Plan_{month_slug(DATA['month'])}.csv",
                           "text/csv", key="dl_plan")

    def week_html(wk: int) -> str:
        rws = [r for r in P["plan"] if r["week"] == wk]
        total = sum(r["cases"] for r in rws)
        out = f'<div class="weekhead"><span>Week {wk}</span><span>{fmt(total)} cases</span></div>'
        if not rws:
            return out + '<div class="weekempty">No production scheduled this week.</div>'
        rows = []
        for ln in line_names:
            rs = sorted((r for r in rws if r["line"] == ln), key=lambda r: -r["cases"])
            if not rs:
                continue
            rates = {r["rate"] for r in rs}
            rows.append(("head", [esc(ln), fmt(rs[0]["rate"]) if len(rates) == 1 else "mixed",
                                  fmt(sum(r["cases"] for r in rs)), f"{sum(r['days'] for r in rs):.2f}"]))
            if sku_detail:
                rows += [("detail", [esc(r["sku"]), fmt(r["rate"]), fmt(r["cases"]), f"{r['days']:.2f}"]) for r in rs]
        rows.append(("total", ["Total", "", fmt(total), f"{sum(r['days'] for r in rws):.2f}"]))
        return out + table([("Line / SKU", False), ("Rate", True), ("Cases", True), ("Days", True)], rows, "week")

    for first in range(1, P["weeks"] + 1, 2):
        pair = st.columns(2)
        for i, wk in enumerate(range(first, min(first + 2, P["weeks"] + 1))):
            with pair[i]:
                show(week_html(wk))
    legend("Based on the Line_Production sheet: each SKU runs at its own cases/day rate on its line. One SKU per "
           "line per day, with fill-days so part-days are not wasted. Week 1 is limited to volume supported by "
           "opening raw-material stock; purchased material (5-day lead time) flows from Week 2. "
           f"{pe.PRIORITY_BRANDS[0]} is always given first priority, {pe.PRIORITY_BRANDS[1]} second.")

    # ---- line-wise capacity
    sec("Line-wise Capacity Analysis")
    L = P["lineAnalysis"]
    over = [r["line"] for r in L if r["balance"] < 0]
    st.caption((", ".join(over) + " over capacity") if over else "All lines within capacity")

    def bal(v):
        return f'<span class="{"neg" if v < 0 else "pos"}">{"+" if v >= 0 else ""}{v:.2f}</span>'

    rows = [("", [esc(r["line"]), fmt(r["demand"]), f"{r['daysNeeded']:.2f}", f"{r['daysAvail']:g}",
                  f"{r['daysPerWeek']:g}", bal(r["balance"]), fmt(r["scheduled"]),
                  f'<span class="neg">{fmt(r["short"])}</span>' if r["short"] > 0 else DASH]) for r in L]
    t_need, t_avail = sum(r["daysNeeded"] for r in L), sum(r["daysAvail"] for r in L)
    rows.append(("total", ["Total", fmt(sum(r["demand"] for r in L)), f"{t_need:.2f}", f"{t_avail:g}", "",
                           bal(t_avail - t_need), fmt(sum(r["scheduled"] for r in L)),
                           fmt(sum(r["short"] for r in L))]))
    show(table([("Line", False), ("Demand (cases)", True), ("Days Needed", True), ("Days Available", True),
                ("Days / Week", True), ("Excess (+) / Short (−)", True), ("Scheduled", True),
                ("Shortfall", True)], rows))
    legend("Days Needed = production demand ÷ that SKU's own daily rate, summed for the line. Days Available "
           "is the figure you entered above. A negative balance means the line cannot complete its demand within "
           "its available days.")

    # ---- brand-wise capacity
    sec("Brand-wise Capacity Analysis")
    brand_detail = st.toggle("Show SKU detail under each brand", key="brand_detail")
    B = P["brandAnalysis"]

    def short_cell(v, text):
        return f'<span class="neg">{text}</span>' if v > 0 else DASH

    rows = []
    for g in B:
        rows.append(("head", [esc(g["brand"]), ", ".join(l.replace("Line ", "L") for l in g["lines"]),
                              fmt(g["demand"]), f"{g['daysNeeded']:.2f}", fmt(g["scheduled"]),
                              short_cell(g["short"], fmt(g["short"])),
                              short_cell(g["short"], f"{g['shortDays']:.2f}")]))
        if brand_detail:
            rows += [("detail", [esc(s["sku"]), f"{s['line'].replace('Line ', 'L')} · {fmt(s['cap'])}/day",
                                 fmt(s["demand"]), f"{s['daysNeeded']:.2f}", fmt(s["scheduled"]),
                                 short_cell(s["short"], fmt(s["short"])),
                                 short_cell(s["short"], f"{s['shortDays']:.2f}")]) for s in g["skus"]]
    rows.append(("total", ["Total", "", fmt(sum(g["demand"] for g in B)), f"{sum(g['daysNeeded'] for g in B):.2f}",
                           fmt(sum(g["scheduled"] for g in B)), fmt(sum(g["short"] for g in B)),
                           f"{sum(g['shortDays'] for g in B):.2f}"]))
    show(table([("Brand / SKU", False), ("Lines", False), ("Demand (cases)", True), ("Days Needed", True),
                ("Scheduled", True), ("Short (cases)", True), ("Short (days)", True)], rows))
    legend("<i>Short (days)</i> is the unmade quantity divided by that SKU's own rate.")

    # ---- shortfall
    sec("Production Shortfall")
    if not P["shortfall"]:
        st.success("No shortfall — the full month's requirement fits within the available line days.")
    else:
        rows = [("", [esc(r["sku"]), esc(r["line"]), f'<span class="neg">{fmt(r["cases"])}</span>',
                      f'<span class="reason">{esc(r["reason"])}</span>']) for r in P["shortfall"]]
        rows.append(("total", ["", "Total shortfall", fmt(P["shortTotal"]), ""]))
        show(table([("SKU", False), ("Line", False), ("Cases Short", True), ("Reason", False)], rows))
        st.download_button("Export shortfall CSV",
                           csv_bytes(pd.DataFrame([{"SKU": r["sku"], "Line": r["line"], "Cases Short": r["cases"],
                                                    "Reason": r["reason"]} for r in P["shortfall"]])),
                           f"Production_Shortfall_{month_slug(DATA['month'])}.csv", "text/csv", key="dl_short")
    legend("Cases that cannot be produced within the available line days. These need management action: add "
           "available days, adjust the sales plan, or carry forward.")

show('''<div class="note"><b>Note:</b> A <b>Blend</b> is a semi-finished (sub) product, <u>not</u> a finished good.
Each finished good consumes a Blend (per its FG BOM, defined per 1,000 cases); each Blend in turn consumes spirits &amp;
flavours (per its Blend BOM, defined per 1,000 BL). The planner nets blend demand against opening blend stock first,
then explodes the shortfall into raw materials.</div>''')
show(f'''<div class="foot">Planning period: <b>{esc(DATA["month"])}</b> · Generated by the RM Purchase &amp; FG Production Planner.
Logic: FG Sales Plan → net opening FG → explode FG BOM (per 1,000 cases) into packing materials + blend demand →
net opening blend stock → explode Blend BOM (per 1,000 BL) into spirits &amp; flavours → net opening raw-material
stock → <b>To Purchase</b>.</div>''')
