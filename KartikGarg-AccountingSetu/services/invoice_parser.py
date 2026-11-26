"""Local rule-based document understanding (no external AI).

Produces the same structured JSON as the AI provider, with per-field confidence:
  0.90  value read next to an explicit label
  0.55  heuristic (e.g. first header line as supplier name)
  0.60  derived arithmetically from other fields (always flagged for review)
  0.00  not found
Nothing is invented: missing values stay None and the document goes to NEEDS REVIEW.
"""
from __future__ import annotations

import re
from decimal import Decimal

from utils.helpers import D, ZERO, normalize_invoice_no, to_date
from utils.validators import parse_place_of_supply, validate_gstin

GSTIN_FIND = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
AMOUNT = r"(-?\(?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?\)?)"
DATE_PAT = (r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}|"
            r"\d{1,2}[\s\-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-,]+\d{2,4})")
INV_NO = re.compile(r"(?:invoice|inv|bill|document|credit\s*note|debit\s*note|voucher)\s*(?:no|number|num|#)\.?\s*[:\-]?\s*"
                    r"([A-Za-z0-9][A-Za-z0-9/\-]{0,30})", re.I)
INV_DATE = re.compile(r"(?:invoice|inv|bill|document|note|dated)?\s*date[d]?\s*[:\-]?\s*" + DATE_PAT, re.I)
CUSTOMER_MARKERS = re.compile(r"\b(bill(?:ed)?\s*to|buyer|customer|recipient|consignee|ship(?:ped)?\s*to|sold\s*to|party)\b", re.I)
SUPPLIER_MARKERS = re.compile(r"\b(supplier|seller|sold\s*by|from|vendor)\b", re.I)
HEADER_SKIP = re.compile(r"^(tax\s*invoice|invoice|original|duplicate|triplicate|bill of supply|credit note|debit note|"
                         r"for recipient|page \d+|gstin|phone|email|cin)\b", re.I)

AMOUNT_LABELS: dict[str, list[str]] = {
    "taxable_value": [r"total\s*taxable\s*(?:value|amount)", r"taxable\s*(?:value|amount|amt)", r"sub\s*-?\s*total",
                      r"assessable\s*value"],
    "cgst": [r"(?:total\s*)?cgst(?:\s*amount)?", r"central\s*tax"],
    "sgst": [r"(?:total\s*)?(?:sgst|utgst)(?:\s*amount)?", r"state\s*tax"],
    "igst": [r"(?:total\s*)?igst(?:\s*amount)?", r"integrated\s*tax"],
    "cess": [r"(?:total\s*)?cess(?:\s*amount)?"],
    "discount": [r"(?:less\s*:?\s*)?discount"],
    "round_off": [r"round(?:ing)?\s*-?\s*off", r"rounding"],
    "total": [r"grand\s*total", r"invoice\s*(?:total|value)", r"total\s*invoice\s*(?:value|amount)",
              r"total\s*amount\s*(?:payable|due)?", r"net\s*(?:amount|payable)", r"amount\s*payable",
              r"^\s*total\b(?!\s*(?:taxable|tax\b|cgst|sgst|igst|cess|qty|quantity|discount))"],
}


def _amounts_in(line: str) -> list[Decimal]:
    vals = []
    for m in re.finditer(AMOUNT, line):
        token = m.group(1)
        # ignore percentages and things glued to letters (HSN, invoice numbers)
        after = line[m.end():m.end() + 1]
        before = line[m.start() - 1:m.start()] if m.start() else ""
        if after == "%" or (before and before.isalpha()):
            continue
        d = D(token, None)
        if d is not None:
            vals.append(d)
    return vals


def _find_amount(lines: list[str], patterns: list[str]) -> tuple[Decimal | None, float]:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for i, line in enumerate(lines):
            m = rx.search(line)
            if not m:
                continue
            rest = line[m.end():]
            vals = _amounts_in(rest)
            # skip 'CGST @ 9%' rate token if an amount follows
            if vals:
                return vals[-1], 0.9
            if i + 1 < len(lines):  # value on next line (table layouts)
                nxt = _amounts_in(lines[i + 1])
                if len(nxt) == 1:
                    return nxt[0], 0.75
    return None, 0.0


def _value_after_marker(lines: list[str], marker: re.Pattern) -> str | None:
    for i, line in enumerate(lines):
        m = marker.search(line)
        if not m:
            continue
        rest = line[m.end():].strip(" :-\t")
        if rest and not GSTIN_FIND.search(rest.upper()) and len(rest) > 2 and not re.match(r"^(details|address)$", rest, re.I):
            return rest[:120]
        for j in range(i + 1, min(i + 4, len(lines))):
            cand = lines[j].strip()
            if cand and not GSTIN_FIND.search(cand.upper()) and not HEADER_SKIP.match(cand) and len(cand) > 2:
                return cand[:120]
    return None


