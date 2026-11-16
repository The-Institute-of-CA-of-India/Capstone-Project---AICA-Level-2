# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller recipe for PDF Redactor PRO. Run through packaging/build.py, not directly.

Designed to keep working as the app grows:
  * every package listed in requirements.txt has its data files collected automatically;
  * every module of the app's own `redact` package is included, even if imported lazily;
  * the whole `static/` folder (interface, fonts, logo) is bundled as it is.
If a future library imports modules dynamically and the built program reports
"No module named ...", add that module to EXTRA_HIDDEN_IMPORTS below.
"""
import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent            # noqa: F821 - provided by PyInstaller
PKG = ROOT / "packaging"
APP = "PDF Redactor PRO"

EXTRA_HIDDEN_IMPORTS = [
    "multipart", "python_multipart",               # FastAPI form parsing
]
EXCLUDES = ["tkinter", "matplotlib", "scipy", "pandas", "IPython", "jupyter", "pytest", "PyQt5", "PyQt6", "PySide2",
            "PySide6", "skimage", "playwright", "streamlit",
            # no longer used (the app window is now Edge/Chrome app mode); excluded even if left in the build env
            "webview", "clr", "clr_loader", "pythonnet"]

# import names of the distributions in requirements.txt (+ the build-only extras)
DIST_TO_IMPORT = {"pymupdf": "pymupdf", "python-multipart": "multipart", "opencv-python-headless": "cv2",
                  "python-docx": "docx", "pillow": "PIL", "uvicorn": "uvicorn"}


def requirement_imports():
    names = []
    for f in (ROOT / "requirements.txt", PKG / "requirements-build.txt"):
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            dist = re.split(r"[<>=!~;\[ ]", line, 1)[0].strip().lower()
            if dist in ("pyinstaller", "pyinstaller-hooks-contrib"):
                continue
            names.append(DIST_TO_IMPORT.get(dist, dist.replace("-", "_")))
    return sorted(set(names))


datas = [(str(ROOT / "static"), "static")]
if (PKG / "tessdata").exists():
    datas.append((str(PKG / "tessdata"), "tessdata"))
hidden = list(EXTRA_HIDDEN_IMPORTS) + collect_submodules("redact") + collect_submodules("uvicorn") + ["server"]
for mod in requirement_imports():
    try:
        datas += collect_data_files(mod, excludes=["**/tests/**", "**/test/**", "**/*.pyi"])
    except Exception as exc:
        print(f"[spec] no data collected for {mod}: {exc}")

icon = str(PKG / "assets" / "logo.ico") if sys.platform == "win32" else None
version_file = str(PKG / "build" / "version_info.txt") if (PKG / "build" / "version_info.txt").exists() else None

a = Analysis(                                       # noqa: F821
    [str(ROOT / "app_main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hidden,
    excludes=EXCLUDES,
    noarchive=False,
    # python-docx finds its templates via paths like docx/parts/../templates: keep its files on disk too
    module_collection_mode={"docx": "pyz+py"},
)
if sys.platform == "win32":
    # OpenCV's video (FFmpeg) plug-in is never used here and adds ~25 MB
    a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0].lower()]
pyz = PYZ(a.pure)                                   # noqa: F821
exe = EXE(                                          # noqa: F821
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=APP,
    console=os.environ.get("REDACTOR_CONSOLE") == "1",
    icon=icon,
    version=version_file,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)   # noqa: F821
