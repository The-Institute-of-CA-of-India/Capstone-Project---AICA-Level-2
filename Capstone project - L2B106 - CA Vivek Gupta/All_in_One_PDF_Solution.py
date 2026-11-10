# -*- coding: utf-8 -*-
"""
=====================================================================
  All in one PDF Solution
  A colourful, offline, single-file PDF toolkit built with PyQt5.

  * Just open this file in IDLE and press F5 (Run > Run Module).
  * Missing libraries are installed automatically on first run.

  Manual install (one line) if ever needed:
  pip install PyQt5 PyMuPDF Pillow python-docx
=====================================================================
"""

# ----------------------------------------------------------------------
# 1. AUTO-INSTALL OF LIBRARIES (runs before anything else is imported)
# ----------------------------------------------------------------------
import sys
import os
import subprocess
import importlib
import importlib.util

APP_NAME = "All in one PDF Solution"
APP_VERSION = "1.0"

# (possible module names, pip package name)
REQUIRED = [
    (("PyQt5",), "PyQt5"),
    (("pymupdf", "fitz"), "PyMuPDF"),
    (("PIL",), "Pillow"),
    (("docx",), "python-docx"),
]
PIP_LINE = "pip install PyQt5 PyMuPDF Pillow python-docx"


def _fatal(msg):
    """Show an error even if PyQt is not available (uses built-in tkinter)."""
    print(msg)
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, msg)
        root.destroy()
    except Exception:
        pass
    sys.exit(1)


def _python_exe():
    exe = sys.executable or "python"
    # IDLE runs code with pythonw.exe on Windows; pip needs python.exe
    if os.name == "nt" and exe.lower().endswith("pythonw.exe"):
        cand = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(cand):
            return cand
    return exe


def _module_present(names):
    for n in names:
        try:
            if importlib.util.find_spec(n) is not None:
                return True
        except Exception:
            pass
    return False


def _pip_install(pkg):
    exe = _python_exe()
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    base = [exe, "-m", "pip", "install", "--disable-pip-version-check", pkg]
    for extra in ([], ["--user"], ["--break-system-packages"]):
        try:
            r = subprocess.run(base + extra, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               universal_newlines=True, creationflags=flags)
            if r.returncode == 0:
                return True
        except Exception as e:  # pragma: no cover
            print("pip error:", e)
    return False


def ensure_libraries():
    missing = [pkg for names, pkg in REQUIRED if not _module_present(names)]
    if not missing:
        return
    print("Installing required libraries: " + ", ".join(missing))
    print("Please wait, this happens only once ...")
    # make sure pip itself exists
    try:
        import pip  # noqa: F401
    except ImportError:
        try:
            import ensurepip
            ensurepip.bootstrap()
        except Exception:
            pass
    failed = []
    for pkg in missing:
        print("  -> installing " + pkg + " ...")
        if not _pip_install(pkg):
            failed.append(pkg)
    importlib.invalidate_caches()
    still = [pkg for names, pkg in REQUIRED if not _module_present(names)]
    if still:
        _fatal("Could not install: " + ", ".join(still) +
               "\n\nPlease open Command Prompt and run:\n\n" + PIP_LINE)
    print("All libraries installed.\n")


ensure_libraries()

# ----------------------------------------------------------------------
# 2. IMPORTS
# ----------------------------------------------------------------------
import io
import re
import html as htmlmod
import difflib
import secrets
import traceback
import webbrowser

try:
    import pymupdf as fitz
except ImportError:  # older PyMuPDF
    import fitz

from PIL import Image, ImageOps
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QSize
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QFileDialog, QMessageBox, QComboBox, QSpinBox, QCheckBox, QFormLayout,
    QScrollArea, QFrame, QStackedWidget, QProgressBar, QPlainTextEdit,
    QColorDialog, QLayout, QButtonGroup, QGraphicsDropShadowEffect, QSizePolicy
)

MM = 72.0 / 25.4  # points per millimetre


# ----------------------------------------------------------------------
# 3. HELPERS
# ----------------------------------------------------------------------
class Cancelled(Exception):
    pass


