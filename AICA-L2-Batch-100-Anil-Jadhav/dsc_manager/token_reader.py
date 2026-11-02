"""Read DSC details from USB tokens plugged into this PC, whatever the brand.

Two ways, tried in this order:

1. PKCS#11 - every DSC token ships a driver DLL with this standard interface.
   We look for the drivers of the common Indian DSC tokens (and any extra
   DLL paths set by the user), ask each for the tokens plugged in, and read
   the token's hardware serial number and the certificates stored on it.
   Needs the PyKCS11 package (pip install PyKCS11).
2. The Windows certificate store - token drivers copy the certificate there
   when the token is plugged in. No token serial number is available this
   way, and certificates of tokens inserted earlier may still be listed.

Only public information is read: no PIN is asked for and nothing is written
to the token. The certificate itself is decoded here (a small DER reader),
so no extra library is needed for that.
"""
import os
import re
import ssl
from datetime import datetime, timezone

# Driver DLLs of DSC tokens commonly issued in India (and a few generic ones).
KNOWN_DRIVERS = [
    ("ePass2003 / HYP2003", "eps2003csp11.dll"),
    ("ePass2003 (v2)", "eps2003csp11v2.dll"),
    ("ePass3003", "ShuttleCsp11_3003.dll"),
    ("ProxKey", "SignatureP11.dll"),
    ("Watchdata", "WDPKCS.dll"),
    ("mToken", "CryptoIDA_pkcs11.dll"),
    ("Trust Key", "TrustKeyP11.dll"),
    ("SafeNet eToken", "eTPKCS11.dll"),
    ("Gemalto IDPrime", "IDPrimePKCS1164.dll"),
    ("Gemalto IDPrime", "IDPrimePKCS11.dll"),
    ("Bit4id", "bit4ipki.dll"),
    ("OpenSC", "opensc-pkcs11.dll"),
]
# Other PKCS#11 drivers in the system folder are found by name.
OTHER_DRIVER = "Other PKCS#11 driver"
_DRIVER_NAME_RE = re.compile(r"(pkcs11|pkcs#11|csp11|p11)[^\\/]*\.dll$|[^\\/]*p11\.dll$", re.IGNORECASE)

OID_CN = bytes.fromhex("550403")
OID_O = bytes.fromhex("55040a")
OID_BASIC_CONSTRAINTS = bytes.fromhex("551d13")
OID_CERT_POLICIES = bytes.fromhex("551d20")
# Every DSC issued in India under the Controller of Certifying Authorities (CCA) carries a
# certificate policy under India's arc 2.16.356.100 (Class 2/3 assurance etc.). Windows also keeps
# other certificates (Microsoft account, Adobe, ...) - those never carry it.
INDIAN_DSC_POLICY = "2.16.356.100."
DRIVE_REMOVABLE, DRIVE_CDROM = 2, 5


class TokenReadResult:
    def __init__(self):
        self.tokens = []      # list of dicts, one per certificate found (or per token without one)
        self.notes = []       # plain-language diagnostics for the user
        self.drivers = []     # (label, path) tried
        self.method = None    # "pkcs11" or "store"


# ---------------------------------------------------------------------- certificate decoding (DER)
def _tlv(data, pos):
    tag = data[pos]
    length = data[pos + 1]
    pos += 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(data[pos:pos + n], "big")
        pos += n
    return tag, pos, pos + length


def _children(data, start, end):
    out = []
    while start < end:
        tag, cs, ce = _tlv(data, start)
        out.append((tag, cs, ce))
        start = ce
    return out


def _string(data, tag, cs, ce):
    raw = data[cs:ce]
    if tag == 0x1E:  # BMPString
        return raw.decode("utf-16-be", "replace")
    return raw.decode("utf-8", "replace") if tag == 0x0C else raw.decode("latin-1")


def _name(data, cs, ce):
    """X.509 Name -> {'CN': ..., 'O': ...}"""
    out = {}
    for _, ss, se in _children(data, cs, ce):           # SET
        for _, as_, ae in _children(data, ss, se):      # SEQUENCE {OID, value}
            parts = _children(data, as_, ae)
            if len(parts) < 2:
                continue
            oid = data[parts[0][1]:parts[0][2]]
            key = {OID_CN: "CN", OID_O: "O"}.get(oid)
            if key and key not in out:
                out[key] = _string(data, *parts[1]).strip()
    return out


