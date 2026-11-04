"""Encrypt saved passwords with Windows DPAPI (tied to the Windows user account).

The encrypted text in the database cannot be decrypted on another computer or by
another Windows user. On non-Windows systems (development only) a reversible
encoding is used and marked as such.
"""
from __future__ import annotations

import base64
import sys


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in, blob_out = BLOB(len(data), buf), BLOB()
    entropy_bytes = b"ContractNoteManager"
    ebuf = ctypes.create_string_buffer(entropy_bytes, len(entropy_bytes))
    entropy = BLOB(len(entropy_bytes), ebuf)
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, ctypes.byref(entropy), None, None, 0x01, ctypes.byref(blob_out))
    if not ok:
        raise OSError("Windows could not " + ("protect" if encrypt else "unprotect") + " the password")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def protect(text: str) -> str:
    if not text:
        return ""
    raw = text.encode("utf-8")
    if sys.platform.startswith("win"):
        return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode()
    return "plain:" + base64.b64encode(raw).decode()


def reveal(stored: str) -> str:
    if not stored:
        return ""
    kind, _, b64 = stored.partition(":")
    data = base64.b64decode(b64)
    if kind == "dpapi":
        return _dpapi(data, False).decode("utf-8")
    return data.decode("utf-8")
