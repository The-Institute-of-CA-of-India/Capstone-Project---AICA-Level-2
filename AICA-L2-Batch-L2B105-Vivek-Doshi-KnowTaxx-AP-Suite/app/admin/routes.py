"""User management, roles, audit log, email configuration, backup and system info."""
import re
import sys
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import or_, text

from ..email_listener.config import encrypt_password
from ..email_listener.listener import test_connection
from ..invoices.ocr_engine import tesseract_status
from ..models import AuditLog, Client, EmailConfig, User, db, utcnow
from ..utils import audit, paginate, roles_required
from .forms import EmailConfigForm, UserForm

bp = Blueprint("admin", __name__, url_prefix="/admin")
_admin_only = roles_required("admin")


def _client_choices():
    return [(c.id, f"{c.code} - {c.name}") for c in Client.query.filter_by(is_archived=False).order_by(Client.code)]


@bp.route("/users")
@_admin_only
def users():
    return render_template("admin/users.html", users=User.query.order_by(User.username).all())


@bp.route("/users/new", methods=["GET", "POST"])
@_admin_only
def new_user():
    form = UserForm()
    form.client_ids.choices = _client_choices()
    if form.validate_on_submit():
        if not form.temp_password.data:
            form.temp_password.errors = ["A temporary password is required for a new user."]
        elif User.query.filter_by(username=form.username.data).first():
            form.username.errors = list(form.username.errors) + ["This username is taken."]
        else:
            user = User(username=form.username.data, must_change_password=True)
            _apply_user(form, user)
            user.set_password(form.temp_password.data)
            db.session.add(user)
            db.session.flush()
            audit("create", "user", user.id, {"username": user.username, "role": user.role})
            db.session.commit()
            flash(f"User {user.username} created. They must change the password at first login.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form, user=None)


def _apply_user(form, user):
    user.full_name, user.email, user.phone, user.role = form.full_name.data, form.email.data, form.phone.data, form.role.data
    user.is_active = form.is_active.data
    user.clients = Client.query.filter(Client.id.in_(form.client_ids.data or [])).all()


def _last_active_admin(user):
    return user.role == "admin" and User.query.filter_by(role="admin", is_active=True).count() <= 1


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@_admin_only
def edit_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = UserForm(obj=user)
    form.client_ids.choices = _client_choices()
    if request.method == "GET":
        form.client_ids.data = [c.id for c in user.clients]
    if form.validate_on_submit():
        duplicate = User.query.filter_by(username=form.username.data).first()
        if duplicate and duplicate.id != user.id:
            form.username.errors = list(form.username.errors) + ["This username is taken."]
        elif _last_active_admin(user) and (form.role.data != "admin" or not form.is_active.data):
            flash("This is the last active administrator, so it cannot be demoted or deactivated.", "danger")
        else:
            old_role = user.role
            user.username = form.username.data
            _apply_user(form, user)
            details = {"role_from": old_role, "role_to": user.role, "is_active": user.is_active}
            if form.temp_password.data:
                user.set_password(form.temp_password.data)
                user.must_change_password = True
                user.failed_logins, user.locked_until = 0, None
                details["password_reset"] = True
            audit("update", "user", user.id, details)
            db.session.commit()
            flash("User updated.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form, user=user)


@bp.route("/users/<int:user_id>/unlock", methods=["POST"])
@_admin_only
def unlock_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    user.failed_logins, user.locked_until = 0, None
    audit("update", "user", user.id, {"action": "unlock"})
    db.session.commit()
    flash(f"{user.username} unlocked.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/roles")
@_admin_only
def roles():
    return render_template("admin/roles.html")


@bp.route("/audit-log")
@roles_required("admin", "manager")
def audit_log():
    term = request.args.get("q", "").strip()
    action = request.args.get("action", "")
    query = AuditLog.query.outerjoin(User, AuditLog.user_id == User.id)
    if action:
        query = query.filter(AuditLog.action == action)
    if term:
        like = f"%{term}%"
        query = query.filter(or_(User.username.ilike(like), AuditLog.entity_type.ilike(like),
                                 AuditLog.details.ilike(like), AuditLog.ip_address.ilike(like)))
    page = paginate(query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()), per_page=50)
    actions = [a for (a,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action)]
    return render_template("admin/audit_log.html", page=page, term=term, action=action, actions=actions)


@bp.route("/email-config", methods=["GET", "POST"])
@_admin_only
def email_config():
    form = EmailConfigForm()
    form.client_id.choices = _client_choices()
    selected_id = request.args.get("client", type=int)
    if request.method == "GET" and selected_id:
        config = EmailConfig.query.filter_by(client_id=selected_id).first()
        form.client_id.data = selected_id
        if config:
            form.imap_server.data, form.imap_port.data = config.imap_server, config.imap_port
            form.email_address.data, form.poll_interval_minutes.data = config.email_address, config.poll_interval_minutes
            form.is_active.data = config.is_active
    if form.validate_on_submit():
        config = EmailConfig.query.filter_by(client_id=form.client_id.data).first() or EmailConfig(client_id=form.client_id.data)
        config.imap_server, config.imap_port = form.imap_server.data, form.imap_port.data
        config.email_address, config.poll_interval_minutes = form.email_address.data, form.poll_interval_minutes.data
        config.is_active = form.is_active.data
        if form.email_password.data:
            config.email_password_encrypted = encrypt_password(form.email_password.data)
        if config.is_active and not config.email_password_encrypted:
            form.email_password.errors = ["Enter a password before activating the listener."]
        else:
            config.last_error = None
            db.session.add(config)
            db.session.flush()
            audit("update", "email_config", config.id, {"client_id": config.client_id, "is_active": config.is_active})
            db.session.commit()
            flash("Email settings saved.", "success")
            return redirect(url_for("admin.email_config", client=config.client_id))
    configs = EmailConfig.query.join(Client).order_by(Client.code).all()
    return render_template("admin/email_config.html", form=form, configs=configs)


@bp.route("/email-config/test", methods=["POST"])
@_admin_only
def email_test():
    form = EmailConfigForm()
    form.client_id.choices = _client_choices()
    password = form.email_password.data
    if not password:
        from ..email_listener.config import decrypt_password
        saved = EmailConfig.query.filter_by(client_id=form.client_id.data).first()
        password = decrypt_password(saved.email_password_encrypted) if saved and saved.email_password_encrypted else None
    if not password:
        flash("Enter the password to test the connection.", "danger")
    else:
        ok, message = test_connection(form.imap_server.data, form.imap_port.data, form.email_address.data, password)
        flash(message, "success" if ok else "danger")
    return redirect(url_for("admin.email_config", client=form.client_id.data))


def _backup_root():
    root = Path(current_app.config["BACKUP_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _directory_size(path):
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) if Path(path).exists() else 0


def _human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@bp.route("/backup")
@_admin_only
def backup():
    files = sorted(_backup_root().glob("apsuite_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    rows = [{"name": f.name, "size": _human(f.stat().st_size),
             "when": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %Y %H:%M")} for f in files]
    db_path = Path(db.engine.url.database)
    started = current_app.config["START_TIME"]
    seconds = int((utcnow() - started).total_seconds())
    info = {"version": current_app.config["VERSION"], "uptime": f"{seconds // 86400}d {seconds % 86400 // 3600}h {seconds % 3600 // 60}m",
            "db_size": _human(db_path.stat().st_size) if db_path.exists() else "-",
            "file_size": _human(_directory_size(current_app.config["FILES_ROOT"])),
            "backup_dir": str(_backup_root()), "ocr": tesseract_status(), "python": sys.version.split()[0]}
    return render_template("admin/backup.html", backups=rows, info=info)


@bp.route("/backup/run", methods=["POST"])
@_admin_only
def run_backup():
    target = _backup_root() / f"apsuite_{utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM INTO :path"), {"path": str(target)})
    audit("create", "backup", None, {"file": target.name})
    db.session.commit()
    flash(f"Backup created: {target.name}", "success")
    return redirect(url_for("admin.backup"))


@bp.route("/backup/<name>")
@_admin_only
def download_backup(name):
    if not re.fullmatch(r"apsuite_\d{8}_\d{6}\.db", name):
        abort(404)
    path = _backup_root() / name
    if not path.exists():
        abort(404)
    audit("download", "backup", None, {"file": name})
    db.session.commit()
    return send_file(path, as_attachment=True, download_name=name)
