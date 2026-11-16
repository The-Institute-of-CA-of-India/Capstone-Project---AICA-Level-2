"""
Transaction-table (CSV) regression test across Indian bank layouts:   python tests/test_statements.py

Builds the fictitious statements of make_statement_formats.py, redacts them with labelled boxes as the
app does, and checks every debit, credit and balance in the CSV, and that column headings and dates
are not mistaken for names.
"""

import csv
import io
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import make_statement_formats as M  # noqa: E402

from redact import batch as B  # noqa: E402
from redact import detect as D  # noqa: E402
from redact import outputs as O  # noqa: E402
from redact import statements as S  # noqa: E402
from redact.model import Options  # noqa: E402

WANT = [(dr, cr, bal) for _, dr, cr, bal in M.EXPECTED]


def _rows(t):
    return list(csv.DictReader(io.StringIO(t.decode("utf-8-sig"))))


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for name, fn in M.FORMATS.items():
            path = Path(tmp) / f"{name}_statement.pdf"
            fn(str(path))
            files.append((path.name, path.read_bytes()))
            # 1. the extractor on the original
            got = [(float(r["Debit"] or 0), float(r["Credit"] or 0), float(r["Balance"] or 0))
                   for r in S.extract(path.read_bytes())]
            if got != WANT:
                failures.append(f"{name} (original): {got[:3]}...")
        # 2. after redaction, as the app does it
        b = B.run_batch(files, Options(rules=set(D.DEFAULT_RULES), style="label"))
        for r in b.results:
            t = O.table_csv(r)
            if not t:
                failures.append(f"{r.name}: no table after redaction")
                continue
            rows = _rows(t[1])
            got = [(float(x["Debit"] or 0), float(x["Credit"] or 0), float(x["Balance"] or 0)) for x in rows]
            if got != WANT:
                failures.append(f"{r.name} (redacted): {got[:3]}...")
            ok = sum(x["Balance check"] == "OK" for x in rows)
            if ok < len(rows) - 1:
                failures.append(f"{r.name}: only {ok}/{len(rows)} balances verified")
        bad = [row["Original value(s)"] for row in b.ctx.key_rows() if row["Label"].startswith("PARTY")
               and row["Original value(s)"].split()[0].lower() in
               {"date", "narration", "particulars", "balance", "value", "withdrawal", "deposit", "closing", "apr", "tran"}]
        if bad:
            failures.append(f"headings/dates redacted as names: {bad}")
    for f in failures:
        print("FAIL", f)
    print(f"{'passed' if not failures else 'FAILED'} test_statements ({len(M.FORMATS)} layouts)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
