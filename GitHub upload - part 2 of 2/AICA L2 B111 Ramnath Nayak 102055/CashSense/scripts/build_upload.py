"""Build the folder to upload to ICAI's GitHub (fork + pull request, Annexure D).

    python scripts/build_upload.py [--out "D:\\path\\ICAI_Upload"]

* Copies code, skills, plugin, n8n workflows, Apps Script, scripts, tests, docs and the SAMPLE test data.
* Leaves out secrets and local state: .env, the database, caches, the inbox, logs.
* The sample data folder is also packed as data.zip so the upload stays under GitHub's 100-files-per-upload limit.
* Scans every file for the real secret values from .env and for key-like patterns; stops if anything is found.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["cashsense", "skills", "plugin", "n8n", "apps_script", "scripts", "tests", "docs", "database_snapshot",
           "README.md", "LICENSE", "requirements.txt", ".env.example", ".gitignore", "Start_CashSense.cmd",
           "Setup_For_Reviewers.cmd"]
SKIP_DIRS = {"__pycache__", "inbox", ".pytest_cache", ".venv"}
SKIP_FILES = {".env", "cashsense.db"}
PATTERNS = [re.compile(p) for p in (r"AIza[0-9A-Za-z_\-]{30,}", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{30,}",
                                    r"sb_secret_[0-9A-Za-z_\-]{10,}", r"eyJhbGciOi[0-9A-Za-z_\-]{20,}")]


def secret_values() -> list[str]:
    env = ROOT / ".env"
    vals = []
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if any(s in k for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CHAT_ID", "SUPABASE_URL", "APPS_SCRIPT_URL")) \
                        and len(v.strip()) >= 6:
                    vals.append(v.strip())
    return vals


def copy_tree(dst: Path) -> None:
    for item in INCLUDE:
        src = ROOT / item
        if not src.exists():
            continue
        if src.is_file():
            shutil.copy2(src, dst / item)
            continue
        for p in src.rglob("*"):
            rel = p.relative_to(ROOT)
            if p.is_dir() or set(rel.parts) & SKIP_DIRS or p.name in SKIP_FILES or p.suffix in (".pyc", ".log"):
                continue
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)


def zip_data(dst: Path) -> int:
    data = ROOT / "data"
    n = 0
    with zipfile.ZipFile(dst / "data.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(data.rglob("*")):
            rel = p.relative_to(ROOT)
            if p.is_file() and not (set(rel.parts) & SKIP_DIRS) and p.name not in SKIP_FILES:
                z.write(p, rel.as_posix())
                n += 1
    return n


def scan(dst: Path) -> list[str]:
    values = secret_values()
    hits = []
    for p in dst.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix in (".zip", ".xlsx", ".docx", ".pptx"):     # Office files are zip archives too
            with zipfile.ZipFile(p) as z:
                blobs = [(f"{p.name}:{n}", z.read(n)) for n in z.namelist()]
        else:
            blobs = [(str(p.relative_to(dst)), p.read_bytes())]
        for name, blob in blobs:
            text = blob.decode("utf-8", errors="ignore")
            for v in values:
                if v in text:
                    hits.append(f"{name}: contains a value from .env")
            for pat in PATTERNS:
                if pat.search(text):
                    hits.append(f"{name}: matches secret pattern {pat.pattern[:20]}...")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "ICAI_Upload"))
    out = Path(ap.parse_args().out) / "CashSense"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copy_tree(out)
    n_data = zip_data(out)
    hits = scan(out)
    if hits:
        shutil.rmtree(out)
        print("STOPPED - possible secrets found, nothing written:\n  " + "\n  ".join(sorted(set(hits))[:20]))
        sys.exit(1)
    files = [p for p in out.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f"Upload folder: {out}\n  {len(files)} files ({size:.1f} MB); data.zip holds {n_data} sample-data files")
    print("  Secret scan: clean (no .env values, no key patterns)")
    if len(files) > 100:
        print("  Note: more than 100 files - upload in batches of folders, or use GitHub Desktop.")


if __name__ == "__main__":
    main()
