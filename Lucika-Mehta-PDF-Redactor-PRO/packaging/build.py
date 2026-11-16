"""
Build PDF Redactor PRO into a Windows program and installer.

    python packaging\\build.py                 full build: program + installer
    python packaging\\build.py --no-installer  program folder + portable ZIP only
    python packaging\\build.py --clean         start from scratch (removes build caches)
    python packaging\\build.py --ocr best      larger, slightly more accurate OCR data

What it does (each step is skipped when already up to date):
  1. creates a private build environment in .build\\venv and installs requirements.txt
     plus packaging\\requirements-build.txt (PyInstaller);
  2. puts the OCR language data (English, Hindi, Marathi) in packaging\\tessdata;
  3. writes the version details (from redact\\model.py) into the program;
  4. runs PyInstaller with packaging\\pdf_redactor_pro.spec;
  5. runs the built program's self-test (redaction, OCR, interface files);
  6. compiles packaging\\installer.iss with Inno Setup into dist\\PDF-Redactor-PRO-Setup-<version>.exe
     (or, without Inno Setup, makes dist\\PDF-Redactor-PRO-<version>-portable.zip).

To release an update: change the code, raise VERSION in redact\\model.py, run this script again,
and share the new Setup file. Installing it over the old version keeps everyone's settings.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packaging"
BUILD = ROOT / ".build"
VENV = BUILD / "venv"
DIST = ROOT / "dist"
APP = "PDF Redactor PRO"
LANGS = ("eng", "hin", "mar")
TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata_{q}/raw/main/{lang}.traineddata"
WIN = sys.platform == "win32"


def say(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd, **kw) -> None:
    print("   $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if WIN else "bin/python")


def read_version() -> str:
    text = (ROOT / "redact" / "model.py").read_text(encoding="utf-8")
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        sys.exit("VERSION not found in redact/model.py")
    return m.group(1)


def digest(*files: Path) -> str:
    h = hashlib.sha256()
    for f in files:
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- 1. environment
def ensure_env(clean: bool) -> None:
    if clean and BUILD.exists():
        say("Removing previous build caches")
        shutil.rmtree(BUILD, ignore_errors=True)
    if not venv_python().exists():
        say("Creating the build environment (.build/venv)")
        run([sys.executable, "-m", "venv", VENV])
    stamp = VENV / "requirements.sha256"
    want = digest(ROOT / "requirements.txt", PKG / "requirements-build.txt")
    if stamp.exists() and stamp.read_text() == want:
        say("Build environment is up to date")
        return
    say("Installing libraries into the build environment (first time: a few minutes)")
    run([venv_python(), "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    run([venv_python(), "-m", "pip", "install", "-r", ROOT / "requirements.txt", "-r", PKG / "requirements-build.txt"])
    stamp.write_text(want)


# ---------------------------------------------------------------- 2. OCR data
def tesseract_dirs():
    env = os.environ.get("TESSDATA_PREFIX")
    cands = [env] if env else []
    cands += [r"C:\Program Files\Tesseract-OCR\tessdata", r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tessdata"),
              "/opt/homebrew/share/tessdata", "/usr/local/share/tessdata", "/usr/share/tesseract-ocr/5/tessdata",
              "/usr/share/tessdata"]
    return [Path(c) for c in cands if c and Path(c).is_dir()]


def ensure_tessdata(quality: str) -> None:
    say(f"OCR language data ({', '.join(LANGS)})")
    dest = PKG / "tessdata"
    dest.mkdir(parents=True, exist_ok=True)
    for lang in LANGS:
        f = dest / f"{lang}.traineddata"
        if f.exists() and f.stat().st_size > 100_000:
            print(f"   {f.name}: present")
            continue
        url = TESSDATA_URL.format(q=quality, lang=lang)
        try:
            print(f"   downloading {f.name} ({quality})")
            with urllib.request.urlopen(url, timeout=120) as r, open(f, "wb") as out:
                shutil.copyfileobj(r, out)
            continue
        except Exception as exc:
            print(f"   download failed ({exc}); looking for an installed Tesseract")
            f.unlink(missing_ok=True)
        for d in tesseract_dirs():
            src = d / f"{lang}.traineddata"
            if src.exists():
                shutil.copy2(src, f)
                print(f"   copied {f.name} from {d}")
                break
        else:
            if lang == "eng":
                sys.exit("English OCR data could not be obtained. Connect to the internet or install Tesseract, then retry.")
            print(f"   WARNING: {lang} not available; the program will offer the other languages.")


# ---------------------------------------------------------------- 3. version details
def write_version_info(version: str) -> None:
    nums = [int(x) for x in re.findall(r"\d+", version)[:4]] + [0, 0, 0, 0]
    t = tuple(nums[:4])
    (PKG / "build").mkdir(exist_ok=True)
    (PKG / "build" / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080904B0', [
      StringStruct('CompanyName', 'CA Lucika Mehta'),
      StringStruct('FileDescription', '{APP}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{APP}'),
      StringStruct('LegalCopyright', 'CA Lucika Mehta'),
      StringStruct('OriginalFilename', '{APP}.exe'),
      StringStruct('ProductName', '{APP}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [2057, 1200])])
  ]
)
""", encoding="utf-8")


