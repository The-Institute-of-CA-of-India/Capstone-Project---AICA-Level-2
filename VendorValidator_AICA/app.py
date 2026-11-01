"""
Vendor Registration & Validation App
AICA Level-2 Capstone Project  |  PAN - GSTIN - Udyam

Flow:  1. Load Excel  ->  2. Offline validation  ->  3. Online validation
       (PAN, then GST, then Udyam - one vendor at a time, captcha/OTP by user)
       ->  4. AI remarks + colour-coded Excel report
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import report
from ai_remarks import generate_remarks
from validators import FAIL, NA, PASS, WARN, run_offline

APP_TITLE = "Vendor Registration & Validation  |  PAN - GSTIN - Udyam"
VERSION = "1.0"

# medium-light palette (same as Excel report)
BG = "#F3F6FA"
BAND = "#9DC3E6"
SECTION = "#DDEBF7"
BTN = "#BDD7EE"
BTN_ACTIVE = "#9DC3E6"
ROW = {"APPROVED": "#C6E0B4", "REVIEW": "#FFE699", "REJECT / FIX": "#F4B183", "": "#FFFFFF"}

CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "VendorValidator")
CFG_FILE = os.path.join(CFG_DIR, "config.json")
DEFAULT_CFG = {"verifier_mobile": "", "ai_provider": "none", "ai_api_key": "", "ai_model": ""}


def load_cfg() -> dict:
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            return {**DEFAULT_CFG, **json.load(f)}
    except Exception:
        return dict(DEFAULT_CFG)


def save_cfg(cfg: dict) -> None:
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x760")
        self.minsize(1100, 640)
        self.configure(bg=BG)
        self.cfg = load_cfg()
        self.vendors = []
        self.input_path = tk.StringVar()
        self.q: queue.Queue = queue.Queue()
        self.ctl = None
        self.worker = None
        self.helper = None
        self._style()
        self._build()
        self.after(150, self._poll)

    # ------------------------------------------------------------ UI
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, font=("Segoe UI", 10))
        s.configure("Sec.TLabelframe", background=BG)
        s.configure("Sec.TLabelframe.Label", background=BG, foreground="#1F3864", font=("Segoe UI", 10, "bold"))
        s.configure("TCheckbutton", background=BG, font=("Segoe UI", 10))
        s.configure("Step.TButton", font=("Segoe UI", 10, "bold"), background=BTN, foreground="#1F3864",
                    padding=(12, 7), borderwidth=1)
        s.map("Step.TButton", background=[("active", BTN_ACTIVE), ("disabled", "#E7E6E6")])
        s.configure("Small.TButton", font=("Segoe UI", 9), background=SECTION, padding=(8, 4))
        s.map("Small.TButton", background=[("active", BTN)])
        s.configure("Treeview", font=("Segoe UI", 9), rowheight=24, fieldbackground="#FFFFFF")
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=BAND, foreground="#1F3864")

    def _build(self):
        band = tk.Frame(self, bg=BAND, height=54)
        band.pack(fill="x")
        tk.Label(band, text="Vendor Registration & Validation", bg=BAND, fg="#1F3864",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(band, text="Offline + Online checks of PAN | GSTIN | Udyam   •   AICA Level-2 Capstone",
                 bg=BAND, fg="#1F3864", font=("Segoe UI", 10)).pack(side="left", pady=14)
        ttk.Button(band, text="⚙ Settings", style="Small.TButton", command=self.settings).pack(side="right", padx=12)

        top = ttk.Frame(self, padding=(14, 10, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Vendor Excel file:").pack(side="left")
        ttk.Entry(top, textvariable=self.input_path, width=80).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(top, text="Browse…", style="Small.TButton", command=self.browse).pack(side="left", padx=3)
        ttk.Button(top, text="Create input template", style="Small.TButton",
                   command=self.make_template).pack(side="left", padx=3)

        steps = ttk.LabelFrame(self, text=" Steps ", style="Sec.TLabelframe", padding=(10, 6))
        steps.pack(fill="x", padx=14, pady=4)
        self.b_off = ttk.Button(steps, text="① Offline Validation", style="Step.TButton", command=self.offline)
        self.b_off.pack(side="left", padx=4)
        self.v_pan, self.v_gst, self.v_udy = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        self.b_on = ttk.Button(steps, text="② Online Validation", style="Step.TButton", command=self.online)
        self.b_on.pack(side="left", padx=(16, 4))
        for t, var in (("PAN", self.v_pan), ("GST", self.v_gst), ("Udyam", self.v_udy)):
            ttk.Checkbutton(steps, text=t, variable=var).pack(side="left", padx=3)
        self.b_rep = ttk.Button(steps, text="③ AI Remarks & Excel Report", style="Step.TButton", command=self.make_report)
        self.b_rep.pack(side="left", padx=(16, 4))
        self.counts = ttk.Label(steps, text="", font=("Segoe UI", 10, "bold"))
        self.counts.pack(side="right", padx=8)

        mid = ttk.Frame(self, padding=(14, 4))
        mid.pack(fill="both", expand=True)
        cols = ("code", "name", "pan", "gstin", "udyam", "pan_off", "gst_off", "udy_off",
                "pan_on", "gst_on", "udy_on", "overall")
        heads = ("Code", "Vendor Name", "PAN", "GSTIN", "Udyam No", "PAN Off", "GST Off", "Udyam Off",
                 "PAN On", "GST On", "Udyam On", "Overall")
        widths = (60, 210, 95, 135, 165, 70, 70, 75, 70, 70, 75, 95)
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("name", "udyam", "gstin") else "center")
        for k, col in ROW.items():
            self.tree.tag_configure(k or "none", background=col)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", self.show_detail)

        bottom = ttk.LabelFrame(self, text=" Activity log ", style="Sec.TLabelframe", padding=6)
        bottom.pack(fill="both", padx=14, pady=(4, 12))
        self.log_box = tk.Text(bottom, height=8, bg="#FFFFFF", fg="#262626", font=("Consolas", 9),
                               relief="flat", wrap="word")
        self.log_box.pack(fill="both", expand=True)
        legend = ttk.Frame(self, padding=(14, 0, 14, 8))
        legend.pack(fill="x")
        for t, c in (("Approved / Pass", ROW["APPROVED"]), ("Review / Warning", ROW["REVIEW"]),
                     ("Reject / Fail", ROW["REJECT / FIX"])):
            tk.Label(legend, text=f"  {t}  ", bg=c, font=("Segoe UI", 9)).pack(side="left", padx=4)
        ttk.Label(legend, text="Double-click a row to see check-wise details.").pack(side="left", padx=12)
        self.log("Ready. Load the vendor Excel (or click 'Create input template'), then run step ①.")

    # ------------------------------------------------------------ helpers
    def log(self, msg):
        self.log_box.insert("end", f"{datetime.now():%H:%M:%S}  {msg}\n")
        self.log_box.see("end")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        short = {PASS: "✔ Pass", WARN: "! Warn", FAIL: "✖ Fail", NA: "– N/A", "": ""}
        for i, v in enumerate(self.vendors):
            ov = v.overall() if v.checks else ""
            self.tree.insert("", "end", iid=str(i), tags=(ov or "none",), values=(
                v.vendor_code, v.name, v.pan, v.gstin, v.udyam,
                short[v.status_of("PAN", "Offline")], short[v.status_of("GST", "Offline")],
                short[v.status_of("UDYAM", "Offline")], short[v.status_of("PAN", "Online")],
                short[v.status_of("GST", "Online")], short[v.status_of("UDYAM", "Online")], ov))
        if self.vendors and self.vendors[0].checks:
            c = {k: sum(1 for v in self.vendors if v.overall() == k) for k in ("APPROVED", "REVIEW", "REJECT / FIX")}
            self.counts.config(text=f"Approved {c['APPROVED']}   Review {c['REVIEW']}   Reject {c['REJECT / FIX']}")

    def ensure_loaded(self) -> bool:
        p = self.input_path.get().strip()
        if not p:
            messagebox.showinfo(APP_TITLE, "Please select the vendor Excel file first.")
            return False
        if not self.vendors or getattr(self, "_loaded", "") != p:
            try:
                self.vendors = report.read_input(p)
                self._loaded = p
                self.log(f"Loaded {len(self.vendors)} vendors from {os.path.basename(p)}")
            except Exception as e:
                messagebox.showerror(APP_TITLE, f"Could not read the Excel file:\n{e}")
                return False
        return True

    # ------------------------------------------------------------ actions
    def browse(self):
        p = filedialog.askopenfilename(title="Select vendor Excel", filetypes=[("Excel", "*.xlsx *.xlsm")])
        if p:
            self.input_path.set(p)
            self.vendors = []
            if self.ensure_loaded():
                self.refresh()

    def make_template(self):
        p = filedialog.asksaveasfilename(title="Save input template", defaultextension=".xlsx",
                                         initialfile="Vendor_Input_Template.xlsx", filetypes=[("Excel", "*.xlsx")])
        if p:
            report.create_template(p, sample=True)
            self.input_path.set(p)
            self.vendors = []
            self.ensure_loaded()
            self.refresh()
            self.log(f"Template with sample data saved: {p}")

    def offline(self):
        if not self.ensure_loaded():
            return
        run_offline(self.vendors)
        self.refresh()
        f = sum(1 for v in self.vendors for c in v.checks if c.stage == "Offline" and c.status == FAIL)
        w = sum(1 for v in self.vendors for c in v.checks if c.stage == "Offline" and c.status == WARN)
        self.log(f"Offline validation done: {f} failed checks, {w} warnings. "
                 "Records failing the offline format check are skipped online.")

    def online(self):
        if not self.ensure_loaded():
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Online validation is already running.")
            return
        if not any(v.checks for v in self.vendors):
            self.offline()
        depts = [d for d, var in (("PAN", self.v_pan), ("GST", self.v_gst), ("UDYAM", self.v_udy)) if var.get()]
        if not depts:
            return
        from online import Control
        self.ctl = Control(lambda kind, text: self.q.put((kind, text)))
        self.open_helper()
        self.worker = threading.Thread(target=self._online_worker, args=(depts,), daemon=True)
        self.worker.start()

    def _online_worker(self, depts):
        from online import PortalBlocked, PortalBrowser, apply_online_checks, verify_manual
        br = PortalBrowser(self.ctl)
        manual = {"PAN"}            # e-Filing portal blocks automated browsers -> operator confirmation
        try:
            for dept in depts:
                key = {"PAN": "pan", "GST": "gstin", "UDYAM": "udyam"}[dept]
                todo = [v for v in self.vendors if getattr(v, key)]
                self.q.put(("log", f"===== {dept} online validation: {len(todo)} vendor(s) ====="))
                for n, v in enumerate(todo, 1):
                    if self.ctl.stop.is_set():
                        break
                    if v.status_of(dept, "Offline") == FAIL:
                        apply_online_checks(v, dept, {"ok": None, "error": "skipped - failed offline format check"})
                        self.q.put(("log", f"{dept} {n}/{len(todo)} {v.vendor_code}: skipped (offline FAIL)"))
                        self.q.put(("refresh", ""))
                        continue
                    self.ctl.reset_record()
                    self.q.put(("progress", f"{dept}  {n} of {len(todo)}"))
                    try:
                        if dept in manual:
                            r = verify_manual(self.ctl, dept, v)
                        else:
                            if not br.page:
                                self.q.put(("log", "Starting browser (Microsoft Edge / Chrome)…"))
                                br.start()
                            self.q.put(("mode", "auto"))
                            r = br.verify_gst(v) if dept == "GST" else br.verify_udyam(v)
                    except PortalBlocked:
                        manual.add(dept)
                        self.q.put(("log", f"{dept} portal could not be opened automatically - switching to "
                                           "operator-confirmation mode (your normal browser)."))
                        self.ctl.reset_record()
                        r = verify_manual(self.ctl, dept, v)
                    except Exception as e:
                        r = {"ok": None, "error": f"browser error: {e}"}
                    if self.ctl.skip.is_set() and self.ctl.not_found:
                        r = {"ok": False, "error": "marked 'Not found / invalid' by user"}
                    apply_online_checks(v, dept, r)
                    msg = "found" if r.get("ok") else r.get("error")
                    self.q.put(("log", f"{dept} {n}/{len(todo)} {v.vendor_code} {v.name}: {msg}"))
                    self.q.put(("refresh", ""))
            self.q.put(("log", "Online validation finished. Click ③ to generate the report."))
        except Exception as e:
            self.q.put(("error", f"{e}\n\n{traceback.format_exc(limit=2)}"))
        finally:
            br.close()
            self.q.put(("done", ""))

    def open_helper(self):
        if self.helper and self.helper.winfo_exists():
            self.helper.destroy()
        h = tk.Toplevel(self)
        h.title("Online validation assistant")
        h.configure(bg=SECTION)
        h.attributes("-topmost", True)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h.geometry(f"430x250+{sw - 450}+{sh - 330}")
        self.h_prog = tk.Label(h, text="", bg=BAND, fg="#1F3864", font=("Segoe UI", 11, "bold"))
        self.h_prog.pack(fill="x")
        self.h_msg = tk.Label(h, text="Opening portal…", bg=SECTION, fg="#1F3864", justify="left",
                              wraplength=400, font=("Segoe UI", 10))
        self.h_msg.pack(fill="both", expand=True, padx=10, pady=8)
        self.h_info = tk.Label(h, text="", bg=SECTION, fg="#9C5700", wraplength=400, font=("Segoe UI", 9))
        self.h_info.pack(fill="x", padx=10)
        # buttons for operator-confirmation mode (PAN / blocked portals)
        self.h_manual = tk.Frame(h, bg=SECTION)
        tk.Button(self.h_manual, text="✔ VALID / Active", bg="#C6E0B4", relief="groove", width=15,
                  font=("Segoe UI", 9, "bold"), command=lambda: self._decide("valid")).pack(side="left", padx=4)
        tk.Button(self.h_manual, text="✖ INVALID / Not found", bg="#F4B183", relief="groove", width=19,
                  font=("Segoe UI", 9, "bold"), command=lambda: self._decide("invalid")).pack(side="left", padx=4)
        # buttons for automated mode
        self.h_auto = tk.Frame(h, bg=SECTION)
        tk.Button(self.h_auto, text="Not found / Invalid", bg="#F4B183", relief="groove", width=17,
                  command=lambda: self._skip(True)).pack(side="left", padx=4)
        bf = tk.Frame(h, bg=SECTION)
        bf.pack(side="bottom", pady=(2, 8))
        tk.Button(bf, text="Skip vendor", bg="#FFE699", relief="groove", width=12,
                  command=lambda: self._skip(False)).pack(side="left", padx=4)
        tk.Button(bf, text="Stop", bg="#D9D9D9", relief="groove", width=8,
                  command=self._stop).pack(side="left", padx=4)
        self.h_auto.pack(side="bottom", pady=2)
        h.geometry(f"470x330+{sw - 490}+{sh - 410}")
        h.protocol("WM_DELETE_WINDOW", self._stop)
        self.helper = h
        self._copied = ""

    def _set_mode(self, mode):
        for f in (self.h_manual, self.h_auto):
            f.pack_forget()
        (self.h_manual if mode == "manual" else self.h_auto).pack(side="bottom", pady=2)

    def _decide(self, decision):
        if not self.ctl:
            return
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            clip = ""
        self.ctl.clip = "" if clip.strip() == self._copied else clip      # ignore if only the copied number
        self.ctl.decision = decision

    def _skip(self, not_found):
        if self.ctl:
            self.ctl.not_found = not_found
            self.ctl.skip.set()

    def _stop(self):
        if self.ctl:
            self.ctl.stop.set()

    def _poll(self):
        try:
            while True:
                kind, text = self.q.get_nowait()
                if kind == "log":
                    self.log(text)
                elif kind == "refresh":
                    self.refresh()
                elif kind == "prompt" and self.helper:
                    self.h_msg.config(text=text)
                    self.h_info.config(text="")
                elif kind == "info" and self.helper:
                    self.h_info.config(text=text)
                elif kind == "clipboard":
                    self.clipboard_clear()
                    self.clipboard_append(text)
                    self._copied = text
                elif kind == "mode" and self.helper and self.helper.winfo_exists():
                    self._set_mode(text)
                elif kind == "progress" and self.helper:
                    self.h_prog.config(text=text)
                elif kind == "error":
                    messagebox.showerror(APP_TITLE, text)
                elif kind == "done":
                    if self.helper and self.helper.winfo_exists():
                        self.helper.destroy()
                    self.refresh()
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def make_report(self):
        if not self.ensure_loaded():
            return
        if not any(v.checks for v in self.vendors):
            self.offline()
        base = os.path.splitext(self.input_path.get())[0]
        out = f"{base}_Validation_Report_{datetime.now():%Y%m%d_%H%M}.xlsx"
        self.log("Generating remarks…")
        self.update_idletasks()
        remarks, summary, engine = generate_remarks(self.vendors, self.cfg, log=self.log)
        try:
            report.write_report(out, self.vendors, remarks, summary, engine)
        except PermissionError:
            messagebox.showerror(APP_TITLE, "Close the report in Excel and try again.")
            return
        self.log(f"Report saved: {out}  (remarks: {engine})")
        if messagebox.askyesno(APP_TITLE, f"Report saved:\n{out}\n\nOpen it now?"):
            try:
                os.startfile(out)              # Windows
            except Exception:
                pass

    def show_detail(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.vendors[int(sel[0])]
        w = tk.Toplevel(self)
        w.title(f"{v.vendor_code} - {v.name}")
        w.geometry("900x420")
        t = ttk.Treeview(w, columns=("stage", "dept", "check", "res", "msg"), show="headings")
        for c, h, wd in (("stage", "Stage", 70), ("dept", "Dept", 60), ("check", "Check", 190),
                         ("res", "Result", 90), ("msg", "Message", 470)):
            t.heading(c, text=h)
            t.column(c, width=wd)
        for k, col in ((PASS, ROW["APPROVED"]), (WARN, ROW["REVIEW"]), (FAIL, ROW["REJECT / FIX"]), (NA, "#E7E6E6")):
            t.tag_configure(k, background=col)
        for c in v.checks:
            t.insert("", "end", values=(c.stage, c.department, c.check, c.status, c.message), tags=(c.status,))
        t.pack(fill="both", expand=True)

    def settings(self):
        w = tk.Toplevel(self)
        w.title("Settings")
        w.configure(bg=BG)
        w.geometry("520x260")
        vars_ = {}
        rows = (("ai_provider", "AI provider (none / gemini / openai)"),
                ("ai_api_key", "AI API key (optional)"), ("ai_model", "AI model (blank = default)"))
        for i, (k, label) in enumerate(rows):
            ttk.Label(w, text=label).grid(row=i, column=0, sticky="w", padx=12, pady=8)
            var = tk.StringVar(value=self.cfg.get(k, ""))
            if k == "ai_provider":
                e = ttk.Combobox(w, textvariable=var, values=("none", "gemini", "openai"), state="readonly", width=34)
            else:
                e = ttk.Entry(w, textvariable=var, width=37, show="*" if k == "ai_api_key" else "")
            e.grid(row=i, column=1, padx=8)
            vars_[k] = var
        ttk.Label(w, text="PAN / GSTIN / Udyam numbers are masked before any text is sent to the AI.",
                  foreground="#7F6000").grid(row=5, column=0, columnspan=2, padx=12, pady=6, sticky="w")

        def ok():
            for k, var in vars_.items():
                self.cfg[k] = var.get().strip()
            save_cfg(self.cfg)
            w.destroy()
            self.log("Settings saved.")
        ttk.Button(w, text="Save", style="Step.TButton", command=ok).grid(row=6, column=1, sticky="e", padx=10)


def simple_input(parent, title, prompt):
    w = tk.Toplevel(parent)
    w.title(title)
    w.configure(bg=BG)
    w.grab_set()
    ttk.Label(w, text=prompt).pack(padx=14, pady=10)
    v = tk.StringVar()
    e = ttk.Entry(w, textvariable=v, width=30)
    e.pack(padx=14)
    e.focus()
    res = {"v": None}

    def ok(*_):
        res["v"] = v.get()
        w.destroy()
    ttk.Button(w, text="OK", style="Small.TButton", command=ok).pack(pady=10)
    w.bind("<Return>", ok)
    parent.wait_window(w)
    return res["v"]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--template":      # helper for build script
        report.create_template(sys.argv[2] if len(sys.argv) > 2 else "Vendor_Input_Template.xlsx")
        sys.exit(0)
    App().mainloop()
