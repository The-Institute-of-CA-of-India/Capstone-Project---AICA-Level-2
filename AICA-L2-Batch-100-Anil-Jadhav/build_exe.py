"""Build a firm's own copy of the DSC Management Tool as a single Windows .exe.

The firm's name and address are compiled into the program, so the people
using it cannot change them. Run once per firm:

    python build_exe.py --firm "ABC & Associates" --address "Office 101, Shivaji Nagar|Pune 411005"

("|" in --address starts a new line.) The result is

    dist\\<firm name>\\DSC Manager.exe    and    How to use.txt

Give that folder to the firm. Needs PyInstaller once:  pip install pyinstaller
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FIRM_FILE = os.path.join(ROOT, "dsc_manager", "firm_info.py")

HOW_TO_USE = """DSC Management Tool - {firm}

1. Copy this folder to a place where you can save files, for example
   Documents or D:\\DSC Manager (not "Program Files"). The database and
   settings are kept next to "DSC Manager.exe".
2. Double-click "DSC Manager.exe".
   First launch: choose where to keep the database (the suggested "data"
   folder next to the program is fine), choose whether to load sample data,
   and appoint the custodian.
3. For "Read from Token", install the driver that came with each DSC token
   (ePass2003/HYP2003, ProxKey, mToken, ...) - most tokens carry the installer on
   their own small drive. Test it under Settings > Test: Read Tokens Now.
4. Back up: on Backup Database, tick "Automatic daily backup" and choose a
   USB drive or a Google Drive / OneDrive folder.
5. WhatsApp messages to clients open with the text typed in; you press Send.
   Install the WhatsApp Desktop app for the smoothest use (each message opens
   in the app). The wording is under Settings.
6. Partners' Google Sheet (optional): Settings > Google Sheet for Partners
   lists the five setup steps. After that every report reaches the sheet
   about a minute after each entry; PAN and mobile numbers are masked.

IMPORTANT: This application is for use on one PC by one user at a time.
Keep the database on this PC - not in a folder shared by several PCs.

No DSC PINs or passwords are stored by this application.
Designed by ABJ@2026
"""


def firm_source(original, firm, address):
    """firm_info.py with this firm's details in place of the defaults."""
    text = re.sub(r"^FIRM_NAME = .*$", lambda m: f"FIRM_NAME = {firm!r}", original, count=1, flags=re.M)
    return re.sub(r"^FIRM_ADDRESS = .*$", lambda m: f"FIRM_ADDRESS = {address!r}", text, count=1, flags=re.M)


def main():
    ap = argparse.ArgumentParser(description="Build a firm's DSC Management Tool .exe")
    ap.add_argument("--firm", required=True, help="CA firm name, e.g. \"ABC & Associates\"")
    ap.add_argument("--address", default="", help="Address; use | between lines")
    args = ap.parse_args()
    firm = " ".join(args.firm.split())
    address = "\n".join(p.strip() for p in args.address.split("|") if p.strip())
    if not firm:
        sys.exit("Please give the firm name with --firm.")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed. Install it once with:  pip install pyinstaller")

    folder = re.sub(r"[^A-Za-z0-9 &.,()_-]", "", firm).strip(" .") or "Firm"
    out_dir = os.path.join(ROOT, "dist", folder)
    work_dir = os.path.join(ROOT, "build")

    # Build from a temporary copy of the program with this firm's details written in, so the source
    # files are never changed - even if the build is stopped half-way.
    staging = tempfile.mkdtemp(prefix="dsc_build_")
    try:
        app = os.path.join(staging, "dsc_manager")
        shutil.copytree(os.path.join(ROOT, "dsc_manager"), app, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(os.path.join(ROOT, "run_dsc_manager.pyw"), staging)
        with open(FIRM_FILE, encoding="utf-8") as fh:
            original = fh.read()
        with open(os.path.join(app, "firm_info.py"), "w", encoding="utf-8") as fh:
            fh.write(firm_source(original, firm, address))
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "DSC Manager", "--distpath", out_dir, "--workpath", work_dir, "--specpath", work_dir,
            "--paths", staging,
            "--hidden-import", "PyKCS11", "--hidden-import", "PyKCS11.LowLevel", "--hidden-import", "openpyxl",
            "--icon", os.path.join(app, "assets", "dsc_manager.ico"),
            "--add-data", f"{os.path.join(app, 'assets')}{os.pathsep}dsc_manager/assets",
            os.path.join(staging, "run_dsc_manager.pyw"),
        ], check=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    with open(os.path.join(out_dir, "How to use.txt"), "w", encoding="utf-8") as fh:
        fh.write(HOW_TO_USE.format(firm=firm))
    print(f"\nDone. Give this folder to {firm}:\n  {out_dir}")


if __name__ == "__main__":
    main()
