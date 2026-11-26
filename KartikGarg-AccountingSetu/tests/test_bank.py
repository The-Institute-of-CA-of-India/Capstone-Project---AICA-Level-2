import datetime as dt

import pytest

from services import accounting_engine as ae, bank_service as bs, document_service as ds
from services.db import get_db
from tests.conftest import CUSTOMER_MH, SUPPLIER_MH
from tests.helpers import add_invoice
from utils.helpers import D

TODAY = dt.date.today()
D1 = TODAY.replace(day=1)


def _d(day):
    return D1.replace(day=min(day, 28)).strftime("%d/%m/%Y")


def statement_csv(rows, opening="100000.00"):
    bal = D(opening)
    out = ["Statement of Account", "Account No: XXXX1234", "Date,Narration,Chq/Ref No,Withdrawal Amt,Deposit Amt,Closing Balance"]
    for day, narr, ref, dr, cr in rows:
        bal = bal - D(dr) + D(cr)
        out.append(f"{_d(day)},{narr},{ref},{dr},{cr},{bal}")
    return ("\n".join(out) + "\n").encode()


@pytest.fixture()
def bank(env):
    acct = bs.create_bank_account(env.a_admin, env.c_a1, "HDFC Bank", "50100012341234", "HDFC0000001")
    return acct


def _import(env, bank, csv):
    parsed = bs.parse_statement_table(__import__("services.ocr_service", fromlist=["x"]).read_table(csv, ".csv"))
    return bs.import_statement(env.a_admin, env.c_a1, bank, parsed), parsed


def test_parse_and_classify(env, bank):
    csv = statement_csv([(3, "NEFT-MEHTA RETAIL-INV S100", "N123", "0", "11800.00"),
                         (5, "BANK CHARGES QTR", "", "590.00", "0"),
                         (6, "SALARY FOR MONTH", "", "25000.00", "0"),
                         (7, "ATM WDL CASH", "", "5000.00", "0"),
                         (8, "GST CHALLAN CPIN 123", "", "3000.00", "0"),
                         (9, "UNKNOWN XYZ", "", "777.00", "0")])
    stats, parsed = _import(env, bank, csv)
    assert stats == {"imported": 6, "duplicates": 0} and not parsed["warnings"]
    cats = {t["narration"][:10]: t["category"] for t in bs.list_transactions(env.a_admin, env.c_a1)}
    assert cats["BANK CHARG"] == "bank_charges" and cats["SALARY FOR"] == "salary"
    assert cats["ATM WDL CA"] == "transfer" and cats["GST CHALLA"] == "tax_payment"


def test_exact_partial_and_unmatched(env, bank):
    add_invoice(env, env.c_a1, category="sales", no="S100", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="10000", cgst="900", sgst="900")
    add_invoice(env, env.c_a1, category="sales", no="S101", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="20000", cgst="1800", sgst="1800",
                date=D1)
    add_invoice(env, env.c_a1, no="P100", party="Sharma Steel", gstin=SUPPLIER_MH, taxable="5000", cgst="450", sgst="450")
    csv = statement_csv([(10, "NEFT-MEHTA RETAIL-INV S100", "N1", "0", "11800.00"),
                         (12, "NEFT MEHTA RETAIL PART", "N2", "0", "10000.00"),
                         (13, "RTGS SHARMA STEEL", "R1", "5900.00", "0"),
                         (14, "RANDOM CREDIT ABC", "", "0", "123.45")])
    _import(env, bank, csv)
    stats = bs.auto_match(env.a_admin, env.c_a1)
    txns = {t["reference"] or t["narration"]: t for t in bs.list_transactions(env.a_admin, env.c_a1)}
    assert txns["N1"]["match_status"] == "matched"
    assert txns["N2"]["match_status"] == "partially_matched"
    assert txns["R1"]["match_status"] == "matched"
    assert txns["RANDOM CREDIT ABC"]["match_status"] == "suspense"
    assert stats["matched"] == 2


