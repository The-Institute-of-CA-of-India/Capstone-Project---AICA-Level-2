import datetime as dt
from decimal import Decimal

import pytest

from services import accounting_engine as ae, period_service, report_service
from services.db import get_db
from tests.conftest import CUSTOMER_DL, CUSTOMER_MH, SUPPLIER_KA, SUPPLIER_MH
from tests.helpers import add_invoice, lines_by_ledger
from utils.helpers import D, month_bounds
from utils.permissions import NotFound, PermissionDenied

TODAY = dt.date.today()
D1 = TODAY.replace(day=1)


def test_purchase_intrastate_entries(env):
    _, vid = add_invoice(env, env.c_a1, no="P1", gstin=SUPPLIER_MH, approve=False)
    v = get_db().get("accounting_vouchers", vid)
    assert v["voucher_type"] == "Purchase" and v["status"] == "draft"
    L = lines_by_ledger(vid)
    assert L["Purchases"] == ("Dr", D("10000"))
    assert L["Input CGST"] == ("Dr", D("900")) and L["Input SGST"] == ("Dr", D("900"))
    assert L["Sharma Steel"] == ("Cr", D("11800"))


def test_purchase_interstate_and_ineligible_itc(env):
    _, vid = add_invoice(env, env.c_a1, no="P2", gstin=SUPPLIER_KA, cgst="0", sgst="0", igst="1800", itc="ineligible", approve=False)
    L = lines_by_ledger(vid)
    assert L["Purchases"] == ("Dr", D("11800"))  # ineligible tax capitalised into cost
    assert "Input IGST" not in L


def test_sales_entries_and_round_off(env):
    _, vid = add_invoice(env, env.c_a1, category="sales", no="S1", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="999.50",
                         cgst="89.96", sgst="89.96", total="1179.42", approve=False)
    L = lines_by_ledger(vid)
    assert L["Mehta Retail"] == ("Dr", D("1179.42")) and L["Sales"] == ("Cr", D("999.50"))
    assert L["Output CGST"] == ("Cr", D("89.96"))


def test_sales_credit_note_reverses(env):
    _, vid = add_invoice(env, env.c_a1, category="sales", no="CN1", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="1000",
                         cgst="90", sgst="90", note_type="credit_note", approve=False)
    v = get_db().get("accounting_vouchers", vid)
    L = lines_by_ledger(vid)
    assert v["voucher_type"] == "Credit Note"
    assert L["Sales Returns"] == ("Dr", D("1000")) and L["Output CGST"] == ("Dr", D("90")) and L["Mehta Retail"] == ("Cr", D("1180"))


def test_reverse_charge_purchase(env):
    _, vid = add_invoice(env, env.c_a1, no="RCM1", party="Advocate Rao", gstin=SUPPLIER_MH, taxable="5000", cgst="450", sgst="450",
                         total="5000", rcm=True, approve=False)
    L = lines_by_ledger(vid)
    assert L["Purchases"] == ("Dr", D("5000")) and L["Input CGST"] == ("Dr", D("450"))
    assert L["RCM CGST Payable"] == ("Cr", D("450")) and L["Advocate Rao"] == ("Cr", D("5000"))
    assert get_db().get("accounting_vouchers", vid)["needs_review"]


def test_expense_head_classification(env):
    _, vid = add_invoice(env, env.c_a1, category="expense", no="E1", party="Airtel Broadband", gstin=SUPPLIER_MH, taxable="1000",
                         cgst="90", sgst="90", approve=False)
    assert lines_by_ledger(vid)["Telephone & Internet"] == ("Dr", D("1000"))


def test_balance_validation(env):
    leds = {l["name"]: l["id"] for l in ae.list_ledgers(env.a_admin, env.c_a1)}
    bad = ae.VoucherDraft("Journal", D1, [ae.Line(leds["Rent"], "Dr", D("100")), ae.Line(leds["Cash"], "Cr", D("90"))])
    with pytest.raises(ae.UnbalancedVoucher):
        ae.create_voucher(env.a_admin, env.c_a1, bad)
    with pytest.raises(ae.UnbalancedVoucher):
        ae.assert_balanced([ae.Line(leds["Rent"], "Dr", D("0")), ae.Line(leds["Cash"], "Cr", D("0"))])