# ---------------------------------------------------------------- 4. PyInstaller
def pyinstaller() -> Path:
    say("Building the program with PyInstaller (a few minutes)")
    out = DIST / APP
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    run([venv_python(), "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", DIST, "--workpath", BUILD / "pyinstaller", PKG / "pdf_redactor_pro.spec"], cwd=ROOT)
    return out


# ---------------------------------------------------------------- 5. self-test
def selftest(folder: Path) -> None:
    say("Self-test of the built program")
    exe = folder / (f"{APP}.exe" if WIN else APP)
    report = Path(tempfile.gettempdir()) / "pdf_redactor_selftest.txt"
    report.unlink(missing_ok=True)
    env = dict(os.environ, REDACTOR_SELFTEST_OUT=str(report))
    env.pop("TESSDATA_PREFIX", None)           # prove the bundled OCR data is used
    code = subprocess.run([str(exe), "--selftest"], env=env, timeout=300).returncode
    text = report.read_text(encoding="utf-8") if report.exists() else "(no report written)"
    print("   " + text.replace("\n", "\n   "))
    if code != 0:
        sys.exit("Self-test FAILED - the installer was not made. See the report above.")


# ---------------------------------------------------------------- 6. installer / portable zip
def find_iscc() -> Path | None:
    for c in (shutil.which("ISCC"), shutil.which("iscc")):
        if c:
            return Path(c)
    # any Inno Setup version (6, 7, ...), per-machine or per-user install; newest first
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             os.path.expandvars(r"%LOCALAPPDATA%\Programs"), r"C:\Program Files (x86)", r"C:\Program Files"]
    found = []
    for r in roots:
        if r and Path(r).is_dir():
            found += [p for p in Path(r).glob("Inno Setup*/ISCC.exe") if p.is_file()]
    return sorted(found, key=lambda p: p.parent.name, reverse=True)[0] if found else None


def make_installer(folder: Path, version: str) -> Path | None:
    iscc = find_iscc() if WIN else None
    if not iscc:
        print("   Inno Setup not found - making a portable ZIP instead (the program itself is complete).\n"
              "   To get a proper installer, install Inno Setup once (winget install JRSoftware.InnoSetup) and rerun.")
        return None
    say("Making the installer with Inno Setup")
    run([iscc, f"/DAppVersion={version}", f"/DSourceDir={folder}", f"/DOutputDir={DIST}", PKG / "installer.iss"])
    return DIST / f"PDF-Redactor-PRO-Setup-{version}.exe"


def make_portable_zip(folder: Path, version: str) -> Path:
    say("Making the portable ZIP")
    z = DIST / f"PDF-Redactor-PRO-{version}-portable.zip"
    z.unlink(missing_ok=True)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in folder.rglob("*"):
            if p.is_file():
                zf.write(p, Path(APP) / p.relative_to(folder))
    return z


def main() -> None:
    ap = argparse.ArgumentParser(description="Build PDF Redactor PRO")
    ap.add_argument("--no-installer", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--skip-selftest", action="store_true")
    ap.add_argument("--ocr", choices=["fast", "best"], default="fast")
    a = ap.parse_args()
    if sys.version_info < (3, 11):
        sys.exit("Use Python 3.11 or later to build.")
    t0 = time.time()
    version = read_version()
    say(f"Building {APP} v{version}{'' if WIN else '  (not Windows: a test build for this system)'}")
    ensure_env(a.clean)
    ensure_tessdata(a.ocr)
    write_version_info(version)
    folder = pyinstaller()
    if not a.skip_selftest:
        selftest(folder)
    setup = None if a.no_installer else make_installer(folder, version)
    portable = make_portable_zip(folder, version) if (setup is None or a.no_installer) else None
    say(f"Done in {(time.time() - t0) / 60:.1f} minutes")
    print(f"   Program folder : {folder}")
    if setup:
        print(f"   Installer      : {setup}  ({setup.stat().st_size / 1e6:.0f} MB)  <- share this file")
    if portable:
        print(f"   Portable ZIP   : {portable}  ({portable.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
