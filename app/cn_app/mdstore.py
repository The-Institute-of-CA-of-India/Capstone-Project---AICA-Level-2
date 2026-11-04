"""Master lists kept as Markdown tables (.md) in Data\\Master Data.

Every downloaded or uploaded master is converted to one standard table (ISIN, symbol,
name, industry, sector, asset class, sub-category, face value), so all masters share one
small, readable format whatever the site sent (JSON, CSV, Excel, zipped text).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

FIELDS = ["isin", "symbol", "name", "industry", "sector", "asset_class", "sub_category", "face_value"]
HEAD = ["ISIN", "Symbol", "Name", "Industry", "Sector", "Asset Class", "Sub Category", "Face Value"]


def _cell(v) -> str:
    s = "" if v is None else str(v)
    return s.replace("\\", "/").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


def write(path: Path, title: str, source: str, rows: list[dict]) -> Path:
    path = Path(path).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "",
             f"Source: {source}  ", f"Saved: {datetime.now():%d %b %Y %H:%M}  ", f"Records: {len(rows)}", "",
             "| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    for r in rows:
        lines.append("| " + " | ".join(_cell(r.get(f)) for f in FIELDS) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read(path: Path) -> tuple[str, list[dict]]:
    title, rows, header = "", [], None
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        rec = dict(zip(FIELDS, cells + [""] * (len(FIELDS) - len(cells))))
        rows.append(rec)
    return title or Path(path).stem, rows


def is_ours(path: Path) -> bool:
    if Path(path).suffix.lower() != ".md":
        return False
    head = Path(path).read_text(encoding="utf-8", errors="ignore")[:2000]
    return "| ISIN | Symbol | Name |" in head


def write_table(path: Path, title: str, source: str, df) -> Path:
    """Any table (pandas DataFrame) as Markdown."""
    path = Path(path).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [str(c) for c in df.columns]
    lines = [f"# {title}", "", f"Source: {source}  ", f"Saved: {datetime.now():%d %b %Y %H:%M}  ",
             f"Records: {len(df)}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_cell("" if v is None or v != v else v) for v in row) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
