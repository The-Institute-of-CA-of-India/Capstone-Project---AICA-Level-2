"""
online.py - ONLINE validation on the official government portals.

  * PAN   : Income Tax e-Filing  -> "Verify Your PAN"    (OTP to verifier's mobile)
  * GST   : GST Portal           -> "Search Taxpayer"    (captcha)
  * UDYAM : Udyam Registration   -> "Verify Udyam"       (captcha)

The app opens a real, visible browser window (Microsoft Edge / Chrome already
installed on Windows), PRE-FILLS the vendor's number, and then WAITS for the
user to type the captcha / OTP and press the portal's own button.
The result is read automatically from the page and the app moves to the next
vendor. Nothing is bypassed: captcha and OTP are always entered by the human.
"""
from __future__ import annotations

import re
import threading
import time

from validators import (FAIL, PASS, WARN, CheckResult, Vendor, msme_43bh_status,
                        name_similarity, parse_date)

URL_GST = "https://services.gst.gov.in/services/searchtp"
URL_UDYAM = "https://udyamregistration.gov.in/Udyam_Verify.aspx"
URL_PAN = "https://eportal.incometax.gov.in/iec/foservices/#/pre-login/knowYourAO"
MANUAL_URL = {"PAN": URL_PAN, "GST": URL_GST, "UDYAM": URL_UDYAM}
BLOCK_MARKERS = ("permission denied", "access denied", "request rejected")

WAIT_PER_RECORD_SEC = 300          # 5 minutes per vendor before auto-skip
WAIT_MANUAL_SEC = 600              # 10 minutes per vendor in operator-confirmation mode


class PortalBlocked(Exception):
    """Raised when a portal refuses automated browsers - app then switches to manual mode."""


class Control:
    """Shared between GUI thread and the online worker thread."""

    def __init__(self, notify):
        self.notify = notify                    # notify(kind, text) -> GUI
        self.skip = threading.Event()
        self.stop = threading.Event()
        self.decision = None                    # manual mode: "valid" / "invalid"
        self.clip = ""                          # manual mode: text copied from the result page
        self.not_found = False

    def reset_record(self):
        self.skip.clear()
        self.decision = None
        self.clip = ""
        self.not_found = False