def classify_text(text: str, filename: str = "", declared: str | None = None) -> tuple[str, float]:
    t = f"{text} {filename}".lower()
    if re.search(r"credit\s*note", t):
        return "credit_note", 0.9
    if re.search(r"debit\s*note", t):
        return "debit_note", 0.9
    if re.search(r"(statement of account|account statement|bank statement)", t) or (
            "opening balance" in t and "closing balance" in t) or ("withdrawal" in t and "deposit" in t):
        return "bank_statement", 0.85
    if re.search(r"(pay\s*slip|salary\s*(statement|register|slip)|payroll)", t):
        return "salary_statement", 0.85
    if re.search(r"(tax\s*invoice|invoice|bill of supply)", t):
        return "invoice", 0.85
    if re.search(r"(payment\s*receipt|receipt\s*(no|voucher)|received\s*with\s*thanks)", t):
        return "payment_receipt", 0.8
    if declared:
        return declared, 0.5
    return "other", 0.3


def parse_invoice_text(text: str, client_gstin: str | None = None) -> dict:
    """Return {'data': {...}, 'confidence': {...}} for a single invoice's text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    upper = text.upper()
    data: dict = {"items": []}
    conf: dict[str, float] = {}

    kind, _ = classify_text(text)
    data["doc_kind"] = kind if kind in ("invoice", "credit_note", "debit_note") else "invoice"

    # invoice number
    m = INV_NO.search(text)
    if m and not re.fullmatch(r"(date|dt|dated)", m.group(1), re.I):
        data["invoice_no"], conf["invoice_no"] = m.group(1).strip("/-"), 0.9
    else:
        data["invoice_no"], conf["invoice_no"] = None, 0.0
    # date
    d = None
    for m in INV_DATE.finditer(text):
        d = to_date(re.sub(r"\s+", " ", m.group(1)).replace(",", ""))
        if d:
            break
    data["invoice_date"] = d.isoformat() if d else None
    conf["invoice_date"] = 0.9 if d else 0.0

    # GSTINs and party roles
    found = []
    for m in GSTIN_FIND.finditer(upper):
        g = m.group(0)
        if g not in [x[0] for x in found]:
            found.append((g, m.start()))
    cust_pos = [m.start() for m in CUSTOMER_MARKERS.finditer(text)]
    supplier_gstin = customer_gstin = None
    for g, pos in found:
        # GSTIN within ~250 chars after a customer marker -> customer
        is_customer = any(0 <= pos - cp <= 250 for cp in cust_pos)
        line = next((ln for ln in lines if g in ln.upper()), "")
        if re.search(r"(buyer|customer|recipient|bill\s*to|consignee)", line, re.I):
            is_customer = True
        if re.search(r"(supplier|seller|our\s*gstin)", line, re.I):
            is_customer = False
        if is_customer and customer_gstin is None:
            customer_gstin = g
        elif not is_customer and supplier_gstin is None:
            supplier_gstin = g
        elif customer_gstin is None:
            customer_gstin = g
    for key, val in (("supplier_gstin", supplier_gstin), ("customer_gstin", customer_gstin)):
        data[key] = val
        conf[key] = (0.9 if validate_gstin(val)[0] else 0.4) if val else 0.0

    # names
    cust = _value_after_marker(lines, CUSTOMER_MARKERS)
    data["customer_name"], conf["customer_name"] = (cust, 0.75) if cust else (None, 0.0)
    sup = _value_after_marker(lines, re.compile(r"\b(supplier|seller|sold\s*by|vendor)\b\s*(?:name)?", re.I))
    if sup:
        data["supplier_name"], conf["supplier_name"] = sup, 0.75
    else:
        header = next((ln for ln in lines[:6] if not HEADER_SKIP.match(ln) and not GSTIN_FIND.search(ln.upper())
                       and not re.search(r"\d{5,}", ln)), None)
        data["supplier_name"], conf["supplier_name"] = (header[:120], 0.55) if header else (None, 0.0)

    # place of supply / reverse charge
    m = re.search(r"place\s*of\s*supply\s*[:\-]?\s*([^\n]+)", text, re.I)
    pos = parse_place_of_supply(m.group(1)) if m else None
    data["place_of_supply"], conf["place_of_supply"] = (pos, 0.9) if pos else (None, 0.0)
    m = re.search(r"reverse\s*charge(?:\s*applicable)?\s*[:\-]?\s*\(?\s*(yes|no|y|n)\b", text, re.I)
    data["reverse_charge"] = bool(m and m.group(1).lower().startswith("y"))
    conf["reverse_charge"] = 0.9 if m else 0.6
    m = re.search(r"(?:against|original|ref\.?)\s*invoice\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9/\-]+)", text, re.I)
    data["original_invoice_no"] = m.group(1) if m and data["doc_kind"] != "invoice" else None

    # amounts
    for field_name, pats in AMOUNT_LABELS.items():
        val, c = _find_amount(lines, pats)
        data[field_name] = str(val) if val is not None else None
        conf[field_name] = c
    for f in ("cgst", "sgst", "igst", "cess", "discount", "round_off"):
        if data[f] is None:
            data[f] = "0.00"
            conf[f] = 0.7 if f in ("cess", "discount", "round_off") else 0.6
    if data["round_off"] and D(data["round_off"]).copy_abs() > Decimal("5"):
        data["round_off"], conf["round_off"] = "0.00", 0.3  # implausible; likely misread

    taxes = D(data["cgst"]) + D(data["sgst"]) + D(data["igst"]) + D(data["cess"])
    if data["taxable_value"] is None and data["total"] is not None:
        data["taxable_value"] = str(D(data["total"]) - taxes - D(data["round_off"]))
        conf["taxable_value"] = 0.6
    if data["total"] is None and data["taxable_value"] is not None:
        data["total"] = str(D(data["taxable_value"]) + taxes + D(data["round_off"]))
        conf["total"] = 0.6
    if data["taxable_value"] is not None and data["total"] is not None:
        if D(data["taxable_value"]) + taxes + D(data["round_off"]) == D(data["total"]):
            for f in ("taxable_value", "total", "cgst", "sgst", "igst"):
                if conf.get(f, 0) >= 0.6 and not (f == "taxable_value" and conf[f] == 0.6):
                    conf[f] = max(conf[f], 0.95)

    # HSN / items
    hsns = re.findall(r"(?:hsn|sac)(?:\s*/\s*sac)?\s*(?:code)?\s*[:\-]?\s*(\d{4,8})", text, re.I)
    for ln in lines:
        m = re.match(r"^(?P<desc>[A-Za-z][A-Za-z0-9 .,&()'\-/]{2,60}?)\s+(?P<hsn>\d{4,8})\s+(?P<rest>.+)$", ln)
        if not m:
            continue
        nums = _amounts_in(m.group("rest"))
        if not nums:
            continue
        item = {"description": m.group("desc").strip(), "hsn_sac": m.group("hsn"), "taxable_value": str(nums[-1])}
        rate = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%", m.group("rest"))
        if rate:
            item["gst_rate"] = rate.group(1)
        if len(nums) >= 3:
            item["quantity"], item["unit_price"] = str(nums[0]), str(nums[1])
        data["items"].append(item)
        hsns.append(m.group("hsn"))
    data["hsn_codes"] = sorted(set(hsns))
    conf["items"] = 0.7 if data["items"] else 0.0
    return {"data": data, "confidence": conf}


def split_pages_into_invoices(pages: list[str]) -> list[tuple[int, int]]:
    """Detect invoice boundaries in a multi-page PDF. Returns 1-based inclusive page ranges."""
    if len(pages) <= 1:
        return [(1, max(1, len(pages)))]
    groups: list[list[int]] = []
    current_no: str | None = None
    for idx, text in enumerate(pages, start=1):
        m = INV_NO.search(text or "")
        no = normalize_invoice_no(m.group(1)) if m else None
        heading = bool(re.search(r"(tax\s*invoice|bill of supply|credit\s*note|debit\s*note)", text or "", re.I))
        continuation = bool(re.search(r"(continued|page\s*\d+\s*of\s*\d+)", text or "", re.I)) and not (no and no != current_no)
        if not groups:
            groups.append([idx])
            current_no = no
            continue
        if no and no != current_no and not continuation:
            groups.append([idx])
            current_no = no
        elif heading and no is None and current_no is not None and not continuation and len((text or "").strip()) > 200:
            groups.append([idx])  # new invoice whose number we could not read
            current_no = None
        else:
            groups[-1].append(idx)
    return [(g[0], g[-1]) for g in groups]


# ---------------------------------------------------------------- tabular registers
COLUMN_SYNONYMS = {
    "invoice_no": ["invoice no", "invoice number", "inv no", "bill no", "voucher no", "document no", "invoice_no", "inum"],
    "invoice_date": ["invoice date", "inv date", "bill date", "date", "invoice_date", "idt"],
    "party_name": ["party name", "customer name", "supplier name", "party", "customer", "supplier", "name", "trade name",
                   "particulars", "party_name"],
    "party_gstin": ["gstin", "gstin/uin", "party gstin", "customer gstin", "supplier gstin", "gst no", "ctin", "party_gstin"],
    "taxable_value": ["taxable value", "taxable amount", "taxable", "assessable value", "txval", "taxable_value"],
    "cgst": ["cgst", "cgst amount", "central tax", "camt"],
    "sgst": ["sgst", "sgst amount", "sgst/utgst", "state tax", "samt"],
    "igst": ["igst", "igst amount", "integrated tax", "iamt"],
    "cess": ["cess", "cess amount", "csamt"],
    "total": ["invoice value", "total", "invoice total", "total amount", "grand total", "val", "amount"],
    "place_of_supply": ["place of supply", "pos"],
    "reverse_charge": ["reverse charge", "rcm", "rchrg"],
    "hsn_sac": ["hsn", "hsn/sac", "sac", "hsn code"],
    "gst_rate": ["rate", "gst rate", "tax rate", "rt"],
    "doc_kind": ["type", "document type", "note type"],
}


def map_columns(columns: list[str]) -> dict[str, str]:
    norm = {c: re.sub(r"[^a-z0-9/ ]", " ", str(c).lower()).strip() for c in columns}
    norm = {c: " ".join(v.split()) for c, v in norm.items()}
    out: dict[str, str] = {}
    for field_name, syns in COLUMN_SYNONYMS.items():
        for syn in syns:
            hit = next((c for c, n in norm.items() if n == syn and c not in out.values()), None)
            if hit:
                out[field_name] = hit
                break
    return out


def parse_register_rows(df) -> list[dict]:
    cols = map_columns(list(df.columns))
    rows = []
    if "invoice_no" not in cols or ("total" not in cols and "taxable_value" not in cols):
        return rows
    for _, r in df.iterrows():
        get = lambda f: (str(r[cols[f]]).strip() if f in cols else None)  # noqa: E731
        if not get("invoice_no"):
            continue
        d = to_date(get("invoice_date"))
        kind_raw = (get("doc_kind") or "").lower()
        data = {
            "doc_kind": "credit_note" if "credit" in kind_raw else "debit_note" if "debit" in kind_raw else "invoice",
            "invoice_no": get("invoice_no"), "invoice_date": d.isoformat() if d else None,
            "party_name": get("party_name"), "party_gstin": (get("party_gstin") or "").upper() or None,
            "taxable_value": str(D(get("taxable_value"), None)) if get("taxable_value") else None,
            "cgst": str(D(get("cgst"))), "sgst": str(D(get("sgst"))), "igst": str(D(get("igst"))), "cess": str(D(get("cess"))),
            "discount": "0.00", "round_off": "0.00",
            "total": str(D(get("total"), None)) if get("total") else None,
            "place_of_supply": parse_place_of_supply(get("place_of_supply")) if get("place_of_supply") else None,
            "reverse_charge": (get("reverse_charge") or "").lower() in ("y", "yes", "true", "1"),
            "items": [{"hsn_sac": get("hsn_sac"), "gst_rate": get("gst_rate"),
                       "taxable_value": str(D(get("taxable_value"))) if get("taxable_value") else None}] if get("hsn_sac") else [],
        }
        if data["total"] is None and data["taxable_value"]:
            data["total"] = str(D(data["taxable_value"]) + D(data["cgst"]) + D(data["sgst"]) + D(data["igst"]) + D(data["cess"]))
        conf = {k: (0.95 if data.get(k) not in (None, "") else 0.0) for k in
                ("invoice_no", "invoice_date", "party_name", "party_gstin", "taxable_value", "total")}
        conf.update({k: 0.95 for k in ("cgst", "sgst", "igst", "cess", "round_off", "discount")})
        if data["party_gstin"]:
            conf["party_gstin"] = 0.95 if validate_gstin(data["party_gstin"])[0] else 0.4
        rows.append({"data": data, "confidence": conf})
    return rows


def looks_like_bank_table(columns: list[str]) -> bool:
    c = " ".join(str(x).lower() for x in columns)
    return ("balance" in c and any(k in c for k in ("debit", "withdrawal", "dr"))
            and any(k in c for k in ("credit", "deposit", "cr")))


ZERO_D = ZERO
