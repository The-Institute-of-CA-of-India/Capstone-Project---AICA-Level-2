"""Client master, cost centres and budgets."""
import uuid
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from ..models import SPEND_STATUSES, Budget, Client, CostCentre, Invoice, Vendor, db
from ..utils import audit, get_client_or_403, lan_base_url, next_code, paginate, roles_required, to_decimal
from .forms import BudgetForm, ClientForm, CostCentreForm

bp = Blueprint("clients", __name__, url_prefix="/clients")
OFFICE_ROLES = ("admin", "manager", "accountant")


@bp.route("")
@roles_required(*OFFICE_ROLES)
def list_clients():
    show_archived = request.args.get("archived") == "1"
    term = request.args.get("q", "").strip()
    query = Client.query.filter_by(is_archived=show_archived)
    if not current_user.sees_all_clients:
        query = query.filter(Client.id.in_([c.id for c in current_user.clients]))
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Client.name.ilike(like), Client.code.ilike(like), Client.gstin.ilike(like), Client.pan.ilike(like)))
    page = paginate(query.order_by(Client.code))
    ids = [c.id for c in page.items]
    stats = {cid: {"vendors": 0, "invoices": 0, "pending": 0} for cid in ids}
    for cid, count in db.session.query(Vendor.client_id, func.count()).filter(Vendor.client_id.in_(ids)).group_by(Vendor.client_id):
        stats[cid]["vendors"] = count
    for cid, status, count in db.session.query(Invoice.client_id, Invoice.status, func.count()).filter(
            Invoice.client_id.in_(ids)).group_by(Invoice.client_id, Invoice.status):
        stats[cid]["invoices"] += count
        if status == "pending_approval":
            stats[cid]["pending"] = count
    return render_template("clients/list.html", page=page, stats=stats, term=term, show_archived=show_archived)


@bp.route("/new", methods=["GET", "POST"])
@roles_required("admin", "manager")
def new_client():
    form = ClientForm()
    if form.validate_on_submit():
        code = next_code("C", [c for (c,) in db.session.query(Client.code)])
        client = Client(code=code, email_alias=code.lower(), vendor_registration_token=str(uuid.uuid4()))
        form.populate_obj(client)
        db.session.add(client)
        db.session.flush()
        audit("create", "client", client.id, {"code": code, "name": client.name})
        db.session.commit()
        flash(f"Client {code} created. Share the vendor registration link below.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", form=form, client=None)


@bp.route("/<int:client_id>")
@roles_required(*OFFICE_ROLES)
def detail(client_id):
    client = get_client_or_403(client_id)
    today = date.today()
    month_start = today.replace(day=1)
    spend = db.session.query(func.coalesce(func.sum(Invoice.final_total_amount), 0)).filter(
        Invoice.client_id == client_id, Invoice.status.in_(SPEND_STATUSES), Invoice.is_duplicate_flag.is_(False),
        Invoice.final_invoice_date >= month_start).scalar()
    stats = {
        "vendors": client.vendors.filter(Vendor.status != "archived").count(),
        "pending_vendors": client.vendors.filter_by(status="pending").count(),
        "invoices": client.invoices.count(),
        "pending": client.invoices.filter_by(status="pending_approval").count(),
        "to_review": client.invoices.filter(Invoice.status.in_(("auto_captured", "pending_review"))).count(),
        "spend": spend,
    }
    registration_url = lan_base_url() + url_for("vendors.register_public", token=client.vendor_registration_token)
    recent = client.invoices.order_by(Invoice.created_at.desc()).limit(8).all()
    return render_template("clients/detail.html", client=client, stats=stats, registration_url=registration_url, recent=recent)


@bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "manager")
def edit(client_id):
    client = get_client_or_403(client_id)
    form = ClientForm(obj=client)
    if form.validate_on_submit():
        form.populate_obj(client)
        audit("update", "client", client.id, {"name": client.name})
        db.session.commit()
        flash("Client updated.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", form=form, client=client)


@bp.route("/<int:client_id>/archive", methods=["POST"])
@roles_required("admin", "manager")
def archive(client_id):
    client = get_client_or_403(client_id)
    client.is_archived = not client.is_archived
    audit("update", "client", client.id, {"is_archived": client.is_archived})
    db.session.commit()
    flash(f"{client.name} {'archived' if client.is_archived else 'restored'}.", "info")
    return redirect(url_for("clients.list_clients", archived="1" if not client.is_archived else None))


