# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MSME Interest Calculator - single-file, windowed, size-optimised.
# Build with:   pyinstaller MSME_Interest_Calculator.spec --clean --noconfirm
import os

ICON = "msme.ico" if os.path.exists("msme.ico") else None

hidden = [
    "openpyxl", "openpyxl.cell._writer", "openpyxl.styles", "openpyxl.worksheet.datavalidation",
    "reportlab", "reportlab.pdfbase._fontdata_enc_winansi",
    "reportlab.pdfbase._fontdata_widths_helvetica", "reportlab.pdfbase._fontdata_widths_helveticabold",
    "reportlab.pdfbase._fontdata_widths_helveticaoblique",
    "dateutil.relativedelta",
]

# Packages the app never uses. Several get pulled in only because they are installed in the
# build environment (pandas -> numpy / pyarrow, etc.). PIL stays: reportlab imports it.
excludes = [
    "pandas", "numpy", "pyarrow", "cryptography", "lxml", "scipy", "matplotlib",
    "PIL.ImageQt", "PIL.ImageTk", "PIL.AvifImagePlugin",
    "tkinter", "IPython", "jupyter", "notebook", "pytest", "numba", "sqlite3", "pydoc_data",
    "xmlrpc", "lib2to3", "setuptools", "pkg_resources",
    "PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore", "PyQt5.QtWebEngineWidgets", "PyQt5.QtMultimedia",
    "PyQt5.QtQml", "PyQt5.QtQuick", "PyQt5.QtQuickWidgets", "PyQt5.Qt3DCore", "PyQt5.QtBluetooth",
    "PyQt5.QtSql", "PyQt5.QtNetwork", "PyQt5.QtXml", "PyQt5.QtTest", "PyQt5.QtDesigner",
    "PyQt5.QtOpenGL", "PyQt5.QtSvg", "PyQt5.QtPrintSupport", "PyQt5.QtDBus", "PyQt5.QtWebSockets",
]

# Qt files a plain widgets app does not need (software OpenGL, QML/Quick, translations, extra
# platform / image plugins). Kept: qwindows (platform), qwindowsvistastyle, qico (window icon).
DROP = (
    "opengl32sw.dll", "d3dcompiler_47.dll", "libglesv2.dll", "libegl.dll",
    "qt5quick", "qt5qml", "qt5network", "qt5websockets", "qt5svg", "qt5dbus", "qt5printsupport",
    "translations",
    "qminimal", "qoffscreen", "qwebgl",
    "qwebp", "qtiff", "qjpeg", "qgif", "qicns", "qtga", "qwbmp", "qsvg",
    "iconengines", "platformthemes", "bearer", "generic",
    "_sqlite3", "sqlite3.dll",
    # PIL is required by reportlab (core _imaging only); drop its optional codecs / font engine
    "pil\\_avif", "pil\\_imagingft", "pil\\_webp", "pil\\_imagingcms", "pil\\_imagingtk",
)


def keep(entry):
    name = entry[0].replace("/", "\\").lower()
    return not any(s in name for s in DROP)


a = Analysis(
    ["MSME_Interest_Calculator.py"],
    pathex=[],
    binaries=[],
    datas=[("msme.ico", ".")] if ICON else [],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MSME_Interest_Calculator",
    debug=False,
    strip=False,
    upx=True,                       # extra compression if upx.exe is on PATH / --upx-dir given
    upx_exclude=["vcruntime140.dll", "python3*.dll", "Qt5Core.dll", "qwindows.dll"],
    runtime_tmpdir=None,
    console=False,                  # = --windowed
    icon=ICON,
)
