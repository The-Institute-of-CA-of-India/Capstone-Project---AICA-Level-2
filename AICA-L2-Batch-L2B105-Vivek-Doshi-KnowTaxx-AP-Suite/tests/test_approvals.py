from decimal import Decimal

import pytest
from conftest import login, make_centre, make_client, make_invoice, make_rule, make_user

from app.approvals import service
from app.approvals.service import ApprovalError, approve, matching_rules, query, reject, sla_stats, submit_for_approval
from app.models import ApprovalLog, db, utcnow


def setup_two_levels(c):
    first, second = make_user("first", "approver"), make_user("second", "manager")
    make_rule(c, first, 0, 10000)
    make_rule(c, first, 10000.01, 100000, level=1)
    make_rule(c, second, 10000.01, 100000, level=2)
    return first, second


def test_amount_picks_right_rules(app):
    c = make_client()
    first, second = setup_two_levels(c)
    small = make_invoice(c, total="5000")
    big = make_invoice(c, total="50000")
    too_big = make_invoice(c, total="500000")
    assert set(matching_rules(small)) == {1}
    assert set(matching_rules(big)) == {1, 2}
    assert matching_rules(too_big) == {}


def test_specific_rule_beats_general(app):
    c = make_client()
    general, special = make_user("general", "approver"), make_user("special", "approver")
    centre = make_centre(c)
    make_rule(c, general)
    make_rule(c, special, category="Rent", centre=centre)
    invoice = make_invoice(c, expense_category="Rent", cost_centre_id=centre.id)
    assert matching_rules(invoice)[1].approver_id == special.id
    other = make_invoice(c, expense_category="Travel & Conveyance")
    assert matching_rules(other)[1].approver_id == general.id


def test_inactive_approver_is_skipped(app):
    c = make_client()
    gone = make_user("gone", "approver")
    make_rule(c, gone)
    gone.is_active = False
    db.session.commit()
    assert matching_rules(make_invoice(c)) == {}


def test_multi_level_flow(app):
    c = make_client()
    first, second = setup_two_levels(c)
    invoice = make_invoice(c, total="50000")
    assert submit_for_approval(invoice, first)
    assert invoice.status == "pending_approval" and invoice.current_approver_id == first.id and invoice.current_level == 1
    assert approve(invoice, first) is False
    assert invoice.status == "pending_approval" and invoice.current_approver_id == second.id and invoice.current_level == 2
    assert approve(invoice, second) is True
    assert invoice.status == "approved" and invoice.current_approver_id is None and invoice.approved_by == second.id
    db.session.commit()
    assert [l.action for l in ApprovalLog.query.order_by(ApprovalLog.id)] == ["submitted", "approved", "approved"]


def test_wrong_approver_refused(app):
    c = make_client()
    first, second = setup_two_levels(c)
    stranger = make_user("stranger", "approver")
    invoice = make_invoice(c, total="5000")
    submit_for_approval(invoice, first)
    with pytest.raises(ApprovalError):
        approve(invoice, stranger)


def test_manager_can_act_on_any(app):
    c = make_client()
    first, second = setup_two_levels(c)
    invoice = make_invoice(c, total="5000")
    submit_for_approval(invoice, first)
    assert approve(invoice, second) is True


def test_reject_requires_reason(app):
    c = make_client()
    first, _ = setup_two_levels(c)
    invoice = make_invoice(c, total="5000")
    submit_for_approval(invoice, first)
    with pytest.raises(ApprovalError):
        reject(invoice, first, "   ")
    reject(invoice, first, "Wrong rate")
    assert invoice.status == "rejected" and invoice.rejection_reason == "Wrong rate"


def test_cannot_decide_twice(app):
    c = make_client()
    first, _ = setup_two_levels(c)
    invoice = make_invoice(c, total="5000")
    submit_for_approval(invoice, first)
    approve(invoice, first)
    with pytest.raises(ApprovalError):
        approve(invoice, first)


