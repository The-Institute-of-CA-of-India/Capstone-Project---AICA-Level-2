"""Package the app: PyInstaller folder build, then the NSIS server and client installers.

Needs:  pip install pyinstaller
        NSIS (makensis on PATH or in its default folder), for the installers
        installer/vendor/WinSW-x64.exe, from https://github.com/winsw/winsw/releases (server installer only)
Optional: tools/tesseract/ is bundled if present, so users need no separate OCR install.

Run:  python installer/build_installer.py [--skip-pyinstaller] [--client-only]
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
sys.path.insert(0, str(ROOT))
from config import VERSION  # noqa: E402

NAME = "KnowTaxx_AP_Suite"


def build_app():
    sep = os.pathsep
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console", "--name", NAME,
               "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
               "--add-data", f"{ROOT / 'app' / 'templates'}{sep}app/templates",
               "--add-data", f"{ROOT / 'app' / 'static'}{sep}app/static",
               "--hidden-import", "sqlalchemy.dialects.sqlite", "--hidden-import", "waitress",
               "--collect-submodules", "app", "--collect-all", "pypdfium2", "--collect-all", "fpdf"]
    tesseract = ROOT / "tools" / "tesseract"
    if tesseract.exists():
        command += ["--add-data", f"{tesseract}{sep}tools/tesseract"]
    else:
        print("NOTE: tools/tesseract not found. The build will expect Tesseract to be installed separately.")
    command.append(str(ROOT / "run.py"))
    subprocess.run(command, check=True, cwd=ROOT)
    print("App folder:", ROOT / "dist" / NAME)


def find_makensis():
    for candidate in (shutil.which("makensis"), r"C:\Program Files (x86)\NSIS\makensis.exe", r"C:\Program Files\NSIS\makensis.exe"):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("makensis not found. Install NSIS from https://nsis.sourceforge.io")


def compile_nsi(makensis, script, *defines):
    subprocess.run([makensis, "/V2", f"/DVERSION={VERSION}", *defines, str(INSTALLER / script)], check=True, cwd=INSTALLER)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-pyinstaller", action="store_true")
    parser.add_argument("--client-only", action="store_true")
    args = parser.parse_args()
    makensis = find_makensis()
    if not args.client_only:
        if not args.skip_pyinstaller:
            build_app()
        winsw = INSTALLER / "vendor" / "WinSW-x64.exe"
        if not winsw.exists():
            sys.exit(f"Missing {winsw}. Download WinSW-x64.exe from https://github.com/winsw/winsw/releases")
        compile_nsi(makensis, "AP_Suite_Server.nsi", f"/DDIST_DIR={ROOT / 'dist' / NAME}", f"/DWINSW={winsw}")
    compile_nsi(makensis, "AP_Suite_Client.nsi")
    print("Installers written to", INSTALLER)


if __name__ == "__main__":
    main()
