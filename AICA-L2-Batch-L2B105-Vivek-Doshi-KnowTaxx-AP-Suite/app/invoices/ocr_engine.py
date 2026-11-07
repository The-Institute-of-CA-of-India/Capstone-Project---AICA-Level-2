"""Offline invoice OCR: Tesseract wrapper plus Indian GST field extraction.

Needs no application context, so it can be tested on its own. If Tesseract is missing,
extraction returns an empty result with a warning and the invoice can be keyed in by hand.
"""
import io
import os
import re
import shutil
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from ..utils import gstin_check_digit, valid_gstin

MAX_PDF_PAGES = 10
PDF_DPI = 250

GSTIN_RE = re.compile(r"\b[0-9OISBZ]{2}[A-Z0-9]{5}[0-9OISBZ]{4}[A-Z0-9][0-9A-Z][Z2][0-9A-Z]\b")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AMOUNT_RE = re.compile(r"(?<![\w.,/-])(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{1,2}|\d+)(?![\d%]|\s*%|[/-]\d)")
INVOICE_NO_RE = re.compile(
    r"(?:invoice|inv|bill|tax\s*invoice)\s*(?:no\b|number\b|num\b|#)\s*\.?\s*[:#.\-]*\s*([A-Z0-9][A-Z0-9/\-_.]{1,40})", re.I)
DATE_TOKEN = (r"(\d{1,2}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{2,4}"
              r"|\d{1,2}[\s\-./]*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s\-./,]*\d{2,4})")
DATE_LABELLED_RE = re.compile(r"(?:invoice|inv|bill)?\s*(?:date|dated|dt)\b\.?\s*[:\-]?\s*" + DATE_TOKEN, re.I)
DUE_DATE_RE = re.compile(r"(?:due\s*date|payment\s*due|pay\s*by)\s*[:\-]?\s*" + DATE_TOKEN, re.I)
ANY_DATE_RE = re.compile(DATE_TOKEN, re.I)
HSN_RE = re.compile(r"(?:hsn|sac)[^\n\d]{0,20}\b(\d{4,8})\b", re.I)
LINE_ITEM_RE = re.compile(
    r"^(?:\d{1,3}[.)]?\s+)?(?P<desc>[A-Za-z][^\n]*?)\s+(?P<hsn>\d{4,8})\s+(?P<qty>\d+(?:\.\d+)?)\s*(?:[A-Za-z]{2,4}\s+)?"
    r"(?P<rate>[\d,]+(?:\.\d{1,2})?)\s+(?P<taxable>[\d,]+(?:\.\d{1,2})?)", re.M)

TOTAL_LABELS = ("grand total", "invoice total", "total invoice value", "total amount payable", "amount payable",
                "net amount", "net payable", "total amount", "total value", "total")
TAXABLE_LABELS = ("taxable value", "taxable amount", "taxable amt", "sub total", "subtotal", "sub-total",
                  "assessable value", "total before tax")
VENDOR_LABELS = re.compile(r"^\s*(?:from|seller|supplier|sold\s*by|billed\s*by|vendor)\s*[:\-]\s*(.+)$", re.I | re.M)
NON_VENDOR_LINE = re.compile(
    r"(tax\s*invoice|^invoice\b|original|duplicate|recipient|bill\s*of\s*supply|receipt|gstin|^page\b|^date\b|credit\s*memo|proforma)", re.I)