def _oid(raw):
    """DER-encoded OBJECT IDENTIFIER body -> dotted text, e.g. '2.16.356.100.2.3'."""
    parts, value = [], 0
    for byte in raw:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    if not parts:
        return ""
    first = parts[0]
    head = [min(first // 40, 2), first - 40 * min(first // 40, 2)]
    return ".".join(str(n) for n in head + parts[1:])


def _time(data, tag, cs, ce):
    s = data[cs:ce].decode("ascii").rstrip("Z")
    if tag == 0x17:  # UTCTime YYMMDDHHMM[SS]
        year = int(s[:2])
        s = f"{2000 + year if year < 50 else 1900 + year}{s[2:]}"
    s = s.ljust(14, "0")[:14]
    utc = datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return utc.astimezone().replace(tzinfo=None)  # local (Indian) time


def parse_certificate(der):
    """Decode the parts of an X.509 certificate this app needs. None if unreadable."""
    try:
        der = bytes(der)
        _, cs, ce = _tlv(der, 0)
        _, ts, te = _children(der, cs, ce)[0]           # tbsCertificate
        fields = _children(der, ts, te)
        i = 1 if fields[0][0] == 0xA0 else 0            # optional [0] version
        serial_raw = der[fields[i][1]:fields[i][2]].lstrip(b"\x00") or b"\x00"
        issuer_f, validity_f, subject_f = fields[i + 2], fields[i + 3], fields[i + 4]
        not_before, not_after = (_time(der, *t) for t in _children(der, validity_f[1], validity_f[2])[:2])
        issuer = _name(der, issuer_f[1], issuer_f[2])
        subject = _name(der, subject_f[1], subject_f[2])
        is_ca = der[issuer_f[1]:issuer_f[2]] == der[subject_f[1]:subject_f[2]]  # self-signed root
        policies = []
        for tag, xs, xe in fields[i + 6:]:
            if tag != 0xA3:                             # [3] extensions
                continue
            for _, es, ee in _children(der, *_children(der, xs, xe)[0][1:]):
                parts = _children(der, es, ee)
                if der[parts[0][1]:parts[0][2]] == OID_BASIC_CONSTRAINTS:
                    _, vs, ve = parts[-1]
                    inner = _children(der, vs, ve)
                    bc = _children(der, inner[0][1], inner[0][2]) if inner else []
                    if bc and bc[0][0] == 0x01 and der[bc[0][1]] != 0:
                        is_ca = True
                elif der[parts[0][1]:parts[0][2]] == OID_CERT_POLICIES:
                    _, vs, ve = parts[-1]
                    for _, ps, pe in _children(der, *_children(der, vs, ve)[0][1:]):   # PolicyInformation
                        first = _children(der, ps, pe)[0]
                        policies.append(_oid(der[first[1]:first[2]]))
        return {
            "cert_serial": serial_raw.hex().upper(),
            "holder_name": subject.get("CN", ""),
            "subject_org": subject.get("O", ""),
            "issuer": issuer.get("O") or issuer.get("CN", ""),
            "issuer_cn": issuer.get("CN", ""),
            "issue_date": not_before.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": not_after.strftime("%Y-%m-%d %H:%M:%S"),
            "is_ca": is_ca,
            "policies": policies,
            "is_indian_dsc": any(p.startswith(INDIAN_DSC_POLICY) for p in policies),
        }
    except (IndexError, ValueError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------- finding drivers
def system_folder():
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


def find_drivers(extra_paths=()):
    """(label, path) for every PKCS#11 driver found, user-configured paths first."""
    found, seen = [], set()

    def add(label, path):
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen and os.path.isfile(path):
            seen.add(key)
            found.append((label, path))

    for p in extra_paths:
        add("Added in Settings", p)
    folder = system_folder()
    for label, name in KNOWN_DRIVERS:
        add(label, os.path.join(folder, name))
    try:
        for name in sorted(os.listdir(folder)):
            if _DRIVER_NAME_RE.search(name) and not name.lower().startswith(("msvcp", "vcamp", "vcomp")):
                add(OTHER_DRIVER, os.path.join(folder, name))
    except OSError:
        pass
    return found


# ---------------------------------------------------------------------- reading
def _pkcs11_module():
    try:
        import PyKCS11
        return PyKCS11
    except ImportError:
        return None


def _read_pkcs11(result, drivers, pk):
    seen = set()
    libs = []  # keep the loaded libraries alive until we are done
    for label, path in drivers:
        lib = pk.PyKCS11Lib()
        try:
            lib.load(path)
            libs.append(lib)
            slots = lib.getSlotList(tokenPresent=True)
        except Exception as exc:  # a driver that fails must not stop the others
            if label != OTHER_DRIVER:  # files found only by their name may not be drivers at all
                result.notes.append(f"{os.path.basename(path)} ({label}): could not be used - {exc}")
            continue
        for slot in slots:
            try:
                info = lib.getTokenInfo(slot)
                serial = (info.serialNumber or "").strip()
                token = {"token_serial": serial.upper(), "token_label": (info.label or "").strip(),
                         "manufacturer": (info.manufacturerID or "").strip(), "driver": label,
                         "driver_path": path, "source": "Token (PKCS#11)"}
                session = lib.openSession(slot)
                try:
                    objects = session.findObjects([(pk.CKA_CLASS, pk.CKO_CERTIFICATE)])
                    ders = [bytes(session.getAttributeValue(o, [pk.CKA_VALUE])[0]) for o in objects]
                finally:
                    session.closeSession()
            except Exception as exc:
                result.notes.append(f"A token seen by {os.path.basename(path)} could not be read - {exc}")
                continue
            certs = [c for c in (parse_certificate(d) for d in ders) if c and not c["is_ca"]]
            if not certs:
                key = (serial, None)
                if key not in seen:
                    seen.add(key)
                    result.tokens.append(dict(token, holder_name="", cert_serial="", issuer="",
                                              issue_date=None, expiry_date=None))
                continue
            for c in certs:
                key = (serial, c["cert_serial"])
                if key not in seen:  # the same token can be visible through two drivers
                    seen.add(key)
                    result.tokens.append(dict(token, **c))
    return libs


def _read_store(result):
    try:
        entries = ssl.enum_certificates("MY")
    except (AttributeError, OSError) as exc:
        result.notes.append(f"Windows certificate store could not be read - {exc}")
        return
    seen = set()
    for der, encoding, _trust in entries:
        if encoding != "x509_asn":
            continue
        c = parse_certificate(der)
        # Only Indian DSC certificates: never the Microsoft account / Adobe / other certificates Windows keeps.
        if not c or c["is_ca"] or not c["is_indian_dsc"] or c["cert_serial"] in seen:
            continue
        seen.add(c["cert_serial"])
        result.tokens.append(dict(c, token_serial="", token_label="", manufacturer="",
                                  driver="", driver_path="", source="Windows certificate store"))
    result.tokens.sort(key=lambda t: t["expiry_date"] or "", reverse=True)


def installer_hints():
    """Driver installers that DSC tokens carry on their own small built-in drive (e.g. HyperPKI, ePass,
    ProxKey): [path, ...]. Shown to the user when no driver is installed."""
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        mask = kernel.GetLogicalDrives()
    except (AttributeError, OSError):
        return []
    found = []
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = f"{chr(65 + i)}:\\"
        if kernel.GetDriveTypeW(root) not in (DRIVE_REMOVABLE, DRIVE_CDROM):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for name in names:
            low = name.lower()
            if low.endswith((".exe", ".msi")) and any(k in low for k in ("setup", "install", "driver")):
                found.append(os.path.join(root, name))
    return found


def read_tokens(extra_paths=()):
    """Read every DSC token plugged in. Never raises: problems go into result.notes."""
    result = TokenReadResult()
    pk = _pkcs11_module()
    result.drivers = find_drivers(extra_paths)
    if pk is None:
        result.notes.append("PyKCS11 is not installed, so token serial numbers cannot be read. "
                            "Install it with:  pip install PyKCS11")
    elif not result.drivers:
        hints = installer_hints()
        if hints:
            result.notes.append("The DSC token's driver is not installed on this PC. The token carries its own "
                                f"installer: run {hints[0]} (double-click it and allow it to install), then click "
                                "'Read from Token' again.")
        else:
            result.notes.append("No DSC token driver was found on this PC. Install the driver that came with the "
                                "token, or add its DLL path under Settings > DSC Token Drivers.")
    else:
        _read_pkcs11(result, result.drivers, pk)
        if result.tokens:
            result.method = "pkcs11"
            return result
        result.notes.append("No token was found through the installed drivers. Check that the token is "
                            "plugged in and its light is on.")
    _read_store(result)
    if result.tokens:
        result.method = "store"
        result.notes.append("Details were read from the Windows certificate store, not from the token: the "
                            "token serial number must be typed in, and certificates of tokens plugged in "
                            "earlier may also be listed.")
    return result