def test_unbalanced_voucher_never_approved(env):
    _, vid = add_invoice(env, env.c_a1, no="P9", gstin=SUPPLIER_MH, approve=False)
    get_db().execute("update accounting_voucher_entries set amount = '1.00' where voucher_id = ? and line_no = 1", [vid])
    with pytest.raises(ae.UnbalancedVoucher):
        ae.approve_voucher(env.a_admin, vid, acknowledge_review=True)


def test_duplicate_voucher_prevention(env):
    inv_id, _ = add_invoice(env, env.c_a1, no="P3", gstin=SUPPLIER_MH, approve=False)
    with pytest.raises(ae.DuplicateVoucher):
        ae.post_invoice(env.a_admin, inv_id)


def test_voucher_numbering_sequential(env):
    _, v1 = add_invoice(env, env.c_a1, no="P4", gstin=SUPPLIER_MH, approve=False)
    _, v2 = add_invoice(env, env.c_a1, no="P5", gstin=SUPPLIER_MH, approve=False)
    n1, n2 = get_db().get("accounting_vouchers", v1)["voucher_no"], get_db().get("accounting_vouchers", v2)["voucher_no"]
    assert n1.startswith("PUR/") and int(n2[-5:]) == int(n1[-5:]) + 1


def test_needs_review_requires_acknowledgement_and_role(env):
    _, vid = add_invoice(env, env.c_a1, no="P6", gstin=None, party="Unknown Vendor", approve=False)
    assert get_db().get("accounting_vouchers", vid)["needs_review"]
    with pytest.raises(ae.AccountingError, match="flagged"):
        ae.approve_voucher(env.a_admin, vid)
    with pytest.raises(PermissionDenied):
        ae.approve_voucher(env.acct, vid, acknowledge_review=True)  # accountants prepare, not approve
    ae.approve_voucher(env.rev, vid, acknowledge_review=True)
    assert get_db().get("accounting_vouchers", vid)["status"] == "approved"


def test_ledger_mapping_change_is_used(env):
    new = ae.create_ledger(env.a_admin, env.c_a1, "Purchase of Steel", "Purchase Accounts")
    ae.set_mapping(env.a_admin, env.c_a1, "purchase_default", new)
    _, vid = add_invoice(env, env.c_a1, no="P7", gstin=SUPPLIER_MH, approve=False)
    assert "Purchase of Steel" in lines_by_ledger(vid)


def test_period_lock_blocks_changes_and_reopen(env):
    _, vid = add_invoice(env, env.c_a1, no="P8", gstin=SUPPLIER_MH)
    period_service.finalize_month(env.a_admin, env.c_a1, D1.year, D1.month, override_warnings=True)
    with pytest.raises(period_service.PeriodLocked):
        add_invoice(env, env.c_a1, no="P8b", gstin=SUPPLIER_MH, approve=False)
    with pytest.raises(period_service.PeriodLocked):
        ae.cancel_voucher(env.a_admin, vid, "test")
    with pytest.raises(PermissionDenied):
        period_service.reopen_month(env.acct, env.c_a1, D1.year, D1.month, "Need to correct purchase entries")
    with pytest.raises(ValueError):
        period_service.reopen_month(env.a_admin, env.c_a1, D1.year, D1.month, "short")
    period_service.reopen_month(env.a_admin, env.c_a1, D1.year, D1.month, "Supplier issued revised invoice")
    add_invoice(env, env.c_a1, no="P8c", gstin=SUPPLIER_MH, approve=False)
    row = period_service.period_row(env.c_a1, D1.year, D1.month)
    assert row["status"] == "reopened" and row["snapshot_hash"] and row["reopen_reason"]


