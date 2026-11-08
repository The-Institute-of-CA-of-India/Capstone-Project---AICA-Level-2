"""
=============================================================================
MSME CERTIFETCH
Bulk Udyam Registration Verifier, Certificate Downloader and Data Extractor
=============================================================================
Reads Udyam numbers from Excel, opens the official portal in Chrome, shows each
captcha for a person to type, then saves the certificate as a PDF and writes
an Excel report.

Pre-requisites:
    pip install selenium openpyxl customtkinter Pillow
=============================================================================
"""

import os
import sys
import time
import re
import base64
import threading
import io
import ctypes
import math
import tkinter as tk
from datetime import datetime

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk


# ---- Configuration ----
HOME_URL = "https://www.udyamregistration.gov.in/default.aspx#"
VERIFY_URL = "https://www.udyamregistration.gov.in/Udyam_Verify.aspx"
PAGE_LOAD_TIMEOUT = 20

# ---- Autumn Palette ----
APP_BG = "#EFF3E6"
SURFACE = "#FCFCF7"
HEADER_TEXT = "#22352A"
SUBHEADER_TEXT = "#3F5444"
PRIMARY = "#C2421A"
PRIMARY_HOVER = "#A23512"
SECONDARY = "#3F7048"
SECONDARY_HOVER = "#E2E9D3"
TEXT = "#22352A"
MUTED = "#566A58"
BORDER = "#D3DBC3"
ENTRY_BG = "#FCFCF7"
ENTRY_TEXT = "#22352A"
PLACEHOLDER = "#6E8070"
LOG_BG = "#F7F8EF"
LOG_TEXT = "#3A4C3E"
DANGER = "#A62B3B"
DANGER_HOVER = "#872231"
SUCCESS = "#2C7A4B"
AMBER = "#9A6200"
DISABLED_BTN = "#DCE1CF"
DISABLED_TEXT = "#6E7B69"
PROGRESS = "#C2421A"
FONT = "Candara"
DISPLAY_FONT = "Sitka Display"
NUMBER_FONT = "Segoe UI Semibold"  # Lining digits: a 0 must never read as a letter
GHOST = "transparent"

# A leaf's year, from first green to last crimson
SEASON = [(92, 134, 62), (130, 148, 52), (186, 158, 44), (226, 158, 40),
          (228, 122, 34), (212, 84, 32), (186, 54, 36)]

WINDOW_WIDTH = 1120
WINDOW_HEIGHT = 740
HEADER_HEIGHT = 138
CAPTCHA_MAX_WIDTH = 320
CAPTCHA_MAX_HEIGHT = 104
ICON_FILE = os.path.join("Art", "autumn_icon.ico")
LOGO_FILE = os.path.join("Art", "autumn_logo.png")
SCENE_FILE = os.path.join("Art", "autumn_scene.png")
LEAF_FILES = [os.path.join("Art", f"leaf_{n}.png") for n in (1, 2, 3)]
HEADER_LOGO_SIZE = 62
DRIFT_LEAVES = 6