# ---------------------------------------------------------------- browser
class PortalBrowser:
    def __init__(self, ctl: Control):
        self.ctl = ctl
        self.pw = None
        self.browser = None
        self.page = None

    def start(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        last = None
        for channel in ("msedge", "chrome", None):
            try:
                kw = {"headless": False, "args": ["--start-maximized"]}
                if channel:
                    kw["channel"] = channel
                self.browser = self.pw.chromium.launch(**kw)
                break
            except Exception as e:          # browser not installed - try next
                last = e
        if not self.browser:
            raise RuntimeError(f"Could not start Edge/Chrome. Install Microsoft Edge or Google Chrome. ({last})")
        ctx = self.browser.new_context(no_viewport=True)
        self.page = ctx.new_page()

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass

    # -------------------------------------------------- helpers
    def _first(self, selectors, timeout=8000):
        """Return the first visible locator among selectors (portal ids change over time)."""
        end = time.time() + timeout / 1000
        while time.time() < end:
            for s in selectors:
                loc = self.page.locator(s)
                try:
                    if loc.count() and loc.first.is_visible():
                        return loc.first
                except Exception:
                    pass
            self.page.wait_for_timeout(300)
        return None

    def _wait(self, done_fn, vendor_label):
        """Poll until done_fn() returns a result, user skips/stops, or timeout."""
        start = time.time()
        while True:
            if self.ctl.stop.is_set():
                return "STOP"
            if self.ctl.skip.is_set():
                return "SKIP"
            if time.time() - start > WAIT_PER_RECORD_SEC:
                return "TIMEOUT"
            try:
                r = done_fn()
                if r:
                    return r
            except Exception:
                pass
            try:
                self.page.wait_for_timeout(600)
            except Exception:
                return "STOP"           # browser closed by user

    def check_blocked(self):
        self.page.wait_for_timeout(1500)
        low = self.page_text().lower()[:400]
        if any(m in low for m in BLOCK_MARKERS):
            raise PortalBlocked(low[:80])

    def page_text(self) -> str:
        try:
            return self.page.inner_text("body", timeout=3000)
        except Exception:
            return ""

    def table_cells(self) -> list[list[str]]:
        try:
            return self.page.evaluate(
                """() => [...document.querySelectorAll('tr')].map(tr =>
                     [...tr.querySelectorAll('th,td')].map(c => c.innerText.replace(/\\s+/g,' ').trim()))""")
        except Exception:
            return []

    # ================================================== GST
    def verify_gst(self, v: Vendor) -> dict:
        captured = {}

        def on_response(resp):
            if "/api/search/taxpayerDetails" in resp.url:
                try:
                    captured["json"] = resp.json()
                except Exception:
                    pass

        self.page.on("response", on_response)
        try:
            self.page.goto(URL_GST, wait_until="domcontentloaded", timeout=60000)
            self.check_blocked()
            box =self._first(["#for_gstin", "input[name='for_gstin']"])
            if box:
                box.click()
                box.fill("")
                box.type(v.gstin, delay=40)            # keyup event makes the captcha appear
                cap = self._first(["#fo-captcha", "input[name='cap']"], timeout=5000)
                if cap:
                    cap.click()
            self.ctl.notify("prompt", f"GST | {v.vendor_code} {v.name}\nGSTIN {v.gstin} filled.\n"
                                      "Type the CAPTCHA in the browser and click SEARCH.")
            last_err = {"code": None}

            def done():
                j = captured.get("json")
                if j:
                    captured.pop("json", None)
                    if j.get("lgnm") or j.get("gstin"):
                        return {"ok": True, "data": j}
                    code = j.get("errorCode") or j.get("error", {}).get("error_cd")
                    if code and code != last_err["code"]:
                        last_err["code"] = code
                        self.ctl.notify("info", f"Portal replied {code} (wrong captcha or invalid GSTIN). "
                                                "Re-enter captcha, or press 'Skip / Not found'.")
                txt = self.page_text()
                if "Legal Name of Business" in txt and v.gstin in txt:
                    return {"ok": True, "data": parse_gst_text(txt)}
                for bad in ("does not exist", "Invalid GSTIN", "No records found"):
                    if bad.lower() in txt.lower():
                        return {"ok": False, "error": bad}
                return None

            r = self._wait(done, v.vendor_code)
        finally:
            self.page.remove_listener("response", on_response)
        return normalise_gst(r)

    # ================================================== UDYAM
    def open_udyam_verify(self):
        """Go directly to Udyam_Verify.aspx. The site may redirect a fresh session to the home page;
        then retry the direct URL (session cookie now set) or click the 'Verify Udyam' link."""
        on_verify = lambda: "udyam_verify" in self.page.url.lower()
        for attempt in range(3):
            self.page.goto(URL_UDYAM, wait_until="domcontentloaded", timeout=90000)
            self.check_blocked()
            self.page.wait_for_timeout(1200)
            if on_verify():
                return
            if attempt == 1:                       # try the menu link on the home page
                for sel in ("a[href*='Udyam_Verify' i]", "text=/Verify Udyam/i"):
                    try:
                        link = self.page.locator(sel).first
                        if link.count():
                            href = link.get_attribute("href") or ""
                            if href and "udyam_verify" in href.lower():
                                self.page.goto(href if href.startswith("http") else
                                               "https://udyamregistration.gov.in/" + href.lstrip("/"),
                                               wait_until="domcontentloaded", timeout=90000)
                            else:
                                link.click()
                                self.page.wait_for_load_state("domcontentloaded")
                            if on_verify():
                                return
                    except Exception:
                        pass
        raise PortalBlocked("Udyam verify page redirected to home page")

    def verify_udyam(self, v: Vendor) -> dict:
        self.open_udyam_verify()
        box = self._first(["#ctl00_ContentPlaceHolder1_txtUdyamNo", "input[id*='Udyam' i]",
                           "input[name*='Udyam' i]", "input[placeholder*='Udyam' i]"])
        if box:
            box.fill(v.udyam)
            cap = self._first(["input[id*='aptcha' i]", "input[name*='aptcha' i]",
                               "input[placeholder*='code' i]"], timeout=4000)
            if cap:
                cap.click()
        self.ctl.notify("prompt", f"UDYAM | {v.vendor_code} {v.name}\n{v.udyam} "
                                  f"{'filled' if box else '- please type it'}.\n"
                                  "Type the verification CODE in the browser and click VERIFY.")

        def done():
            txt = self.page_text()
            low = txt.lower()
            if "name of enterprise" in low and ("major activity" in low or "enterprise type" in low):
                return {"ok": True, "data": parse_udyam(txt, self.table_cells())}
            for bad in ("does not exist", "invalid udyam", "not found", "no record", "is not valid"):
                if bad in low:
                    return {"ok": False, "error": bad}
            return None

        return normalise(self._wait(done, v.vendor_code))

# ================================================== OPERATOR-CONFIRMATION MODE
def verify_manual(ctl: Control, dept: str, v: Vendor) -> dict:
    """Used for PAN (Know Your AO) and as fallback when a portal blocks automated browsers.

    The portal is opened in the user's NORMAL default browser (no automation).
    The number is copied to the clipboard; the operator pastes it, enters the
    mobile OTP / captcha, reads the result and confirms it in the assistant window.
    Optionally the operator copies the result page (Ctrl+A, Ctrl+C) so that
    the app can store name / jurisdiction details as audit evidence.
    """
    import webbrowser
    value = {"PAN": v.pan, "GST": v.gstin, "UDYAM": v.udyam}[dept]
    ctl.notify("clipboard", value)
    ctl.notify("mode", "manual")
    how = {"PAN": "Know Your AO: paste PAN (Ctrl+V), enter YOUR mobile no., Continue, enter OTP.",
           "GST": "Search Taxpayer: paste GSTIN (Ctrl+V), type captcha, Search.",
           "UDYAM": "Verify Udyam: paste Udyam No (Ctrl+V), type code, Verify."}[dept]
    ctl.notify("prompt", f"{dept} | {v.vendor_code} {v.name}\n{value}  (copied to clipboard)\n\n{how}\n"
                         "Optional: on the result page press Ctrl+A, Ctrl+C to save the details.\n"
                         "Then click VALID or INVALID below.")
    try:
        webbrowser.open(MANUAL_URL[dept], new=2)
    except Exception:
        pass
    start = time.time()
    while True:
        if ctl.stop.is_set():
            return normalise("STOP")
        if ctl.skip.is_set():
            return normalise("SKIP")
        if time.time() - start > WAIT_MANUAL_SEC:
            return normalise("TIMEOUT")
        if ctl.decision:
            break
        time.sleep(0.3)
    clip = ctl.clip or ""
    if ctl.decision == "invalid":
        return {"ok": False, "error": "marked INVALID by operator after portal check", "evidence": clip[:2000]}
    if dept == "PAN":
        data = parse_ao(clip)
    elif dept == "GST":
        data = normalise_gst({"ok": True, "data": parse_gst_text(clip)})["data"] if clip else {"status": "Active"}
    else:
        data = parse_udyam(clip, []) if clip else {}
    data["confirmed_by"] = "Operator (portal checked manually)"
    return {"ok": True, "data": data, "evidence": clip[:2000]}


# ---------------------------------------------------------------- parsers
def normalise(r) -> dict:
    if isinstance(r, dict):
        return r
    return {"ok": None, "error": {"SKIP": "Skipped by user", "TIMEOUT": "Timed out (5 min)",
                                  "STOP": "Stopped by user"}.get(r, str(r))}


def normalise_gst(r) -> dict:
    r = normalise(r)
    if r.get("ok") and "data" in r:
        j = r["data"]
        r["data"] = {
            "legal_name": j.get("lgnm", j.get("legal_name", "")),
            "trade_name": j.get("tradeNam", j.get("trade_name", "")),
            "status": j.get("sts", j.get("status", "")),
            "registration_date": j.get("rgdt", j.get("registration_date", "")),
            "cancellation_date": j.get("cxdt", j.get("cancellation_date", "")),
            "constitution": j.get("ctb", j.get("constitution", "")),
            "taxpayer_type": j.get("dty", j.get("taxpayer_type", "")),
            "address": (j.get("pradr") or {}).get("adr", j.get("address", "")) if isinstance(j.get("pradr"), dict)
            else j.get("address", ""),
            "nature_of_business": ", ".join(j.get("nba", []) or []) if isinstance(j.get("nba"), list) else "",
        }
    return r


def _after(label: str, txt: str) -> str:
    m = re.search(re.escape(label) + r"\s*:?\s*\n?\s*([^\n]+)", txt, re.I)
    return m.group(1).strip() if m else ""


def parse_gst_text(txt: str) -> dict:
    return {"lgnm": _after("Legal Name of Business", txt), "tradeNam": _after("Trade Name", txt),
            "rgdt": _after("Effective Date of registration", txt), "ctb": _after("Constitution of Business", txt),
            "sts": _after("GSTIN / UIN Status", txt) or _after("GSTIN/UIN Status", txt),
            "dty": _after("Taxpayer Type", txt), "pradr": {"adr": _after("Principal Place of Business", txt)}}


UDYAM_LABELS = {
    "name of enterprise": "enterprise_name", "organisation type": "organisation_type",
    "major activity": "major_activity", "date of incorporation": "date_of_incorporation",
    "date of commencement of production/business": "date_of_commencement",
    "date of udyam registration": "date_of_udyam_registration", "social category": "social_category",
    "type of enterprise": "enterprise_type",
}


def parse_udyam(txt: str, cells: list[list[str]]) -> dict:
    d: dict = {}
    # 1) label / value pairs from table cells
    for row in cells:
        for i, c in enumerate(row[:-1]):
            key = UDYAM_LABELS.get(c.lower().rstrip(" :"))
            if key and row[i + 1] and key not in d:
                d[key] = row[i + 1]
    # 2) fallback on plain text
    for label, key in UDYAM_LABELS.items():
        if key not in d:
            val = _after(label, txt)
            if val:
                d[key] = val
    # 3) enterprise-type history: "2026-27  Micro  22/04/2026"
    rows = re.findall(r"(\d{4}-\d{2,4})\s*\|?\s*(Micro|Small|Medium)\s*\|?\s*(\d{2}[/-]\d{2}[/-]\d{4})", txt, re.I)
    if not rows:
        for r in cells:
            j = " ".join(r)
            m = re.search(r"(\d{4}-\d{2,4}).*?(Micro|Small|Medium).*?(\d{2}[/-]\d{2}[/-]\d{4})", j, re.I)
            if m:
                rows.append(m.groups())
    seen, hist = set(), []
    for y, t, dt in rows:
        if (y, t, dt) not in seen:
            seen.add((y, t, dt))
            hist.append({"classification_year": y, "enterprise_type": t.title(), "classification_date": dt})
    hist.sort(key=lambda r: parse_date(r["classification_date"]) or parse_date("01/01/1900"))
    d["enterprise_types"] = hist
    if hist:
        d["enterprise_type"] = hist[-1]["enterprise_type"]
        d["classification_date"] = hist[-1]["classification_date"]
        d["classification_year"] = hist[-1]["classification_year"]
    # 4) NIC codes (2-digit) and activity
    nic2, acts = [], set()
    for r in cells:
        j = " ".join(r)
        m = re.match(r"^\s*\d+\s+(\d{2})\s*-", j) or re.match(r"^(\d{2})\s*-\s*[A-Za-z]", j)
        if m:
            nic2.append(m.group(1))
            for a in ("Manufacturing", "Services", "Trading"):
                if a.lower() in j.lower()[-40:]:
                    acts.add(a)
    d["nic_2digit"] = sorted(set(nic2))
    d["nic_activity"] = ", ".join(sorted(acts))
    return d


AO_LABELS = {
    "pan": "pan", "name": "name", "name of assessee": "name", "pan status": "pan_status", "status": "pan_status",
    "area code": "area_code", "ao type": "ao_type", "range code": "range_code", "ao number": "ao_number",
    "jurisdiction": "jurisdiction", "building name": "ao_building", "email id": "ao_email",
    "ao email id": "ao_email", "ao address": "ao_address",
}


def parse_ao(txt: str) -> dict:
    """Parse text copied from the e-Filing 'Know Your AO' result page."""
    d: dict = {}
    lines = [l.strip() for l in (txt or "").splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if ":" in line:                                   # "Label : value" on one line
            k, _, val = line.partition(":")
            key = AO_LABELS.get(k.strip(" *").lower())
            if key and val.strip() and key not in d:
                d[key] = val.strip()
                continue
        key = AO_LABELS.get(line.rstrip(" :*").lower())   # label on one line, value on next
        if key and i + 1 < len(lines) and key not in d and lines[i + 1].rstrip(" :*").lower() not in AO_LABELS:
            d[key] = lines[i + 1]
    low = (txt or "").lower()
    if "pan_status" not in d:
        m = re.search(r"\bis\s+(active|inactive|inoperative|deleted|deactivated)", low)
        if m:
            d["pan_status"] = m.group(1).title()
    if d.get("ao_type") or d.get("jurisdiction") or d.get("area_code"):
        d["ao_details"] = " / ".join(x for x in (d.get("area_code"), d.get("ao_type"), d.get("range_code"),
                                                   d.get("ao_number"), d.get("jurisdiction")) if x)
    return d


def parse_pan(txt: str, pan: str) -> dict:
    low = txt.lower()
    m = re.search(r"\bis\s+(active|inactive|deleted|deactivated|fake|marked as \w+)", low)
    status = m.group(1).title() if m else ("Active" if "details are matching" in low else "")
    match = "Matching" if "details are matching" in low or "is matching" in low else \
            ("Not matching" if "not matching" in low else "")
    lines = [l.strip() for l in txt.splitlines() if pan.lower() in l.lower() or "matching" in l.lower()]
    return {"pan_status": status, "name_dob_match": match, "portal_message": " | ".join(lines[:3])}


# ---------------------------------------------------------------- online checks
def apply_online_checks(v: Vendor, dept: str, r: dict) -> None:
    v.checks = [c for c in v.checks if not (c.stage == "Online" and c.department == dept)]
    v.online[dept] = r
    add = lambda fld, chk, st, msg: v.checks.append(CheckResult(dept, fld, chk, st, msg, "Online"))
    main_fld = {"PAN": "PAN", "GST": "GSTIN", "UDYAM": "Udyam No"}[dept]

    if r.get("ok") is None:
        add(main_fld, "Online verification", WARN, f"Not verified online: {r.get('error')}.")
        return
    if r.get("ok") is False:
        add(main_fld, "Found on portal", FAIL, f"Portal says: {r.get('error')}.")
        return
    d = r["data"]

    op = d.get("confirmed_by")
    if dept == "GST":
        st = (d.get("status") or "").strip()
        if op and not d.get("legal_name"):
            add("GSTIN", "GSTIN status", PASS, f"Confirmed valid by {op}.")
        elif st.lower() == "active":
            add("GSTIN", "GSTIN status", PASS, f"Active since {d.get('registration_date')}.")
        else:
            extra = f" w.e.f. {d['cancellation_date']}" if d.get("cancellation_date") else ""
            add("GSTIN", "GSTIN status", FAIL, f"GSTIN status is '{st}'{extra}. ITC not available on such invoices.")
        _name_check(v, add, d.get("legal_name"), "GST legal name", d.get("trade_name"))
        from validators import pincode
        p_in, p_gst = pincode(v.address), pincode(d.get("address", ""))
        if p_in and p_gst:
            add("Address", "Address vs GST principal place", PASS if p_in == p_gst else WARN,
                f"PIN code {'matches' if p_in == p_gst else 'differs'}: input {p_in}, GST portal {p_gst}.")
    elif dept == "PAN":
        st = d.get("pan_status", "")
        ao = f" Jurisdictional AO: {d['ao_details']}." if d.get("ao_details") else ""
        if st and st.lower() != "active":
            add("PAN", "PAN status", FAIL, f"PAN status on portal: {st}.{ao} Higher TDS u/s 206AA may apply.")
        elif st:
            add("PAN", "PAN status", PASS, f"PAN status: Active.{ao}")
        else:
            add("PAN", "PAN status", PASS, f"PAN found on Know Your AO and confirmed valid by operator.{ao}")
            d["pan_status"] = "Valid (operator confirmed)"
        if d.get("name") and "*" not in d["name"]:
            _name_check(v, add, d["name"], "Name as per PAN")
        mt = d.get("name_dob_match")
        if mt:
            add("Vendor Name", "Name & DOB as per PAN", PASS if mt == "Matching" else FAIL,
                f"Name / Date of Birth {mt.lower()} with PAN database.")
    elif dept == "UDYAM":
        add("Udyam No", "Udyam registration", PASS,
            f"Registered on {d.get('date_of_udyam_registration', '-')}." + (f" Confirmed by {op}." if op else ""))
        _name_check(v, add, d.get("enterprise_name"), "Udyam enterprise name")
        flag, reason = msme_43bh_status(d)
        d["sec_43bh"] = flag
        d["sec_43bh_reason"] = reason
        add("Udyam No", "43B(h) / 37(2)(g) applicability", PASS if flag != "Review" else WARN, f"{flag}: {reason}")


def _name_check(v, add, portal_name, label, alt=None):
    if not portal_name:
        return
    s = max(name_similarity(v.name, portal_name), name_similarity(v.name, alt or ""))
    if s >= 0.85:
        add("Vendor Name", f"{label} match", PASS, f"'{portal_name}' matches ({s:.0%}).")
    elif s >= 0.6:
        add("Vendor Name", f"{label} match", WARN, f"'{portal_name}' partly matches '{v.name}' ({s:.0%}).")
    else:
        add("Vendor Name", f"{label} match", FAIL, f"'{portal_name}' does not match '{v.name}' ({s:.0%}).")