def test_finalize_blocked_by_unapproved_vouchers(env):
    add_invoice(env, env.c_a1, no="P10", gstin=SUPPLIER_MH, approve=False)
    with pytest.raises(period_service.PeriodLocked, match="unapproved"):
        period_service.finalize_month(env.a_admin, env.c_a1, D1.year, D1.month, override_warnings=True)


def test_reports_trial_balance_pnl_and_provisional_bs(env):
    add_invoice(env, env.c_a1, category="sales", no="S10", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="50000", cgst="4500", sgst="4500")
    add_invoice(env, env.c_a1, no="P11", gstin=SUPPLIER_MH, taxable="30000", cgst="2700", sgst="2700")
    add_invoice(env, env.c_a1, category="expense", no="E2", party="City Rent Co", gstin=SUPPLIER_MH, taxable="5000", cgst="450",
                sgst="450", expense_head="exp:rent")
    s, e = month_bounds(D1.year, D1.month)
    tb = report_service.trial_balance(env.a_admin, env.c_a1, s, e)
    assert tb["difference"] == 0 and tb["total_debit"] > 0
    pnl = report_service.profit_and_loss(env.a_admin, env.c_a1, s, e)
    assert pnl["net_sales"] == D("50000") and pnl["net_purchases"] == D("30000")
    assert pnl["gross_profit"] == D("20000") and pnl["net_profit"] == D("15000")
    bs = report_service.balance_sheet(env.a_admin, env.c_a1, e)
    assert bs["is_provisional"] and any("Opening balances" in r for r in bs["provisional_reasons"])
    assert bs["total_assets"] == bs["total_liabilities"]


def test_balance_sheet_with_opening_balances_and_stock(env):
    leds = {l["name"]: l["id"] for l in ae.list_ledgers(env.a_admin, env.c_a1)}
    bank = ae.create_ledger(env.a_admin, env.c_a1, "HDFC Bank", "Bank Accounts")
    fy = report_service._fy(get_db().get("clients", env.c_a1), D1)[0]
    ae.set_opening_balance(env.a_admin, env.c_a1, fy, leds["Capital Account"], D("100000"), "Cr")
    ae.set_opening_balance(env.a_admin, env.c_a1, fy, bank, D("80000"), "Dr")
    ae.set_opening_balance(env.a_admin, env.c_a1, fy, leds["Stock-in-Hand"], D("20000"), "Dr")
    assert ae.opening_difference(env.c_a1, fy) == 0
    add_invoice(env, env.c_a1, no="P12", gstin=SUPPLIER_MH, taxable="10000", cgst="900", sgst="900")
    add_invoice(env, env.c_a1, category="sales", no="S12", party="Mehta Retail", gstin=CUSTOMER_MH, taxable="15000", cgst="1350", sgst="1350")
    _, e = month_bounds(D1.year, D1.month)
    ae.set_closing_stock(env.a_admin, env.c_a1, e, D("22000"))
    bs = report_service.balance_sheet(env.a_admin, env.c_a1, e)
    assert bs["difference"] == 0
    # P&L for FY to date: sales 15000 - (opening 20000 + purchases 10000 - closing 22000) = 7000
    assert bs["net_profit"] == D("7000")
    assert not any("Closing stock" in r for r in bs["provisional_reasons"])


def test_manual_journal_and_opening_balance_permissions(env):
    leds = {l["name"]: l["id"] for l in ae.list_ledgers(env.a_admin, env.c_a1)}
    vid = ae.manual_journal(env.acct, env.c_a1, D1, [{"ledger_id": leds["Depreciation"], "dr_cr": "Dr", "amount": "1000"},
                                                     {"ledger_id": leds["Suspense Account"], "dr_cr": "Cr", "amount": "1000"}],
                            "Depreciation provision")
    assert get_db().get("accounting_vouchers", vid)["status"] == "draft"
    with pytest.raises((PermissionDenied, NotFound)):
        ae.manual_journal(env.ro, env.c_a1, D1, [], "x")
