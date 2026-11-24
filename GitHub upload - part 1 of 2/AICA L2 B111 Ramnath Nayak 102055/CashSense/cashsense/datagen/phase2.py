"""Phase 2 test data: the Phase 1 statements rendered the way banks actually send them.

  CA01  Sample Bank of India   -> bank CSV export (metadata rows, dd-mm-yyyy, Indian number format)
  CC01  Sample Heritage Bank   -> digital PDF, landscape, grid table, balances with Dr/Cr
  CL01  Sample Kaveri Bank     -> phone photos of a printed statement (tilt, shadow, noise, JPEG)
  EF01  Sample Kaveri Bank     -> digital PDF in USD

Periods: October 2025 and March 2026. The answer key holds the exact expected lines for every
rendered file and the true category of every Phase 1 bank line.
"""
from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from datetime import date
from pathlib import Path

from ..categories import truth_category
from ..money import fmt_num, to_paise

PERIODS = ("2025-10", "2026-03")
RENDER = {"CA01": "csv", "CC01": "pdf", "CL01": "photo", "EF01": "pdf"}
COMPANY_NAME = "SAMPLE PRECISION COMPONENTS PVT LTD (SAMPLE)"
FONT_DIR = Path("C:/Windows/Fonts")


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_statement(p1: Path, account_id: str, period: str) -> dict:
    acc = next(a for a in _rows(p1 / "bank_accounts.csv") if a["account_id"] == account_id)
    idx = next(s for s in _rows(p1 / "statement_index.csv") if s["account_id"] == account_id and s["period"] == period)
    y, m = map(int, period.split("-"))
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return {"account": acc, "account_id": account_id, "period": period, "currency": acc["currency"],
            "from": date(y, m, 1), "to": date.fromordinal(nxt.toordinal() - 1),
            "opening": to_paise(idx["opening"]), "closing": to_paise(idx["closing"]),
            "debits": to_paise(idx["debits"]), "credits": to_paise(idx["credits"]),
            "lines": _rows(p1 / idx["file"])}


def _side(minor: int, currency: str) -> str:
    return f"{fmt_num(abs(minor), currency)} {'Dr' if minor < 0 else 'Cr'}"


def _d(iso: str, fmt: str) -> str:
    return date.fromisoformat(iso).strftime(fmt)


# ----------------------------------------------------------------------------- CSV
def render_csv(st: dict, path: Path) -> None:
    a, cur = st["account"], st["currency"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"{a['bank_name'].upper()} - ACCOUNT STATEMENT"])
        w.writerow(["Account Name:", COMPANY_NAME])
        w.writerow(["Account Number:", a["account_no"]])
        w.writerow(["IFSC:", a["ifsc"]])
        w.writerow(["Statement Period:", f"{st['from']:%d-%m-%Y} to {st['to']:%d-%m-%Y}"])
        w.writerow(["Opening Balance:", fmt_num(st["opening"], cur)])
        w.writerow([])
        w.writerow(["Tran Date", "Value Date", "Particulars", "Chq/Ref No", "Withdrawal (Dr)", "Deposit (Cr)",
                    "Balance"])
        for r in st["lines"]:
            w.writerow([_d(r["txn_date"], "%d-%m-%Y"), _d(r["value_date"], "%d-%m-%Y"), r["description"], r["ref_no"],
                        fmt_num(to_paise(r["debit"]), cur) if r["debit"] else "",
                        fmt_num(to_paise(r["credit"]), cur) if r["credit"] else "",
                        fmt_num(to_paise(r["balance"]), cur)])
        w.writerow([])
        w.writerow(["Closing Balance:", fmt_num(st["closing"], cur)])
        w.writerow(["Total Withdrawals:", fmt_num(st["debits"], cur)])
        w.writerow(["Total Deposits:", fmt_num(st["credits"], cur)])
        w.writerow(["*** SAMPLE STATEMENT - FICTITIOUS DATA ***"])


