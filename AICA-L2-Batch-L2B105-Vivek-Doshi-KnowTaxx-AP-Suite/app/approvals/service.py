"""Approval routing engine, shared by web pages, the REST API and offline sync."""
from ..models import ApprovalLog, ApprovalMatrix, Invoice, db, utcnow
from ..utils import audit


class ApprovalError(Exception):
    pass


def matching_rules(invoice):
    """Applicable rule per level, most specific winning. Returns {level: rule}."""
    amount = float(invoice.final_total_amount or 0)
    rules = ApprovalMatrix.query.filter_by(client_id=invoice.client_id, is_active=True).all()
    best = {}
    for rule in rules:
        if float(rule.min_amount or 0) > amount:
            continue
        if rule.max_amount is not None and float(rule.max_amount) < amount:
            continue
        if rule.expense_category and rule.expense_category != invoice.expense_category:
            continue
        if rule.cost_centre_id and rule.cost_centre_id != invoice.cost_centre_id:
            continue
        if not rule.approver or not rule.approver.is_active:
            continue
        specificity = (1 if rule.expense_category else 0) + (1 if rule.cost_centre_id else 0)
        current = best.get(rule.approval_level)
        if current is None or specificity > current[0]:
            best[rule.approval_level] = (specificity, rule)
    return {level: pair[1] for level, pair in best.items()}


def _log(invoice, action, actor, comments=None):
    db.session.add(ApprovalLog(invoice_id=invoice.id, action=action, actor_id=actor.id, actor_role=actor.role,
                               level=invoice.current_level, comments=comments, acted_at=utcnow()))


def _move_to_level(invoice, level, rule):
    invoice.current_level = level
    invoice.current_approver_id = rule.approver_id
    invoice.level_entered_at = utcnow()


def submit_for_approval(invoice, actor):
    """Route to the first approval level. Returns False if no rule applies (status stays 'reviewed')."""
    rules = matching_rules(invoice)
    if not rules:
        return False
    first = min(rules)
    invoice.status = "pending_approval"
    invoice.submitted_at = utcnow()
    _move_to_level(invoice, first, rules[first])
    _log(invoice, "submitted", actor)
    audit("update", "invoice", invoice.id, {"action": "submitted", "approver_id": invoice.current_approver_id})
    return True


def can_act(invoice, user):
    return invoice.current_approver_id == user.id or user.role in ("admin", "manager")


def _check(invoice, user):
    if invoice.status != "pending_approval":
        raise ApprovalError("This invoice is not awaiting approval.")
    if not can_act(invoice, user):
        raise ApprovalError("This invoice is assigned to another approver.")


def approve(invoice, user, comments=None):
    """Approve the current level. Moves up a level if one remains. Returns True when fully approved."""
    _check(invoice, user)
    _log(invoice, "approved", user, comments)
    remaining = {lvl: rule for lvl, rule in matching_rules(invoice).items() if lvl > (invoice.current_level or 0)}
    if remaining:
        next_level = min(remaining)
        _move_to_level(invoice, next_level, remaining[next_level])
        audit("approve", "invoice", invoice.id, {"next_level": next_level})
        return False
    invoice.status = "approved"
    invoice.approved_by, invoice.approved_at = user.id, utcnow()
    invoice.current_approver_id = None
    audit("approve", "invoice", invoice.id, {"final": True, "comments": comments})
    return True


def reject(invoice, user, reason):
    _check(invoice, user)
    if not (reason or "").strip():
        raise ApprovalError("A reason is required to reject an invoice.")
    invoice.status = "rejected"
    invoice.rejected_by, invoice.rejected_at, invoice.rejection_reason = user.id, utcnow(), reason.strip()
    invoice.current_approver_id = None
    _log(invoice, "rejected", user, reason.strip())
    audit("reject", "invoice", invoice.id, {"reason": reason.strip()})


def query(invoice, user, comment):
    """Send back to the accountant with a question."""
    _check(invoice, user)
    if not (comment or "").strip():
        raise ApprovalError("Please write the question for the accountant.")
    invoice.status = "pending_review"
    invoice.current_approver_id = None
    invoice.current_level = 0
    invoice.notes = f"Query from {user.full_name}: {comment.strip()}"
    _log(invoice, "queried", user, comment.strip())
    audit("update", "invoice", invoice.id, {"action": "queried", "comment": comment.strip()})


def sla_stats(client_ids=None, approver_id=None):
    """Average approval time and items waiting beyond 24/48/72 hours, for clients or one approver."""
    pending = Invoice.query.filter_by(status="pending_approval")
    done = Invoice.query.filter(Invoice.approved_at.isnot(None), Invoice.submitted_at.isnot(None))
    if approver_id is not None:
        pending = pending.filter_by(current_approver_id=approver_id)
        done = done.filter(Invoice.logs.any(ApprovalLog.actor_id == approver_id))
    elif client_ids is not None:
        pending = pending.filter(Invoice.client_id.in_(client_ids))
        done = done.filter(Invoice.client_id.in_(client_ids))
    now = utcnow()
    ages = [(now - (i.submitted_at or i.updated_at or now)).total_seconds() / 3600 for i in pending]
    durations = [(i.approved_at - i.submitted_at).total_seconds() / 3600 for i in done]
    return {"pending": len(ages),
            "over_24": sum(1 for a in ages if a > 24), "over_48": sum(1 for a in ages if a > 48),
            "over_72": sum(1 for a in ages if a > 72),
            "avg_hours": round(sum(durations) / len(durations), 1) if durations else None}