@bp.route("/<int:client_id>/regenerate-link", methods=["POST"])
@roles_required("admin", "manager", "accountant")
def regenerate_link(client_id):
    client = get_client_or_403(client_id)
    client.vendor_registration_token = str(uuid.uuid4())
    audit("update", "client", client.id, {"field": "vendor_registration_token"})
    db.session.commit()
    flash("New registration link generated. The old link no longer works.", "info")
    return redirect(url_for("clients.detail", client_id=client.id))


# ---- Cost centres --------------------------------------------------------------

def _parent_choices(client_id, exclude_id=None):
    centres = CostCentre.query.filter_by(client_id=client_id).order_by(CostCentre.code).all()
    return [(0, "- None (top level) -")] + [(c.id, f"{c.code} - {c.name}") for c in centres if c.id != exclude_id]


def _creates_cycle(centre, parent_id):
    seen = db.session.get(CostCentre, parent_id) if parent_id else None
    while seen is not None:
        if seen.id == centre.id:
            return True
        seen = seen.parent
    return False


@bp.route("/<int:client_id>/cost-centres", methods=["GET", "POST"])
@roles_required(*OFFICE_ROLES)
def cost_centres(client_id):
    client = get_client_or_403(client_id)
    edit_id = request.args.get("edit", type=int)
    centre = CostCentre.query.filter_by(id=edit_id, client_id=client_id).first() if edit_id else None
    form = CostCentreForm(obj=centre) if centre else CostCentreForm()
    form.parent_id.choices = _parent_choices(client_id, centre.id if centre else None)
    if request.method == "GET" and centre:
        form.parent_id.data = centre.parent_id or 0
    if form.validate_on_submit():
        duplicate = CostCentre.query.filter_by(client_id=client_id, code=form.code.data).first()
        if duplicate and (not centre or duplicate.id != centre.id):
            form.code.errors.append("This code is already used.")
        elif centre and _creates_cycle(centre, form.parent_id.data):
            form.parent_id.errors.append("A cost centre cannot sit under its own child.")
        else:
            target = centre or CostCentre(client_id=client_id)
            target.code, target.name = form.code.data, form.name.data
            target.parent_id = form.parent_id.data or None
            target.is_active = form.is_active.data
            db.session.add(target)
            db.session.flush()
            audit("update" if centre else "create", "cost_centre", target.id, {"code": target.code})
            db.session.commit()
            flash("Cost centre saved.", "success")
            return redirect(url_for("clients.cost_centres", client_id=client_id))
    centres = CostCentre.query.filter_by(client_id=client_id).order_by(CostCentre.code).all()
    return render_template("clients/cost_centres.html", client=client, form=form, centres=centres, editing=centre)


# ---- Budgets -------------------------------------------------------------------

@bp.route("/<int:client_id>/budgets", methods=["GET", "POST"])
@roles_required(*OFFICE_ROLES)
def budgets(client_id):
    client = get_client_or_403(client_id)
    form = BudgetForm()
    centres = CostCentre.query.filter_by(client_id=client_id, is_active=True).order_by(CostCentre.code).all()
    form.cost_centre_id.choices = [(c.id, f"{c.code} - {c.name}") for c in centres]
    today = date.today()
    if request.method == "GET":
        form.period_year.data, form.period_month.data = today.year, today.month
    if form.validate_on_submit():
        budget = Budget.query.filter_by(client_id=client_id, cost_centre_id=form.cost_centre_id.data,
                                        period_year=form.period_year.data, period_month=form.period_month.data).first()
        created = budget is None
        if created:
            budget = Budget(client_id=client_id, cost_centre_id=form.cost_centre_id.data,
                            period_year=form.period_year.data, period_month=form.period_month.data)
            db.session.add(budget)
        budget.budget_amount = to_decimal(form.budget_amount.data)
        budget.gl_account, budget.notes = form.gl_account.data, form.notes.data
        db.session.flush()
        audit("create" if created else "update", "budget", budget.id, {"amount": str(budget.budget_amount)})
        db.session.commit()
        flash("Budget saved.", "success")
        return redirect(url_for("clients.budgets", client_id=client_id))
    rows = Budget.query.filter_by(client_id=client_id).order_by(
        Budget.period_year.desc(), Budget.period_month.desc(), Budget.cost_centre_id).limit(120).all()
    return render_template("clients/budgets.html", client=client, form=form, rows=rows)