# ----------------------------------------------------------------------------- PDF
PDF_COLS = (("Date", 62), ("Narration", 340), ("Ref No", 112), ("Debit", 88), ("Credit", 88), ("Balance", 100))
PDF_ROWS_PER_PAGE = 30


def render_pdf(st: dict, path: Path) -> None:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    a, cur = st["account"], st["currency"]
    W, H = landscape(A4)
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(W, H), invariant=1)
    c.setTitle(f"SAMPLE statement {a['account_id']} {st['period']}")
    lines = st["lines"]
    chunks = [lines[i:i + PDF_ROWS_PER_PAGE] for i in range(0, len(lines), PDF_ROWS_PER_PAGE)] or [[]]
    x0, row_h = 30, 14
    for pno, chunk in enumerate(chunks, 1):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x0, H - 40, a["bank_name"].upper())
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(W - 30, H - 40, "STATEMENT OF ACCOUNT  -  SAMPLE / FICTITIOUS")
        c.setFont("Helvetica", 9)
        c.drawString(x0, H - 58, f"Customer: {COMPANY_NAME}")
        c.drawString(x0, H - 71, f"Account No: {a['account_no']}   Type: {a['name']}   IFSC: {a['ifsc']}   Currency: {cur}")
        c.drawString(x0, H - 84, f"Period: {st['from']:%d/%m/%Y} to {st['to']:%d/%m/%Y}")
        if pno == 1:
            c.drawString(x0, H - 97, f"Opening Balance: {_side(st['opening'], cur)}")
        top = H - 112
        n_rows = len(chunk) + 1
        xs = [x0]
        for _, wdt in PDF_COLS:
            xs.append(xs[-1] + wdt)
        c.setLineWidth(0.4)
        for i in range(n_rows + 1):
            c.line(xs[0], top - i * row_h, xs[-1], top - i * row_h)
        for x in xs:
            c.line(x, top, x, top - n_rows * row_h)
        c.setFont("Helvetica-Bold", 7.5)
        for (name, _), x, x_end in zip(PDF_COLS, xs, xs[1:]):
            if name in ("Debit", "Credit", "Balance"):
                c.drawRightString(x_end - 3, top - row_h + 4, name)
            else:
                c.drawString(x + 3, top - row_h + 4, name)
        c.setFont("Helvetica", 7)
        for i, r in enumerate(chunk, 1):
            y = top - (i + 1) * row_h + 4
            c.drawString(xs[0] + 3, y, _d(r["txn_date"], "%d/%m/%Y"))
            c.drawString(xs[1] + 3, y, r["description"])
            c.drawString(xs[2] + 3, y, r["ref_no"])
            if r["debit"]:
                c.drawRightString(xs[4] - 3, y, fmt_num(to_paise(r["debit"]), cur))
            if r["credit"]:
                c.drawRightString(xs[5] - 3, y, fmt_num(to_paise(r["credit"]), cur))
            c.drawRightString(xs[6] - 3, y, _side(to_paise(r["balance"]), cur))
        c.setFont("Helvetica", 9)
        if pno == len(chunks):
            yb = top - n_rows * row_h - 18
            c.drawString(x0, yb, f"Closing Balance: {_side(st['closing'], cur)}")
            c.drawString(x0, yb - 13, f"Total Debits: {fmt_num(st['debits'], cur)}    "
                                      f"Total Credits: {fmt_num(st['credits'], cur)}")
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(x0, 20, "SAMPLE STATEMENT - FICTITIOUS DATA - generated for the CashSense capstone")
        c.drawRightString(W - 30, 20, f"Page {pno} of {len(chunks)}")
        c.showPage()
    c.save()


# ----------------------------------------------------------------------------- photo
PHOTO_ROWS_PER_PAGE = 24