# Rule-based auto-categorisation: first keyword hit wins.
CATEGORY_RULES = (
    ("Rent", ("rent", "lease", "premises", "licence fee")),
    ("Professional Fees", ("professional fee", "consultancy", "consulting", "legal fee", "audit fee", "retainer", "advisory")),
    ("Contractor Services", ("contractor", "labour charge", "job work", "manpower", "housekeeping", "security service")),
    ("Telecom & Internet", ("broadband", "internet", "telephone", "mobile bill", "airtel", "jio", "leased line")),
    ("IT & Software", ("software", "licence", "license", "subscription", "laptop", "hosting", "saas", "cloud", "amc")),
    ("Utilities", ("electricity", "power bill", "water charges", "diesel", "kwh", "units consumed")),
    ("Freight & Logistics", ("freight", "transport", "courier", "logistics", "cartage", "lorry")),
    ("Travel & Conveyance", ("hotel", "flight", "air ticket", "cab", "taxi", "conveyance", "travel", "train")),
    ("Marketing", ("advertis", "marketing", "promotion", "printing of brochures", "hoarding", "digital campaign")),
    ("Repairs & Maintenance", ("repair", "maintenance", "servicing", "spare")),
    ("Commission", ("commission", "brokerage")),
    ("Office Supplies", ("stationery", "printer", "toner", "paper", "office supplies", "pantry", "receipt")),
    ("Raw Materials", ("raw material", "steel", "copper", "aluminium", "chemical", "polymer", "resin", "packing material", "packaging")),
)
# Suggested TDS by nature of payment. Section labels use the familiar 1961 Act numbers; from
# 1 April 2026 these are consolidated in s.393 of the Income-tax Act 2025. The accountant confirms.
TDS_RULES = (
    ("194J", Decimal("10"), ("professional fee", "consultancy", "consulting", "legal fee", "audit fee", "retainer", "advisory")),
    ("194I", Decimal("10"), ("rent", "lease", "premises")),
    ("194H", Decimal("2"), ("commission", "brokerage")),
    ("194C", Decimal("2"), ("contractor", "job work", "labour charge", "manpower", "housekeeping", "security service", "freight", "transport")),
)


