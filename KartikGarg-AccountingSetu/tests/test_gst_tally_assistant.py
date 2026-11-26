import datetime as dt
import json
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from services import accounting_engine as ae, assistant_service, gst_service as gs, tally_service as ts
from services.db import get_db
from tests.conftest import CLIENT_A1_GSTIN, CUSTOMER_DL, CUSTOMER_MH, SUPPLIER_KA, SUPPLIER_MH
from tests.helpers import add_invoice
from utils.helpers import D, month_bounds
from utils.validators import gstin_checksum, make_gstin, validate_gstin, validate_invoice_no, validate_tax_amounts

TODAY = dt.date.today()
D1 = TODAY.replace(day=1)
Y, M = D1.year, D1.month
PERIOD = f"{M:02d}{Y}"


# ---------------------------------------------------------------- validators
def test_gstin_validation():
    g = make_gstin("27", "AAPFU0939F")
    assert validate_gstin(g)[0]
    bad = g[:-1] + ("A" if g[-1] != "A" else "B")
    assert validate_gstin(bad) == (False, "GSTIN checksum digit invalid")
    assert not validate_gstin("27AAPFU0939F1Z")[0]
    assert validate_gstin("99AAPFU0939F1ZV")[1].startswith("Invalid state")
    assert gstin_checksum("27AAPFU0939F1Z") == make_gstin("27", "AAPFU0939F")[-1]


def test_invoice_no_and_tax_checks():
    assert validate_invoice_no("INV/2025-26/001")[0]
    assert not validate_invoice_no("THIS-INVOICE-NUMBER-IS-TOO-LONG")[0]
    assert not validate_tax_amounts({"taxable_value": "1000", "cgst": "90", "sgst": "90", "igst": "0", "total": "1180"})
    issues = validate_tax_amounts({"taxable_value": "1000", "cgst": "90", "sgst": "80", "igst": "0", "total": "1200"})
    msgs = " ".join(i["message"] for i in issues)
    assert "differ" in msgs and "Total" in msgs
    assert any("Both IGST" in i["message"] for i in validate_tax_amounts({"taxable_value": "100", "cgst": "9", "sgst": "9", "igst": "18", "total": "136"}))


# ---------------------------------------------------------------- GSTR-1
def test_gstr1_categorisation(env):
    c = env.c_a1  # Maharashtra
    add_invoice(env, c, category="sales", no="B2B-1", party="Mehta", gstin=CUSTOMER_MH, taxable="1000", cgst="90", sgst="90",
                items=[{"hsn": "7208", "taxable": "1000", "rate": "18", "qty": 2}])
    add_invoice(env, c, category="sales", no="B2CL-1", party="Walk-in Delhi", gstin=None, pos="07", taxable="200000", cgst="0",
                sgst="0", igst="36000")
    add_invoice(env, c, category="sales", no="B2CS-1", party="Walk-in Delhi small", gstin=None, pos="07", taxable="50000", cgst="0",
                sgst="0", igst="9000")
    add_invoice(env, c, category="sales", no="B2CS-2", party="Local cash", gstin=None, taxable="1000", cgst="90", sgst="90")
    add_invoice(env, c, category="sales", no="EXP-1", party="US Buyer", gstin=None, pos="96", taxable="300000", cgst="0", sgst="0",
                igst="0", supply_type="export_wopay")
    add_invoice(env, c, category="sales", no="CN-1", party="Mehta", gstin=CUSTOMER_MH, taxable="100", cgst="9", sgst="9",
                note_type="credit_note")
    add_invoice(env, c, category="sales", no="NIL-1", party="Mehta", gstin=CUSTOMER_MH, taxable="500", cgst="0", sgst="0",
                supply_type="exempt")
    p = gs.prepare_gstr1(env.a_admin, c, Y, M)
    sec = p["sections"]
    assert [r["invoice_no"] for r in sec["b2b"]] == ["B2B-1"]
    assert [r["invoice_no"] for r in sec["b2cl"]] == ["B2CL-1"]
    assert {(r["pos"], r["supply"]) for r in sec["b2cs"]} == {("07", "INTER"), ("27", "INTRA")}
    assert [r["invoice_no"] for r in sec["exp"]] == ["EXP-1"] and sec["exp"][0]["export_type"] == "WOPAY"
    assert [r["invoice_no"] for r in sec["cdnr"]] == ["CN-1"] and sec["cdnr"][0]["note_type"] == "C"
    assert sec["nil"][0]["exempted"] == D("500")
    assert any(r["hsn"] == "7208" and r["table"] == "B2B" for r in sec["hsn"])
    js = gs.gstr1_portal_json(p)
    assert js["b2b"][0]["inv"][0]["itms"][0]["itm_det"]["rt"] == 18.0 and js["fp"] == PERIOD
    json.dumps(js)
    assert gs.gstr1_excel(p)[:2] == b"PK"