def _font(name: str, size: int):
    from PIL import ImageFont

    for candidate in (FONT_DIR / name, FONT_DIR / "arial.ttf"):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _page_image(st: dict, chunk: list[dict], pno: int, pages: int):
    from PIL import Image, ImageDraw

    a, cur = st["account"], st["currency"]
    img = Image.new("RGB", (1240, 1754), (252, 252, 248))
    dr = ImageDraw.Draw(img)
    title, bold, body = _font("arialbd.ttf", 34), _font("arialbd.ttf", 19), _font("consola.ttf", 18)
    # light diagonal watermark
    wm = Image.new("L", (1240, 1754), 0)
    ImageDraw.Draw(wm).text((180, 700), "SAMPLE", font=_font("arialbd.ttf", 260), fill=255)
    wm = wm.rotate(30, center=(620, 877))
    img.paste((236, 236, 236), mask=wm.point(lambda v: 255 if v > 128 else 0))
    dr.text((60, 50), a["bank_name"].upper(), font=title, fill=(20, 40, 90))
    dr.text((60, 100), "STATEMENT OF ACCOUNT (SAMPLE - FICTITIOUS DATA)", font=bold, fill=(30, 30, 30))
    dr.text((60, 140), f"{COMPANY_NAME}", font=body, fill=(30, 30, 30))
    dr.text((60, 168), f"A/c No: {a['account_no']}   {a['name']}   IFSC: {a['ifsc']}", font=body, fill=(30, 30, 30))
    dr.text((60, 196), f"Statement from {st['from']:%d %b %Y} to {st['to']:%d %b %Y}   Page {pno} of {pages}",
            font=body, fill=(30, 30, 30))
    y = 240
    if pno == 1:
        dr.text((60, y), f"Opening Balance: {_side(st['opening'], cur)}", font=bold, fill=(0, 0, 0))
        y += 36
    cols = {"date": 60, "part": 200, "wd_r": 855, "dp_r": 1000, "bal_r": 1195}
    dr.line((50, y, 1200, y), fill=(60, 60, 60), width=2)
    dr.text((cols["date"], y + 6), "Date", font=bold, fill=(0, 0, 0))
    dr.text((cols["part"], y + 6), "Particulars", font=bold, fill=(0, 0, 0))
    for label, key in (("Withdrawals", "wd_r"), ("Deposits", "dp_r"), ("Balance", "bal_r")):
        dr.text((cols[key], y + 6), label, font=bold, fill=(0, 0, 0), anchor="ra")
    y += 36
    dr.line((50, y, 1200, y), fill=(60, 60, 60), width=1)
    for r in chunk:
        wrapped = textwrap.wrap(r["description"], width=44, break_on_hyphens=True)[:2] or [""]
        dr.text((cols["date"], y + 6), _d(r["txn_date"], "%d %b %Y"), font=body, fill=(15, 15, 15))
        for k, part in enumerate(wrapped[:2]):
            dr.text((cols["part"], y + 6 + k * 24), part, font=body, fill=(15, 15, 15))
        if r["debit"]:
            dr.text((cols["wd_r"], y + 6), fmt_num(to_paise(r["debit"]), cur), font=body, fill=(15, 15, 15), anchor="ra")
        if r["credit"]:
            dr.text((cols["dp_r"], y + 6), fmt_num(to_paise(r["credit"]), cur), font=body, fill=(15, 15, 15), anchor="ra")
        dr.text((cols["bal_r"], y + 6), _side(to_paise(r["balance"]), cur), font=body, fill=(15, 15, 15), anchor="ra")
        y += 24 * max(1, len(wrapped[:2])) + 14
        dr.line((50, y, 1200, y), fill=(200, 200, 200), width=1)
    if pno == pages:
        y += 20
        dr.text((60, y), f"Closing Balance: {_side(st['closing'], cur)}", font=bold, fill=(0, 0, 0))
        dr.text((60, y + 30), f"Total Withdrawals: {fmt_num(st['debits'], cur)}   "
                              f"Total Deposits: {fmt_num(st['credits'], cur)}", font=body, fill=(0, 0, 0))
    return img