def resource_path(relative_path):
    """Finds bundled files both from source and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def animations_allowed():
    """Honours the Windows setting that turns interface animation off."""
    if sys.platform != "win32":
        return True
    enabled = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
    return bool(enabled.value)


class TwigProgress(tk.Canvas):
    """A twig whose leaves open and turn from green to crimson as work completes."""

    def __init__(self, master, scale):
        self.scale_factor = scale
        super().__init__(
            master, height=int(84 * scale), highlightthickness=0, bd=0, bg=APP_BG
        )
        self.value = 0.0
        self.picture = None
        self.bind("<Configure>", lambda e: self._render())

    def get(self):
        return self.value

    def set(self, value):
        self.value = max(0.0, min(1.0, float(value)))
        self._render()

    def _render(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 40:
            return
        ss = 3
        W, H = width * ss, height * ss
        ground = tuple(int(APP_BG[i:i + 2], 16) for i in (1, 3, 5))
        img = Image.new("RGB", (W, H), ground)
        draw = ImageDraw.Draw(img)

        def y_at(x):
            return H * .52 + H * .10 * math.sin(x / W * math.pi * 2.2)

        steps = 240
        for i in range(steps):
            a, b = i / steps, (i + 1) / steps
            thick = int((5.2 - 3.4 * a) * self.scale_factor * ss / 1.6)
            done = a <= self.value
            colour = (118, 82, 54) if done else (190, 196, 170)
            draw.line([(W * a, y_at(W * a)), (W * b, y_at(W * b))], fill=colour, width=max(2, thick))

        count = max(8, int(width / (self.scale_factor * 25)))
        for i in range(count):
            position = (i + .5) / count
            x = W * (.015 + position * .955)
            side = -1 if i % 2 else 1
            opened = position <= self.value
            if opened:
                index = min(len(SEASON) - 1, int(position * len(SEASON)))
                length = H * .36
                colour = SEASON[index]
            else:
                length = H * .12
                colour = (190, 200, 164)
            self._leaf(draw, x, y_at(x), length, side * (.55 + .22 * math.sin(i * 2.4)), colour)
        self.picture = ImageTk.PhotoImage(img.resize((width, height), Image.LANCZOS))
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self.picture)

    @staticmethod
    def _leaf(draw, x, y, length, angle, colour):
        direction = -math.pi / 2 + angle * 1.5
        ux, uy = math.cos(direction), math.sin(direction)
        px, py = -uy, ux
        outline_a, outline_b = [], []
        steps = 18
        for i in range(steps + 1):
            t = i / steps
            half = length * .26 * math.sin(math.pi * t) ** .8
            cx, cy = x + ux * length * t, y + uy * length * t
            outline_a.append((cx + px * half, cy + py * half))
            outline_b.append((cx - px * half, cy - py * half))
        draw.polygon(outline_a + outline_b[::-1], fill=colour)
        vein = tuple(min(255, c + 46) for c in colour)
        draw.line([(x, y), (x + ux * length * .92, y + uy * length * .92)], fill=vein, width=2)


class UdyamVerifierApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Ramesh Rajni | MSME CertiFetch")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
        self.configure(fg_color=APP_BG)
        self._fit_window_to_screen()
        try:
            self.iconbitmap(resource_path(ICON_FILE))
        except Exception:
            pass  # The app still works with the default icon

        # State
        self.excel_path_var = ctk.StringVar()
        self.folder_path_var = ctk.StringVar()
        self.captcha_text_var = ctk.StringVar()
        self.is_running = False
        self.stop_requested = False
        self.driver = None
        self.worker = None
        self.closing = False
        self.waiting_for_captcha = False
        self.captcha_action = None
        self.captcha_photo = None
        self.last_saved = 0
        # CustomTkinter cannot clear a CTkImage with image=None, so use a blank one
        blank = Image.new("RGB", (1, 1), APP_BG)
        self.blank_image = ctk.CTkImage(light_image=blank, dark_image=blank, size=(1, 1))
        self._focus_attempts = 0
        self.run_failed = False
        # Track if we have already navigated to verify page at least once
        self.on_verify_page = False

        self._build_header()
        self._build_status_bar()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=44, pady=(6, 0))
        body.grid_columnconfigure(0, weight=10, uniform="col")
        body.grid_columnconfigure(1, weight=11, uniform="col")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 26))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(26, 0))

        self._build_file_section(left)
        self._build_controls(left)
        self._build_stats(left)
        self._build_captcha_section(right)
        self._build_log(right)

        self.bind("<Return>", lambda e: self._on_captcha_submit())
        self.bind("<F5>", lambda e: self._on_captcha_refresh())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _fit_window_to_screen(self):
        """Keeps the whole window, including the log, on the visible screen."""
        scale = self._get_window_scaling()
        if sys.platform == "win32":
            # Actual pixels. Tk can report a size already reduced by display scaling.
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        else:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
        width = min(WINDOW_WIDTH, int(screen_w / scale) - 40)
        height = min(WINDOW_HEIGHT, int(screen_h / scale) - 110)
        x = max(0, int((screen_w - width * scale) / 2))
        y = max(0, int((screen_h - height * scale) / 2) - 40)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(980, width), min(660, height))

    def _on_close(self):
        """Closing mid-run ends Chrome too, and keeps the Excel status correct."""
        if self.closing:
            return
        self.closing = True
        self.stop_requested = True
        self.waiting_for_captcha = False
        self.captcha_action = "quit"
        if not self.driver and not (self.worker and self.worker.is_alive()):
            self.destroy()
            return

        self.withdraw()

        def shut_down():
            driver = self.driver
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=6)
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            self.after(0, self.destroy)

        threading.Thread(target=shut_down, daemon=True).start()

    # ==================================================================
    # GUI LAYOUT
    # ==================================================================

    def _build_header(self):
        scale = self._get_window_scaling()
        self.header_logo = None
        self.scene_source = None
        self.scene_picture = None
        self.scene_size = None
        self.drifters = []
        self.leaf_sources = []
        try:
            size = int(HEADER_LOGO_SIZE * scale)
            logo = Image.open(resource_path(LOGO_FILE)).convert("RGBA")
            self.header_logo = ImageTk.PhotoImage(logo.resize((size, size), Image.LANCZOS))
            self.scene_source = Image.open(resource_path(SCENE_FILE)).convert("RGB")
            self.leaf_sources = [
                Image.open(resource_path(path)).convert("RGBA") for path in LEAF_FILES
            ]
        except Exception:
            pass  # The header still works without the artwork
        self.header = tk.Canvas(
            self, height=int(HEADER_HEIGHT * scale), highlightthickness=0, bd=0, bg=APP_BG
        )
        self.header.pack(fill="x")
        self.header.bind("<Configure>", self._draw_header)
        if self.leaf_sources and animations_allowed():
            self.after(600, self._start_breeze)

    def _draw_header(self, event):
        canvas = self.header
        scale = self._get_window_scaling()
        width, height = event.width, event.height
        if self.scene_source and self.scene_size != (width, height):
            source = self.scene_source
            ratio = max(width / source.width, height / source.height)
            resized = source.resize(
                (int(source.width * ratio) + 1, int(source.height * ratio) + 1), Image.LANCZOS
            )
            left = resized.width - width
            top = resized.height - height
            self.scene_picture = ImageTk.PhotoImage(
                resized.crop((left, top, left + width, top + height))
            )
            self.scene_size = (width, height)

        canvas.delete("scene", "words")
        if self.scene_picture:
            canvas.create_image(0, 0, anchor="nw", image=self.scene_picture, tags="scene")
            canvas.tag_lower("scene")

        text_left = int(44 * scale)
        if self.header_logo:
            canvas.create_image(
                text_left, int(58 * scale), anchor="w", image=self.header_logo, tags="words"
            )
            text_left += int((HEADER_LOGO_SIZE + 18) * scale)

        canvas.create_text(
            text_left, int(42 * scale), anchor="w", text="MSME CertiFetch", tags="words",
            fill=HEADER_TEXT, font=(DISPLAY_FONT, -int(38 * scale), "bold")
        )
        canvas.create_text(
            text_left + int(2 * scale), int(78 * scale), anchor="w", tags="words",
            text="MSME certificate downloader and data extractor  ·  by Ramesh Rajni & Co LLP",
            fill=SUBHEADER_TEXT, font=(FONT, -int(16 * scale))
        )

    def _start_breeze(self):
        scale = self._get_window_scaling()
        for number in range(DRIFT_LEAVES):
            self.drifters.append(self._new_drifter(
                self.leaf_sources[number % len(self.leaf_sources)],
                int((20 + number % 3 * 7) * scale),
                x=(number + .3) / DRIFT_LEAVES,
                speed=.9 + number % 3 * .3,
            ))
        self._blow()

    def _new_drifter(self, source, size, x, speed, once=False):
        frames = [
            ImageTk.PhotoImage(source.resize((size, size), Image.LANCZOS).rotate(angle * 15, resample=Image.BICUBIC, expand=True))
            for angle in range(24)
        ]
        width = max(self.header.winfo_width(), 400)
        return {
            "frames": frames,
            "item": self.header.create_image(int(width * x), 0, image=frames[0]),
            "x": width * x,
            "speed": speed,
            "phase": x * 40,
            "base": .18 + (x * 7 % 1) * .42,
            "turn": x * 24,
            "once": once,
        }

    def _blow(self):
        if self.closing:
            return
        if self.state() != "iconic":
            width = self.header.winfo_width()
            height = self.header.winfo_height()
            for leaf in list(self.drifters):
                leaf["x"] += leaf["speed"]
                leaf["phase"] += .022
                leaf["turn"] = (leaf["turn"] + leaf["speed"] * .16) % 24
                if leaf["x"] > width + 40:
                    if leaf["once"]:
                        self.header.delete(leaf["item"])
                        self.drifters.remove(leaf)
                        continue
                    leaf["x"] = -40
                y = height * leaf["base"] + math.sin(leaf["phase"]) * height * .10
                self.header.coords(leaf["item"], leaf["x"], y)
                self.header.itemconfigure(leaf["item"], image=leaf["frames"][int(leaf["turn"])])
            self.header.tag_raise("words")
        self.after(40, self._blow)

    def _gust(self):
        """One golden leaf crosses the sky for every certificate saved."""
        if not self.leaf_sources or not animations_allowed() or len(self.drifters) > DRIFT_LEAVES + 3:
            return
        scale = self._get_window_scaling()
        self.drifters.append(self._new_drifter(self.leaf_sources[1], int(34 * scale), x=0, speed=7, once=True))

    def _heading(self, parent, title):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", anchor="w")
        ctk.CTkLabel(
            row, text=title, text_color=TEXT, height=30,
            font=ctk.CTkFont(family=DISPLAY_FONT, size=21, weight="bold")
        ).pack(side="left")
        return row

    def _ghost_button(self, parent, text, command, width=84, height=34, **extra):
        return ctk.CTkButton(
            parent, text=text, width=width, height=height, corner_radius=height // 2,
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            fg_color=GHOST, hover_color=SECONDARY_HOVER, border_width=1,
            border_color=BORDER, text_color=SECONDARY,
            text_color_disabled=DISABLED_TEXT, command=command, **extra
        )

    def _build_path_row(self, parent, label, variable, placeholder, command, top):
        ctk.CTkLabel(
            parent, text=label, text_color=MUTED, height=22,
            font=ctk.CTkFont(family=FONT, size=14)
        ).pack(anchor="w", pady=(top, 4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        self._ghost_button(row, "Browse", command).pack(side="right", padx=(10, 0))
        entry = ctk.CTkEntry(
            row, textvariable=variable, height=38, corner_radius=19, border_width=1,
            font=ctk.CTkFont(family=FONT, size=14), fg_color=ENTRY_BG,
            border_color=BORDER, text_color=ENTRY_TEXT,
            placeholder_text=placeholder, placeholder_text_color=PLACEHOLDER
        )
        entry.pack(side="left", fill="x", expand=True)
        return entry

    def _build_file_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x")
        title_row = self._heading(section, "Your files")
        self.template_btn = self._ghost_button(
            title_row, "Get Excel template", self._export_template, width=150
        )
        self.template_btn.pack(side="right")
        self.excel_entry = self._build_path_row(
            section, "Excel file", self.excel_path_var,
            "Choose your .xlsx file", self._browse_excel, 12
        )
        self.folder_entry = self._build_path_row(
            section, "Save certificates to", self.folder_path_var,
            "Choose a folder", self._browse_folder, 14
        )

    def _build_controls(self, parent):
        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.pack(fill="x", pady=(24, 0))

        self.start_btn = ctk.CTkButton(
            controls, text="Start processing", height=50, corner_radius=25,
            font=ctk.CTkFont(family=FONT, size=18, weight="bold"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="#FFFFFF",
            text_color_disabled=DISABLED_TEXT, command=self._start_processing
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.stop_btn = ctk.CTkButton(
            controls, text="Stop", height=50, width=96, corner_radius=25,
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            fg_color=DISABLED_BTN, hover_color=DANGER_HOVER, text_color="#FFFFFF",
            text_color_disabled=DISABLED_TEXT, state="disabled", command=self._stop_processing
        )
        self.stop_btn.pack(side="left")

    def _build_stats(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="both", expand=True, pady=(26, 0))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x")
        self._heading(header, "Progress").pack_configure(side="left", fill=None)
        self.progress_label = ctk.CTkLabel(
            header, text="", text_color=PROGRESS,
            font=ctk.CTkFont(family=NUMBER_FONT, size=15)
        )
        self.progress_label.pack(side="right")

        self.progress_bar = TwigProgress(section, self._get_window_scaling())
        self.progress_bar.pack(fill="x", pady=(4, 12))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="count")

        self.tile_values = {}
        counts = [
            ("total", "To process", TEXT),
            ("saved", "Saved", SUCCESS),
            ("failed", "Failed", DANGER),
            ("skipped", "Skipped", AMBER),
        ]
        for column, (key, caption, colour) in enumerate(counts):
            holder = ctk.CTkFrame(row, fg_color="transparent")
            holder.grid(row=0, column=column, sticky="w")
            value = ctk.CTkLabel(
                holder, text="0", text_color=colour, height=44,
                font=ctk.CTkFont(family=NUMBER_FONT, size=32)
            )
            value.pack(anchor="w")
            ctk.CTkLabel(
                holder, text=caption, text_color=MUTED, height=20,
                font=ctk.CTkFont(family=FONT, size=14)
            ).pack(anchor="w")
            self.tile_values[key] = value

    def _build_captcha_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x")
        self._heading(section, "Captcha")

        self.captcha_card = ctk.CTkFrame(
            section, fg_color=SURFACE, corner_radius=22, border_width=2, border_color=BORDER
        )
        self.captcha_card.pack(fill="x", pady=(10, 0))

        self.captcha_status = ctk.CTkLabel(
            self.captcha_card, text="Waiting to begin",
            font=ctk.CTkFont(family=NUMBER_FONT, size=14), text_color=MUTED
        )
        self.captcha_status.pack(padx=24, pady=(14, 8), anchor="w")

        self.captcha_image_label = ctk.CTkLabel(
            self.captcha_card, text="The captcha will appear here",
            font=ctk.CTkFont(family=FONT, size=14), text_color=MUTED,
            fg_color=APP_BG, corner_radius=14,
            height=CAPTCHA_MAX_HEIGHT, width=CAPTCHA_MAX_WIDTH
        )
        self.captcha_image_label.pack(padx=24, pady=(0, 12))

        input_row = ctk.CTkFrame(self.captcha_card, fg_color="transparent")
        input_row.pack(fill="x", padx=24)

        self.captcha_entry = ctk.CTkEntry(
            input_row, textvariable=self.captcha_text_var,
            height=46, width=150, border_width=2, corner_radius=23,
            font=ctk.CTkFont(family="Consolas", size=21, weight="bold"),
            fg_color=ENTRY_BG, border_color=SECONDARY, text_color=ENTRY_TEXT,
            justify="center"
        )
        self.captcha_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.submit_btn = ctk.CTkButton(
            input_row, text="Submit", width=92, height=46, corner_radius=23,
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            fg_color=DISABLED_BTN, hover_color=PRIMARY_HOVER, text_color="#FFFFFF",
            text_color_disabled=DISABLED_TEXT, state="disabled", command=self._on_captcha_submit
        )
        self.submit_btn.pack(side="left", padx=(0, 6))

        self.refresh_btn = self._ghost_button(
            input_row, "Refresh", self._on_captcha_refresh, width=78, height=46, state="disabled"
        )
        self.refresh_btn.pack(side="left", padx=(0, 6))

        self.skip_btn = self._ghost_button(
            input_row, "Skip", self._on_captcha_skip, width=60, height=46, state="disabled"
        )
        self.skip_btn.pack(side="left")

        ctk.CTkLabel(
            self.captcha_card,
            text="Just type and press Enter. F5 brings a new captcha.",
            font=ctk.CTkFont(family=FONT, size=14), text_color=MUTED
        ).pack(padx=24, pady=(8, 14), anchor="w")

    def _build_log(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="both", expand=True, pady=(16, 0))
        self.log_box = ctk.CTkTextbox(
            section, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=LOG_BG, text_color=LOG_TEXT, border_width=0,
            corner_radius=16, wrap="word", scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=SECONDARY
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("good", foreground=SUCCESS)
        self.log_box.tag_config("bad", foreground=DANGER)
        self.log_box.configure(state="disabled")

    def _build_status_bar(self):
        self.status_label = ctk.CTkLabel(
            self, text="Ready when you are. Choose your files and press Start.",
            font=ctk.CTkFont(family=FONT, size=14), text_color=MUTED, anchor="w"
        )
        self.status_label.pack(side="bottom", fill="x", padx=46, pady=(10, 12))

    # ==================================================================
    # GUI ACTIONS
    # ==================================================================

    def _browse_excel(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")]
        )
        if path:
            self.excel_path_var.set(path)

    def _browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select Folder to Save PDFs")
        if folder:
            self.folder_path_var.set(folder)

    def _export_template(self):
        """Saves a blank input file in the exact format the tool reads."""
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(
            title="Save Excel Template",
            defaultextension=".xlsx",
            initialfile="Udyam_Numbers_Template.xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )
        if not path:
            return
        try:
            self._write_template(path)
        except PermissionError:
            messagebox.showerror(
                "Could Not Save",
                "That file is open in Excel. Close it and try again."
            )
            return
        except Exception as e:
            messagebox.showerror("Could Not Save", str(e))
            return

        self.excel_path_var.set(path)
        self.log(f"Template saved: {path}")
        if messagebox.askyesno(
            "Template Saved",
            "Template saved and selected for you.\n\n"
            "Enter one Udyam number per row in column A, then save and close it.\n\n"
            "Open it in Excel now?"
        ):
            try:
                os.startfile(path)
            except Exception as e:
                self.log(f"Could not open the template: {e}")

    def _write_template(self, path):
        from openpyxl import Workbook
        from openpyxl.worksheet.datavalidation import DataValidation

        twb = Workbook()
        sheet = twb.active
        sheet.title = "Udyam Numbers"

        header_font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
        header_fill = PatternFill(start_color="4C2FD1", end_color="4C2FD1", fill_type="solid")
        locked_fill = PatternFill(start_color="EFEDF8", end_color="EFEDF8", fill_type="solid")
        for column, name, width in [(1, "Udyam Number", 32), (2, "Status", 16)]:
            cell = sheet.cell(row=1, column=column, value=name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            sheet.column_dimensions[cell.column_letter].width = width
        sheet.row_dimensions[1].height = 24
        sheet.freeze_panes = "A2"

        for row in range(2, 502):
            sheet.cell(row=row, column=1).number_format = "@"
            sheet.cell(row=row, column=2).fill = locked_fill

        check = DataValidation(
            type="custom",
            formula1='AND(LEN(TRIM(A2))=19,UPPER(LEFT(TRIM(A2),6))="UDYAM-")',
            allow_blank=True,
            showErrorMessage=True,
            errorStyle="warning",
            errorTitle="Check this Udyam number",
            error="A Udyam number has 19 characters, like UDYAM-XX-00-0000000.",
            showInputMessage=True,
            promptTitle="Udyam Number",
            prompt="One number per row, like UDYAM-XX-00-0000000"
        )
        sheet.add_data_validation(check)
        check.add("A2:A5000")

        guide = twb.create_sheet("Instructions")
        guide.column_dimensions["A"].width = 92
        steps = [
            "How to fill this file",
            "1. Go to the 'Udyam Numbers' sheet.",
            "2. Enter one Udyam number per row in column A, starting at row 2.",
            "3. Use the full format, for example UDYAM-XX-00-0000000.",
            "4. Leave column B (Status) empty. The tool fills it in.",
            "5. Do not change the headers or move the columns.",
            "6. Save and close this file, then click START PROCESSING in the tool.",
            "",
            "To continue a stopped run, use the same file again. Only rows marked Done are left out.",
        ]
        for row, line in enumerate(steps, 1):
            cell = guide.cell(row=row, column=1, value=line)
            cell.font = Font(name="Calibri", size=14 if row == 1 else 12, bold=row == 1)

        twb.active = 0
        twb.save(path)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}]  {message}\n"
        lowered = message.lower()
        tag = None
        if "error" in lowered or "failed" in lowered and "failed  :" not in lowered or "giving up" in lowered:
            tag = "bad"
        elif message.startswith(("PDF saved", "Report saved", "COMPLETE")):
            tag = "good"
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line, tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)

    def _set_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def _set_progress(self, text):
        self.after(0, lambda: self.progress_label.configure(text=text))

    def _update_counts(self, total, saved, failed, skipped):
        def _update():
            self.tile_values["total"].configure(text=str(total))
            self.tile_values["saved"].configure(text=str(saved))
            self.tile_values["failed"].configure(text=str(failed))
            self.tile_values["skipped"].configure(text=str(skipped))
            if saved > self.last_saved:
                self._gust()
            self.last_saved = saved
            finished = saved + failed + skipped
            self.progress_bar.set(finished / total if total else 0)
        self.after(0, _update)

    def _set_button(self, button, enabled, colour):
        button.configure(
            state="normal" if enabled else "disabled",
            fg_color=colour if enabled or colour == GHOST else DISABLED_BTN
        )

    def _force_foreground(self):
        """
        Windows blocks a background app from taking the keyboard, and Chrome
        has just been used by the automation. Briefly attaching to the input
        queue of the current foreground window allows this window to take over.
        """
        if sys.platform != "win32":
            self.focus_force()
            return
        attached_thread = 0
        user32 = ctypes.windll.user32
        this_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        try:
            window = user32.GetAncestor(self.winfo_id(), 2)
            foreground = user32.GetForegroundWindow()
            if foreground == window:
                return
            foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
            if foreground_thread and foreground_thread != this_thread:
                if user32.AttachThreadInput(this_thread, foreground_thread, True):
                    attached_thread = foreground_thread
            if user32.IsIconic(window):
                user32.ShowWindow(window, 9)
            user32.BringWindowToTop(window)
            user32.SetForegroundWindow(window)
        except Exception:
            self.focus_force()
        finally:
            if attached_thread:
                user32.AttachThreadInput(this_thread, attached_thread, False)

    def _window_has_keyboard(self):
        if sys.platform != "win32":
            return True
        user32 = ctypes.windll.user32
        return user32.GetForegroundWindow() == user32.GetAncestor(self.winfo_id(), 2)

    def _popup_window(self):
        """
        Brings the window to the front. While a captcha is waiting, it also
        puts the cursor in the captcha box so no mouse click is needed.
        """
        def _do():
            self.deiconify()
            self.lift()
            self._force_foreground()
            self.attributes('-topmost', True)
            self.after(500, lambda: self.attributes('-topmost', False))
            self._focus_attempts = 0
            self._focus_captcha_entry()
        self.after(0, _do)

    def _focus_captcha_entry(self):
        """
        Repeats for up to 2 seconds until the box really has the keyboard,
        because Chrome or the window restore can take focus back.
        """
        if not self.waiting_for_captcha:
            return
        inner_entry = self.captcha_entry._entry
        has_focus = self._window_has_keyboard() and self.focus_get() is inner_entry
        if not has_focus:
            self._force_foreground()
            inner_entry.focus_force()
            inner_entry.icursor("end")
        self._focus_attempts += 1
        if self._focus_attempts < 16:
            self.after(125, self._focus_captcha_entry)

    def _minimize_window(self):
        """Minimizes the GUI so you can continue other work."""
        def _do():
            self.iconify()
        self.after(0, _do)

    def _on_captcha_submit(self):
        if not self.waiting_for_captcha:
            return
        captcha_text = self.captcha_text_var.get().strip()
        if not captcha_text:
            return
        self.captcha_action = "submit"
        self.waiting_for_captcha = False
        # Minimize after submitting so you can work while it processes
        self._minimize_window()

    def _on_captcha_skip(self):
        if not self.waiting_for_captcha:
            return
        self.captcha_action = "skip"
        self.waiting_for_captcha = False

    def _on_captcha_refresh(self):
        if not self.waiting_for_captcha:
            return
        self.captcha_action = "refresh"
        self.waiting_for_captcha = False

    def _enable_captcha_controls(self, udyam_number):
        def _update():
            self.captcha_status.configure(
                text=f"Type the captcha for:  {udyam_number}",
                text_color=PRIMARY
            )
            self.captcha_card.configure(border_color=PRIMARY)
            self.captcha_entry.configure(state="normal")
            self.captcha_text_var.set("")
            self._set_button(self.submit_btn, True, PRIMARY)
            self._set_button(self.refresh_btn, True, GHOST)
            self._set_button(self.skip_btn, True, GHOST)
        self.after(0, _update)

    def _disable_captcha_controls(self, status_text="Processing...", colour=MUTED):
        def _update():
            self.captcha_status.configure(text=status_text, text_color=colour)
            self.captcha_card.configure(border_color=BORDER)
            self.captcha_entry.configure(state="disabled")
            self._set_button(self.submit_btn, False, PRIMARY)
            self._set_button(self.refresh_btn, False, GHOST)
            self._set_button(self.skip_btn, False, GHOST)
        self.after(0, _update)

    def _display_captcha_image(self, image_bytes):
        def _update():
            try:
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                ratio = min(CAPTCHA_MAX_WIDTH / img.width, CAPTCHA_MAX_HEIGHT / img.height)
                size = (round(img.width * ratio), round(img.height * ratio))
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=size)
                self.captcha_photo = photo
                self.captcha_image_label.configure(image=photo, text="")
            except Exception as e:
                self.captcha_image_label.configure(
                    text=f"Could not load captcha: {e}", image=self.blank_image
                )
        self.after(0, _update)

    def _clear_captcha_image(self):
        def _update():
            self.captcha_image_label.configure(text="No captcha waiting", image=self.blank_image)
            self.captcha_photo = None
        self.after(0, _update)

    # ==================================================================
    # START / STOP
    # ==================================================================

    def _start_processing(self):
        excel = self.excel_path_var.get().strip()
        folder = self.folder_path_var.get().strip()

        if not excel:
            self._show_warning("Please select an Excel file first.")
            return
        if not os.path.exists(excel):
            self._show_warning(f"Excel file not found:\n{excel}")
            return
        if not folder:
            self._show_warning("Please select a save folder first.")
            return
        if not os.path.exists(folder):
            os.makedirs(folder)

        self._set_button(self.start_btn, False, PRIMARY)
        self._set_button(self.stop_btn, True, DANGER)
        self.is_running = True
        self.stop_requested = False
        self.on_verify_page = False
        self._update_counts(0, 0, 0, 0)
        self._set_progress("")

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self.last_saved = 0
        self.worker = threading.Thread(
            target=self._process_all, args=(excel, folder), daemon=True
        )
        self.worker.start()

    def _stop_processing(self):
        self.stop_requested = True
        self.waiting_for_captcha = False
        self.captcha_action = "quit"
        self.log("STOP requested...")
        self._set_status("Stopping...")

    def _show_warning(self, msg):
        from tkinter import messagebox
        messagebox.showwarning("Input Required", msg)

    def _finish(self):
        if self.closing:
            return
        def _update():
            self._set_button(self.start_btn, True, PRIMARY)
            self._set_button(self.stop_btn, False, DANGER)
            if self.run_failed:
                self._disable_captcha_controls("Stopped by an error. See the activity log.", DANGER)
            else:
                self._disable_captcha_controls("Complete.", SUCCESS)
            self._clear_captcha_image()
            self.captcha_text_var.set("")
            self._set_status(
                "Stopped. Run the same file again to continue." if self.run_failed
                else "All done. Your certificates are in the folder you chose."
            )
            self.is_running = False
        self.after(0, _update)
        self._popup_window()

    # ==================================================================
    # CORE PROCESSING
    # ==================================================================

    def _process_all(self, excel_path, save_folder):
        driver = None
        wb = None
        report_data = []  # Collected data for the report Excel
        report_saved = False
        self.run_failed = False

        try:
            # ---- Read input Excel ----
            self.log("Reading Excel file...")
            wb = load_workbook(excel_path)
            ws = wb.active

            if ws.cell(row=1, column=2).value != "Status":
                ws.cell(row=1, column=2, value="Status")
                wb.save(excel_path)

            udyam_list = []
            for row in range(2, ws.max_row + 1):
                val = ws.cell(row=row, column=1).value
                status = ws.cell(row=row, column=2).value
                if val is None or str(val).strip() == "":
                    continue
                if status and str(status).strip().lower() == "done":
                    self.log(f"Row {row}: {val}  already done, skipping.")
                    continue
                udyam_list.append((row, str(val).strip()))

            total = len(udyam_list)
            self.log(f"Found {total} number(s) to process.")
            if total == 0:
                self.log("Nothing to process.")
                self._finish()
                return

            # ---- Launch Chrome ----
            self.log("Launching Chrome...")
            driver = self._setup_chrome()
            self.driver = driver
            self.log("Chrome ready.")

            # ---- Navigate to verify page once at the start ----
            self._navigate_to_verify_page_via_menu(driver)

            done_count = 0
            failed_count = 0
            skipped_count = 0
            self._update_counts(total, 0, 0, 0)

            for idx, (row, udyam_number) in enumerate(udyam_list, 1):
                if self.stop_requested:
                    break

                self.log(f"--- [{idx}/{total}]  {udyam_number} ---")
                self._set_progress(f"{idx} / {total}")
                self._set_status(f"Processing: {udyam_number}")

                max_retries = 3
                attempt = 0
                resolved = False   # True once this row has a final status
                refreshed = False  # A captcha refresh does not use up an attempt
                page_ready = False  # After a wrong captcha the portal already shows a new one

                while (attempt < max_retries or refreshed) and not self.stop_requested:
                    if refreshed:
                        refreshed = False
                    else:
                        attempt += 1
                        if attempt > 1:
                            self.log(f"Retry {attempt}/{max_retries}")
                            if page_ready:
                                page_ready = False
                                time.sleep(0.4)  # Lets the new captcha image finish drawing
                            elif not self._try_reset_verify_page(driver):
                                continue

                    # Step A: Enter Udyam number
                    try:
                        self._enter_udyam_number(driver, udyam_number)
                    except Exception as e:
                        self.log(f"Input error: {self._short_error(e)}")
                        continue

                    # Step B: Capture captcha and show in GUI
                    captcha_bytes = self._capture_captcha_image(driver)
                    if captcha_bytes:
                        self._display_captcha_image(captcha_bytes)
                    else:
                        self.log("Could not capture captcha. Check Chrome.")

                    # Step C: Pop up GUI and wait for user
                    self.captcha_action = None
                    self.waiting_for_captcha = True
                    self._enable_captcha_controls(udyam_number)
                    self._popup_window()

                    while self.waiting_for_captcha and not self.stop_requested:
                        time.sleep(0.15)

                    self._disable_captcha_controls()

                    if self.stop_requested or self.captcha_action == "quit":
                        self._update_excel(wb, ws, excel_path, row, "Pending")
                        resolved = True
                        break

                    if self.captcha_action == "skip":
                        self.log(f"Skipped: {udyam_number}")
                        self._update_excel(wb, ws, excel_path, row, "Skipped")
                        skipped_count += 1
                        resolved = True
                        break

                    if self.captcha_action == "refresh":
                        self.log("Refreshing page for new captcha...")
                        refreshed = self._try_reset_verify_page(driver)
                        continue

                    # Step D: Enter captcha in browser and click Verify
                    captcha_text = self.captcha_text_var.get().strip()
                    self.log(f"Captcha: {captcha_text}")
                    if not self._enter_captcha_in_browser(driver, captcha_text):
                        continue
                    if not self._click_verify(driver):
                        continue

                    # Step E: Check result page
                    if not self._is_result_page(driver):
                        if self._wrong_captcha_shown(driver):
                            self.log("Wrong captcha. Showing the new one.")
                            page_ready = True
                        else:
                            self.log("Verification did not reach result page. Possible invalid Udyam number or portal error.")
                        if attempt < max_retries:
                            continue
                        self._update_excel(wb, ws, excel_path, row, "Failed")
                        failed_count += 1
                        resolved = True
                        break

                    # Step F: Extract data from result page
                    extracted = self._extract_all_data(driver)
                    enterprise_name = extracted.get("name", "Unknown")
                    major_activity = extracted.get("major_activity", "")
                    classifications = extracted.get("classifications", [])

                    self.log(f"Enterprise: {enterprise_name}")

                    # Build report row: ONE row per Udyam number
                    # with the top 2 classification years side by side
                    row_data = {
                        "udyam_number": udyam_number,
                        "name": enterprise_name,
                        "major_activity": major_activity,
                        "year_1": "",
                        "type_1": "",
                        "year_2": "",
                        "type_2": ""
                    }
                    if len(classifications) >= 1:
                        row_data["year_1"] = classifications[0].get("year", "")
                        row_data["type_1"] = classifications[0].get("type", "")
                    if len(classifications) >= 2:
                        row_data["year_2"] = classifications[1].get("year", "")
                        row_data["type_2"] = classifications[1].get("type", "")
                    report_data.append(row_data)

                    # Step G: Click Print button (intercepted) and save as PDF
                    self.log("Saving PDF...")
                    pdf_saved = self._save_page_as_pdf(
                        driver, save_folder, enterprise_name, udyam_number
                    )

                    # Only a PDF that was really written counts as Done
                    if pdf_saved:
                        self._update_excel(wb, ws, excel_path, row, "Done")
                        done_count += 1
                    else:
                        self.log(f"PDF failed for {udyam_number}. Marked Failed so the next run retries it.")
                        self._update_excel(wb, ws, excel_path, row, "Failed")
                        failed_count += 1
                    resolved = True

                    # Step H: Click Back to return to the verify form
                    self._click_back(driver)
                    break

                if not resolved and not self.stop_requested:
                    self.log(f"Giving up on {udyam_number} after {max_retries} attempts.")
                    self._update_excel(wb, ws, excel_path, row, "Failed")
                    failed_count += 1

                self._update_counts(total, done_count, failed_count, skipped_count)

            # ---- Save report Excel ----
            if report_data:
                self._save_report_safely(report_data, save_folder)
                report_saved = True

            # ---- Summary ----
            self.log("=" * 50)
            self.log("COMPLETE")
            self.log(f"  Saved   : {done_count}")
            self.log(f"  Failed  : {failed_count}")
            self.log(f"  Skipped : {skipped_count}")
            self.log(f"  PDFs at : {save_folder}")
            self.log("=" * 50)

        except Exception as e:
            self.run_failed = True
            self.log(f"ERROR: {self._short_error(e)}")
            # Rows already marked Done must still reach the report
            if report_data and not report_saved:
                self._save_report_safely(report_data, save_folder)
        finally:
            if wb:
                try:
                    wb.save(excel_path)
                except Exception:
                    self.log("Could not save input Excel. Close it if open.")
            if driver:
                try:
                    driver.quit()
                    self.log("Browser closed.")
                except Exception:
                    pass
                self.driver = None
            self._finish()

    # ==================================================================
    # BROWSER SETUP
    # ==================================================================

    def _setup_chrome(self):
        opts = Options()
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-popup-blocking")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")

        opts.add_experimental_option("prefs", {
            "plugins.always_open_pdf_externally": True
        })
        try:
            driver = webdriver.Chrome(options=opts)
        except Exception as e:
            self.log(f"Chrome failed: {e}")
            raise

        driver.set_page_load_timeout(60)
        driver.implicitly_wait(0)

        # Chrome 146 sometimes opens with a blank data: page.
        # Navigate to a simple page first to get past any startup issues.
        try:
            driver.get("about:blank")
            time.sleep(1)
            # Close any extra tabs that Chrome opened on startup
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass

        return driver

    # ==================================================================
    # NAVIGATION
    # ==================================================================


    def _navigate_to_verify_page_via_menu(self, driver):
        """
        Goes to the home page, hovers the Print/Verify menu, then clicks
        Verify Udyam Registration. Uses flexible locators because the site
        text may vary slightly across renders.
        """
        try:
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception:
            self.log("Browser windows issue.")
            raise

        for attempt in range(1, 4):
            self.log(f"Navigating to verify page (attempt {attempt})...")
            try:
                driver.get(HOME_URL)
                wait = WebDriverWait(driver, 30)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

                menu = wait.until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//a[contains(normalize-space(.), 'Print') and contains(normalize-space(.), 'Verify')]"
                    ))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", menu)
                time.sleep(0.3)

                hovered = False
                try:
                    ActionChains(driver).move_to_element(menu).pause(1).perform()
                    hovered = True
                except Exception as hover_err:
                    self.log(f"ActionChains hover failed: {hover_err}")

                if not hovered:
                    driver.execute_script("""
                        var el = arguments[0];
                        ['mouseover', 'mouseenter', 'mousemove'].forEach(function(evt) {
                            el.dispatchEvent(new MouseEvent(evt, {
                                view: window,
                                bubbles: true,
                                cancelable: true
                            }));
                        });
                    """, menu)
                    time.sleep(0.8)

                link = wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//a[contains(@href, 'Udyam_Verify.aspx') or contains(normalize-space(.), 'Verify Udyam Registration')]"
                    ))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                time.sleep(0.2)
                try:
                    link.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", link)

                wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")))
                wait.until(lambda d: self._find_captcha_field(d) is not None)
                self.on_verify_page = True
                self.log("On verification page.")
                return

            except Exception as e:
                self.log(f"Attempt {attempt} failed: {self._short_error(e)}")
                if attempt < 3:
                    time.sleep(2)
                    continue

                self.log("Trying direct URL as last resort...")
                try:
                    driver.get(VERIFY_URL)
                    wait = WebDriverWait(driver, 30)
                    wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")))
                    wait.until(lambda d: self._find_captcha_field(d) is not None)
                    self.on_verify_page = True
                    self.log("On verification page (direct URL).")
                    return
                except Exception as e2:
                    self.log(f"Direct URL also failed: {self._short_error(e2)}")
                    raise

    def _ensure_on_verify_page(self, driver):
        """
        Makes sure we are on the verify form page.
        If already there, does nothing. Otherwise navigates via menu.
        """
        try:
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")
            if self._find_captcha_field(driver) is not None:
                self.on_verify_page = True
                return
        except Exception:
            pass

        self._navigate_to_verify_page_via_menu(driver)

    @staticmethod
    def _short_error(error):
        """First line only: browser errors can carry a very long stack trace."""
        text = str(error).strip()
        return text.splitlines()[0] if text else type(error).__name__

    def _reset_verify_page(self, driver):
        """
        Opens a fresh verify page with a new captcha. This goes through the
        site menu because the portal sends direct links back to its home page.
        """
        self.log("Opening fresh verify page...")
        self._navigate_to_verify_page_via_menu(driver)
        time.sleep(0.4)

    def _try_reset_verify_page(self, driver):
        """A portal problem should cost one attempt, not end the whole run."""
        try:
            self._reset_verify_page(driver)
            return True
        except Exception as e:
            self.log(f"Could not reopen the verify page: {self._short_error(e)}")
            return False

    def _click_back(self, driver):
        """
        Clicks the Back button on the result page (or the print page)
        to return to the verify form. This is faster than reloading.
        """
        try:
            # Close any extra tabs first (if Print opened a new tab)
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])

            # Try clicking the Back button on the page
            # The Back button could be a link (<a>) or an input (<input>),
            # similar to how the Print button is an <input type="button">
            try:
                back_btn = None
                # Try by link text first
                try:
                    back_btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.LINK_TEXT, "Back"))
                    )
                except Exception:
                    pass
                # Try input/button with value "Back"
                if not back_btn:
                    for el in driver.find_elements(By.TAG_NAME, "input") + driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a"):
                        val = (el.get_attribute("value") or "").strip()
                        txt = (el.text or "").strip()
                        if val == "Back" or txt == "Back":
                            back_btn = el
                            break
                if back_btn:
                    back_btn.click()
                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        EC.element_to_be_clickable(
                            (By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")
                        )
                    )
                    self.log("Back to verify page.")
                    self.on_verify_page = True
                    return
            except Exception:
                pass

            # Fallback: use browser back
            driver.back()
            time.sleep(1)

            # Check if we landed on the verify page
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")
                    )
                )
                self.log("Back via browser navigation.")
                self.on_verify_page = True
                return
            except Exception:
                pass

            # If still not on verify page, might need one more back
            driver.back()
            time.sleep(1)
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")
                    )
                )
                self.log("Back via double browser back.")
                self.on_verify_page = True
                return
            except Exception:
                pass

            # Last resort: navigate fresh
            self.log("Could not go back. Navigating fresh.")
            self._navigate_to_verify_page_via_menu(driver)

        except Exception as e:
            self.log(f"Back error: {self._short_error(e)}. Navigating fresh.")
            self._navigate_to_verify_page_via_menu(driver)

    # ==================================================================
    # FORM INTERACTION
    # ==================================================================

    def _enter_udyam_number(self, driver, udyam_number):
        """Clicks the input field first, then clears and types the number."""
        wait = WebDriverWait(driver, PAGE_LOAD_TIMEOUT)
        try:
            field = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "ctl00_ContentPlaceHolder1_txtUdyamNo")
                )
            )
        except Exception:
            # Fallback search
            field = None
            for inp in driver.find_elements(By.TAG_NAME, "input"):
                ph = (inp.get_attribute("placeholder") or "").lower()
                iid = (inp.get_attribute("id") or "").lower()
                if "udyam" in ph or "udyam" in iid:
                    field = inp
                    break
            if not field:
                raise Exception("Udyam input field not found.")

        field.click()
        time.sleep(0.15)
        field.clear()
        field.send_keys(udyam_number)
        self.log(f"Entered: {udyam_number}")

    def _capture_captcha_image(self, driver):
        """Screenshots just the captcha image element from the page."""
        try:
            captcha_img = None

            # Strategy 1: known ID
            try:
                captcha_img = driver.find_element(
                    By.ID, "ctl00_ContentPlaceHolder1_imgCaptcha"
                )
            except Exception:
                pass

            # Strategy 2: any img with captcha in src/alt/id
            if not captcha_img:
                for img in driver.find_elements(By.TAG_NAME, "img"):
                    src = (img.get_attribute("src") or "").lower()
                    alt = (img.get_attribute("alt") or "").lower()
                    iid = (img.get_attribute("id") or "").lower()
                    if "captcha" in src or "captcha" in alt or "captcha" in iid:
                        captcha_img = img
                        break

            # Strategy 3: small image with typical captcha dimensions
            if not captcha_img:
                for img in driver.find_elements(By.TAG_NAME, "img"):
                    w = img.size.get("width", 0)
                    h = img.size.get("height", 0)
                    if 80 <= w <= 300 and 25 <= h <= 100:
                        captcha_img = img
                        break

            if captcha_img:
                return captcha_img.screenshot_as_png
            else:
                self.log("Captcha image element not found.")
                return None
        except Exception as e:
            self.log(f"Captcha capture error: {e}")
            return None


    def _find_captcha_field(self, driver):
        """Return the visible captcha textbox element, or None."""
        for by, value in [
            (By.ID, "ctl00_ContentPlaceHolder1_txtCaptcha"),
            (By.NAME, "ctl00$ContentPlaceHolder1$txtCaptcha"),
        ]:
            try:
                el = driver.find_element(by, value)
                if el.is_displayed() and el.is_enabled():
                    return el
            except Exception:
                pass

        for inp in driver.find_elements(By.TAG_NAME, "input"):
            typ = (inp.get_attribute("type") or "").lower()
            if typ in ["hidden", "submit", "button", "radio", "checkbox"]:
                continue

            meta = " ".join([
                inp.get_attribute("id") or "",
                inp.get_attribute("name") or "",
                inp.get_attribute("placeholder") or "",
                inp.get_attribute("aria-label") or "",
                inp.get_attribute("class") or "",
            ]).lower()

            if "txtudyamno" in meta:
                continue

            if any(k in meta for k in ["captcha", "verification", "verify code", "security code", "code"]):
                if inp.is_displayed() and inp.is_enabled():
                    return inp

        try:
            el = driver.find_element(
                By.XPATH,
                "(//img[contains(translate(@id,'CAPTCHA','captcha'),'captcha') or contains(translate(@src,'CAPTCHA','captcha'),'captcha') or contains(translate(@alt,'CAPTCHA','captcha'),'captcha')])[1]/following::input[not(@type='hidden') and not(contains(@id,'txtUdyamNo')) and not(contains(@name,'txtUdyamNo'))][1]"
            )
            if el.is_displayed() and el.is_enabled():
                return el
        except Exception:
            pass

        return None


    def _enter_captcha_in_browser(self, driver, captcha_text):
        """Finds the captcha field reliably and types the captcha."""
        try:
            wait = WebDriverWait(driver, 10)
            captcha_field = wait.until(lambda d: self._find_captcha_field(d))

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_field)
            time.sleep(0.2)

            try:
                captcha_field.click()
            except Exception:
                driver.execute_script("arguments[0].click();", captcha_field)

            time.sleep(0.15)

            try:
                captcha_field.clear()
            except Exception:
                pass

            driver.execute_script("arguments[0].value='';", captcha_field)
            captcha_field.send_keys(captcha_text)
            return True

        except Exception as e:
            self.log(f"Captcha input field not found or not ready: {e}")
            return False



    def _click_verify(self, driver):
        """Clicks the Verify button and waits briefly for page transition."""
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btnVerify"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.2)
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)

            self._wait_for_verify_outcome(driver, timeout=15)
            return True

        except Exception:
            try:
                for el in driver.find_elements(By.TAG_NAME, "input") + driver.find_elements(By.TAG_NAME, "button"):
                    val = (el.get_attribute("value") or "").lower()
                    iid = (el.get_attribute("id") or "").lower()
                    name = (el.get_attribute("name") or "").lower()
                    if "verify" in val or "btnverify" in iid or "btnverify" in name:
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        self._wait_for_verify_outcome(driver, timeout=15)
                        return True
            except Exception as e:
                self.log(f"Verify click error: {e}")
            return False

    def _wait_for_verify_outcome(self, driver, timeout=15):
        """
        Gives the portal time to either redirect to the result page
        or return to the verify form after a failed submission.
        """
        end_time = time.time() + timeout
        time.sleep(1)

        while time.time() < end_time:
            if self._is_result_page(driver) or self._wrong_captcha_shown(driver):
                return True
            time.sleep(0.5)

        return False

    def _wrong_captcha_shown(self, driver):
        """
        True once the portal has rejected the code. It empties the code box at
        that moment, which also rules out a message left from an earlier try.
        """
        try:
            return driver.execute_script("""
                var body = document.body ? document.body.innerText.toLowerCase() : '';
                var box = document.getElementById('ctl00_ContentPlaceHolder1_txtCaptcha');
                return body.indexOf('incorrect verification') !== -1 && !!box && box.value === '';
            """) is True
        except Exception:
            return False


    def _is_result_page(self, driver):
        """Checks if we have landed on the result detail page."""
        try:
            page = driver.page_source.lower()
            url = driver.current_url.lower()

            if "printudyamapplication" in url:
                return True
            if "verify udyam registration detail" in page:
                return True
            if "name of enterprise" in page and "udyam_verify" not in url:
                return True
            return False
        except Exception:
            return False

    # ==================================================================
    # DATA EXTRACTION
    # ==================================================================

    def _extract_all_data(self, driver):
        """
        Extracts enterprise name, major activity, and classification table.
        
        The classification table ALWAYS has exactly 4 columns:
            Column 0: SNo.
            Column 1: Classification Year (e.g. 2025-26)
            Column 2: Enterprise Type (Micro / Small / Medium)
            Column 3: Classification Date
        
        Previous versions tried to be clever by searching for year patterns
        within each row. That caused the wrong cells to be picked up.
        This version simply uses fixed column positions since the table
        structure is always the same.
        """
        result = {
            "name": "Unknown",
            "major_activity": "",
            "classifications": []
        }

        try:
            time.sleep(2)

            extracted = driver.execute_script("""
                var data = { name: '', major_activity: '', classifications: [] };

                // ---- Name and Major Activity ----
                var allCells = document.querySelectorAll('td');
                for (var i = 0; i < allCells.length; i++) {
                    var cellLower = allCells[i].innerText.trim().toLowerCase();
                    if (cellLower.indexOf('name of enterprise') !== -1 && i + 1 < allCells.length) {
                        data.name = allCells[i + 1].innerText.trim();
                    }
                    if (cellLower === 'major activity' && i + 1 < allCells.length) {
                        var activity = allCells[i + 1].innerText.trim();
                        var bi = activity.indexOf('[');
                        if (bi !== -1) activity = activity.substring(0, bi).trim();
                        data.major_activity = activity;
                    }
                }

                // ---- Classification Table ----
                // Find the table, then use FIXED column positions:
                // index 0 = SNo, index 1 = Year, index 2 = Type, index 3 = Date
                var tables = document.querySelectorAll('table');
                for (var t = 0; t < tables.length; t++) {
                    if (tables[t].innerText.toLowerCase().indexOf('classification year') === -1) continue;

                    var rows = tables[t].querySelectorAll('tr');
                    var headerPassed = false;

                    for (var r = 0; r < rows.length; r++) {
                        var rowText = rows[r].innerText.toLowerCase();

                        // Detect and skip the header row
                        if (rowText.indexOf('classification year') !== -1) {
                            headerPassed = true;
                            continue;
                        }
                        if (!headerPassed) continue;

                        // Get ONLY direct <td> children (not from nested tables)
                        var tds = rows[r].querySelectorAll(':scope > td');
                        // If :scope doesn't work, fall back to regular td
                        if (tds.length === 0) tds = rows[r].querySelectorAll('td');

                        if (tds.length >= 3) {
                            // Fixed positions: Year is col 1 (or 0 if no SNo), Type is next
                            var yearCol = (tds.length >= 4) ? 1 : 0;
                            var typeCol = (tds.length >= 4) ? 2 : 1;

                            var yearVal = tds[yearCol].innerText.trim();
                            var typeVal = tds[typeCol].innerText.trim();

                            // Only accept if type is one of the valid values
                            var typeLower = typeVal.toLowerCase();
                            if ((typeLower === 'micro' || typeLower === 'small' || typeLower === 'medium')
                                && /\\d{4}-\\d{2}/.test(yearVal)) {
                                data.classifications.push({
                                    year: yearVal,
                                    type: typeVal
                                });
                            }
                        }
                    }
                    if (headerPassed) break;
                }

                return data;
            """)

            if extracted:
                result["name"] = extracted.get("name", "Unknown") or "Unknown"
                result["major_activity"] = extracted.get("major_activity", "")
                if extracted.get("classifications"):
                    result["classifications"] = extracted["classifications"]

            # Fallback: page source regex if JS found nothing
            if not result["classifications"]:
                self.log("JS found no classifications. Trying page source...")
                try:
                    page_src = driver.page_source
                    matches = re.findall(
                        r'(\d{4}-\d{2})\s*</td>\s*<td[^>]*>\s*(Micro|Small|Medium)',
                        page_src, re.IGNORECASE
                    )
                    for year, etype in matches:
                        result["classifications"].append({"year": year, "type": etype})
                    if matches:
                        self.log(f"Page source found {len(matches)} classification(s).")
                except Exception as e:
                    self.log(f"Page source fallback error: {e}")

            # Fallback: body text scan
            if not result["classifications"]:
                self.log("Trying body text scan...")
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
                    for i, line in enumerate(lines):
                        if re.match(r'^\d{4}-\d{2}$', line):
                            for j in range(i + 1, min(i + 3, len(lines))):
                                if lines[j].lower() in ["micro", "small", "medium"]:
                                    result["classifications"].append({
                                        "year": line, "type": lines[j]
                                    })
                                    break
                except Exception as e:
                    self.log(f"Text scan error: {e}")

            self.log(f"Data: {result['name']} | {result['major_activity']} | "
                     + ", ".join(f"{c['year']}={c['type']}" for c in result["classifications"]))

        except Exception as e:
            self.log(f"Extraction error: {e}")

        return result

    # ==================================================================
    # PRINT + PDF SAVE
    # ==================================================================

    def _save_page_as_pdf(self, driver, save_folder, enterprise_name, udyam_number):
        """
        Saves the certificate content as PDF by replicating what the
        Print button does, but under our control.

        The website's printDiv('divPrint') function works like this:
            1. Saves original body HTML
            2. Replaces body with just divPrint content
            3. Calls window.print() (which opens the dialog)
            4. Restores original body

        Problem: this all happens in one synchronous JS call, so by the
        time Python gets control back, the page is already restored.

        Our approach:
            1. Use JS to save the original body HTML
            2. Use JS to replace body with divPrint content (same as the site)
            3. Use Page.printToPDF to capture the reformatted page
            4. Use JS to restore the original body

        This gives us the exact same print output as the website's own
        Print button, because we are using the same divPrint content.
        The page's own CSS handles the print-friendly layout, so no
        manual scaling is needed.
        """
        clean_name = re.sub(r'[\\/:*?"<>|]', '', enterprise_name.replace("/", "_")).strip()
        filename = f"{clean_name} - {udyam_number}.pdf"
        filepath = os.path.join(save_folder, filename)

        saved = False
        try:
            # Step 1: Save original body and replace with divPrint content
            # We do this in JavaScript running inside the browser.
            driver.execute_script("""
                // Save the original page content
                window.__originalBody = document.body.innerHTML;

                // Get the print-ready content
                var printContent = document.getElementById('divPrint');
                if (printContent) {
                    document.body.innerHTML = printContent.innerHTML;
                }
            """)

            # Brief pause to let the browser re-render with new content
            time.sleep(0.5)

            # Step 2: Capture the reformatted page as PDF
            result = driver.execute_cdp_cmd("Page.printToPDF", {
                "landscape": False,
                "displayHeaderFooter": False,
                "printBackground": True,
                "preferCSSPageSize": False,
                "paperWidth": 8.27,
                "paperHeight": 11.69,
                "marginTop": 0.2,
                "marginBottom": 0.2,
                "marginLeft": 0.2,
                "marginRight": 0.2
            })

            pdf_data = base64.b64decode(result["data"])
            if not pdf_data:
                raise ValueError("Chrome returned an empty PDF.")
            with open(filepath, "wb") as f:
                f.write(pdf_data)

            saved = os.path.getsize(filepath) > 0
            if saved:
                self.log(f"PDF saved: {filename}")

        except Exception as e:
            self.log(f"PDF save error: {e}")

        # Step 3: Restore the original page content, even if the PDF failed
        try:
            driver.execute_script("""
                if (window.__originalBody) {
                    document.body.innerHTML = window.__originalBody;
                    delete window.__originalBody;
                }
            """)
            time.sleep(0.5)
        except Exception as e:
            self.log(f"Page restore error: {e}")

        return saved

    # ==================================================================
    # REPORT EXCEL
    # ==================================================================

    def _save_report_safely(self, report_data, save_folder):
        """Saves the report and logs the result without stopping the run."""
        try:
            report_path = os.path.join(save_folder, "UDYAM_Report.xlsx")
            saved_path = self._save_report_excel(report_data, report_path)
            self.log(f"Report saved: {saved_path}")
        except Exception as e:
            self.log(f"Report save error: {e}")

    def _merge_with_existing_report(self, report_data, filepath):
        """
        Keeps rows from earlier runs. A number processed again in this run
        replaces its older row.
        """
        keys = ["udyam_number", "name", "major_activity",
                "year_1", "type_1", "year_2", "type_2"]
        merged = {}
        if os.path.exists(filepath):
            try:
                existing = load_workbook(filepath, read_only=True)
                for values in existing.active.iter_rows(min_row=2, max_col=7, values_only=True):
                    if values[0]:
                        merged[str(values[0]).strip()] = {
                            key: (value if value is not None else "")
                            for key, value in zip(keys, values)
                        }
                existing.close()
            except Exception as e:
                self.log(f"Could not read the earlier report: {e}")
        for data in report_data:
            merged[data["udyam_number"]] = data
        return list(merged.values())

    def _save_report_excel(self, report_data, filepath):
        """
        Creates a formatted Excel report with ONE row per Udyam number.
        Columns: Udyam Number | Enterprise Name | Major Activity |
                 Classification Year 1 | Enterprise Type 1 |
                 Classification Year 2 | Enterprise Type 2
        """
        from openpyxl import Workbook

        report_data = self._merge_with_existing_report(report_data, filepath)

        rwb = Workbook()
        rws = rwb.active
        rws.title = "UDYAM Report"

        # Styles
        header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
        header_fill = PatternFill(start_color="1a56db", end_color="1a56db", fill_type="solid")
        data_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )
        center = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        # Headers
        headers = [
            ("Udyam Number", 28),
            ("Enterprise Name", 35),
            ("Major Activity", 16),
            ("Classification Year 1", 22),
            ("Enterprise Type 1", 18),
            ("Classification Year 2", 22),
            ("Enterprise Type 2", 18)
        ]

        for col, (name, width) in enumerate(headers, 1):
            cell = rws.cell(row=1, column=col, value=name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border
            rws.column_dimensions[cell.column_letter].width = width

        # Data rows
        for r, data in enumerate(report_data, 2):
            values = [
                data["udyam_number"],
                data["name"],
                data["major_activity"],
                data["year_1"],
                data["type_1"],
                data["year_2"],
                data["type_2"]
            ]
            for col, val in enumerate(values, 1):
                cell = rws.cell(row=r, column=col, value=val)
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = left_align if col <= 3 else center

        # Freeze header row
        rws.freeze_panes = "A2"

        try:
            rwb.save(filepath)
        except PermissionError:
            base, ext = os.path.splitext(filepath)
            filepath = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            self.log("Report is open in Excel, so saving a new copy instead.")
            rwb.save(filepath)
        self.log(f"Report: {len(report_data)} row(s) written.")
        return filepath

    # ==================================================================
    # UTILITY
    # ==================================================================

    def _update_excel(self, wb, ws, path, row, status):
        ws.cell(row=row, column=2, value=status)
        try:
            wb.save(path)
        except PermissionError:
            self.log("Close input Excel to save status.")


# ---- ENTRY POINT ----
if __name__ == "__main__":
    if sys.platform == "win32":
        # Lets Windows show this app's own icon on the taskbar
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RameshRajni.MSMECertiFetch")
    app = UdyamVerifierApp()
    app.mainloop()
