"""PDF reports (landscape A4) built with ReportLab."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#1F3A5F")
PALE = colors.HexColor("#F3F6FA")


def _inr(v, dec=2):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v or "")
    neg, v = v < 0, abs(v)
    s = f"{v:.{dec}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    out = whole + ("." + frac if dec else "")
    return "-" + out if neg else out


def _table(df, cols, money=(), rupee=(), widths=None):
    style = getSampleStyleSheet()["BodyText"].clone("cell")
    style.fontSize, style.leading = 7, 8.5
    head = [Paragraph(f"<b><font color='white'>{c}</font></b>", style) for c in cols]
    rows = [head]
    for _, r in df.iterrows():
        row = []
        for c in cols:
            v = r[c]
            if c in money:
                row.append(_inr(v))
            elif c in rupee:
                row.append(_inr(v, 0))
            elif "Date" in c and isinstance(v, str) and len(v) == 10 and v[4] == "-":
                row.append(f"{v[8:]}-{v[5:7]}-{v[:4]}")
            else:
                row.append(Paragraph(str(v if v is not None else ""), style))
        rows.append(row)
    t = Table(rows, colWidths=widths, repeatRows=1)
    ts = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("FONTSIZE", (0, 1), (-1, -1), 7),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7DE"))]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            ts.append(("BACKGROUND", (0, i), (-1, i), PALE))
    for j, c in enumerate(cols):
        if c in money or c in rupee:
            ts.append(("ALIGN", (j, 1), (j, -1), "RIGHT"))
    t.setStyle(TableStyle(ts))
    return t


def build_pdf(frames: dict, path: Path, client_label: str = "All clients") -> Path:
    ss = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title="Contract Note Register", author="Investor Manager")
    story = [Paragraph("Contract Note Register", ss["Title"]),
             Paragraph(f"{client_label} &nbsp;|&nbsp; generated {datetime.now():%d-%m-%Y %H:%M}", ss["Normal"]),
             Spacer(1, 6 * mm)]

    nf = frames["notes"]
    if len(nf):
        story.append(Paragraph("Contract notes", ss["Heading2"]))
        cols = ["Trade Date", "Contract Note No", "Broker", "Client / Account", "Gross Purchase Value",
                "Gross Sale Value", "Total Charges", "Net Amount (Rs, rounded)", "Direction", "Status"]
        story.append(_table(nf, cols, money=cols[4:7], rupee=["Net Amount (Rs, rounded)"],
                            widths=[20 * mm, 30 * mm, 34 * mm, 45 * mm, 28 * mm, 28 * mm, 20 * mm, 26 * mm, 30 * mm, 18 * mm]))
        story.append(PageBreak())

    df = frames["daily"]
    if len(df):
        story.append(Paragraph("Daily script summary (BUY and SELL kept separate)", ss["Heading2"]))
        cols = ["Trade Date", "Client / Account", "Script", "ISIN", "Side", "Quantity", "Avg Gross Rate",
                "Gross Value", "Total Charges", "Net Cost / Proceeds (Rs)", "Net Rate per Unit (Rs)"]
        story.append(_table(df, cols, money=["Avg Gross Rate", "Gross Value", "Total Charges", "Net Rate per Unit (Rs)"],
                            rupee=["Net Cost / Proceeds (Rs)"],
                            widths=[20 * mm, 45 * mm, 28 * mm, 26 * mm, 12 * mm, 18 * mm, 22 * mm, 28 * mm, 20 * mm, 30 * mm, 24 * mm]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(landscape(A4)[0] - 10 * mm, 6 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