def _photo_effect(img, seed: int):
    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.RandomState(seed)
    desk = (88, 70, 56)
    rot = img.rotate(float(rng.uniform(-1.8, 1.8)), expand=True, resample=Image.BICUBIC, fillcolor=desk)
    canvas = Image.new("RGB", (rot.width + 120, rot.height + 140), desk)
    canvas.paste(rot, (60 + int(rng.randint(-15, 15)), 70 + int(rng.randint(-15, 15))))
    arr = np.asarray(canvas).astype(np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    light = 1.0 - 0.18 * ((xx / w) * 0.6 + (yy / h) * 0.4)          # soft shadow towards bottom-right
    arr = arr * light[..., None] + rng.normal(0, 5.0, arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    return out


def _row_height(r: dict) -> int:
    return 24 * max(1, len(textwrap.wrap(r["description"], width=44, break_on_hyphens=True)[:2])) + 14


def _photo_pages(lines: list[dict]) -> list[list[dict]]:
    """Break pages by printed height so no row runs off the paper (1754 px page, 90 px reserved
    at the bottom for the closing balance)."""
    pages, cur, y = [], [], 312            # page 1 table starts lower (opening balance line)
    for r in lines:
        h = _row_height(r)
        if cur and (y + h > 1754 - 150 or len(cur) >= PHOTO_ROWS_PER_PAGE):
            pages.append(cur)
            cur, y = [], 276
        cur.append(r)
        y += h
    pages.append(cur)
    return pages


def render_photos(st: dict, out_dir: Path, stem: str, seed: int) -> list[Path]:
    chunks = _photo_pages(st["lines"])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for pno, chunk in enumerate(chunks, 1):
        photo = _photo_effect(_page_image(st, chunk, pno, len(chunks)), seed + pno)
        p = out_dir / f"{stem}_page{pno}.jpg"
        photo.save(p, "JPEG", quality=82)
        paths.append(p)
    return paths


# ----------------------------------------------------------------------------- driver
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def generate(p1: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    key_dir = out_dir / "answer_key"
    (key_dir / "expected").mkdir(parents=True, exist_ok=True)
    files = []
    for n, (acc, fmt) in enumerate(sorted(RENDER.items())):
        for period in PERIODS:
            st = load_statement(p1, acc, period)
            stem = f"{acc}_{period}"
            if fmt == "csv":
                paths = [out_dir / "statements" / f"{stem}_bank_export.csv"]
                render_csv(st, paths[0])
            elif fmt == "pdf":
                paths = [out_dir / "statements" / f"{stem}.pdf"]
                render_pdf(st, paths[0])
            else:
                paths = render_photos(st, out_dir / "statements", f"{stem}_photo", seed=2026 + n * 10 + int(period[-2:]))
            expected = {"account_id": acc, "period": period, "currency": st["currency"], "format": fmt,
                        "account_no": st["account"]["account_no"],
                        "opening": str(st["opening"]), "closing": str(st["closing"]),
                        "files": [p.relative_to(out_dir).as_posix() for p in paths], "lines": st["lines"]}
            (key_dir / "expected" / f"{stem}.json").write_text(json.dumps(expected, indent=1), encoding="utf-8")
            files.append({"account_id": acc, "period": period, "format": fmt,
                          "files": expected["files"], "lines": len(st["lines"])})

    kinds = _rows(p1 / "answer_key" / "line_kinds.csv")
    with (key_dir / "categories_truth.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["line_id", "account_id", "category", "party_id"])
        for k in kinds:
            w.writerow([k["line_id"], k["account_id"], truth_category(k["kind"], k["party_category"]), k["party_id"]])

    all_files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "manifest.json"
                       and p.suffix in (".csv", ".json", ".pdf", ".jpg")
                       and p.relative_to(out_dir).parts[0] in ("statements", "answer_key"))
    manifest = {"phase": 2, "statements": files,
                "files": {p.relative_to(out_dir).as_posix(): _sha(p) for p in all_files}}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
