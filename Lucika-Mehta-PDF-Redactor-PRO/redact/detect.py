"""
Detectors for Indian tax, KYC and banking identifiers, names and addresses.

Everything here works on plain text. A page is represented as one string with
its visual rows separated by "\\n"; `boxes` (optional) gives the position of
each character, which some detectors use to follow an address down a column.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Check-digit validators
# --------------------------------------------------------------------------
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(num: str) -> bool:
    total, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    group: str
    pattern: re.Pattern | None = None   # None = procedural / visual detector
    target_group: int = 0
    validator: object = None
    default_on: bool = True


_NS = r"(?<![\d])(?<!\d[.,])"
_NE = r"(?![\d])(?![.,]\d)"
_H = r"[ \-]"           # separator allowed inside a number (never a line break)

_NAME_LABELS = (
    r"account\s*(?:holder\s*)?name|a/c\s*name|customer\s*name|holder\s*name|taxpayer\s*name|"
    r"assessee(?:'s)?\s*name|name\s*of\s*(?:the\s*)?(?:assessee|account\s*holder|customer|deductee|"
    r"employee|tax\s*payer|taxpayer|depositor|applicant|director|partner|proprietor|borrower|client)|name"
)
_STOP_AFTER_NAME = r"(?:PAN|A/c|Account|Customer|Branch|IFSC|Date|D\.?O\.?B|Mobile|Email|E-mail|Address|Phone|GSTIN|CIF)\b"

RULES: list[Rule] = [
    # ---------------- Tax / KYC ----------------
    Rule("GSTIN", "GSTIN", "tax",
         re.compile(r"\b\d{2}[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z][0-9A-Z]{2,4}\b")),
    Rule("PAN", "PAN", "tax", re.compile(r"\b[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z]\b")),
    Rule("TAN", "TAN", "tax", re.compile(r"\b[A-Z]{4}\d{5}[A-Z]\b")),
    Rule("AADHAAR", "Aadhaar", "tax",
         re.compile(_NS + r"[2-9]\d{3}" + _H + r"?\d{4}" + _H + r"?\d{4}" + _NE),
         validator=lambda s: verhoeff_ok(digits(s))),
    Rule("AADHAAR_VID", "Aadhaar VID", "tax",
         re.compile(r"(?i)\bVID\s*(?:No\.?|Number)?\s*[:\-]?\s*(\d{4}" + _H + r"?\d{4}" + _H + r"?\d{4}" + _H + r"?\d{4})"),
         target_group=1),
    Rule("DOB", "Date of birth (labelled)", "tax",
         re.compile(r"(?i)\b(?:date\s+of\s+birth|d\.?\s?o\.?\s?b\.?|birth\s+date|year\s+of\s+birth)\s*[:\-]?\s*"
                    r"(\d{1,2}[-/. ]\d{1,2}[-/. ]\d{2,4}|\d{1,2}[-/. ]?[A-Za-z]{3,9}[-/. ]?\d{2,4}|\d{4})"),
         target_group=1),
    Rule("CIN", "CIN", "tax", re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")),
    Rule("LLPIN", "LLPIN", "tax", re.compile(r"(?i)\bLLPIN\s*[:\-]?\s*([A-Z]{3}-\d{4})"), target_group=1),
    Rule("DIN_DIRECTOR", "Director DIN", "tax",
         re.compile(r"(?i)\b(?:DIN|DPIN)\s*(?:No\.?|Number)?\s*[:\-]?\s*(\d{8})(?!\d)"), target_group=1),
    Rule("PASSPORT", "Passport No.", "tax",
         re.compile(r"(?i)passport\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z][0-9]{7})\b"), target_group=1),
    Rule("VOTER_ID", "Voter ID (EPIC)", "tax",
         re.compile(r"(?i)\b(?:EPIC|Voter\s*ID)\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z]{3}\d{7})\b"), target_group=1),

    # ---------------- Banking ----------------
    Rule("ACCOUNT_CTX", "Account No. (labelled)", "bank",
         re.compile(r"(?i)\b(?:a/c|acct|account|a\.c\.)\s*(?:no\.?|number|num|#)?\s*[:\-.]?\s*"
                    r"([X\*\d]{2,}(?:[ \-][X\*\d]{2,}){0,4})(?![\d])(?![.,]\d)"), target_group=1),
    Rule("CARD", "Card number", "bank",
         re.compile(_NS + r"\d{4}" + _H + r"?\d{4}" + _H + r"?\d{4}" + _H + r"?\d{1,7}" + _NE),
         validator=lambda s: 13 <= len(digits(s)) <= 19 and luhn_ok(digits(s))),
    Rule("MASKED_NUM", "Masked number (XXXX1234)", "bank",
         re.compile(r"(?<![A-Za-z])[Xx\*]{4,}[Xx\* \-]*?\d{2,6}(?!\d)")),
    Rule("LONG_NUMBER", "Any 9-18 digit number (UTR, refs)", "bank", re.compile(_NS + r"\d{9,18}" + _NE)),
    Rule("IFSC", "IFSC", "bank", re.compile(r"\b[A-Z]{4}[0O][A-Z0-9]{6}\b")),
    Rule("MICR", "MICR (labelled)", "bank",
         re.compile(r"(?i)\bMICR\s*(?:Code|No\.?)?\s*[:\-]?\s*(\d{9})\b"), target_group=1),
    Rule("UPI", "UPI ID", "bank", re.compile(r"(?<![A-Za-z0-9._])(?:[A-Za-z0-9._]{2,64}(?:-\d{1,4})?@[A-Za-z][A-Za-z0-9]{0,31}\b(?!\.[A-Za-z])"
                                            r"|[A-Za-z0-9._]{3,64}(?:-\d{1,4})?@(?=[/\s|]|$))")),  # also cut short: 'name72@/HDFC'

    Rule("CUSTOMER_ID", "Customer / CIF ID (labelled)", "bank",
         re.compile(r"(?i)\b(?:customer\s*id|cust\s*id|cif\s*(?:no\.?|id)?|client\s*id|crn)\s*[:\-.]?\s*([A-Z0-9]{5,20})\b"),
         target_group=1),

    # ---------------- Names and addresses ----------------
    Rule("NAME_LABELLED", "Names next to a label (Account Name:, Name of Assessee:)", "names",
         re.compile(r"(?im)(?<![A-Za-z])(?:" + _NAME_LABELS + r")[ \t]*[:\-][ \t]*([A-Za-z][^\n]*?)"
                    r"(?=\s{3,}|\s*[,;]?\s*" + _STOP_AFTER_NAME + r"|\s*$)"),
         target_group=1),
    Rule("ADDRESS", "Addresses next to a label (Address:, Regd. Office:)", "names"),
    Rule("TO_BLOCK", "Addressee block in letters and notices (To, …)", "names"),
    Rule("COUNTERPARTY", "Counterparty names in UPI / NEFT / IMPS narrations", "names"),

    # ---------------- Contact ----------------
    Rule("MOBILE", "Mobile number", "contact",
         re.compile(r"(?<![\d])(?:\+91[\-\s]?|0)?[6-9]\d{4}[ \-]?\d{5}(?![\d])"), default_on=False),
    Rule("EMAIL", "E-mail address", "contact",
         re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), default_on=False),

    # ---------------- Images ----------------
    Rule("QR", "QR codes and barcodes", "visual"),
    Rule("PHOTO", "Photographs of people (ID cards)", "visual", default_on=False),
    Rule("SIGNATURE", "Signatures (near 'Signature' labels) - experimental", "visual", default_on=False),
]

# Internal sub-rules (reported separately, switched on by their parent)
_EXTRA = [
    Rule("TO_NAME", "Addressee name", "names"),
    Rule("TO_ADDR", "Addressee address", "names"),
    Rule("CUSTOM", "Client-specific word", "custom"),
    Rule("MANUAL", "Added in review", "custom"),
]
RULES_BY_KEY = {r.key: r for r in RULES + _EXTRA}

GROUP_LABELS = {
    "tax": "Tax / KYC identifiers",
    "bank": "Banking details",
    "names": "Names and addresses",
    "contact": "Contact details",
    "visual": "Images",
}

DEFAULT_RULES = {r.key for r in RULES if r.default_on}
VISUAL_RULES = {"QR", "PHOTO", "SIGNATURE"}
HEURISTIC_RULES = {"NAME_LABELLED", "ADDRESS", "TO_NAME", "TO_ADDR", "COUNTERPARTY"}


def rule_label(key: str) -> str:
    r = RULES_BY_KEY.get(key)
    return r.label if r else key


# --------------------------------------------------------------------------
# Document profiles
# --------------------------------------------------------------------------
PROFILE_LABELS = {
    "bank": "Bank statement",
    "notice": "IT notice / order",
    "kyc": "KYC document",
    "other": "Other",
}
# Adjustments applied on top of the user's selection
PROFILE_ADJUST = {
    "bank": {"add": set(), "remove": set()},
    # in notices and orders, long numbers are DINs, acknowledgement and demand
    # references that the analysis needs; counterparties do not occur
    "notice": {"add": set(), "remove": {"LONG_NUMBER", "COUNTERPARTY"}},
    "kyc": {"add": {"PHOTO", "SIGNATURE"}, "remove": set()},
    "other": {"add": set(), "remove": set()},
}


def effective_rules(selected: set, profile: str, mode: str) -> set:
    if mode == "asis":
        return set(selected)
    adj = PROFILE_ADJUST.get(profile, PROFILE_ADJUST["other"])
    return (set(selected) | adj["add"]) - adj["remove"]


_CLASSIFY = {
    "bank": [r"statement\s+of\s+account", r"account\s+statement", r"opening\s+balance", r"closing\s+balance",
             r"\bwithdrawal", r"\bnarration\b", r"value\s+date", r"\bbalance\b", r"\bchq\b", r"\bdeposits?\b",
             r"\bifsc\b", r"\bneft\b", r"\bupi\b"],
    "notice": [r"income[\s\-]*tax\s+department", r"\bitba/", r"assessment\s+year", r"\bsection\s+1(?:4[238]|56)",
               r"\b148a?\b", r"\b270a\b", r"\b271\b", r"\bnotice\b", r"\bassessment\s+order", r"\bfaceless\b",
               r"\bnfac\b", r"\bintimation\b", r"centrali[sz]ed\s+processing", r"\bdin\s*:", r"\bita,?\s*1961",
               r"income[\s\-]tax\s+act", r"\bappeal\b", r"\bassessee\b"],
    "kyc": [r"\baadhaa?r\b", r"unique\s+identification", r"permanent\s+account\s+number", r"date\s+of\s+birth",
            r"\bdob\b", r"\bpassport\b", r"election\s+commission", r"\benrol?ment\s+no", r"\bvid\b",
            r"\bcancelled\b", r"\bgovt\.?\s+of\s+india\b", r"\bfather'?s\s+name\b"],
}


def classify(text: str) -> str:
    t = text.lower()
    scores = {k: sum(1 for p in pats if re.search(p, t)) for k, pats in _CLASSIFY.items()}
    best = max(scores, key=scores.get)
    if scores[best] < 2:
        return "other"
    # a statement mentioning "notice" or a notice quoting a balance: compare margins
    return best


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
@dataclass
class Match:
    start: int
    end: int
    rule: str
    value: str


PROTECT_ITBA = re.compile(r"ITBA/[A-Z0-9()/\-]*\d{6,}(?:\(\d+\))?")

_LABEL_LINE = re.compile(r"^\s*[A-Za-z][A-Za-z ./()'&]{1,35}\s*:")
_DATE_START = re.compile(r"^\s*\d{1,2}[-/. ](?:\d{1,2}|[A-Za-z]{3})[-/. ]\d{2,4}")
_PIN = re.compile(r"\b[1-9]\d{2}\s?\d{3}\b|\bindia\b", re.I)
_SEGMENT = re.compile(r"(?:(?!\s{3})[^\n])+")
_NOT_ADDRESS = re.compile(r"(?i)(?:e-?mail|ip|branch|bank|web|website|delivery)\s*$")


def _line_spans(text: str) -> list[tuple[int, int]]:
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out


def _x0(boxes, start: int, end: int):
    if not boxes:
        return None
    for i in range(start, min(end, len(boxes))):
        if boxes[i] is not None:
            return boxes[i][0]
    return None


def _segments(text: str, ls: int, le: int) -> list[tuple[int, int]]:
    out = []
    for m in _SEGMENT.finditer(text, ls, le):
        s, e = m.start(), m.end()
        while s < e and text[s] == " ":
            s += 1
        while e > s and text[e - 1] in " ,":
            e -= 1
        if e > s:
            out.append((s, e))
    return out


def _follow_column(text, boxes, lines, li, anchor_x, max_lines, stop_words=None):
    """Collect continuation segments below line `li` that line up with anchor_x."""
    found = []
    for j in range(li + 1, min(li + 1 + max_lines, len(lines))):
        ls, le = lines[j]
        segs = _segments(text, ls, le)
        if not segs:
            break
        seg = segs[0]
        if anchor_x is not None and boxes:
            cand = [s for s in segs if (x := _x0(boxes, *s)) is not None and abs(x - anchor_x) <= 25]
            if not cand:
                break
            seg = cand[0]
        s_text = text[seg[0]:seg[1]]
        if _LABEL_LINE.match(s_text) or _DATE_START.match(s_text) or len(s_text) > 120:
            break
        if stop_words and stop_words.match(s_text):
            break
        found.append(seg)
        if _PIN.search(s_text):
            break
    return found


_ADDR_LABEL = re.compile(
    r"(?im)(?<![A-Za-z])((?:(?:registered|regd\.?|communication|correspondence|residential|permanent|"
    r"mailing|present|office)\s+)?address(?:\s+of\s+[A-Za-z ]{2,20}?)?)\s*[:\-]?[ \t]*")


def _addresses(text: str, boxes) -> list[Match]:
    out = []
    lines = _line_spans(text)
    for m in _ADDR_LABEL.finditer(text):
        li = next(i for i, (s, e) in enumerate(lines) if s <= m.start() <= e)
        ls, le = lines[li]
        if _NOT_ADDRESS.search(text[ls:m.start()]):
            continue
        # value on the same line, up to a column break
        rest = [(s, e) for s, e in _segments(text, m.end(), le)]
        anchor = None
        if rest and rest[0][0] - m.end() < 3:
            s, e = rest[0]
            if len(text[s:e]) >= 3:
                out.append(Match(s, e, "ADDRESS", text[s:e]))
                anchor = _x0(boxes, s, e)
        else:
            anchor = _x0(boxes, m.start(), m.end())
        for s, e in _follow_column(text, boxes, lines, li, anchor, 4):
            out.append(Match(s, e, "ADDRESS", text[s:e]))
    return out


_TO_LINE = re.compile(r"(?im)^[ \t]*To[ \t]*([,:])?[ \t]*(\S[^\n]*)?$")
_AUTHORITY = re.compile(r"(?i)^\s*(?:the\s+)?(?:learned\s+|ld\.?\s+)?(?:assessing|income[\s\-]tax|deputy|assistant|additional|"
                        r"joint|principal|chief|commissioner|ito\b|acit\b|dcit\b|addl|jcit\b|cit\b|pcit\b|ao\b|"
                        r"national\s+faceless|nfac|faceless|hon'?ble|registrar|bench|tribunal|branch\s+manager|manager|"
                        r"secretary|officer|authority|director\s+of\s+income)")
_TO_STOP = re.compile(r"(?i)^\s*(?:sir|madam|dear|sub(?:ject)?\b|ref(?:erence)?\b|kindly|please|pan\b|gstin\b|"
                      r"assessment|a\.?\s?y\b|notice|with\s+reference|whereas|in\s+this|date[d]?\b)")


def _to_block(text: str, boxes) -> list[Match]:
    out = []
    lines = _line_spans(text)
    for m in _TO_LINE.finditer(text):
        punct, rest = m.group(1), m.group(2)
        li = next(i for i, (s, e) in enumerate(lines) if s <= m.start() <= e)
        if rest:
            if not punct:
                continue                       # "TO TRANSFER-UPI…" in a narration
            s = m.start(2)
            stop = re.search(r",?\s*(?:PAN|GSTIN|Assessment|A\.?Y\.?)\b|\s{3,}", text[s:m.end()])
            e = s + (stop.start() if stop else len(rest))
            while e > s and text[e - 1] in " ,":
                e -= 1
            if _AUTHORITY.match(text[s:e]):
                continue
            if e - s >= 3:
                out.append(Match(s, e, "TO_NAME", text[s:e]))
            anchor = _x0(boxes, s, e)
            for s2, e2 in _follow_column(text, boxes, lines, li, anchor, 5, _TO_STOP):
                out.append(Match(s2, e2, "TO_ADDR", text[s2:e2]))
        else:
            anchor = _x0(boxes, m.start(), m.end())
            segs = _follow_column(text, boxes, lines, li, anchor, 6, _TO_STOP)
            if segs and _AUTHORITY.match(text[segs[0][0]:segs[0][1]]):
                continue
            for k, (s2, e2) in enumerate(segs):
                out.append(Match(s2, e2, "TO_NAME" if k == 0 else "TO_ADDR", text[s2:e2]))
    return out


_RAILS = re.compile(r"(?i)\b(?:UPI|NEFT|IMPS|RTGS|NACH|ACH|ECS|INB|TRF|TRANSFER|MOB|BY\s+CLG|CHQ|BIL|MMT)\b")
_CP_SEG = re.compile(r"(?:(?!\s{3})[^/\-:|\n])+")
_CP_STOP = set("""
UPI NEFT IMPS RTGS NACH ACH ECS INB TRF TRANSFER TO BY FROM DR CR P2A P2M P2P PAYMENT PAY PAID SENT RECEIVED RECD
REF REFUND REVERSAL SALARY SAL INT INTEREST CHQ CHEQUE CLG CLEARING CASH DEP DEPOSIT ATM WDL WITHDRAWAL POS ECOM
IB MB MOB MOBILE NET NETBANKING BANKING BANK OF INDIA THE AND NA NOTPROVIDED NOT PROVIDED NO REMARKS REMARK BILL
BILLPAY RENT LOAN EMI FUND FUNDS GST TAX TDS CHARGES CHARGE FEE FEES AUTOPAY SI MANDATE COLLECT REQUEST OTHERS
OTHER SELF OWN ACCOUNT AC LINKED PURCHASE SALE INVOICE TXN TRANSACTION CREDIT DEBIT REV RET RETURN OK YBL
STATE SBI SBIN HDFC HDFCBANK ICICI ICIC AXIS UTIB KOTAK KKBK YES YESB PNB PUNB BOB BARB CANARA CNRB UNION UBIN
IDFC IDFB INDUSIND INDB FEDERAL FDRL PAYTM PYTM PHONEPE GPAY GOOGLE BHIM AMAZON AIRTEL JIO RAZORPAY CRED
LIMITED LTD PVT PRIVATE QR VPA RRN UTR IFSC MICR CMS SWEEP FD RD OD CC TERM DEPOSITS MAINTENANCE MIN BAL
DATE DT VALUE TRAN NARRATION PARTICULARS DESCRIPTION DETAILS BALANCE CLOSING OPENING AMT AMOUNT WITHDRAWALS
DEPOSITS CREDITS DEBITS NUMBER NUM SNO SR SERIAL STATEMENT SUMMARY PAGE TOTAL INR RS SMS QTR QUARTERLY ANNUAL
JAN FEB MAR APR MAY JUN JUL AUG SEP SEPT OCT NOV DEC JANUARY FEBRUARY MARCH APRIL JUNE JULY AUGUST SEPTEMBER
OCTOBER NOVEMBER DECEMBER
MMT ONL BIL GIB MCA NEFTINW RTGSINW INET INETIMPS TRXN LIFE INSUR INSURANCE PREMI PREMIUM POLICY URGENT REMARKS
BANDHAN CANARA INDUSIND TJSB SARASWAT COSMOS ANDHRA BARODA UCO IDBI RBL DCB AU EQUITAS UJJIVAN JANATA SAHAKARI
COOP COOPERATIVE NSDL FINO DBS HSBC CITI CITIBANK SCB STANDARD CHARTERED DEUTSCHE KARNATAKA KARUR VYSYA SOUTH
INDIAN OVERSEAS CENTRAL MAHARASHTRA PUNJAB SIND NATIONAL JAMMU KASHMIR TAMILNAD MERCANTILE CATHOLIC SYRIAN
NAINITAL DHANLAXMI DHANLAKSHMI CITY LAKSHMI VILAS GRAMIN GRAMEEN NAGARIK URBAN PAYMENTS SMALL FINANCE APNA
ICICIBANK AXISBANK KOTAKBANK YESBANK IDFCFIRST FIRST INDIA
OLD NEW LATE FIRM OPEN CLOSE MONTH ADVANCE DUES DUE FOR
""".split())
# a statement's column-heading row ("Date  Narration  Chq./Ref.No.  Value Dt  Withdrawal Amt. ...")
_TABLE_HEADER_WORDS = re.compile(r"(?i)\b(?:date|narration|particulars|description|remarks|balance|withdrawals?|"
                                 r"deposits?|debit|credit|amount|value\s*dt|chq|cheque|ref\.?\s*no)\b")


_CP_TRIM = set("TO BY FROM UPI NEFT IMPS RTGS TRF TRANSFER P2A P2M DR CR MOB INB PAYMENT SENT RECEIVED REF".split())


def _counterparties(text: str) -> list[Match]:
    out = []
    prev_rails = False
    for ls, le in _line_spans(text):
        line = text[ls:le]
        here = bool(_RAILS.search(line))
        # a narration continues on the next line ('BIL/ONL/0003.../MCA 21/...,' then '2/Rita Mishra')
        cont = prev_rails and not here and not re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", line)
        prev_rails = here
        if not (here or cont):
            continue
        if len({w.group(0).lower()[:5] for w in _TABLE_HEADER_WORDS.finditer(line)}) >= 3 and not re.search(r"\d", line):
            continue                                   # column headings, not a narration
        for m in _CP_SEG.finditer(text, ls, le):
            s, e = m.start(), m.end()
            seg = text[s:e]
            stripped = seg.strip()
            if not stripped or any(c.isdigit() for c in stripped) or "@" in stripped:
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z .&']{2,50}", stripped):
                continue
            words = re.findall(r"[A-Za-z]+", stripped)
            if not words or all(w.upper() in _CP_STOP or len(w) <= 1 for w in words):
                continue
            # trim leading/trailing stop words ("TO RAMESH KUMAR" -> "RAMESH KUMAR")
            s += len(seg) - len(seg.lstrip())
            e -= len(seg) - len(seg.rstrip())
            while True:
                w = re.match(r"([A-Za-z]+)\s+", text[s:e])
                if w and w.group(1).upper() in _CP_TRIM:
                    s += w.end()
                    continue
                break
            while True:
                w = re.search(r"\s+([A-Za-z]+)$", text[s:e])
                if w and w.group(1).upper() in _CP_TRIM:
                    e = s + w.start()
                    continue
                break
            if e - s >= 3:
                out.append(Match(s, e, "COUNTERPARTY", text[s:e]))
    return out


def _cells_x(text, ls, le, boxes):
    """(start, end, x0, x1) of each cell of a line (runs separated by two or more spaces)."""
    out = []
    for m in re.finditer(r"\S+(?: \S+)*", text[ls:le]):
        s, e = ls + m.start(), ls + m.end()
        bs = [b for b in boxes[s:e] if b] if boxes else []
        if bs:
            out.append((s, e, min(b[0] for b in bs), max(b[2] for b in bs), min(b[1] for b in bs), max(b[3] for b in bs)))
    return out



def custom_patterns(term: str) -> list[re.Pattern]:
    """A client word list entry; long addresses are also matched part by part."""
    term = term.strip()
    if len(term) < 3:
        return []
    parts = [term]
    if re.search(r"[,\n]", term):
        for p in re.split(r"[,\n]+", term):
            p = p.strip()
            if (len(p) >= 8 and " " in p) or (re.search(r"\d", p) and len(p) >= 5):
                parts.append(p)
    pats = []
    for p in parts:
        words = [re.escape(w) for w in re.split(r"[\s,]+", p) if w]
        body = r"[\s,]*".join(words)            # may run over a line break
        pats.append(re.compile(r"(?i)(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])"))
    return pats


def keep_key(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", v.upper())


def _core_hits(text: str, rules: set, opts, boxes=None) -> list[Match]:
    hits: list[Match] = []
    for rule in RULES:
        if rule.key not in rules or rule.pattern is None:
            continue
        for m in rule.pattern.finditer(text):
            g = rule.target_group
            if g and m.group(g) is None:
                continue
            s, e = m.span(g)
            while e > s and text[e - 1] in " -,.":
                e -= 1
            val = text[s:e]
            if not val.strip() or (rule.validator and not rule.validator(val)):
                continue
            if rule.key in ("LONG_NUMBER", "CARD", "AADHAAR") and _in_hash(text, s, e):
                continue
            key = rule.key
            if key in ("AADHAAR", "CARD") and val.isdigit() and "LONG_NUMBER" in rules:
                # 'UPI/221210758023/...' or a reference alone on its line: a transaction reference that happens to
                # pass the Aadhaar check digit (1 in 10 do). Unspaced and unlabelled, it is labelled as a reference.
                ls = text.rfind("\n", 0, s) + 1
                le = text.find("\n", e)
                line = text[ls:le if le >= 0 else len(text)]
                label_rx = (r"(?i)aadh|\buid\b|\u0906\u0927\u093e\u0930" if key == "AADHAAR"
                            else r"(?i)card|visa|master|rupay|maestro|amex|\bpos\b|\batm\b|\becom")
                labelled = re.search(label_rx, text[max(0, s - 40):s])
                slashed = (s > 0 and text[s - 1] in "/-:") or text[e:e + 1] in ("/", "-")
                if not labelled and (slashed or _RAILS.search(line) or line.strip() == val):
                    key = "LONG_NUMBER"
            hits.append(Match(s, e, key, val))
    if "ADDRESS" in rules:
        hits += _addresses(text, boxes)
    if "TO_BLOCK" in rules:
        hits += _to_block(text, boxes)
    if "COUNTERPARTY" in rules:
        hits += _counterparties(text)
    if "UPI" in rules:
        hits += _upi_segments(text)
    return hits


_HASH = re.compile(r"[A-Z]{0,6}[0-9a-f]{16,}")


def _in_hash(text: str, s: int, e: int) -> bool:
    """Digits inside a transaction hash ('HDF1176736f488344479cbe44a25c8277b2'), which identify no one."""
    a, b = s, e
    while a > 0 and text[a - 1].isalnum():
        a -= 1
    while b < len(text) and text[b].isalnum():
        b += 1
    tok = text[a:b]
    return len(tok) >= 20 and bool(re.search(r"[a-f]", tok)) and bool(_HASH.fullmatch(tok))


_LINE_RULES = {"ADDRESS", "TO_BLOCK", "NAME_LABELLED", "DOB"}       # need whole lines / labels: not on joined cells


def _wrapped_hits(text: str, boxes, rules: set, opts) -> list[Match]:
    """Values broken across two lines of a narration cell. Banks such as ICICI wrap narrations at a fixed
    width, mid-word ('.../AKA' + 'NKSHA /State Bank', 'lallanpan' + 'dey72@okaxis'). The two parts are joined,
    checked again, and any value running over the join is redacted in both parts under its whole value."""
    lines = _line_spans(text)
    cells = [_cells_x(text, ls, le, boxes) for ls, le in lines]
    right: dict = {}
    for row in cells:
        for c in row:
            k = round(c[2] / 3)
            right[k] = max(right.get(k, 0), c[3])
    sub = set(rules) - _LINE_RULES
    out = []
    for i in range(len(lines) - 1):
        if not cells[i + 1]:
            continue
        c2 = cells[i + 1][0]
        for c1 in cells[i]:
            if abs(c1[2] - c2[2]) > 4 or c2[4] - c1[5] > (c1[5] - c1[4]) * 0.8 or c2[4] < c1[4]:
                continue                                    # not the same column / not the next line
            w = (c1[3] - c1[2]) / max(1, c1[1] - c1[0])     # average character width
            t1, t2 = text[c1[0]:c1[1]], text[c2[0]:c2[1]]
            full = c1[3] >= right.get(round(c1[2] / 3), c1[3]) - 2.5 * w
            # a line that was not full is an ordinary word break, unless the next line starts with the rest of
            # a UPI ID ('.../singhtanu.' + 'b@oki/Union Bank')
            if not full and not re.match(r"[\w.\-]{0,30}@", t2):
                continue
            if not (t1[-1:].isalnum() or t1[-1:] in "@._-") or not (t2[:1].isalnum() or t2[:1] in "@._-"):
                continue
            joined = t1 + t2
            n = len(t1)
            for m in merge(_core_hits(joined, sub, opts)):
                if not (m.start < n < m.end):
                    continue                                # wholly inside one line: found by the normal pass
                if not full and m.rule != "UPI":
                    continue
                if m.rule == "COUNTERPARTY":
                    a, b = joined[m.start:n], joined[n:m.end]
                    if a.upper() in _CP_STOP or b.split()[0].upper() in _CP_STOP if b.split() else True:
                        continue
                out.append(Match(c1[0] + m.start, c1[1], m.rule, m.value))
                out.append(Match(c2[0], c2[0] + (m.end - n), m.rule, m.value))
    return out


_UPI_SEG = re.compile(r"(?<=/)([a-z0-9][a-z0-9.\-_]{4,}[a-z0-9.\-_@]?)(?=/[A-Za-z]|\s*$)")


def _upi_segments(text: str) -> list[Match]:
    """UPI IDs that the bank cut short (ICICI keeps 15 characters, dropping '@bank'): in a UPI narration, the
    lower-case segment just before the payer's bank name ('UPI/2168.../old balance/jaijagdishindus/Canara Bank')."""
    out = []
    prev = False
    for ls, le in _line_spans(text):
        line = text[ls:le]
        here = bool(re.search(r"\bUPI\b", line))
        ok, prev = here or (prev and not re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", line)), here
        if not ok:
            continue
        for m in _UPI_SEG.finditer(text, ls, le):
            v = m.group(1)
            if not re.search(r"[a-z]", v) or v in ("payment", "upi", "ybl", "okaxis", "paytm"):
                continue
            if not (re.search(r"[\d.\-_@]", v) or len(v) >= 10):
                continue                                    # a short remark word ('rent'), not an ID
            out.append(Match(m.start(1), m.end(1), "UPI", v))
    return out


def find_matches(text: str, rules: set, opts, boxes=None, extra_terms=(), keep_extra=()) -> list[Match]:
    """All detections in `text`, overlapping hits merged (first label wins)."""
    protected = [m.span() for m in PROTECT_ITBA.finditer(text)] if opts.protect_itba_din else []
    keep = {keep_key(k) for k in list(opts.keep_terms) + list(keep_extra) if k.strip()}

    hits = _core_hits(text, rules, opts, boxes)
    if boxes:
        hits = _wrapped_hits(text, boxes, rules, opts) + hits   # first: these carry the whole value

    for term in list(opts.custom_terms):
        for rx in custom_patterns(term):
            hits += [Match(m.start(), m.end(), "CUSTOM", m.group(0)) for m in rx.finditer(text)]
    for term in extra_terms:
        for rx in custom_patterns(term):
            hits += [Match(m.start(), m.end(), "MANUAL", m.group(0)) for m in rx.finditer(text)]

    hits = [h for h in hits
            if keep_key(h.value) not in keep
            and not any(ps <= h.start and h.end <= pe for ps, pe in protected)]
    return merge(hits)


def merge(hits: list[Match]) -> list[Match]:
    order = {r.key: i for i, r in enumerate(RULES + _EXTRA)}
    hits.sort(key=lambda h: (h.start, -(h.end - h.start), order.get(h.rule, 99)))
    out: list[Match] = []
    for h in hits:
        if out and h.start < out[-1].end:
            last = out[-1]
            if h.end > last.end:
                out[-1] = Match(last.start, h.end, last.rule, last.value)
            continue
        out.append(h)
    return out


# --------------------------------------------------------------------------
# Normalisation (for consistent labels and batch-wide propagation)
# --------------------------------------------------------------------------
# rule -> (namespace, label prefix, priority: lower wins when namespaces collide)
CATEGORY = {
    "PAN": ("id", "PAN", 1), "GSTIN": ("id", "GSTIN", 1), "TAN": ("id", "TAN", 1),
    "AADHAAR": ("num", "AADHAAR", 1), "AADHAAR_VID": ("num", "VID", 1), "CIN": ("id", "CIN", 1),
    "LLPIN": ("id", "LLPIN", 1), "DOB": ("id", "DOB", 1), "DIN_DIRECTOR": ("num", "DIN", 2), "PASSPORT": ("id", "PASSPORT", 1),
    "VOTER_ID": ("id", "VOTERID", 1), "CARD": ("num", "CARD", 2), "ACCOUNT_CTX": ("num", "ACCT", 1),
    "MASKED_NUM": ("masked", "ACCT", 3), "LONG_NUMBER": ("num", "REF", 5), "IFSC": ("id", "IFSC", 1),
    "MICR": ("num", "MICR", 2), "UPI": ("lower", "UPI", 1), "CUSTOMER_ID": ("id", "CUSTID", 2),
    "NAME_LABELLED": ("name", "NAME", 1), "TO_NAME": ("name", "NAME", 1), "TO_ADDR": ("addr", "ADDR", 1),
    "ADDRESS": ("addr", "ADDR", 1), "COUNTERPARTY": ("name", "PARTY", 4), "CUSTOM": ("name", "TERM", 3),
    "MANUAL": ("name", "TERM", 6), "MOBILE": ("mobile", "MOBILE", 1), "EMAIL": ("lower", "EMAIL", 1),
    "QR": ("visual", "QR", 1), "PHOTO": ("visual", "PHOTO", 1), "SIGNATURE": ("visual", "SIGNATURE", 1),
}

_HONORIFIC = re.compile(r"^(?:M/S\.?|MESSRS\.?|MR\.?|MRS\.?|MS\.?|SHRI\.?|SMT\.?|DR\.?|KUM\.?)\s+", re.I)


def clean_name(v: str) -> str:
    v = re.sub(r"\s+", " ", v).strip(" ,.;:-")
    return _HONORIFIC.sub("", v).strip()


def norm_key(rule: str, value: str) -> tuple:
    ns = CATEGORY.get(rule, ("name", "TERM", 9))[0]
    if ns == "num":
        return ("num", digits(value))
    if ns == "mobile":
        return ("num", digits(value)[-10:])
    if ns == "id":
        return ("id", re.sub(r"[^A-Z0-9]", "", value.upper()).replace("O", "0") if rule == "IFSC"
                else re.sub(r"[^A-Z0-9]", "", value.upper()))
    if ns == "lower":
        return ("lower", value.strip().lower())
    if ns == "masked":
        return ("masked", re.sub(r"\s", "", value.upper()))
    if ns == "visual":
        return ("visual", value)
    v = clean_name(value).upper()
    v = re.sub(r"[^A-Z0-9 ]", " ", v)
    v = re.sub(r"\bPRIVATE\b", "PVT", v)
    v = re.sub(r"\bLIMITED\b", "LTD", v)
    v = re.sub(r"\s+", " ", v).strip()
    return ("addr" if ns == "addr" else "name", v)


_LOOKALIKE = {"0": "[0O]", "O": "[O0]", "1": "[1Il]", "I": "[I1l]", "5": "[5S]", "S": "[S5]",
              "8": "[8B]", "B": "[B8]", "2": "[2Z]", "Z": "[Z2]"}


def _tolerant(ch: str) -> str:
    return _LOOKALIKE.get(ch.upper(), re.escape(ch))


def propagation_pattern(rule: str, value: str) -> re.Pattern | None:
    """Regex that finds the same value elsewhere, tolerant of spacing."""
    ns = CATEGORY.get(rule, ("name",))[0]
    if ns in ("num", "mobile"):
        d = digits(value)
        if ns == "mobile":
            d = d[-10:]
        if len(d) < 8:
            return None
        return re.compile(r"(?<!\d)" + (_H + "?").join(_tolerant(c) for c in d) + r"(?!\d)")
    if ns == "id":
        v = re.sub(r"[^A-Za-z0-9]", "", value)
        if len(v) < 6:
            return None
        return re.compile(r"(?i)(?<![A-Za-z0-9])" + r"[ \-]?".join(_tolerant(c) for c in v) + r"(?![A-Za-z0-9])")
    if ns == "lower":
        return re.compile(r"(?i)(?<![\w.])" + re.escape(value.strip()) + r"(?![\w])")
    if ns == "name":
        v = clean_name(value)
        words = [w for w in re.split(r"[\s,]+", v) if w]
        letters = sum(c.isalpha() for c in v)
        if letters < 5 or (len(words) < 2 and letters < 8):
            return None
        def tok(w):
            u = w.upper().rstrip(".")
            if u in ("PRIVATE", "PVT"):
                return r"(?:PRIVATE|PVT\.?)"
            if u in ("LIMITED", "LTD"):
                return r"(?:LIMITED|LTD\.?)"
            return re.escape(w)
        body = r"[\s,.]*".join(tok(w) for w in words)
        return re.compile(r"(?i)(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])")
    return None


def all_matches(text: str, rules, opts, ctx=None, ov=None, boxes=None) -> list[Match]:
    """Rule hits + client words + review additions + values known from the batch."""
    terms = list(ov.terms) if ov else []
    keep_extra = list(ov.keep_values) if ov else []
    hits = find_matches(text, rules, opts, boxes, extra_terms=terms, keep_extra=keep_extra)
    if ctx is not None and opts.propagate:
        keep = {keep_key(k) for k in list(opts.keep_terms) + keep_extra if k.strip()}
        protected = [m.span() for m in PROTECT_ITBA.finditer(text)] if opts.protect_itba_din else []
        extra = []
        for rule, value, rx in ctx.patterns:
            if keep_key(value) in keep:
                continue
            for m in rx.finditer(text):
                if keep_key(m.group(0)) in keep:
                    continue
                if any(ps <= m.start() and m.end() <= pe for ps, pe in protected):
                    continue
                extra.append(Match(m.start(), m.end(), rule, value))
        if extra:
            hits = merge(hits + extra)
    return hits


_LABEL_TOKEN = re.compile(r"\[[A-Z]+(?:-\d+)?\]")


def is_noise(rule: str, value: str) -> bool:
    """A re-check hit that is only our own label text or OCR noise."""
    v = _LABEL_TOKEN.sub(" ", value)
    if not re.search(r"[A-Za-z0-9]{3}", v):
        return True
    if rule in HEURISTIC_RULES:
        if "[" in value or "]" in value:
            return True
        words = [w for w in re.findall(r"[A-Za-z]{3,}", v) if w.upper() not in _CP_STOP]
        return len(words) < 2
    return False


SHORT = {
    "GSTIN": "GSTIN", "PAN": "PAN", "TAN": "TAN", "AADHAAR": "Aadhaar", "AADHAAR_VID": "Aadhaar VID",
    "DOB": "Date of birth", "CIN": "CIN", "LLPIN": "LLPIN", "DIN_DIRECTOR": "Director DIN", "PASSPORT": "Passport",
    "VOTER_ID": "Voter ID", "ACCOUNT_CTX": "Account no.", "CARD": "Card no.", "MASKED_NUM": "Masked no.",
    "LONG_NUMBER": "Reference no.", "IFSC": "IFSC", "MICR": "MICR", "UPI": "UPI ID", "CUSTOMER_ID": "Customer ID",
    "NAME_LABELLED": "Name", "ADDRESS": "Address", "TO_NAME": "Addressee", "TO_ADDR": "Addressee address",
    "COUNTERPARTY": "Counterparty", "MOBILE": "Mobile", "EMAIL": "E-mail", "QR": "QR / barcode", "PHOTO": "Photograph",
    "SIGNATURE": "Signature", "CUSTOM": "Added word", "MANUAL": "Added in review",
}


def rule_short(key: str) -> str:
    return SHORT.get(key, rule_label(key))