def test_gstr3b_tables_and_itc_exceptions(env):
    c = env.c_a1
    add_invoice(env, c, category="sales", no="S1", party="Mehta", gstin=CUSTOMER_MH, taxable="100000", cgst="9000", sgst="9000")
    add_invoice(env, c, category="sales", no="S2", party="Delhi B2C", gstin=None, pos="07", taxable="10000", cgst="0", sgst="0", igst="1800")
    add_invoice(env, c, no="P1", gstin=SUPPLIER_KA, taxable="50000", cgst="0", sgst="0", igst="9000", itc="eligible")
    add_invoice(env, c, no="P2", gstin=SUPPLIER_MH, taxable="1000", cgst="90", sgst="90", itc="blocked", party="Caterer")
    add_invoice(env, c, no="P3", gstin=SUPPLIER_MH, taxable="2000", cgst="180", sgst="180", itc="ineligible", party="Late Vendor")
    add_invoice(env, c, no="P4", gstin=SUPPLIER_MH, taxable="3000", cgst="270", sgst="270", itc="pending", party="Pending Vendor")
    add_invoice(env, c, no="R1", gstin=SUPPLIER_MH, taxable="10000", cgst="900", sgst="900", total="10000", rcm=True, itc="eligible",
                party="Advocate")
    r = gs.prepare_gstr3b(env.a_admin, c, Y, M)
    t31, t4 = r["table_3_1"], r["table_4"]
    assert t31["a"]["taxable_value"] == D("110000") and t31["a"]["igst"] == D("1800") and t31["a"]["cgst"] == D("9000")
    assert t31["d"]["cgst"] == D("900")
    assert r["table_3_2"] == [{"pos": "07", "taxable_value": D("10000"), "igst": D("1800")}]
    assert t4["A5"]["igst"] == D("9000") and t4["A5"]["cgst"] == D("90")        # eligible + blocked in 4A
    assert t4["B1"]["cgst"] == D("90")                                         # blocked reversed in 4B(1)
    assert t4["D2"]["cgst"] == D("180")                                        # ineligible in 4D(2)
    assert t4["A3"]["cgst"] == D("900")                                        # RCM ITC
    assert any("pending" in w for w in r["warnings"])                           # pending excluded
    # Rule 88A: IGST credit 9000 → IGST 1800 first, then CGST/SGST shortfall
    so = r["setoff"]
    assert so["utilisation"]["igst->igst"] == D("1800")
    assert r["cash_payable"]["cgst"] >= D("900")                               # RCM always in cash


def test_rule_88a_utilisation_order():
    res = gs.utilise_itc({"igst": D("100"), "cgst": D("500"), "sgst": D("500"), "cess": D("0")},
                         {"igst": D("600"), "cgst": D("100"), "sgst": D("0"), "cess": D("0")})
    u = res["utilisation"]
    assert u["igst->igst"] == D("100")
    assert res["cash_payable"]["cgst"] + res["cash_payable"]["sgst"] == D("400")  # 1000 C+S liability - (500 IGST + 100 CGST credit)
    assert res["itc_balance_carried_forward"]["igst"] == 0
    assert "cgst->sgst" not in u and "sgst->cgst" not in u