def test_manual_match_and_vouchers_and_brs(env, bank):
    inv_id, _ = add_invoice(env, env.c_a1, category="sales", no="S200", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="10000",
                            cgst="900", sgst="900")
    csv = statement_csv([(10, "CHQ DEP 445566", "445566", "0", "5000.00"),
                         (11, "BANK CHARGES", "", "100.00", "0")], opening="0.00")
    _import(env, bank, csv)
    t1, t2 = bs.list_transactions(env.a_admin, env.c_a1)
    # allocating only part of the bank amount -> partially matched; full allocation -> matched
    assert bs.confirm_match(env.a_admin, t1["id"], [{"target_type": "invoice", "target_id": inv_id, "amount": "3000"}]) == "partially_matched"
    assert bs.confirm_match(env.a_admin, t1["id"], [{"target_type": "invoice", "target_id": inv_id, "amount": "5000"}]) == "matched"
    with pytest.raises(ValueError):
        bs.confirm_match(env.a_admin, t1["id"], [{"target_type": "invoice", "target_id": inv_id, "amount": "99999"}])
    res = bs.generate_vouchers(env.a_admin, env.c_a1, [t1["id"], t2["id"]])
    assert res["created"] == 2, res
    for t in bs.list_transactions(env.a_admin, env.c_a1):
        v = get_db().get("accounting_vouchers", t["voucher_id"])
        ae.approve_voucher(env.a_admin, v["id"], acknowledge_review=True)
    rec = bs.reconciliation(env.a_admin, env.c_a1, bank, D1.replace(day=28))
    assert rec["statement_balance"] == D("4900.00")
    assert rec["book_balance"] == D("4900.00")
    assert rec["difference"] == 0 and not rec["not_in_books"]


def test_brs_shows_unreconciled_items(env, bank):
    acct = get_db().get("bank_accounts", bank)
    leds = {l["name"]: l["id"] for l in ae.list_ledgers(env.a_admin, env.c_a1)}
    # cheque issued in books but not yet presented
    vid = ae.create_voucher(env.a_admin, env.c_a1, ae.VoucherDraft("Payment", D1, [ae.Line(leds["Rent"], "Dr", D("2000")),
                                                                                  ae.Line(acct["ledger_id"], "Cr", D("2000"))]))
    ae.approve_voucher(env.a_admin, vid)
    _import(env, bank, statement_csv([(5, "INTEREST CREDIT", "", "0", "50.00")], opening="0.00"))
    rec = bs.reconciliation(env.a_admin, env.c_a1, bank, D1.replace(day=28))
    assert rec["pending_payments_total"] == D("2000") and rec["bank_credits_not_in_books"] == D("50")
    assert rec["adjusted_bank_balance"] == rec["adjusted_book_balance"] and rec["difference"] == 0


def test_duplicate_transactions(env, bank):
    csv = statement_csv([(3, "NEFT ABC", "X1", "0", "100.00")])
    s1, _ = _import(env, bank, csv)
    s2, _ = _import(env, bank, csv)
    assert s1["imported"] == 1 and s2["duplicates"] == 1
    statuses = [t["match_status"] for t in bs.list_transactions(env.a_admin, env.c_a1)]
    assert statuses.count("duplicate") == 1
    dup = next(t for t in bs.list_transactions(env.a_admin, env.c_a1) if t["match_status"] == "duplicate")
    assert bs.generate_vouchers(env.a_admin, env.c_a1, [dup["id"]])["skipped"] == 1


def test_balance_continuity_warning():
    import pandas as pd

    df = pd.DataFrame({"Date": ["01/04/2025", "02/04/2025"], "Narration": ["a", "b"], "Debit": ["0", "10"],
                       "Credit": ["100", "0"], "Balance": ["100", "999"]})
    parsed = bs.parse_statement_table(df)
    assert parsed["warnings"] and "does not follow" in parsed["warnings"][0]


def test_pdf_statement_parsing():
    text = ("Opening Balance: 1,000.00\n01/04/2025 NEFT CR MEHTA 500.00 1,500.00\n02/04/2025 ATM WDL 200.00 1,300.00\n")
    p = bs.parse_statement_text(text)
    assert [(t["debit"], t["credit"]) for t in p["transactions"]] == [("0.00", "500.00"), ("200.00", "0.00")]


def test_bank_statement_document_flow(env, bank):
    csv = statement_csv([(3, "NEFT ABC", "X1", "0", "100.00")])
    doc = ds.upload_document(env.cu_a1, env.c_a1, D1.year, D1.month, "stmt.csv", csv, "bank_statement")
    assert ds.process_document(env.a_admin, doc) == "processed"
    parsed = ds.current_extraction(env.a_admin, doc)["data"]
    bs.import_statement(env.a_admin, env.c_a1, bank, parsed, document_id=doc)
    assert get_db().get("documents", doc)["status"] == "approved"
