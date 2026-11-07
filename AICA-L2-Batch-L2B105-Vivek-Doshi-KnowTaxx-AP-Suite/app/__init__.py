"""Flask application factory."""
import json
import os
import warnings
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SAWarning

from config import Config, INSTANCE_DIR

from .models import Client, Invoice, User, Vendor, db, utcnow
from .utils import fmt_date, inr, ist

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"
csrf = CSRFProtect()

# SQLite stores NUMERIC as float; amounts are rounded to 2 places on every read and display.
warnings.filterwarnings("ignore", category=SAWarning, message=".*does \\*not\\* support Decimal.*")


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


@login_manager.user_loader
def _load_user(user_id):
    user = db.session.get(User, int(user_id))
    return user if user and user.is_active else None


@login_manager.unauthorized_handler
def _unauthorized():
    from flask import flash, redirect, url_for
    if request.path.startswith("/api/"):
        return jsonify(error="authentication required"), 401
    flash(login_manager.login_message, "info")
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def _bootstrap_admin(app):
    """First run on an empty database: create the admin with a temporary password."""
    if User.query.count() == 0:
        admin = User(username="admin", full_name="System Administrator", role="admin", must_change_password=True)
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()
        app.logger.warning("First run: created user 'admin' (see README). Password change is forced at first login.")


def create_app(overrides=None):
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["FILES_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BACKUP_ROOT"]).mkdir(parents=True, exist_ok=True)
    app.config["START_TIME"] = utcnow()

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    app.jinja_env.filters.update(inr=inr, ist=ist, fdate=fmt_date)
    app.jinja_env.filters["fromjson"] = lambda s: json.loads(s) if s else {}

    from .admin.routes import bp as admin_bp
    from .api.routes import bp as api_bp
    from .approvals.routes import bp as approvals_bp
    from .auth.routes import bp as auth_bp
    from .clients.routes import bp as clients_bp
    from .invoices.routes import bp as invoices_bp
    from .main_routes import bp as main_bp
    from .reports.routes import bp as reports_bp
    from .vendors.routes import bp as vendors_bp
    for blueprint in (main_bp, auth_bp, clients_bp, vendors_bp, invoices_bp, approvals_bp, reports_bp, admin_bp, api_bp):
        app.register_blueprint(blueprint)

    _register_hooks(app)

    with app.app_context():
        db.create_all()
        _bootstrap_admin(app)

    if app.config.get("EMAIL_LISTENER_ENABLED") and not os.environ.get("KTAP_NO_LISTENER"):
        from .email_listener.listener import start_listener
        start_listener(app)
    return app


def _register_hooks(app):
    @app.before_request
    def _force_password_change():
        from flask import redirect, url_for
        session.permanent = True
        if (current_user.is_authenticated and current_user.must_change_password
                and request.endpoint not in ("auth.change_password", "auth.logout", "static", "api.health",
                                             "main.manifest", "main.service_worker", "main.offline")):
            if request.path.startswith("/api/"):
                return jsonify(error="password change required"), 403
            return redirect(url_for("auth.change_password"))

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.context_processor
    def _inject_globals():
        ctx = {"app_version": app.config["VERSION"], "active_client": None, "my_clients": [],
               "pending_count": 0, "pending_vendor_count": 0, "review_count": 0}
        if not current_user.is_authenticated:
            return ctx
        view_args = request.view_args or {}
        if view_args.get("client_id"):
            session["active_client_id"] = view_args["client_id"]
        clients = current_user.accessible_clients()
        ctx["my_clients"] = clients
        active_id = session.get("active_client_id")
        ctx["active_client"] = next((c for c in clients if c.id == active_id), clients[0] if clients else None)
        ctx["pending_count"] = Invoice.query.filter_by(status="pending_approval",
                                                       current_approver_id=current_user.id).count()
        if current_user.role in ("admin", "manager", "accountant") and ctx["active_client"]:
            # These badges sit under the active client's heading in the sidebar
            client_id = ctx["active_client"].id
            ctx["pending_vendor_count"] = Vendor.query.filter_by(status="pending", client_id=client_id).count()
            ctx["review_count"] = Invoice.query.filter(Invoice.status.in_(("auto_captured", "pending_review")),
                                                       Invoice.client_id == client_id).count()
        return ctx

    def _error(code, title, message):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return render_template("error.html", code=code, title=title, message=message), code

    app.register_error_handler(403, lambda e: _error(403, "Access denied", "Your role does not allow this action."))
    app.register_error_handler(404, lambda e: _error(404, "Not found", "That page or record does not exist."))
    app.register_error_handler(413, lambda e: _error(413, "File too large", "The upload exceeds the size limit."))
    app.register_error_handler(CSRFError, lambda e: _error(400, "Session expired", "Please go back, refresh the page and try again."))

    @app.errorhandler(500)
    def _server_error(_e):
        db.session.rollback()
        return _error(500, "Something went wrong", "The error has been logged. Please try again.")