def find_tesseract():
    bundled_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    candidates = [os.environ.get("TESSERACT_CMD"), str(bundled_root / "tools" / "tesseract" / "tesseract.exe"),
                  shutil.which("tesseract"), r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                  os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")]
    return next((c for c in candidates if c and os.path.exists(c)), None)


def tesseract_status():
    path = find_tesseract()
    return {"available": bool(path), "path": path}


def load_pages(filepath, max_pages=MAX_PDF_PAGES):
    """Return the document's pages as PIL images (pdf2image if Poppler exists, else pypdfium2)."""
    path = Path(filepath)
    if path.suffix.lower() != ".pdf":
        image = Image.open(path)
        return [ImageOps.exif_transpose(image).convert("RGB")]
    try:
        from pdf2image import convert_from_path
        return convert_from_path(str(path), dpi=PDF_DPI, first_page=1, last_page=max_pages)
    except Exception:  # Poppler not installed or could not read this file: use the bundled renderer
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        try:
            return [pdf[i].render(scale=PDF_DPI / 72).to_pil().convert("RGB") for i in range(min(len(pdf), max_pages))]
        finally:
            pdf.close()


def preprocess(image):
    """Grayscale, upscale small captures, denoise, stretch contrast."""
    gray = ImageOps.grayscale(image)
    if gray.width < 1500:
        factor = 1500 / gray.width
        gray = gray.resize((1500, int(gray.height * factor)), Image.LANCZOS)
    gray = gray.filter(ImageFilter.MedianFilter(3))
    return ImageOps.autocontrast(gray, cutoff=1)


def threshold(gray):
    return gray.point(lambda p: 255 if p > 170 else 0)


def run_tesseract(images):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = find_tesseract()
    texts = []
    for image in images:
        gray = preprocess(image)
        text = pytesseract.image_to_string(gray, config="--oem 3 --psm 6 -c preserve_interword_spaces=1")
        # A faint or shadowed photo reads better after hard thresholding
        if len(text.strip()) < 40:
            text = pytesseract.image_to_string(threshold(gray), config="--oem 3 --psm 6")
        texts.append(text)
    return "\n\f\n".join(texts)


def parse_amount(token):
    try:
        return Decimal(token.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def parse_date(token):
    if not token:
        return None
    cleaned = re.sub(r"\s+", " ", token.strip()).replace(",", " ")
    numeric = re.sub(r"\s*([/\-.])\s*", r"\1", cleaned)
    formats = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y")
    for fmt in formats:
        try:
            return _plausible(datetime.strptime(numeric, fmt).date())
        except ValueError:
            pass
    words = re.sub(r"[\-./]", " ", cleaned)
    words = re.sub(r"(\d)([A-Za-z])", r"\1 \2", words)
    words = re.sub(r"([A-Za-z])(\d)", r"\1 \2", words)
    words = re.sub(r"\s+", " ", words).strip().replace("Sept", "Sep").replace("sept", "sep")
    for fmt in ("%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y"):
        try:
            return _plausible(datetime.strptime(words, fmt).date())
        except ValueError:
            pass
    return None


def _plausible(value):
    return value if 2000 <= value.year <= date.today().year + 1 else None


def repair_gstin(token):
    """Fix common OCR confusions position by position, then test the check digit."""
    token = token.upper()
    if valid_gstin(token):
        return token, True
    to_digit = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"})
    to_alpha = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"})
    chars = list(token)
    for i in (0, 1, 7, 8, 9, 10):
        chars[i] = chars[i].translate(to_digit)
    for i in (2, 3, 4, 5, 6, 11):
        chars[i] = chars[i].translate(to_alpha)
    chars[13] = "Z"
    fixed = "".join(chars)
    if valid_gstin(fixed):
        return fixed, True
    if re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", fixed):
        # The last character is the check digit and the one most often misread.
        corrected = fixed[:14] + gstin_check_digit(fixed[:14])
        return corrected, False
    return None, False


def extract_gstin(text, exclude=None):
    """Pick the seller's GSTIN: skip the buyer's (own GSTIN, or labelled bill-to / recipient)."""
    candidates = []
    lines = text.splitlines()
    for number, line in enumerate(lines):
        for match in GSTIN_RE.finditer(line.upper().replace(" ", "")):
            gstin, valid = repair_gstin(match.group())
            # Compare without the check digit: that is the character OCR most often misreads
            if not gstin or (exclude and gstin[:14] == exclude[:14]):
                continue
            context = " ".join(lines[max(0, number - 3):number + 1]).lower()
            is_buyer = bool(re.search(r"bill(ed)?\s*to|ship(ped)?\s*to|buyer|recipient|customer|consignee", context))
            candidates.append((is_buyer, not valid, number, gstin, valid))
    if not candidates:
        return None, False
    candidates.sort(key=lambda c: c[:3])
    if candidates[0][0]:  # only the buyer's GSTIN is on the page: a blank is safer than the wrong party
        return None, False
    return candidates[0][3], candidates[0][4]


def _amounts_on(line):
    return [a for a in (parse_amount(m) for m in AMOUNT_RE.findall(line)) if a is not None]


def _amount_for_labels(lines, labels):
    """Last amount on the last line carrying the highest-priority label found."""
    for label in labels:
        pattern = re.compile(r"(?<![a-z])" + re.escape(label) + r"(?![a-z])", re.I)
        for line in reversed(lines):
            match = pattern.search(line)
            if match:
                amounts = _amounts_on(line[match.end():])
                if amounts:
                    return amounts[-1], label
    return None, None


def _tax_amount(lines, label):
    """Tax amount from a summary line. Scans bottom-up so summary rows beat line-item rows."""
    pattern = re.compile(r"(?<![a-z])" + label + r"(?![a-z])", re.I)
    for line in reversed(lines):
        match = pattern.search(line)
        if match:
            tail = re.sub(r"[@(]?\s*\d+(?:\.\d+)?\s*%\s*\)?", " ", line[match.end():])
            amounts = _amounts_on(tail)
            if amounts:
                return amounts[-1]
    return None


def extract_vendor_name(text):
    match = VENDOR_LABELS.search(text)
    if match and len(match.group(1).strip()) >= 3:
        return _clean_name(match.group(1)), 0.9
    for line in text.splitlines()[:12]:
        stripped = line.strip()
        if len(re.sub(r"[^A-Za-z]", "", stripped)) >= 4 and not NON_VENDOR_LINE.search(stripped):
            return _clean_name(stripped), 0.65
    return None, 0.0


def _clean_name(name):
    return re.sub(r"\s{2,}.*$", "", name.strip(" :-|_~.,"))[:200]


def _has_keyword(lowered, keywords):
    """Whole-word match from the keyword's start, so 'rent' never fires on 'current' or 'parent'.
    A trailing word may continue ('advertis' matches 'advertising', 'charges' matches 'charge')."""
    return any(re.search(r"(?<![a-z])" + re.escape(k) + (r"" if k == "advertis" else r"(?:s|es)?(?![a-z])"), lowered) for k in keywords)


def suggest_category(text):
    lowered = text.lower()
    for category, keywords in CATEGORY_RULES:
        if _has_keyword(lowered, keywords):
            return category
    return None


def suggest_tds(text):
    lowered = text.lower()
    for section, rate, keywords in TDS_RULES:
        if _has_keyword(lowered, keywords):
            return section, rate
    return None, None


def _nature_of_supply_text(text, line_items):
    """What was supplied. Line items are far better evidence than footers, addresses and bank details."""
    return " ".join(item["description"] for item in line_items) if line_items else text


def extract_line_items(text):
    items = []
    for match in LINE_ITEM_RE.finditer(text):
        description = match.group("desc").strip(" |")
        if re.search(r"\b(total|taxable|cgst|sgst|igst|description)\b", description, re.I):
            continue
        items.append({"description": description[:300], "hsn_sac": match.group("hsn"),
                      "quantity": parse_amount(match.group("qty")), "unit_price": parse_amount(match.group("rate")),
                      "taxable_amount": parse_amount(match.group("taxable"))})
    return items


def parse_invoice_text(text, exclude_gstin=None):
    """Turn raw OCR text into structured fields, per-field confidence and warnings."""
    lines = [line for line in text.splitlines() if line.strip()]
    conf, warnings = {}, []

    gstin, gstin_ok = extract_gstin(text, exclude=exclude_gstin)
    conf["gstin"] = 1.0 if gstin_ok else (0.55 if gstin else 0.0)
    if gstin and not gstin_ok:
        warnings.append("GSTIN check digit did not match what was read; please compare it with the document.")

    pan_match = PAN_RE.search(text.upper())
    pan = gstin[2:12] if gstin else (pan_match.group() if pan_match else None)

    number_match = INVOICE_NO_RE.search(text)
    invoice_number = number_match.group(1).strip(" .-") if number_match else None
    if invoice_number and invoice_number.lower() in ("date", "dated", "dt"):
        invoice_number = None
    conf["invoice_number"] = 0.9 if invoice_number else 0.0

    date_match = DATE_LABELLED_RE.search(re.sub(r"due\s*date[^\n]*", "", text, flags=re.I))
    invoice_date = parse_date(date_match.group(1)) if date_match else None
    conf["invoice_date"] = 0.9 if invoice_date else 0.0
    if not invoice_date:
        loose = ANY_DATE_RE.search(text)
        invoice_date = parse_date(loose.group(1)) if loose else None
        conf["invoice_date"] = 0.55 if invoice_date else 0.0
    due_match = DUE_DATE_RE.search(text)
    due_date = parse_date(due_match.group(1)) if due_match else None

    total, total_label = _amount_for_labels(lines, TOTAL_LABELS)
    taxable, _ = _amount_for_labels(lines, TAXABLE_LABELS)
    cgst, sgst, igst = (_tax_amount(lines, tax) for tax in ("cgst", "sgst|utgst", "igst"))
    conf["total_amount"] = 0.0 if total is None else (0.75 if total_label != "total" else 0.6)
    conf["taxable_amount"] = 0.7 if taxable is not None else 0.0
    for name, value in (("cgst", cgst), ("sgst", sgst), ("igst", igst)):
        conf[name] = 0.75 if value is not None else 0.0

    # Arithmetic validation: taxable + taxes should equal total
    taxes = sum((v for v in (cgst, sgst, igst) if v is not None), Decimal("0"))
    if total is None and taxable is not None:
        total = taxable + taxes
        conf["total_amount"] = 0.55
        warnings.append("Total was not found; calculated it as taxable value plus taxes.")
    if taxable is None and total is not None and taxes:
        taxable = total - taxes
        conf["taxable_amount"] = 0.55
        warnings.append("Taxable value was not found; calculated it as total minus taxes.")
    arithmetic_ok = None
    if total is not None and taxable is not None:
        # Round-off of up to one rupee is normal on Indian invoices
        arithmetic_ok = abs(taxable + taxes - total) <= Decimal("1.00")
        if arithmetic_ok:
            conf["total_amount"] = conf["taxable_amount"] = 1.0
            for name, value in (("cgst", cgst), ("sgst", sgst), ("igst", igst)):
                if value is not None:
                    conf[name] = 1.0
        else:
            warnings.append(f"Arithmetic check failed: taxable {taxable} + taxes {taxes} does not equal total {total}.")
            conf["total_amount"] = min(conf["total_amount"], 0.45)
    # An invoice is either intra-state (CGST + SGST) or inter-state (IGST): the unused fields are not misses
    if igst is not None and cgst is None and sgst is None:
        conf["cgst"] = conf["sgst"] = 1.0
    elif cgst is not None and sgst is not None and igst is None:
        conf["igst"] = 1.0
    elif arithmetic_ok and not taxes:
        conf["cgst"] = conf["sgst"] = conf["igst"] = 0.8  # unregistered supplier or exempt supply

    vendor_name, conf["vendor_name"] = extract_vendor_name(text)
    hsn_match = HSN_RE.search(text)
    line_items = extract_line_items(text)
    hsn = hsn_match.group(1) if hsn_match else (line_items[0]["hsn_sac"] if line_items else None)
    supply_text = _nature_of_supply_text(text, line_items)
    tds_section, tds_rate = suggest_tds(supply_text)

    scored = ("vendor_name", "gstin", "invoice_number", "invoice_date", "total_amount", "taxable_amount", "cgst", "sgst", "igst")
    confidence = sum(conf.get(f, 0.0) for f in scored) / len(scored)

    return {
        "vendor_name": vendor_name, "gstin": gstin, "pan": pan, "invoice_number": invoice_number,
        "invoice_date": invoice_date, "due_date": due_date, "total_amount": total, "taxable_amount": taxable,
        "cgst": cgst, "sgst": sgst, "igst": igst, "hsn_sac": hsn, "line_items": line_items,
        "tds_applicable": bool(tds_section), "tds_section": tds_section, "tds_rate": tds_rate,
        "category": suggest_category(supply_text), "field_confidence": conf, "arithmetic_ok": arithmetic_ok,
        "confidence": round(confidence, 3), "warnings": warnings, "raw_text": text,
    }


def _empty_result(warning):
    result = parse_invoice_text("")
    result["warnings"] = [warning]
    return result


def extract_invoice_data(filepath, exclude_gstin=None, max_pages=MAX_PDF_PAGES):
    """Full pipeline: load, preprocess, OCR, parse, validate, score. Never raises for a bad document."""
    if not find_tesseract():
        return _empty_result("Tesseract OCR is not installed on the server, so fields must be entered by hand.")
    try:
        pages = load_pages(filepath, max_pages)
        text = run_tesseract(pages)
    except Exception as exc:  # corrupt image, unreadable PDF, Tesseract crash
        return _empty_result(f"The document could not be read by OCR ({type(exc).__name__}).")
    return parse_invoice_text(text, exclude_gstin=exclude_gstin)


def render_preview(filepath, page=1, max_width=1400):
    """PNG of one page for the review screen. Returns (png_bytes, page_count)."""
    path = Path(filepath)
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        try:
            count = len(pdf)
            image = pdf[min(max(page, 1), count) - 1].render(scale=2).to_pil().convert("RGB")
        finally:
            pdf.close()
    else:
        count = 1
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, int(image.height * max_width / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue(), count


def name_similarity(a, b):
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()