def test_query_returns_to_accountant(app):
    c = make_client()
    first, _ = setup_two_levels(c)
    invoice = make_invoice(c, total="5000")
    submit_for_approval(invoice, first)
    with pytest.raises(ApprovalError):
        query(invoice, first, "")
    query(invoice, first, "Which PO is this?")
    assert invoice.status == "pending_review" and invoice.current_approver_id is None
    assert "Which PO" in invoice.notes


def test_sla_counts(app):
    c = make_client()
    from datetime import timedelta
    now = utcnow()
    make_invoice(c, status="pending_approval", submitted_at=now - timedelta(hours=30))
    make_invoice(c, status="pending_approval", submitted_at=now - timedelta(hours=80))
    make_invoice(c, status="approved", submitted_at=now - timedelta(hours=10), approved_at=now)
    stats = sla_stats([c.id])
    assert stats["over_24"] == 2 and stats["over_48"] == 1 and stats["over_72"] == 1 and stats["avg_hours"] == 10.0


def test_sla_for_one_approver_counts_only_their_queue(app):
    from datetime import timedelta
    c = make_client()
    mine, other = make_user("mine", "approver"), make_user("other", "approver")
    now = utcnow()
    make_invoice(c, status="pending_approval", current_approver_id=mine.id, submitted_at=now - timedelta(hours=30))
    make_invoice(c, status="pending_approval", current_approver_id=other.id, submitted_at=now - timedelta(hours=80))
    stats = sla_stats(approver_id=mine.id)
    assert stats["over_24"] == 1 and stats["over_72"] == 0


def test_pending_page_and_buttons(client):
    c = make_client()
    approver = make_user("boss", "approver")
    make_rule(c, approver)
    invoice = make_invoice(c, status="pending_approval", current_approver_id=approver.id, current_level=1, submitted_at=utcnow())
    login(client, "boss")
    page = client.get("/approvals/pending")
    assert page.status_code == 200 and b"approval-card" in page.data
    assert client.get("/approvals/history").status_code == 200
    client.post(f"/approvals/{invoice.id}/reject", data={"comments": ""})
    db.session.refresh(invoice)
    assert invoice.status == "pending_approval"
    client.post(f"/approvals/{invoice.id}/approve", data={"comments": "OK"})
    db.session.refresh(invoice)
    assert invoice.status == "approved"


def test_approver_sees_only_own_queue(client):
    c = make_client()
    mine, other = make_user("mine", "approver"), make_user("other", "approver")
    make_invoice(c, status="pending_approval", current_approver_id=other.id, submitted_at=utcnow(), final_vendor_name="HiddenVendor")
    login(client, "mine")
    assert b"HiddenVendor" not in client.get("/approvals/pending").data


def test_matrix_crud_managers_only(client):
    c = make_client()
    approver = make_user("boss", "approver")
    make_user("mgr", "manager")
    make_user("acc", "accountant", [c])
    login(client, "acc")
    assert client.get(f"/clients/{c.id}/approval-matrix").status_code == 403
    client.post("/auth/logout")
    login(client, "mgr")
    assert client.get(f"/clients/{c.id}/approval-matrix").status_code == 200
    response = client.post(f"/clients/{c.id}/approval-matrix", data={"min_amount": "0", "max_amount": "1,00,000", "expense_category": "", "cost_centre_id": "0",
                                                                     "approver_id": approver.id, "approval_level": 1, "is_active": "y"})
    assert response.status_code == 302
    from app.models import ApprovalMatrix
    rule = ApprovalMatrix.query.one()
    assert rule.max_amount == Decimal("100000")
    client.post(f"/clients/{c.id}/approval-matrix/{rule.id}/delete")
    assert ApprovalMatrix.query.count() == 0


def test_service_module_exposes_can_act(app):
    c = make_client()
    approver = make_user("boss", "approver")
    invoice = make_invoice(c, current_approver_id=approver.id)
    assert service.can_act(invoice, approver)