def test_gstr2b_reconciliation(env):
    c = env.c_a1
    add_invoice(env, c, no="INV-001", gstin=SUPPLIER_MH, taxable="1000", cgst="90", sgst="90")               # matched
    add_invoice(env, c, no="INV-002", gstin=SUPPLIER_MH, taxable="2000", cgst="180", sgst="180")             # amount mismatch
    add_invoice(env, c, no="INV-003", gstin=SUPPLIER_MH, taxable="3000", cgst="270", sgst="270")             # missing in 2B
    add_invoice(env, c, no="INV-004", gstin=SUPPLIER_KA, taxable="4000", cgst="0", sgst="0", igst="720")     # gstin mismatch
    add_invoice(env, c, no="INV-005", gstin=SUPPLIER_MH, taxable="500", cgst="45", sgst="45",
                date=(D1 - dt.timedelta(days=5)))                                                          # period mismatch
    other = make_gstin("24", "ZZZZZ9999Z")
    data = {"data": {"docdata": {"b2b": [
        {"ctin": SUPPLIER_MH, "trdnm": "Sharma", "inv": [
            {"inum": "INV001", "dt": D1.strftime("%d-%m-%Y"), "val": 1180, "itcavl": "Y", "items": [{"txval": 1000, "cgst": 90, "sgst": 90}]},
            {"inum": "INV-002", "dt": D1.strftime("%d-%m-%Y"), "val": 2300, "itcavl": "Y", "items": [{"txval": 2000, "cgst": 150, "sgst": 150}]},
            {"inum": "INV-005", "dt": (D1 - dt.timedelta(days=5)).strftime("%d-%m-%Y"), "val": 590, "itcavl": "Y",
             "items": [{"txval": 500, "cgst": 45, "sgst": 45}]},
            {"inum": "NEW-9", "dt": D1.strftime("%d-%m-%Y"), "val": 118, "itcavl": "N", "items": [{"txval": 100, "cgst": 9, "sgst": 9}]}]},
        {"ctin": other, "inv": [{"inum": "INV-004", "dt": D1.strftime("%d-%m-%Y"), "val": 4720, "itcavl": "Y",
                                 "items": [{"txval": 4000, "igst": 720}]}]}]}}}
    up = gs.import_gstr2b(env.a_admin, c, PERIOD, "2b.json", json.dumps(data).encode())
    res = gs.reconcile_2b(env.a_admin, c, up)
    by_no = {i["details"]["invoice_no"]: i["status"] for i in res["items"]}
    assert by_no["INV001"] == "matched"
    assert by_no["INV-002"] == "amount_mismatch"
    assert by_no["INV-003"] == "missing_in_2b"
    assert by_no["INV-004"] == "gstin_mismatch"
    assert by_no["INV-005"] == "period_mismatch"
    assert by_no["NEW-9"] == "missing_in_books"
    assert res["summary"]["counts"]["matched"] == 1
    r3b = gs.prepare_gstr3b(env.a_admin, c, Y, M, itc_basis="gstr2b_matched")
    assert r3b["table_4"]["A5"]["cgst"] == D("90") + D("180")  # matched + amount-mismatch (books value), not missing ones


def test_return_workflow_never_claims_filing(env):
    p = gs.prepare_gstr1(env.a_admin, env.c_a1, Y, M)
    rid = gs.save_return(env.a_admin, env.c_a1, p)
    with pytest.raises(ValueError):
        gs.record_external_filing(env.a_admin, rid, "AA2704250000001")
    gs.approve_return(env.a_admin, rid)
    gs.record_external_filing(env.a_admin, rid, "AA2704250000001")
    r = get_db().get("gst_returns", rid)
    assert r["status"] == "filed_externally" and r["external_arn"]


