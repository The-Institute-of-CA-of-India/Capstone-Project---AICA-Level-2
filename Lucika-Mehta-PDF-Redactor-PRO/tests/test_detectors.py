"""Detector unit tests:  python tests/test_detectors.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import batch as B  # noqa: E402
from redact import detect as D  # noqa: E402
from redact.model import Options  # noqa: E402
from make_samples import AADHAAR, CARD  # noqa: E402

OPTS = Options(rules=set(D.DEFAULT_RULES))


def keys(text, opts=OPTS):
    return [(m.rule, m.value) for m in D.find_matches(text, opts.rules, opts)]


def test_tax_ids():
    assert keys("PAN: AAKCS1234F") == [("PAN", "AAKCS1234F")]
    assert keys("GSTIN 27AAKCS1234F1Z5")[0][0] == "GSTIN"
    assert keys("TAN PNES12345B") == [("TAN", "PNES12345B")]
    assert keys("CIN U51909PN2015PTC123456")[0][0] == "CIN"
    assert keys(f"Aadhaar {AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}")[0][0] == "AADHAAR"
    assert keys("DIN: 08123456") == [("DIN_DIRECTOR", "08123456")]
    assert keys("Date of Birth: 15/04/1980") == [("DOB", "15/04/1980")]


def test_banking():
    assert keys("Account No : 32014567891234") == [("ACCOUNT_CTX", "32014567891234")]
    assert keys("IFSC SBIN0004567") == [("IFSC", "SBIN0004567")]
    assert ("UPI", "abc.traders@okhdfcbank") in keys("UPI/123/abc.traders@okhdfcbank/ref")
    assert ("UPI", "suresh@ybl") in keys("UPI-SURESH PATIL-suresh@ybl-PAYMENT")
    assert keys(f"CARD {CARD[:4]} {CARD[4:8]} {CARD[8:12]} {CARD[12:]}")[0][0] == "CARD"
    assert keys("Linked A/c XXXXXXXX7788")[0][1].endswith("7788")


def test_names_addresses():
    assert ("NAME_LABELLED", "M/s Sample Traders Private Limited") in keys("Account Name : M/s Sample Traders Private Limited")
    got = keys("Address : Plot 12, Sector 5\nKothrud, Pune 411038\nAccount No : 1234567890")
    assert ("ADDRESS", "Plot 12, Sector 5") in got and ("ADDRESS", "Kothrud, Pune 411038") in got
    got = keys("To,\nSample Traders Pvt Ltd\nPlot 12, Kothrud\nPune - 411038\nSub: Notice")
    assert got[0] == ("TO_NAME", "Sample Traders Pvt Ltd") and len(got) == 3
    assert keys("To,\nThe Assessing Officer\nWard 1(1), Pune") == []          # authority stays visible
    assert ("COUNTERPARTY", "RAMESH KUMAR") in keys("NEFT/UTR 525091234567/RAMESH KUMAR   1,25,000.00")
    assert keys("E-mail Address: x   Branch Address: MG Road") == []


def test_things_that_must_survive():
    for text in [
        "Rs. 1,25,00,000.00 deposited", "Interest 1500000.00",
        "Assessment Year 2024-25, section 143(3) of the ITA, 1961", "Dated 15-04-2025 at 10:30",
        "DIN: ITBA/AST/F/142(1)/2025-26/1076543210(1)", "Email: accounts@sampletraders.in",
        "Mobile +91 98220 12345", "05-04-2025 CASH DEPOSIT BY SELF 25,00,000.00",
    ]:
        assert keys(text) == [], (text, keys(text))


def test_aadhaar_checksum_filters_random_numbers():
    assert all(k != "AADHAAR" for k, _ in keys("Ref 4321 6789 0121"))


def test_custom_and_keep_terms():
    o = Options(rules=set(D.DEFAULT_RULES), custom_terms=["Sample Traders"], keep_terms=["SBIN0004567"])
    assert keys("M/s Sample  Traders Pvt Ltd, IFSC SBIN0004567", o) == [("CUSTOM", "Sample  Traders")]
    o = Options(rules=set(), custom_terms=["Plot 12, Sector 5, Kothrud, Pune 411038"])
    assert len(keys("Address Plot 12, Sector 5,\nKothrud, Pune 411038", o)) >= 1   # across a line break


def test_propagation_and_labels():
    rx = D.propagation_pattern("NAME_LABELLED", "M/s Sample Traders Private Limited")
    assert rx.search("NEFT-SAMPLE TRADERS PVT. LTD-3201")
    assert D.propagation_pattern("IFSC", "SBIN0004567").search("SBINO004567")     # OCR O for 0
    assert D.norm_key("COUNTERPARTY", "SAMPLE TRADERS PVT LTD") == D.norm_key("NAME_LABELLED", "M/s Sample Traders Private Limited")


def test_password_formats():
    c = B.password_candidates([], {"pans": ["AAKCS1234F"], "dates": ["15/04/1980"], "names": ["Sample Traders"]})
    assert "aakcs1234f15041980" in c and "SAMP1504" in c and "15041980" in c


def test_classify():
    assert D.classify("Statement of Account opening balance narration closing balance") == "bank"
    assert D.classify("Income Tax Department notice section 143(2) assessment year ITBA/") == "notice"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed", name)
