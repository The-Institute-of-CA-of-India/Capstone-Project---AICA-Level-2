"""Pending approvals, history, approval matrix, offline sync conflicts."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import ApprovalLog, ApprovalMatrix, CostCentre, Invoice, OfflineSyncQueue, User, db
from ..utils import audit, can_view_invoice, get_client_or_403, paginate, roles_required
from . import service
from .forms import MatrixRuleForm

bp = Blueprint("approvals", __name__, url_prefix="")
APPROVER_ROLES = ("admin", "manager", "approver")


def visible_pending():
    """Invoices this user should see: admins and managers see all, unless they filter to 'mine'."""
    query = Invoice.query.filter_by(status="pending_approval")
    if current_user.role in ("admin", "manager") and request.args.get("view") != "mine":
        return query
    return query.filter_by(current_approver_id=current_user.id)


@bp.route("/approvals/pending")
@roles_required(*APPROVER_ROLES, "accountant")
def pending():
    query = visible_pending()
    if current_user.role == "accountant":
        query = Invoice.query.filter(Invoice.status == "pending_approval", Invoice.current_approver_id == current_user.id)
    invoices = query.order_by(Invoice.submitted_at).all()
    if current_user.sees_all_clients:
        sla = service.sla_stats()
    else:
        sla = service.sla_stats(approver_id=current_user.id)
    conflicts = []
    if current_user.role in ("admin", "manager"):
        conflicts = OfflineSyncQueue.query.filter_by(sync_status="conflict", resolved=False).order_by(OfflineSyncQueue.synced_at.desc()).all()
    return render_template("approvals/pending.html", invoices=invoices, sla=sla, conflicts=conflicts, view=request.args.get("view", "all"))


@bp.route("/approvals/history")
@roles_required(*APPROVER_ROLES, "accountant")
def history():
    query = ApprovalLog.query.join(Invoice)
    if current_user.role == "approver":
        query = query.filter(ApprovalLog.actor_id == current_user.id)
    elif current_user.role == "accountant":
        query = query.filter(Invoice.client_id.in_([c.id for c in current_user.clients]))
    page = paginate(query.order_by(ApprovalLog.acted_at.desc()))
    return render_template("approvals/history.html", page=page)


def _act(invoice_id, action):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        abort(404)
    comment = request.form.get("comments", "").strip()
    try:
        if action == "approve":
            done = service.approve(invoice, current_user, comment or None)
            flash("Approved." if done else f"Approved. Sent to {invoice.current_approver.full_name} for level {invoice.current_level}.", "success")
        elif action == "reject":
            service.reject(invoice, current_user, comment)
            flash("Invoice rejected.", "info")
        else:
            service.query(invoice, current_user, comment)
            flash("Query sent to the accountant.", "info")
        db.session.commit()
    except service.ApprovalError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("approvals.pending"))


@bp.route("/approvals/<int:invoice_id>/approve", methods=["POST"])
@login_required
def approve(invoice_id):
    return _act(invoice_id, "approve")


@bp.route("/approvals/<int:invoice_id>/reject", methods=["POST"])
@login_required
def reject(invoice_id):
    return _act(invoice_id, "reject")


@bp.route("/approvals/<int:invoice_id>/query", methods=["POST"])
@login_required
def query_invoice(invoice_id):
    return _act(invoice_id, "query")


@bp.route("/approvals/conflicts/<int:item_id>/resolve", methods=["POST"])
@roles_required("admin", "manager")
def resolve_conflict(item_id):
    item = db.session.get(OfflineSyncQueue, item_id)
    if item is None:
        abort(404)
    item.resolved = True
    audit("update", "offline_sync", item.id, {"action": "conflict_resolved"})
    db.session.commit()
    flash("Conflict marked as resolved.", "success")
    return redirect(url_for("approvals.pending"))


@bp.route("/clients/<int:client_id>/approval-matrix", methods=["GET", "POST"])
@roles_required("admin", "manager")
def matrix(client_id):
    client = get_client_or_403(client_id)
    edit_id = request.args.get("edit", type=int)
    rule = ApprovalMatrix.query.filter_by(id=edit_id, client_id=client_id).first() if edit_id else None
    form = MatrixRuleForm(obj=rule) if rule else MatrixRuleForm()
    centres = CostCentre.query.filter_by(client_id=client_id, is_active=True).order_by(CostCentre.code).all()
    form.cost_centre_id.choices = [(0, "Any cost centre")] + [(c.id, f"{c.code} - {c.name}") for c in centres]
    approvers = User.query.filter(User.is_active.is_(True), User.role.in_(APPROVER_ROLES)).order_by(User.full_name).all()
    form.approver_id.choices = [(u.id, f"{u.full_name} ({u.role})") for u in approvers]
    if request.method == "GET" and rule:
        form.cost_centre_id.data = rule.cost_centre_id or 0
        form.expense_category.data = rule.expense_category or ""
    if form.validate_on_submit():
        target = rule or ApprovalMatrix(client_id=client_id)
        target.min_amount = form.min_amount.data or 0
        target.max_amount = form.max_amount.data
        target.expense_category = form.expense_category.data or None
        target.cost_centre_id = form.cost_centre_id.data or None
        target.approver_id, target.approval_level = form.approver_id.data, form.approval_level.data
        target.is_active = form.is_active.data
        db.session.add(target)
        db.session.flush()
        audit("update" if rule else "create", "approval_rule", target.id,
              {"min": str(target.min_amount), "max": str(target.max_amount), "approver": target.approver_id, "level": target.approval_level})
        db.session.commit()
        flash("Approval rule saved.", "success")
        return redirect(url_for("approvals.matrix", client_id=client_id))
    rules = ApprovalMatrix.query.filter_by(client_id=client_id).order_by(ApprovalMatrix.min_amount, ApprovalMatrix.approval_level).all()
    return render_template("approvals/matrix.html", client=client, form=form, rules=rules, editing=rule)


@bp.route("/clients/<int:client_id>/approval-matrix/<int:rule_id>/delete", methods=["POST"])
@roles_required("admin", "manager")
def delete_rule(client_id, rule_id):
    get_client_or_403(client_id)
    rule = ApprovalMatrix.query.filter_by(id=rule_id, client_id=client_id).first_or_404()
    audit("delete", "approval_rule", rule.id, {"min": str(rule.min_amount), "max": str(rule.max_amount), "approver": rule.approver_id})
    db.session.delete(rule)
    db.session.commit()
    flash("Rule deleted.", "info")
    return redirect(url_for("approvals.matrix", client_id=client_id))
