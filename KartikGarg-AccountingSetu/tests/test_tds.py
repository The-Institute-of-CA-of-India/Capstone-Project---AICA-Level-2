import datetime as dt

import pytest

from services import accounting_engine as ae, document_service as ds, tds_service as tds
from services.db import get_db
from tests.conftest import SUPPLIER_MH
from tests.helpers import add_invoice
from utils.helpers import D

TODAY = dt.date.today()
D1 = TODAY.replace(day=1)
PROF_PARTY = "Rao Professional Consultancy"  # matches the 194J "professional"/"consultancy" hint


def _make_deductor(env):
    get_db().update("clients", env.c_a1, {"is_tds_deductor": True, "tan": "MUMK12345A"})


def test_non_deductor_client_gets_no_tds_suggestion(env):
    inv_id, _ = add_invoice(env, env.c_a1, category="expense", no="E-TDS-1", party=PROF_PARTY, gstin=SUPPLIER_MH,
                            taxable="20000", cgst="1800", sgst="1800", approve=False)
    assert get_db().get("invoices", inv_id)["tds_status"] == "not_applicable"


def test_deductor_gets_pending_suggestion_with_section(env):
    _make_deductor(env)
    inv_id, _ = add_invoice(env, env.c_a1, category="expense", no="E-TDS-2", party=PROF_PARTY, gstin=SUPPLIER_MH,
                            taxable="50000", cgst="4500", sgst="4500", approve=False)
    inv = get_db().get("invoices", inv_id)
    assert inv["tds_status"] == "pending"
    assert inv["tds_section"] == "194J_PROF"


def test_set_tds_decision_computes_amount(env):
    _make_deductor(env)
    inv_id, _ = add_invoice(env, env.c_a1, category="expense", no="E-TDS-3", party=PROF_PARTY, gstin=SUPPLIER_MH,
                            taxable="50000", cgst="4500", sgst="4500", approve=False)
    tds.set_tds_decision(env.a_admin, inv_id, deduct=True, section="194J_PROF")
    inv = get_db().get("invoices", inv_id)
    assert inv["tds_status"] == "deducted" and D(inv["tds_amount"]) == D("5000.00")  # 10% of 50000
    tds.set_tds_decision(env.a_admin, inv_id, deduct=False)
    inv = get_db().get("invoices", inv_id)
    assert inv["tds_status"] == "not_deducted" and D(inv["tds_amount"]) == D("0")


def test_sales_invoices_never_get_tds(env):
    _make_deductor(env)
    from tests.conftest import CUSTOMER_MH

    inv_id, _ = add_invoice(env, env.c_a1, category="sales", no="S-TDS-1", party="Mehta", gstin=CUSTOMER_MH, taxable="50000",
                            cgst="4500", sgst="4500", approve=False)
    assert get_db().get("invoices", inv_id)["tds_status"] == "not_applicable"


def test_26q_preparation_groups_by_deductee(env):
    _make_deductor(env)
    inv1, v1 = add_invoice(env, env.c_a1, category="expense", no="E-TDS-4", party=PROF_PARTY, gstin=SUPPLIER_MH,
                           taxable="50000", cgst="4500", sgst="4500", approve=False)
    inv2, v2 = add_invoice(env, env.c_a1, category="expense", no="E-TDS-5", party=PROF_PARTY, gstin=SUPPLIER_MH,
                           taxable="30000", cgst="2700", sgst="2700", approve=False)
    tds.set_tds_decision(env.a_admin, inv1, deduct=True, section="194J_PROF")
    tds.set_tds_decision(env.a_admin, inv2, deduct=True, section="194J_PROF")
    ae.approve_voucher(env.a_admin, v1, acknowledge_review=True)
    ae.approve_voucher(env.a_admin, v2, acknowledge_review=True)
    q, fy = tds.quarter_for(D1.year, D1.month)
    prep = tds.prepare_26q(env.a_admin, env.c_a1, q, fy)
    assert prep["total_invoices"] == 2 and len(prep["deductees"]) == 1
    d = prep["deductees"][0]
    assert d["amount_paid"] == D("80000") and d["tds_deducted"] == D("8000.00")


def test_26q_save_approve_and_filing_workflow(env):
    _make_deductor(env)
    inv1, v1 = add_invoice(env, env.c_a1, category="expense", no="E-TDS-6", party=PROF_PARTY, gstin=SUPPLIER_MH,
                           taxable="50000", cgst="4500", sgst="4500", approve=False)
    tds.set_tds_decision(env.a_admin, inv1, deduct=True, section="194J_PROF")
    ae.approve_voucher(env.a_admin, v1, acknowledge_review=True)
    q, fy = tds.quarter_for(D1.year, D1.month)
    prep = tds.prepare_26q(env.a_admin, env.c_a1, q, fy)
    rid = tds.save_return(env.a_admin, env.c_a1, prep)
    with pytest.raises(ValueError):
        tds.record_external_filing(env.a_admin, rid, "ACKNO123456")
    tds.approve_return(env.a_admin, rid)
    tds.record_external_filing(env.a_admin, rid, "ACKNO123456")
    row = get_db().get("tds_returns", rid)
    assert row["status"] == "filed_externally" and row["external_ack_no"] == "ACKNO123456"
    assert tds.to_excel(prep)[:2] == b"PK"