# ---------------------------------------------------------------- Tally
def test_tally_xml_generation(env):
    add_invoice(env, env.c_a1, category="sales", no="S-T1", party="Mehta & Sons <Retail>", gstin=CUSTOMER_MH, taxable="1000",
                cgst="90", sgst="90")
    add_invoice(env, env.c_a1, no="P-T1", gstin=SUPPLIER_MH, taxable="500", cgst="45", sgst="45")
    add_invoice(env, env.c_a1, no="P-T2", gstin=SUPPLIER_MH, taxable="700", cgst="63", sgst="63", approve=False)  # draft excluded
    s, e = month_bounds(Y, M)
    pv = ts.preview(env.a_admin, env.c_a1, s, e)
    assert len(pv["vouchers"]) == 2 and pv["draft_count"] == 1 and not pv["blocking"]
    xml, info = ts.export(env.a_admin, env.c_a1, s, e)
    root = ET.fromstring(xml)
    vouchers = root.findall(".//VOUCHER")
    assert len(vouchers) == 2 and root.find(".//REPORTNAME").text == "Vouchers"
    for v in vouchers:
        amounts = [Decimal(a.text) for a in v.findall("./ALLLEDGERENTRIES.LIST/AMOUNT")]
        assert sum(amounts) == 0                                     # balanced
        for ent in v.findall("./ALLLEDGERENTRIES.LIST"):
            pos = ent.find("ISDEEMEDPOSITIVE").text == "Yes"
            assert (Decimal(ent.find("AMOUNT").text) < 0) == pos     # Tally sign convention
    sales = next(v for v in vouchers if v.get("VCHTYPE") == "Sales")
    assert sales.find("PARTYLEDGERNAME").text == "Mehta & Sons <Retail>"  # escaped correctly by the XML writer
    masters = ET.fromstring(info["masters_xml"])
    assert {l.get("NAME") for l in masters.findall(".//LEDGER")} >= {"Sales", "Output CGST", "Mehta & Sons <Retail>"}
    # second export skips already-exported vouchers
    with pytest.raises(ts.TallyExportError, match="No approved vouchers"):
        ts.export(env.a_admin, env.c_a1, s, e)
    assert "already exported" in ts.preview(env.a_admin, env.c_a1, s, e)["vouchers"][0]["flags"]


def test_tally_blocks_unbalanced(env):
    _, vid = add_invoice(env, env.c_a1, no="P-U", gstin=SUPPLIER_MH)
    get_db().execute("update accounting_voucher_entries set amount = '1.00' where voucher_id = ? and line_no = 1", [vid])
    s, e = month_bounds(Y, M)
    assert ts.preview(env.a_admin, env.c_a1, s, e)["blocking"]
    with pytest.raises(ts.TallyExportError):
        ts.export(env.a_admin, env.c_a1, s, e)


def test_tally_permission(env):
    s, e = month_bounds(Y, M)
    from utils.permissions import PermissionDenied

    with pytest.raises(PermissionDenied):
        ts.preview(env.rev, env.c_a1, s, e)


# ---------------------------------------------------------------- Assistant
def test_assistant_answers_from_records(env):
    add_invoice(env, env.c_a1, category="sales", no="S-A1", party="Mehta", gstin=CUSTOMER_MH, taxable="10000", cgst="900", sgst="900")
    add_invoice(env, env.c_a1, category="sales", no="S-A2", party="Delhi Co", gstin=CUSTOMER_DL, taxable="5000", cgst="0", sgst="0", igst="900")
    add_invoice(env, env.c_a1, no="P-A1", gstin=SUPPLIER_MH, taxable="4000", cgst="360", sgst="360")
    r = assistant_service.answer(env.cu_a1, "What were my sales this month?", env.c_a1)
    assert r["intent"] == "sales_total" and "15,000.00" in r["answer"]
    r = assistant_service.answer(env.cu_a1, "What is my monthly profit?", env.c_a1)
    assert r["intent"] == "profit" and "11,000.00" in r["answer"]
    r = assistant_service.answer(env.a_admin, "Show my top customers", env.c_a1)
    assert r["records"][0]["party"] == "Mehta"
    r = assistant_service.answer(env.a_admin, "How much GST liability is estimated?", env.c_a1)
    assert r["intent"] == "gst_liability" and "Rule 88A" in r["answer"]
    r = assistant_service.answer(env.a_admin, "Which clients have not submitted documents?", None)
    assert r["intent"] == "pending_submissions" and len(r["records"]) == 2
    r = assistant_service.answer(env.a_admin, "Which bank transactions are unmatched?", env.c_a1)
    assert r["intent"] == "unmatched_bank"
    r = assistant_service.answer(env.a_admin, "tell me a joke", env.c_a1)
    assert r["intent"] is None


def test_assistant_period_parsing():
    today = dt.date(2025, 6, 15)
    assert assistant_service.parse_period("last month", None, today)[:2] == (dt.date(2025, 5, 1), dt.date(2025, 5, 31))
    assert assistant_service.parse_period("sales in march 2025", None, today)[0] == dt.date(2025, 3, 1)
    assert assistant_service.parse_period("this financial year", {"fy_start_month": 4}, today)[0] == dt.date(2025, 4, 1)
    assert assistant_service.parse_period("last fy", {"fy_start_month": 4}, today)[:2] == (dt.date(2024, 4, 1), dt.date(2025, 3, 31))