def fmt_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def base_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def unique_path(folder, name):
    p = os.path.join(folder, name)
    if not os.path.exists(p):
        return p
    stem, ext = os.path.splitext(name)
    i = 1
    while True:
        p = os.path.join(folder, "%s_%d%s" % (stem, i, ext))
        if not os.path.exists(p):
            return p
        i += 1


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def latin(text):
    """Built-in PDF fonts support Latin-1 only; replace anything else."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _expand(part, total):
    part = part.strip().lower().replace("last", str(total))
    if not part:
        return []
    try:
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else total
            step = 1 if a <= b else -1
            nums = list(range(a, b + step, step))
        else:
            nums = [int(part)]
    except ValueError:
        raise ValueError("Invalid page entry: '%s'. Use a format like 1, 3-5, 8-10" % part)
    for p in nums:
        if p < 1 or p > total:
            raise ValueError("Page %d is out of range (this PDF has %d pages)." % (p, total))
    return [p - 1 for p in nums]


def parse_pages(text, total):
    """'1,3-5,8-10' / 'all' / 'odd' / 'even' / 'last'  ->  list of 0-based pages."""
    t = (text or "").strip().lower()
    if t in ("", "all", "*"):
        return list(range(total))
    if t == "odd":
        return list(range(0, total, 2))
    if t == "even":
        return list(range(1, total, 2))
    result = []
    for part in re.split(r"[,;\s]+", t):
        result.extend(_expand(part, total))
    if not result:
        raise ValueError("No pages selected.")
    return result


def parse_groups(text, total):
    """'1, 3-5, 8-10' -> [[0],[2,3,4],[7,8,9]]  (each comma part is one group)."""
    groups = []
    for part in re.split(r"[,;]+", (text or "")):
        if part.strip():
            g = _expand(part, total)
            if g:
                groups.append(g)
    if not groups:
        raise ValueError("Please enter page ranges, e.g.  1, 3-5, 8-10")
    return groups


def open_pdf(path, pw=""):
    doc = fitz.open(path)
    if doc.needs_pass:
        if not pw or not doc.authenticate(pw):
            doc.close()
            raise ValueError("'%s' is password protected. Enter the correct password in "
                             "the 'Open password' box." % os.path.basename(path))
    return doc


def pix_to_pil(pix):
    mode = "L" if pix.n == 1 else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def place_text(page, text, pos, size, color, margin, opacity=1.0):
    """Write text at a corner/edge of the *visible* page (handles rotated pages)."""
    text = latin(text)
    r = page.rect
    tl = fitz.get_text_length(text, fontname="helv", fontsize=size)
    p = pos.lower()
    if "left" in p:
        x = r.x0 + margin
    elif "right" in p:
        x = r.x1 - margin - tl
    else:
        x = r.x0 + (r.width - tl) / 2.0
    y = (r.y0 + margin + size * 0.8) if p.startswith("top") else (r.y1 - margin)
    pt = fitz.Point(x, y) * page.derotation_matrix
    page.insert_text(pt, text, fontsize=size, fontname="helv", color=color,
                     rotate=page.rotation, fill_opacity=opacity)


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class Ctx:
    """Everything a tool needs: files, options, output folder, logging."""

    def __init__(self, files, opts, outdir, log_cb=None, prog_cb=None):
        self.files = files
        self.o = opts
        self.outdir = outdir
        self.outputs = []
        self.cancelled = False
        self.log_cb = log_cb or (lambda s: None)
        self.prog_cb = prog_cb or (lambda p: None)

    def log(self, msg):
        self.log_cb(str(msg))

    def progress(self, i, n):
        self.prog_cb(int(i * 100 / max(n, 1)))

    def check(self):
        if self.cancelled:
            raise Cancelled()

    def out(self, name):
        return unique_path(self.outdir, name)

    def done(self, path):
        self.outputs.append(path)
        self.log("   ✔ Saved: " + path)

    def open(self, path):
        return open_pdf(path, self.o.get("_pw", ""))

    def pdf_name(self, key, default):
        n = (self.o.get(key) or default).strip()
        if not n.lower().endswith(".pdf"):
            n += ".pdf"
        return n


def save_pdf(doc, path, **kw):
    doc.save(path, garbage=3, deflate=True, **kw)


def each_pdf(c, suffix, mutate):
    """Open each input PDF, call mutate(doc), save as <name>_<suffix>.pdf"""
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        doc = c.open(f)
        try:
            msg = mutate(doc)
            if msg is False:      # tool decided there is nothing to save
                continue
            path = c.out("%s_%s.pdf" % (base_name(f), suffix))
            save_pdf(doc, path)
            c.done(path)
            if isinstance(msg, str):
                c.log("   " + msg)
        finally:
            doc.close()
        c.progress(i + 1, n)


# ----------------------------------------------------------------------
# 4. TOOL IMPLEMENTATIONS
# ----------------------------------------------------------------------
# ---- ORGANIZE ---------------------------------------------------------
def t_merge(c):
    out = fitz.open()
    toc = []
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        d = c.open(f)
        toc.append([1, os.path.basename(f), out.page_count + 1])
        out.insert_pdf(d)
        c.log("Added %s (%d pages)" % (os.path.basename(f), d.page_count))
        d.close()
        c.progress(i + 1, n)
    if c.o.get("bookmarks"):
        out.set_toc(toc)
    path = c.out(c.pdf_name("name", "merged.pdf"))
    save_pdf(out, path)
    out.close()
    c.done(path)


def t_split(c):
    mode = c.o["mode"]
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        doc = c.open(f)
        total = doc.page_count
        if mode.startswith("Custom"):
            groups = parse_groups(c.o["ranges"], total)
        elif mode.startswith("Every"):
            k = max(1, int(c.o["n"]))
            groups = [list(range(s, min(s + k, total))) for s in range(0, total, k)]
        else:
            groups = [[p] for p in range(total)]
        for gi, g in enumerate(groups, 1):
            c.check()
            new = fitz.open()
            for p in g:
                new.insert_pdf(doc, from_page=p, to_page=p)
            contiguous = all(g[k + 1] == g[k] + 1 for k in range(len(g) - 1))
            if len(g) == 1:
                label = str(g[0] + 1)
            elif contiguous:
                label = "%d-%d" % (g[0] + 1, g[-1] + 1)
            else:
                label = "custom"
            path = c.out("%s_part%d_pages_%s.pdf" % (base_name(f), gi, label))
            save_pdf(new, path)
            new.close()
            c.done(path)
        doc.close()
        c.progress(i + 1, n)


def t_extract(c):
    def m(doc):
        pages = parse_pages(c.o["pages"], doc.page_count)
        doc.select(pages)
        return "%d page(s) extracted" % len(pages)
    each_pdf(c, "extracted", m)


def t_remove(c):
    def m(doc):
        rm = sorted(set(parse_pages(c.o["pages"], doc.page_count)))
        if len(rm) >= doc.page_count:
            raise ValueError("You cannot remove every page of the PDF.")
        doc.delete_pages(rm)
        return "%d page(s) removed" % len(rm)
    each_pdf(c, "removed", m)


def t_rearrange(c):
    def m(doc):
        total = doc.page_count
        if c.o["reverse"]:
            order = list(range(total - 1, -1, -1))
        else:
            order = parse_pages(c.o["order"], total)
            if c.o["append"]:
                order += [p for p in range(total) if p not in order]
        doc.select(order)
        return "New order: " + ", ".join(str(p + 1) for p in order[:40]) + (" ..." if len(order) > 40 else "")
    each_pdf(c, "rearranged", m)


def t_rotate(c):
    ang = {"90° clockwise": 90, "180°": 180, "90° counter-clockwise": 270}[c.o["angle"]]

    def m(doc):
        pages = parse_pages(c.o["pages"], doc.page_count)
        for p in pages:
            pg = doc[p]
            pg.set_rotation((pg.rotation + ang) % 360)
        return "%d page(s) rotated" % len(pages)
    each_pdf(c, "rotated", m)


def t_blank(c):
    def m(doc):
        blanks = []
        for p in range(doc.page_count):
            pg = doc[p]
            if pg.get_text("text").strip():
                continue
            pix = pg.get_pixmap(dpi=30, colorspace=fitz.csGRAY, alpha=False)
            if min(pix.samples) >= 250:
                blanks.append(p)
        if not blanks:
            c.log("   No blank pages found - nothing saved.")
            return False
        if len(blanks) == doc.page_count:
            raise ValueError("Every page looks blank.")
        doc.delete_pages(blanks)
        return "Removed blank pages: " + ", ".join(str(p + 1) for p in blanks)
    each_pdf(c, "no_blanks", m)


# ---- CONVERT ----------------------------------------------------------
def t_pdf2img(c):
    ext = c.o["fmt"].lower()
    dpi = int(c.o["dpi"])
    q = int(c.o["quality"])
    docs = []
    total_pages = 0
    for f in c.files:
        d = c.open(f)
        docs.append((f, d, parse_pages(c.o["pages"], d.page_count)))
        total_pages += len(docs[-1][2])
    done = 0
    for f, d, pages in docs:
        c.log("▶ " + os.path.basename(f))
        for p in pages:
            c.check()
            pix = d[p].get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            img = pix_to_pil(pix)
            path = c.out("%s_page_%03d.%s" % (base_name(f), p + 1, ext))
            if ext == "jpg":
                img.save(path, "JPEG", quality=q, dpi=(dpi, dpi))
            else:
                img.save(path, "PNG", dpi=(dpi, dpi))
            c.outputs.append(path)
            done += 1
            c.progress(done, total_pages)
        d.close()
        c.log("   ✔ %d image(s) saved to %s" % (len(pages), c.outdir))


def _prep_image(path, quality):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue(), im.size


def t_img2pdf(c):
    doc = fitz.open()
    size_opt = c.o["size"]
    margin = c.o["margin"] * MM
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        try:
            data, (w, h) = _prep_image(f, int(c.o["quality"]))
        except Exception as e:
            c.log("   ! Skipped %s (%s)" % (os.path.basename(f), e))
            continue
        if size_opt.startswith("Fit"):
            W, H = w * 0.75, h * 0.75
            margin_used = margin
            W += 2 * margin_used
            H += 2 * margin_used
        else:
            W, H = (595.0, 842.0) if size_opt.startswith("A4") else (612.0, 792.0)
            if w > h:
                W, H = H, W
        page = doc.new_page(width=W, height=H)
        avail_w, avail_h = W - 2 * margin, H - 2 * margin
        s = min(avail_w / w, avail_h / h)
        iw, ih = w * s, h * s
        x0, y0 = (W - iw) / 2.0, (H - ih) / 2.0
        page.insert_image(fitz.Rect(x0, y0, x0 + iw, y0 + ih), stream=data)
        c.log("Added " + os.path.basename(f))
        c.progress(i + 1, n)
    if doc.page_count == 0:
        raise ValueError("None of the selected images could be read.")
    path = c.out(c.pdf_name("name", "images.pdf"))
    save_pdf(doc, path)
    doc.close()
    c.done(path)


def t_pdf2txt(c):
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        doc = c.open(f)
        parts = []
        for p in parse_pages(c.o["pages"], doc.page_count):
            parts.append("===== Page %d =====\n%s" % (p + 1, doc[p].get_text("text")))
        doc.close()
        path = c.out(base_name(f) + ".txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(parts))
        c.done(path)
        c.progress(i + 1, n)


def t_pdf2html(c):
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        doc = c.open(f)
        body = "".join(pg.get_text("html") for pg in doc)
        doc.close()
        path = c.out(base_name(f) + ".html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("<html><head><meta charset='utf-8'><title>%s</title></head><body>%s</body></html>"
                     % (htmlmod.escape(base_name(f)), body))
        c.done(path)
        c.progress(i + 1, n)


_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def t_pdf2word(c):
    from docx import Document
    from docx.shared import Pt, Inches
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        doc = c.open(f)
        word = Document()
        for pno in range(doc.page_count):
            c.check()
            page = doc[pno]
            try:
                data = page.get_text("dict", sort=True)
            except TypeError:
                data = page.get_text("dict")
            for b in data["blocks"]:
                if b["type"] == 0:
                    para = word.add_paragraph()
                    lines = b["lines"]
                    for li, line in enumerate(lines):
                        for sp in line["spans"]:
                            t = _BAD_XML.sub("", sp["text"])
                            if not t:
                                continue
                            run = para.add_run(t)
                            run.font.size = Pt(max(6, min(sp["size"], 72)))
                            run.bold = bool(sp["flags"] & 16)
                            run.italic = bool(sp["flags"] & 2)
                        if li < len(lines) - 1:
                            para.add_run(" ")
                elif b["type"] == 1:
                    try:
                        wi = (b["bbox"][2] - b["bbox"][0]) / 72.0
                        word.add_picture(io.BytesIO(b["image"]), width=Inches(max(0.3, min(6.0, wi))))
                    except Exception:
                        pass
            if pno < doc.page_count - 1:
                word.add_page_break()
        doc.close()
        path = c.out(base_name(f) + ".docx")
        word.save(path)
        c.done(path)
        c.progress(i + 1, n)
    c.log("Note: text-based conversion - complex layouts/tables may look different in Word.")


def t_txt2pdf(c):
    if not hasattr(fitz, "Story"):
        raise ValueError("Your PyMuPDF is too old. Run: pip install --upgrade PyMuPDF")
    n = len(c.files)
    size = int(c.o["fontsize"])
    paper = "a4" if c.o["paper"].startswith("A4") else "letter"
    m = c.o["margin"] * MM
    for i, f in enumerate(c.files):
        c.check()
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        rows = []
        for line in text.splitlines():
            if line.strip():
                rows.append("<p>%s</p>" % htmlmod.escape(line).replace("  ", "&nbsp;&nbsp;"))
            else:
                rows.append("<p>&nbsp;</p>")
        story = fitz.Story(html="<html><body>%s</body></html>" % "".join(rows),
                           user_css="p{margin:0;font-size:%dpt;line-height:1.35;font-family:sans-serif;}" % size)
        path = c.out(base_name(f) + ".pdf")
        writer = fitz.DocumentWriter(path)
        mediabox = fitz.paper_rect(paper)
        where = mediabox + (m, m, -m, -m)
        more = 1
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(dev)
            writer.end_page()
        writer.close()
        c.done(path)
        c.progress(i + 1, n)


def t_extract_images(c):
    minsz = int(c.o["min_size"])
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        doc = c.open(f)
        seen = set()
        count = 0
        for pno in range(doc.page_count):
            for img in doc[pno].get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    info = doc.extract_image(xref)
                except Exception:
                    continue
                if not info or info["width"] < minsz or info["height"] < minsz:
                    continue
                count += 1
                path = c.out("%s_p%03d_img%03d.%s" % (base_name(f), pno + 1, count, info["ext"]))
                with open(path, "wb") as fh:
                    fh.write(info["image"])
                c.outputs.append(path)
        doc.close()
        c.log("   ✔ %d image(s) extracted" % count)
        c.progress(i + 1, n)


# ---- OPTIMIZE ---------------------------------------------------------
def t_compress(c):
    level = c.o["level"]
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        doc = c.open(f)
        if not level.startswith("Low") and hasattr(fitz.Page, "replace_image"):
            quality, maxdim = (70, 2000) if level.startswith("Medium") else (45, 1400)
            seen = set()
            for page in doc:
                for img in page.get_images(full=True):
                    xref, smask = img[0], img[1]
                    if xref in seen or smask:
                        continue
                    seen.add(xref)
                    try:
                        info = doc.extract_image(xref)
                        if not info or info.get("bpc", 8) == 1:
                            continue
                        raw = info["image"]
                        im = Image.open(io.BytesIO(raw))
                        if im.mode not in ("RGB", "L"):
                            im = im.convert("RGB")
                        im.thumbnail((maxdim, maxdim))
                        buf = io.BytesIO()
                        im.save(buf, "JPEG", quality=quality, optimize=True)
                        if len(buf.getvalue()) < len(raw) * 0.95:
                            page.replace_image(xref, stream=buf.getvalue())
                    except Exception:
                        continue
        path = c.out("%s_compressed.pdf" % base_name(f))
        doc.save(path, garbage=4, deflate=True, clean=True)
        doc.close()
        a, b = os.path.getsize(f), os.path.getsize(path)
        c.done(path)
        if b < a:
            c.log("   %s -> %s  (saved %d%%)" % (fmt_size(a), fmt_size(b), round(100 - b * 100.0 / a)))
        else:
            c.log("   %s -> %s  (already well optimised; try a higher level)" % (fmt_size(a), fmt_size(b)))
        c.progress(i + 1, n)


def t_repair(c):
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        doc = c.open(f)
        path = c.out("%s_repaired.pdf" % base_name(f))
        doc.save(path, garbage=4, deflate=True, clean=True)
        doc.close()
        c.done(path)
        c.progress(i + 1, n)


def t_flatten(c):
    dpi, q, gray = int(c.o["dpi"]), int(c.o["quality"]), c.o["gray"]
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        c.log("▶ " + os.path.basename(f))
        src = c.open(f)
        new = fitz.open()
        for page in src:
            c.check()
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY if gray else fitz.csRGB, alpha=False)
            buf = io.BytesIO()
            pix_to_pil(pix).save(buf, "JPEG", quality=q)
            np_ = new.new_page(width=page.rect.width, height=page.rect.height)
            np_.insert_image(np_.rect, stream=buf.getvalue())
        src.close()
        path = c.out("%s_flattened.pdf" % base_name(f))
        save_pdf(new, path)
        new.close()
        c.done(path)
        c.progress(i + 1, n)


# ---- SECURE -----------------------------------------------------------
def t_protect(c):
    pw = c.o["newpw"]
    if not pw:
        raise ValueError("Please type a password to protect the PDF with.")
    owner = c.o["ownerpw"] or secrets.token_urlsafe(12)
    perm = fitz.PDF_PERM_ACCESSIBILITY
    if c.o["allow_print"]:
        perm |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if c.o["allow_copy"]:
        perm |= fitz.PDF_PERM_COPY
    if c.o["allow_edit"]:
        perm |= fitz.PDF_PERM_MODIFY | fitz.PDF_PERM_ANNOTATE | fitz.PDF_PERM_FORM | fitz.PDF_PERM_ASSEMBLE
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        doc = c.open(f)
        path = c.out("%s_protected.pdf" % base_name(f))
        doc.save(path, garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_AES_256,
                 user_pw=pw, owner_pw=owner, permissions=perm)
        doc.close()
        c.done(path)
        c.progress(i + 1, n)
    c.log("Remember your password - it cannot be recovered.")


def t_unlock(c):
    n = len(c.files)
    for i, f in enumerate(c.files):
        c.check()
        doc = fitz.open(f)
        if doc.needs_pass:
            if not doc.authenticate(c.o["pw"] or ""):
                doc.close()
                raise ValueError("Wrong password for '%s'." % os.path.basename(f))
        else:
            c.log("   '%s' is not password protected - saving a clean copy." % os.path.basename(f))
        path = c.out("%s_unlocked.pdf" % base_name(f))
        doc.save(path, garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        c.done(path)
        c.progress(i + 1, n)


def t_redact(c):
    terms = [t.strip() for t in re.split(r"[,;\n]+", c.o["terms"]) if t.strip()]
    if not terms:
        raise ValueError("Type the word(s) to black out, separated by commas.")
    fill = hex2rgb(c.o["fill"])

    def m(doc):
        count = 0
        for page in doc:
            hit = False
            for t in terms:
                for r in page.search_for(t):
                    page.add_redact_annot(r, fill=fill)
                    count += 1
                    hit = True
            if hit:
                page.apply_redactions()
        if count == 0:
            c.log("   No matches found - nothing saved.")
            return False
        return "%d occurrence(s) permanently redacted" % count
    each_pdf(c, "redacted", m)


# ---- EDIT -------------------------------------------------------------
def t_pagenum(c):
    o = c.o

    def m(doc):
        pages = parse_pages(o["pages"], doc.page_count)
        start = int(o["start"])
        last = start + len(pages) - 1
        color = hex2rgb(o["color"])
        for idx, p in enumerate(pages):
            num = start + idx
            text = {"1": str(num), "Page 1": "Page %d" % num,
                    "Page 1 of N": "Page %d of %d" % (num, last),
                    "1 / N": "%d / %d" % (num, last)}[o["fmt"]]
            place_text(doc[p], text, o["pos"], int(o["size"]), color, o["margin"] * MM)
        return "Numbered %d page(s)" % len(pages)
    each_pdf(c, "numbered", m)


def t_watermark(c):
    o = c.o
    text = latin(o["text"].strip())
    if not text:
        raise ValueError("Please type the watermark text.")
    size = int(o["size"])
    color = hex2rgb(o["color"])
    opacity = max(1, min(100, int(o["opacity"]))) / 100.0

    def m(doc):
        pages = parse_pages(o["pages"], doc.page_count)
        tl = fitz.get_text_length(text, fontname="helv", fontsize=size)
        for p in pages:
            pg = doc[p]
            center = fitz.Point(pg.rect.x0 + pg.rect.width / 2.0,
                                pg.rect.y0 + pg.rect.height / 2.0) * pg.derotation_matrix
            start = fitz.Point(center.x - tl / 2.0, center.y + size * 0.3)
            pg.insert_text(start, text, fontsize=size, fontname="helv", color=color,
                           fill_opacity=opacity,
                           morph=(center, fitz.Matrix(float(o["angle"]) + pg.rotation)))
        return "Watermark added to %d page(s)" % len(pages)
    each_pdf(c, "watermarked", m)


def t_stamp(c):
    o = c.o
    img = o["image"].strip()
    if not img or not os.path.isfile(img):
        raise ValueError("Please choose an image (PNG with transparent background works best).")
    iw, ih = Image.open(img).size
    pct = max(5, min(100, int(o["width"])))
    margin = o["margin"] * MM

    def m(doc):
        pages = parse_pages(o["pages"], doc.page_count)
        for p in pages:
            pg = doc[p]
            r = pg.rect
            w = r.width * pct / 100.0
            h = w * ih / iw
            pos = o["pos"].lower()
            if "left" in pos:
                x = r.x0 + margin
            elif "right" in pos:
                x = r.x1 - margin - w
            else:
                x = r.x0 + (r.width - w) / 2.0
            if pos.startswith("top"):
                y = r.y0 + margin
            elif pos.startswith("bottom"):
                y = r.y1 - margin - h
            else:
                y = r.y0 + (r.height - h) / 2.0
            rect = (fitz.Rect(x, y, x + w, y + h) * pg.derotation_matrix).normalize()
            pg.insert_image(rect, filename=img, rotate=pg.rotation, overlay=True)
        return "Image placed on %d page(s)" % len(pages)
    each_pdf(c, "signed", m)


def t_headfoot(c):
    o = c.o
    if not o["header"].strip() and not o["footer"].strip():
        raise ValueError("Type a header and/or footer text.")
    color = hex2rgb(o["color"])
    import datetime
    today = datetime.date.today().strftime("%d-%m-%Y")

    def m(doc):
        total = doc.page_count
        fname = os.path.basename(doc.name or "")
        for p in range(total):
            for key, vert in (("header", "Top"), ("footer", "Bottom")):
                t = o[key].strip()
                if not t:
                    continue
                t = (t.replace("{page}", str(p + 1)).replace("{pages}", str(total))
                     .replace("{date}", today).replace("{file}", fname))
                place_text(doc[p], t, "%s %s" % (vert, o["align"]), int(o["size"]), color, 20 * 0.3528 * 2)
        return "Header/footer added"
    each_pdf(c, "header_footer", m)


def t_crop(c):
    o = c.o
    l, r_, t, b = (o["left"] * MM, o["right"] * MM, o["top"] * MM, o["bottom"] * MM)

    def m(doc):
        pages = parse_pages(o["pages"], doc.page_count)
        for p in pages:
            pg = doc[p]
            v = pg.rect
            vis = fitz.Rect(v.x0 + l, v.y0 + t, v.x1 - r_, v.y1 - b)
            if vis.is_empty or vis.width < 20 or vis.height < 20:
                raise ValueError("Crop margins are too large for page %d." % (p + 1))
            pg.set_cropbox((vis * pg.derotation_matrix).normalize())
        return "%d page(s) cropped" % len(pages)
    each_pdf(c, "cropped", m)


def t_metadata(c):
    o = c.o

    def m(doc):
        md = {} if o["clear"] else dict(doc.metadata or {})
        md.pop("format", None)
        md.pop("encryption", None)
        for k in ("title", "author", "subject", "keywords"):
            if o[k].strip():
                md[k] = o[k].strip()
        doc.set_metadata(md)
        if o["clear"]:
            try:
                doc.del_xml_metadata()
            except Exception:
                pass
        return "Metadata updated"
    each_pdf(c, "metadata", m)


def t_highlight(c):
    term = c.o["term"].strip()
    if not term:
        raise ValueError("Type the text to highlight.")
    color = hex2rgb(c.o["color"])

    def m(doc):
        count = 0
        for page in doc:
            quads = page.search_for(term, quads=True)
            for q in quads:
                a = page.add_highlight_annot(q)
                a.set_colors(stroke=color)
                a.update()
                count += 1
        if count == 0:
            c.log("   '%s' not found - nothing saved." % term)
            return False
        return "%d occurrence(s) highlighted" % count
    each_pdf(c, "highlighted", m)


# ---- ANALYZE ----------------------------------------------------------
def t_info(c):
    for f in c.files:
        c.check()
        doc = fitz.open(f)
        c.log("=" * 60)
        c.log("File      : " + os.path.basename(f))
        c.log("Size      : " + fmt_size(os.path.getsize(f)))
        c.log("Encrypted  : " + ("Yes (password needed for full details)" if doc.needs_pass else "No"))
        if not doc.needs_pass:
            c.log("Pages     : %d" % doc.page_count)
            if doc.page_count:
                r = doc[0].rect
                c.log("Page size : %.0f x %.0f mm (first page)" % (r.width / MM, r.height / MM))
            imgs = sum(len(pg.get_images()) for pg in doc)
            chars = sum(len(pg.get_text("text")) for pg in doc)
            c.log("Images    : %d    Text characters: %d" % (imgs, chars))
            if chars == 0 and doc.page_count:
                c.log("           (No selectable text - this looks like a scanned PDF)")
            for k, v in (doc.metadata or {}).items():
                if v:
                    c.log("%-10s: %s" % (k.capitalize(), v))
            toc = doc.get_toc()
            c.log("Bookmarks : %d" % len(toc))
        doc.close()


def t_compare(c):
    texts = []
    for f in c.files[:2]:
        doc = c.open(f)
        lines = []
        for i, pg in enumerate(doc):
            lines.append("--- Page %d ---" % (i + 1))
            lines.extend(l.rstrip() for l in pg.get_text("text").splitlines())
        doc.close()
        texts.append(lines)
    ratio = difflib.SequenceMatcher(None, texts[0], texts[1]).ratio()
    page = difflib.HtmlDiff(wrapcolumn=90).make_file(
        texts[0], texts[1], os.path.basename(c.files[0]), os.path.basename(c.files[1]),
        context=True, numlines=3)
    path = c.out("compare_%s_vs_%s.html" % (base_name(c.files[0]), base_name(c.files[1])))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    c.done(path)
    c.log("Text similarity: %.1f%%" % (ratio * 100))
    if c.o["open"]:
        webbrowser.open("file:///" + path.replace("\\", "/"))


def t_search(c):
    term = c.o["term"].strip()
    if not term:
        raise ValueError("Type the text to search for.")
    case = c.o["case"]
    for f in c.files:
        c.check()
        doc = c.open(f)
        c.log("▶ %s" % os.path.basename(f))
        total = 0
        shown = 0
        for pno, pg in enumerate(doc):
            hits = len(pg.search_for(term))
            if hits:
                total += hits
                c.log("   Page %d: %d match(es)" % (pno + 1, hits))
                for line in pg.get_text("text").splitlines():
                    ok = (term in line) if case else (term.lower() in line.lower())
                    if ok and shown < 100:
                        c.log("        … " + line.strip()[:110])
                        shown += 1
        c.log("   Total: %d match(es)" % total)
        doc.close()


# ----------------------------------------------------------------------
# 5. TOOL CATALOGUE (categories, options)
# ----------------------------------------------------------------------
CATS = {
    "Organize": {"color": "#3B82F6", "icon": "🗂️", "blurb": "Merge, split, reorder and clean pages"},
    "Convert":  {"color": "#10B981", "icon": "🔁", "blurb": "PDF to and from images, text, Word, HTML"},
    "Optimize": {"color": "#F59E0B", "icon": "⚡", "blurb": "Shrink, repair and flatten PDFs"},
    "Secure":   {"color": "#8B5CF6", "icon": "🔐", "blurb": "Passwords and permanent redaction"},
    "Edit":     {"color": "#EC4899", "icon": "🎨", "blurb": "Numbers, watermarks, signatures, metadata"},
    "Analyze":  {"color": "#06B6D4", "icon": "🔍", "blurb": "Inspect, search and compare"},
}

POSITIONS = ["Bottom center", "Bottom right", "Bottom left", "Top center", "Top right", "Top left"]
PW_DESC = "Leave empty unless the PDF is encrypted."


def O(k, t, label, default=None, **kw):
    d = dict(k=k, t=t, label=label, default=default)
    d.update(kw)
    return d


def T(key, title, cat, icon, desc, fn, hint, opts=(), exts=(".pdf",), min_files=1,
      max_files=None, open_pw=True, needs_out=True):
    return dict(key=key, title=title, cat=cat, icon=icon, desc=desc, fn=fn, hint=hint,
                opts=list(opts), exts=tuple(exts), min_files=min_files, max_files=max_files,
                open_pw=open_pw, needs_out=needs_out)


IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")
RANGE_TIP = "Examples:  1, 3-5, 8-10   |   all   |   odd   |   even   |   last"

TOOLS = [
    # ---------------- ORGANIZE
    T("merge", "Merge PDF", "Organize", "🔗", "Combine many PDFs into one", t_merge,
      "Add 2 or more PDFs. Use ⬆ ⬇ (or drag) to set the order.",
      [O("name", "text", "Output file name", "merged.pdf"),
       O("bookmarks", "check", "Add a bookmark for each file", True)], min_files=2),
    T("split", "Split PDF", "Organize", "✂️", "Cut a PDF into several PDFs", t_split,
      "Choose a split method. Every comma-separated range becomes its own PDF.",
      [O("mode", "choice", "Split method", "Custom ranges (one PDF per range)",
         choices=["Custom ranges (one PDF per range)", "Every N pages", "Each page separately"]),
       O("ranges", "text", "Ranges (custom method)", "1, 3-5, 8-10",
         tip="10-page PDF with  1, 3-5, 8-10  gives 3 PDFs."),
       O("n", "int", "N (for 'Every N pages')", 2, min=1, max=1000)]),
    T("extract", "Extract Pages", "Organize", "📤", "Pull selected pages into ONE new PDF", t_extract,
      "Pages are saved together in a single PDF, in the order you type.",
      [O("pages", "text", "Pages to extract", "1, 3-5, 8-10", tip=RANGE_TIP)]),
    T("remove", "Remove Pages", "Organize", "🗑️", "Delete unwanted pages", t_remove,
      "Type the pages you want to DELETE.",
      [O("pages", "text", "Pages to remove", "2", tip=RANGE_TIP)]),
    T("rearrange", "Rearrange Pages", "Organize", "🔀", "Change the page order", t_rearrange,
      "Type the new order, e.g.  3, 1, 2, 4-10",
      [O("order", "text", "New page order", "3, 1, 2, 4-10", tip="Pages you leave out are added at the end if the box below is ticked."),
       O("append", "check", "Append pages that are not listed", True),
       O("reverse", "check", "Just reverse the whole document (ignores the order above)", False)]),
    T("rotate", "Rotate Pages", "Organize", "🔄", "Turn pages 90° / 180°", t_rotate,
      "Rotate all pages or only some of them.",
      [O("angle", "choice", "Rotation", "90° clockwise",
         choices=["90° clockwise", "180°", "90° counter-clockwise"]),
       O("pages", "text", "Pages", "all", tip=RANGE_TIP)]),
    T("blank", "Remove Blank Pages", "Organize", "🧹", "Auto-detect and delete empty pages", t_blank,
      "Pages with no text and a plain white look are removed."),

    # ---------------- CONVERT
    T("pdf2img", "PDF to Images", "Convert", "🖼️", "Pages to JPG / PNG pictures", t_pdf2img,
      "Every selected page is saved as a picture in the output folder.",
      [O("fmt", "choice", "Image format", "JPG", choices=["JPG", "PNG"]),
       O("dpi", "int", "Quality (DPI)", 150, min=36, max=600),
       O("quality", "int", "JPG quality (1-100)", 90, min=10, max=100),
       O("pages", "text", "Pages", "all", tip=RANGE_TIP)]),
    T("img2pdf", "Images to PDF", "Convert", "📸", "Combine pictures into one PDF", t_img2pdf,
      "Add JPG, PNG, BMP, GIF, TIFF or WEBP images. Order matters.",
      [O("name", "text", "Output file name", "images.pdf"),
       O("size", "choice", "Page size", "Fit to image", choices=["Fit to image", "A4", "Letter"]),
       O("margin", "int", "Margin (mm)", 0, min=0, max=50),
       O("quality", "int", "Image quality (1-100)", 90, min=30, max=100)],
      exts=IMG_EXTS, open_pw=False),
    T("pdf2txt", "PDF to Text", "Convert", "📝", "Extract all text into .txt", t_pdf2txt,
      "Works for PDFs with selectable text.",
      [O("pages", "text", "Pages", "all", tip=RANGE_TIP)]),
    T("pdf2html", "PDF to HTML", "Convert", "🌐", "Turn PDF into a web page", t_pdf2html,
      "Creates one .html file per PDF."),
    T("pdf2word", "PDF to Word", "Convert", "📘", "Create an editable .docx", t_pdf2word,
      "Text, bold/italic and pictures are carried over (layout is approximate)."),
    T("txt2pdf", "Text to PDF", "Convert", "🔤", "Make a PDF from a .txt file", t_txt2pdf,
      "Add .txt / .md / .csv / .log files.",
      [O("fontsize", "int", "Font size", 11, min=6, max=40),
       O("paper", "choice", "Paper", "A4", choices=["A4", "Letter"]),
       O("margin", "int", "Margin (mm)", 20, min=5, max=60)],
      exts=(".txt", ".md", ".csv", ".log", ".py", ".json"), open_pw=False),
    T("extimg", "Extract Images", "Convert", "🎞️", "Save pictures embedded in a PDF", t_extract_images,
      "Original embedded images are saved as-is.",
      [O("min_size", "int", "Ignore images smaller than (pixels)", 50, min=0, max=2000)]),

    # ---------------- OPTIMIZE
    T("compress", "Compress PDF", "Optimize", "🗜️", "Reduce file size", t_compress,
      "Medium is recommended. High gives the smallest file with visible quality loss in images.",
      [O("level", "choice", "Compression level", "Medium (recommended)",
         choices=["Low (lossless clean-up)", "Medium (recommended)", "High (smallest file)"])]),
    T("repair", "Repair PDF", "Optimize", "🛠️", "Try to fix a damaged PDF", t_repair,
      "Re-builds the PDF structure. Works for many broken files."),
    T("flatten", "Flatten / Rasterize", "Optimize", "🧱", "Convert pages to pictures inside a PDF", t_flatten,
      "Makes text non-selectable (useful before sharing). Also removes form fields.",
      [O("dpi", "int", "Quality (DPI)", 150, min=72, max=400),
       O("quality", "int", "JPEG quality (1-100)", 85, min=30, max=100),
       O("gray", "check", "Convert to grayscale", False)]),

    # ---------------- SECURE
    T("protect", "Protect PDF", "Secure", "🔒", "Add a password (AES-256)", t_protect,
      "Anyone opening the file will need the password.",
      [O("newpw", "password", "New password"),
       O("ownerpw", "password", "Owner password (optional)", tip="Controls the permissions below. Random if empty."),
       O("allow_print", "check", "Allow printing", True),
       O("allow_copy", "check", "Allow copying text", True),
       O("allow_edit", "check", "Allow editing", False)]),
    T("unlock", "Unlock PDF", "Secure", "🔓", "Remove a password you already know", t_unlock,
      "Enter the existing password to save an unprotected copy. (No password recovery or cracking.)",
      [O("pw", "password", "Current password")], open_pw=False),
    T("redact", "Redact PDF", "Secure", "⬛", "Permanently black out words", t_redact,
      "Matching text is REMOVED from the file, not just covered. Original is untouched.",
      [O("terms", "text", "Words / phrases", "", tip="Separate several with commas."),
       O("fill", "color", "Box colour", "#000000")]),

    # ---------------- EDIT
    T("pagenum", "Add Page Numbers", "Edit", "🔢", "Number your pages", t_pagenum,
      "Choose position, style and the starting number.",
      [O("pos", "choice", "Position", "Bottom center", choices=POSITIONS),
       O("fmt", "choice", "Format", "Page 1 of N", choices=["1", "Page 1", "Page 1 of N", "1 / N"]),
       O("start", "int", "Starting number", 1, min=0, max=100000),
       O("size", "int", "Font size", 11, min=6, max=48),
       O("color", "color", "Colour", "#333333"),
       O("margin", "int", "Distance from edge (mm)", 10, min=2, max=60),
       O("pages", "text", "Pages to number", "all", tip=RANGE_TIP)]),
    T("watermark", "Add Watermark", "Edit", "💧", "Stamp text across pages", t_watermark,
      "A big transparent text on every selected page.",
      [O("text", "text", "Watermark text", "CONFIDENTIAL"),
       O("size", "int", "Font size", 60, min=8, max=250),
       O("color", "color", "Colour", "#E11D48"),
       O("opacity", "int", "Opacity % (1-100)", 25, min=1, max=100),
       O("angle", "int", "Angle (degrees)", 45, min=0, max=359),
       O("pages", "text", "Pages", "all", tip=RANGE_TIP)]),
    T("stamp", "Sign / Add Image", "Edit", "✍️", "Place a signature or logo", t_stamp,
      "Use a PNG with transparent background for a clean signature.",
      [O("image", "file", "Image file", "", filter="Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"),
       O("pos", "choice", "Position", "Bottom right", choices=POSITIONS + ["Center"]),
       O("width", "int", "Width (% of page)", 25, min=5, max=100),
       O("margin", "int", "Distance from edge (mm)", 10, min=0, max=80),
       O("pages", "text", "Pages", "last", tip=RANGE_TIP)]),
    T("headfoot", "Header & Footer", "Edit", "📑", "Add text on top / bottom", t_headfoot,
      "Use {page} {pages} {date} {file} inside the text.",
      [O("header", "text", "Header text", ""),
       O("footer", "text", "Footer text", "{file}  -  Page {page} of {pages}"),
       O("align", "choice", "Alignment", "center", choices=["left", "center", "right"]),
       O("size", "int", "Font size", 10, min=6, max=36),
       O("color", "color", "Colour", "#444444")]),
    T("crop", "Crop Pages", "Edit", "📐", "Trim margins", t_crop,
      "Enter how much to cut from each side.",
      [O("left", "int", "Left (mm)", 10, min=0, max=200),
       O("right", "int", "Right (mm)", 10, min=0, max=200),
       O("top", "int", "Top (mm)", 10, min=0, max=200),
       O("bottom", "int", "Bottom (mm)", 10, min=0, max=200),
       O("pages", "text", "Pages", "all", tip=RANGE_TIP)]),
    T("metadata", "Edit Metadata", "Edit", "🏷️", "Title, author, keywords", t_metadata,
      "Fill only what you want to change. Blank fields stay as they are.",
      [O("title", "text", "Title", ""), O("author", "text", "Author", ""),
       O("subject", "text", "Subject", ""), O("keywords", "text", "Keywords", ""),
       O("clear", "check", "Remove ALL existing metadata first", False)]),
    T("highlight", "Highlight Text", "Edit", "🖍️", "Mark every match of a word", t_highlight,
      "Every occurrence of the word/phrase is highlighted.",
      [O("term", "text", "Text to highlight", ""),
       O("color", "color", "Highlight colour", "#FFEB3B")]),

    # ---------------- ANALYZE
    T("info", "PDF Information", "Analyze", "ℹ️", "Pages, size, metadata, images", t_info,
      "Shows details in the log below. Nothing is saved.", needs_out=False, open_pw=False),
    T("search", "Search in PDF", "Analyze", "🔎", "Find a word & list pages", t_search,
      "Shows page numbers and matching lines. Nothing is saved.",
      [O("term", "text", "Search for", ""), O("case", "check", "Match case", False)],
      needs_out=False),
    T("compare", "Compare PDFs", "Analyze", "⚖️", "See text differences", t_compare,
      "Add exactly 2 PDFs. A side-by-side HTML report is created.",
      [O("open", "check", "Open the report in my browser when ready", True)],
      min_files=2, max_files=2),
]
TOOL_COUNT = len(TOOLS)


# ----------------------------------------------------------------------
# 6. GUI PARTS
# ----------------------------------------------------------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, hspacing=16, vspacing=16):
        super().__init__(parent)
        self._items = []
        self.hs, self.vs = hspacing, vspacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _layout(self, rect, test):
        x, y, lh = rect.x(), rect.y(), 0
        for it in self._items:
            sz = it.sizeHint()
            if x + sz.width() > rect.right() + 1 and lh > 0:
                x = rect.x()
                y += lh + self.vs
                lh = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), sz))
            x += sz.width() + self.hs
            lh = max(lh, sz.height())
        return y + lh - rect.y()


def shadow(widget, blur=18, alpha=40):
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setOffset(0, 3)
    eff.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(eff)


class ToolCard(QPushButton):
    def __init__(self, spec):
        super().__init__()
        color = CATS[spec["cat"]]["color"]
        self.setObjectName("card")
        self.setFixedSize(220, 124)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(spec["desc"])
        self.setStyleSheet(
            "QPushButton#card{background:white;border:1px solid #E2E8F0;border-left:7px solid COLOR;"
            "border-radius:14px;text-align:left;}"
            "QPushButton#card:hover{background:#F5F8FF;border:1px solid COLOR;border-left:7px solid COLOR;}"
            "QPushButton#card:pressed{background:#E8EEFF;}".replace("COLOR", color))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(2)
        top = QHBoxLayout()
        ic = QLabel(spec["icon"])
        ic.setStyleSheet("font-size:26px;background:transparent;")
        title = QLabel(spec["title"])
        title.setStyleSheet("font-size:14px;font-weight:700;color:#0F172A;background:transparent;")
        top.addWidget(ic)
        top.addWidget(title, 1)
        desc = QLabel(spec["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:11px;color:#64748B;background:transparent;")
        lay.addLayout(top)
        lay.addWidget(desc, 1)
        for w in (ic, title, desc):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        shadow(self, 14, 28)


class HomePage(QWidget):
    def __init__(self, on_open):
        super().__init__()
        self.on_open = on_open
        self.cat = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        banner = QFrame()
        banner.setObjectName("banner")
        banner.setStyleSheet(
            "QFrame#banner{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:0.5 #7C3AED,stop:1 #EC4899);}")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(30, 20, 30, 20)
        t = QLabel("📄  " + APP_NAME)
        t.setStyleSheet("color:white;font-size:27px;font-weight:800;background:transparent;")
        self.sub = QLabel("%d powerful tools  •  100%% offline  •  your files never leave your computer" % TOOL_COUNT)
        self.sub.setStyleSheet("color:#EDE9FE;font-size:13px;background:transparent;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Search a tool  (merge, compress, watermark ...)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(38)
        self.search.setMaximumWidth(460)
        self.search.setStyleSheet(
            "QLineEdit{background:white;border:none;border-radius:19px;padding:0 16px;font-size:13px;color:#0F172A;}")
        self.search.textChanged.connect(self.refresh)
        bl.addWidget(t)
        bl.addWidget(self.sub)
        bl.addSpacing(8)
        bl.addWidget(self.search)
        root.addWidget(banner)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def set_category(self, cat):
        self.cat = cat
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh()

    def refresh(self):
        q = self.search.text().strip().lower()
        holder = QWidget()
        holder.setStyleSheet("background:#F1F5FB;")
        v = QVBoxLayout(holder)
        v.setContentsMargins(30, 20, 30, 30)
        v.setSpacing(10)
        shown = 0
        for cat, info in CATS.items():
            if self.cat and cat != self.cat:
                continue
            specs = [s for s in TOOLS if s["cat"] == cat and
                     (not q or q in s["title"].lower() or q in s["desc"].lower() or q in cat.lower())]
            if not specs:
                continue
            head = QLabel("%s  %s   <span style='font-size:12px;color:#64748B;font-weight:400;'>%s</span>"
                          % (info["icon"], cat, info["blurb"]))
            head.setTextFormat(Qt.RichText)
            head.setStyleSheet("font-size:19px;font-weight:800;color:%s;background:transparent;margin-top:10px;" % info["color"])
            v.addWidget(head)
            wrap = QWidget()
            fl = FlowLayout(wrap)
            fl.setContentsMargins(0, 4, 0, 4)
            for s in specs:
                card = ToolCard(s)
                card.clicked.connect(lambda _=False, sp=s: self.on_open(sp))
                fl.addWidget(card)
                shown += 1
            v.addWidget(wrap)
        if not shown:
            lab = QLabel("No tool matches your search.")
            lab.setStyleSheet("font-size:15px;color:#64748B;background:transparent;")
            v.addWidget(lab)
        v.addStretch(1)
        self.scroll.setWidget(holder)


class FileList(QListWidget):
    dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            self.dropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class Worker(QThread):
    log = pyqtSignal(str)
    prog = pyqtSignal(int)
    ok = pyqtSignal(list)
    fail = pyqtSignal(str)

    def __init__(self, fn, ctx):
        super().__init__()
        self.fn, self.ctx = fn, ctx
        ctx.log_cb = self.log.emit
        ctx.prog_cb = self.prog.emit

    def run(self):
        try:
            self.fn(self.ctx)
            self.ok.emit(self.ctx.outputs)
        except Cancelled:
            self.fail.emit("Cancelled.")
        except ValueError as e:
            self.fail.emit(str(e))
        except Exception as e:
            self.log.emit(traceback.format_exc())
            self.fail.emit("%s: %s" % (e.__class__.__name__, e))


LAST_OUT = {"dir": ""}


class ToolPage(QWidget):
    def __init__(self, spec, on_back):
        super().__init__()
        self.spec = spec
        self.worker = None
        self.getters = {}
        color = CATS[spec["cat"]]["color"]
        dark = QColor(color).darker(140).name()
        self.color = color
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        head = QFrame()
        head.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 %s,stop:1 %s);}" % (color, dark))
        hl = QHBoxLayout(head)
        hl.setContentsMargins(20, 14, 24, 14)
        back = QPushButton("←  All tools")
        back.setCursor(Qt.PointingHandCursor)
        back.setStyleSheet("QPushButton{background:rgba(255,255,255,0.22);color:white;border:none;border-radius:16px;"
                           "padding:7px 16px;font-weight:700;}QPushButton:hover{background:rgba(255,255,255,0.4);}")
        back.clicked.connect(on_back)
        title = QLabel("%s  %s" % (spec["icon"], spec["title"]))
        title.setStyleSheet("color:white;font-size:24px;font-weight:800;background:transparent;")
        desc = QLabel(spec["desc"])
        desc.setStyleSheet("color:rgba(255,255,255,0.9);font-size:13px;background:transparent;")
        tv = QVBoxLayout()
        tv.setSpacing(0)
        tv.addWidget(title)
        tv.addWidget(desc)
        hl.addWidget(back)
        hl.addSpacing(14)
        hl.addLayout(tv, 1)
        root.addWidget(head)

        body = QWidget()
        body.setStyleSheet("background:#F1F5FB;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(22, 16, 22, 16)
        bl.setSpacing(12)
        root.addWidget(body, 1)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        mid.addWidget(self._files_box(), 3)
        mid.addWidget(self._opts_box(), 2)
        bl.addLayout(mid, 3)

        if spec["needs_out"]:
            bl.addWidget(self._out_box())

        # run row
        rr = QHBoxLayout()
        self.run_btn = QPushButton("▶  Start")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setFixedHeight(44)
        self.run_btn.setMinimumWidth(190)
        self.run_btn.setStyleSheet(
            "QPushButton{background:%s;color:white;border:none;border-radius:22px;font-size:15px;font-weight:800;padding:0 26px;}"
            "QPushButton:hover{background:%s;}QPushButton:disabled{background:#94A3B8;}" % (color, dark))
        self.run_btn.clicked.connect(self.run)
        shadow(self.run_btn, 16, 70)
        self.cancel_btn = QPushButton("■  Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setFixedHeight(44)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#EF4444;color:white;border:none;border-radius:22px;font-weight:700;padding:0 22px;}"
            "QPushButton:disabled{background:#CBD5E1;}QPushButton:hover{background:#DC2626;}")
        self.cancel_btn.clicked.connect(self.cancel)
        self.open_btn = QPushButton("📂  Open output folder")
        self.open_btn.setFixedHeight(44)
        self.open_btn.setVisible(False)
        self.open_btn.setStyleSheet(
            "QPushButton{background:#0EA5E9;color:white;border:none;border-radius:22px;font-weight:700;padding:0 22px;}"
            "QPushButton:hover{background:#0284C7;}")
        self.open_btn.clicked.connect(lambda: open_folder(self.out_edit.text()))
        rr.addWidget(self.run_btn)
        rr.addWidget(self.cancel_btn)
        rr.addWidget(self.open_btn)
        rr.addStretch(1)
        bl.addLayout(rr)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(14)
        self.bar.setStyleSheet(
            "QProgressBar{background:#E2E8F0;border:none;border-radius:7px;text-align:center;color:transparent;}"
            "QProgressBar::chunk{border-radius:7px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 %s,stop:1 %s);}" % (color, dark))
        bl.addWidget(self.bar)

        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMinimumHeight(110)
        self.logbox.setPlaceholderText("Progress and results will appear here ...")
        self.logbox.setStyleSheet("QPlainTextEdit{background:#0F172A;color:#E2E8F0;border-radius:10px;padding:8px;"
                                  "font-family:Consolas,'Courier New',monospace;font-size:12px;}")
        bl.addWidget(self.logbox, 2)

    # ----- builders
    def _box(self, title):
        box = QFrame()
        box.setObjectName("box")
        box.setStyleSheet("QFrame#box{background:white;border-radius:14px;border:1px solid #E2E8F0;}"
                          "QFrame#box QLabel{background:transparent;}")
        shadow(box, 14, 26)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)
        lab = QLabel(title)
        lab.setStyleSheet("font-size:14px;font-weight:800;color:%s;" % self.color)
        lay.addWidget(lab)
        return box, lay

    def _files_box(self):
        s = self.spec
        kind = "PDF" if s["exts"] == (".pdf",) else "file"
        box, lay = self._box("1️⃣  Select %s file(s)" % kind)
        hint = QLabel(s["hint"])
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;font-size:12px;")
        lay.addWidget(hint)
        self.flist = FileList()
        self.flist.setStyleSheet(
            "QListWidget{border:2px dashed #CBD5E1;border-radius:10px;background:#FAFBFF;font-size:12px;}"
            "QListWidget::item{padding:6px;}QListWidget::item:selected{background:%s;color:white;border-radius:6px;}"
            "QListWidget{alternate-background-color:#F3F6FD;}" % self.color)
        self.flist.dropped.connect(self.add_paths)
        lay.addWidget(self.flist, 1)
        row = QHBoxLayout()
        for text, fn, col in (("➕ Add", self.browse_files, self.color), ("➖ Remove", self.remove_sel, "#64748B"),
                              ("⬆", lambda: self.move(-1), "#64748B"), ("⬇", lambda: self.move(1), "#64748B"),
                              ("🗑 Clear", self.flist_clear, "#EF4444")):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton{background:%s;color:white;border:none;border-radius:8px;padding:7px 12px;font-weight:700;}"
                            "QPushButton:hover{opacity:0.8;}" % col)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.count_lab = QLabel("No files added")
        self.count_lab.setStyleSheet("color:#64748B;font-size:11px;")
        lay.addWidget(self.count_lab)
        return box

    def _opts_box(self):
        s = self.spec
        box, lay = self._box("2️⃣  Options")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent;")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        form = QFormLayout(inner)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        opts = list(s["opts"])
        if s["open_pw"]:
            opts.append(O("_pw", "password", "Open password", "", tip=PW_DESC))
        if not opts:
            n = QLabel("No options needed for this tool.\nJust add your file(s) and press Start.")
            n.setStyleSheet("color:#64748B;font-size:12px;")
            form.addRow(n)
        for o in opts:
            self._add_option(form, o)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return box

    def _add_option(self, form, o):
        t, k = o["t"], o["k"]
        label = QLabel(o["label"])
        label.setWordWrap(True)
        label.setStyleSheet("font-weight:600;color:#1E293B;font-size:12px;")
        if t == "check":
            w = QCheckBox(o["label"])
            w.setChecked(bool(o["default"]))
            w.setStyleSheet("font-weight:600;color:#1E293B;font-size:12px;")
            self.getters[k] = w.isChecked
            form.addRow(w)
        else:
            if t in ("text", "password"):
                w = QLineEdit(o["default"] or "")
                if t == "password":
                    w.setEchoMode(QLineEdit.Password)
                self.getters[k] = w.text
            elif t == "int":
                w = QSpinBox()
                w.setRange(o.get("min", 0), o.get("max", 99999))
                w.setValue(int(o["default"]))
                self.getters[k] = w.value
            elif t == "choice":
                w = QComboBox()
                w.addItems(o["choices"])
                w.setCurrentText(o["default"])
                self.getters[k] = w.currentText
            elif t == "color":
                w = QPushButton(o["default"])
                w.setProperty("hex", o["default"])
                w.setCursor(Qt.PointingHandCursor)
                self._paint_color(w, o["default"])
                w.clicked.connect(lambda _=False, b=w: self._pick_color(b))
                self.getters[k] = lambda b=w: b.property("hex")
            elif t == "file":
                w = QWidget()
                hl = QHBoxLayout(w)
                hl.setContentsMargins(0, 0, 0, 0)
                ed = QLineEdit(o["default"] or "")
                br = QPushButton("Browse…")
                br.clicked.connect(lambda _=False, e=ed, f=o.get("filter", "All files (*.*)"): self._pick_file(e, f))
                hl.addWidget(ed, 1)
                hl.addWidget(br)
                self.getters[k] = ed.text
            form.addRow(label, w)
        if o.get("tip"):
            tip = QLabel(o["tip"])
            tip.setWordWrap(True)
            tip.setStyleSheet("color:#94A3B8;font-size:11px;")
            form.addRow(tip)

    def _out_box(self):
        box, lay = self._box("3️⃣  Choose where to save")
        row = QHBoxLayout()
        self.out_edit = QLineEdit(LAST_OUT["dir"])
        self.out_edit.setPlaceholderText("Select the output folder ...")
        b = QPushButton("📁  Browse")
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton{background:#F59E0B;color:white;border:none;border-radius:8px;padding:7px 16px;font-weight:700;}"
                        "QPushButton:hover{background:#D97706;}")
        b.clicked.connect(self.browse_out)
        row.addWidget(self.out_edit, 1)
        row.addWidget(b)
        lay.addLayout(row)
        return box

    # ----- option helpers
    @staticmethod
    def _paint_color(btn, hexcol):
        c = QColor(hexcol)
        fg = "#000" if c.lightness() > 140 else "#FFF"
        btn.setStyleSheet("QPushButton{background:%s;color:%s;border:1px solid #94A3B8;border-radius:6px;padding:5px;font-weight:700;}" % (hexcol, fg))

    def _pick_color(self, btn):
        col = QColorDialog.getColor(QColor(btn.property("hex")), self, "Choose colour")
        if col.isValid():
            btn.setProperty("hex", col.name())
            btn.setText(col.name())
            self._paint_color(btn, col.name())

    def _pick_file(self, edit, flt):
        p, _ = QFileDialog.getOpenFileName(self, "Select file", "", flt)
        if p:
            edit.setText(p)

    # ----- file list
    def browse_files(self):
        exts = " ".join("*" + e for e in self.spec["exts"])
        paths, _ = QFileDialog.getOpenFileNames(self, "Select file(s)", "", "Supported files (%s);;All files (*.*)" % exts)
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths):
        mx = self.spec["max_files"]
        rejected = 0
        for p in paths:
            if os.path.isdir(p):
                continue
            if not p.lower().endswith(self.spec["exts"]):
                rejected += 1
                continue
            if mx and self.flist.count() >= mx:
                QMessageBox.information(self, APP_NAME, "This tool accepts at most %d file(s)." % mx)
                break
            it = QListWidgetItem(self._label_for(p))
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            self.flist.addItem(it)
        if rejected:
            QMessageBox.warning(self, APP_NAME, "%d file(s) skipped - unsupported type.\nSupported: %s"
                                % (rejected, ", ".join(self.spec["exts"])))
        if hasattr(self, "out_edit") and not self.out_edit.text() and self.flist.count():
            self.out_edit.setText(os.path.dirname(self.flist.item(0).data(Qt.UserRole)))
        self._update_count()

    @staticmethod
    def _label_for(p):
        extra = fmt_size(os.path.getsize(p)) if os.path.exists(p) else ""
        if p.lower().endswith(".pdf"):
            try:
                d = fitz.open(p)
                extra = ("🔒 encrypted • " if d.needs_pass else "%d pages • " % d.page_count) + extra
                d.close()
            except Exception:
                extra = "⚠ unreadable • " + extra
        return "%s    (%s)" % (os.path.basename(p), extra)

    def remove_sel(self):
        for it in self.flist.selectedItems():
            self.flist.takeItem(self.flist.row(it))
        self._update_count()

    def flist_clear(self):
        self.flist.clear()
        self._update_count()

    def move(self, d):
        r = self.flist.currentRow()
        n = r + d
        if r < 0 or n < 0 or n >= self.flist.count():
            return
        it = self.flist.takeItem(r)
        self.flist.insertItem(n, it)
        self.flist.setCurrentRow(n)

    def _update_count(self):
        n = self.flist.count()
        self.count_lab.setText("%d file(s) selected" % n if n else "No files added")

    def browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "Choose output folder", self.out_edit.text() or "")
        if d:
            self.out_edit.setText(d)

    # ----- run
    def log(self, s):
        self.logbox.appendPlainText(s)

    def run(self):
        s = self.spec
        files = [self.flist.item(i).data(Qt.UserRole) for i in range(self.flist.count())]
        if len(files) < s["min_files"]:
            QMessageBox.warning(self, APP_NAME, "Please add at least %d file(s) first." % s["min_files"])
            return
        outdir = ""
        if s["needs_out"]:
            outdir = self.out_edit.text().strip()
            if not outdir:
                QMessageBox.warning(self, APP_NAME, "Please choose an output folder.")
                return
            try:
                os.makedirs(outdir, exist_ok=True)
                test = os.path.join(outdir, ".write_test")
                open(test, "w").close()
                os.remove(test)
            except Exception:
                QMessageBox.warning(self, APP_NAME, "Cannot write to that folder. Please choose another one.")
                return
            LAST_OUT["dir"] = outdir
        opts = {k: g() for k, g in self.getters.items()}
        ctx = Ctx(files, opts, outdir)
        self.logbox.clear()
        self.bar.setValue(0)
        self.open_btn.setVisible(False)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log("Working ...")
        self.worker = Worker(s["fn"], ctx)
        self.worker.log.connect(self.log)
        self.worker.prog.connect(self.bar.setValue)
        self.worker.ok.connect(self.finished_ok)
        self.worker.fail.connect(self.finished_fail)
        self.worker.start()

    def cancel(self):
        if self.worker:
            self.worker.ctx.cancelled = True
            self.cancel_btn.setEnabled(False)

    def _reset_buttons(self):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def finished_ok(self, outputs):
        self._reset_buttons()
        self.bar.setValue(100)
        if self.spec["needs_out"] and outputs:
            self.log("\n✅ Done - %d file(s) created in:\n%s" % (len(outputs), self.out_edit.text()))
            self.open_btn.setVisible(True)
            QMessageBox.information(self, APP_NAME, "Finished!\n\n%d file(s) saved to:\n%s"
                                    % (len(outputs), self.out_edit.text()))
        elif self.spec["needs_out"]:
            self.log("\nFinished - no output file was created (see messages above).")
        else:
            self.log("\n✅ Done.")

    def finished_fail(self, msg):
        self._reset_buttons()
        self.log("\n❌ " + msg)
        if msg != "Cancelled.":
            QMessageBox.critical(self, APP_NAME, msg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1260, 820)
        self.setMinimumSize(1000, 660)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame()
        side.setFixedWidth(232)
        side.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1E3A8A,stop:0.55 #5B21B6,stop:1 #BE185D);}")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 22, 14, 16)
        sl.setSpacing(6)
        logo = QLabel("📄 All in one\nPDF Solution")
        logo.setStyleSheet("color:white;font-size:20px;font-weight:800;background:transparent;")
        sl.addWidget(logo)
        ver = QLabel("v%s  •  works offline" % APP_VERSION)
        ver.setStyleSheet("color:#DDD6FE;font-size:11px;background:transparent;")
        sl.addWidget(ver)
        sl.addSpacing(14)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.cat_buttons = {}
        entries = [(None, "🏠  All Tools  (%d)" % TOOL_COUNT)] + \
                  [(k, "%s  %s  (%d)" % (v["icon"], k, sum(1 for t in TOOLS if t["cat"] == k))) for k, v in CATS.items()]
        for cat, text in entries:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            col = CATS[cat]["color"] if cat else "#FFFFFF"
            b.setStyleSheet(
                "QPushButton{color:white;text-align:left;padding:11px 14px;border:none;border-radius:10px;"
                "font-size:14px;font-weight:600;background:transparent;border-left:5px solid transparent;}"
                "QPushButton:hover{background:rgba(255,255,255,0.15);}"
                "QPushButton:checked{background:rgba(255,255,255,0.28);border-left:5px solid %s;}" % col)
            b.clicked.connect(lambda _=False, c=cat: self.show_category(c))
            self.group.addButton(b)
            sl.addWidget(b)
            self.cat_buttons[cat] = b
        sl.addStretch(1)
        foot = QLabel("🔒 Files stay on your PC.\nNo uploads. No internet needed.")
        foot.setStyleSheet("color:#E9D5FF;font-size:11px;background:transparent;")
        sl.addWidget(foot)
        root.addWidget(side)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.home = HomePage(self.open_tool)
        self.stack.addWidget(self.home)
        self.tool_page = None
        self.cat_buttons[None].setChecked(True)

    def show_category(self, cat):
        self._close_tool()
        self.home.set_category(cat)
        self.stack.setCurrentWidget(self.home)

    def _close_tool(self):
        if self.tool_page is not None:
            self.stack.removeWidget(self.tool_page)
            self.tool_page.deleteLater()
            self.tool_page = None

    def open_tool(self, spec):
        self._close_tool()
        self.tool_page = ToolPage(spec, lambda: self.show_category(self.home.cat))
        self.stack.addWidget(self.tool_page)
        self.stack.setCurrentWidget(self.tool_page)

    def closeEvent(self, e):
        tp = self.tool_page
        if tp is not None and tp.worker is not None and tp.worker.isRunning():
            tp.worker.ctx.cancelled = True
            tp.worker.wait(3000)
        e.accept()


GLOBAL_CSS = """
QWidget{font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;font-size:13px;color:#1E293B;}
QToolTip{background:#0F172A;color:white;border:none;padding:6px;}
QLineEdit,QSpinBox,QComboBox{background:white;border:1px solid #CBD5E1;border-radius:8px;padding:6px 8px;min-height:20px;}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus{border:2px solid #7C3AED;}
QComboBox QAbstractItemView{background:white;selection-background-color:#7C3AED;selection-color:white;}
QCheckBox::indicator{width:18px;height:18px;}
QScrollBar:vertical{background:transparent;width:11px;margin:2px;}
QScrollBar::handle:vertical{background:#CBD5E1;border-radius:5px;min-height:30px;}
QScrollBar::handle:vertical:hover{background:#94A3B8;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QMessageBox{background:white;}
QPushButton{font-size:13px;}
"""


def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(GLOBAL_CSS)
    win = MainWindow()
    win.show()
    app.exec_()


if __name__ == "__main__":
    main()
