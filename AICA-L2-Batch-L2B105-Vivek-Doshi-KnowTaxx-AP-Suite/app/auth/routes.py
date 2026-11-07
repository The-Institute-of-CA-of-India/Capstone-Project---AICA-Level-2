"""Login, logout, forced password change, account lockout."""
from datetime import timedelta
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import User, db, utcnow
from ..utils import audit
from .forms import ChangePasswordForm, LoginForm

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Compared when the username is unknown, so response time does not reveal which usernames exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method="pbkdf2:sha256")


def _safe_next(target):
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        now = utcnow()
        if user and user.locked_until and user.locked_until > now:
            minutes = int((user.locked_until - now).total_seconds() // 60) + 1
            audit("login", "user", user.id, {"result": "blocked_locked"}, user_id=user.id)
            db.session.commit()
            flash(f"Account locked after repeated failures. Try again in {minutes} minute(s).", "danger")
        elif user and user.is_active and user.check_password(form.password.data):
            user.failed_logins = 0
            user.locked_until = None
            user.last_login = now
            session.clear()
            session.permanent = True
            login_user(user)
            audit("login", "user", user.id, {"result": "success"})
            db.session.commit()
            return redirect(_safe_next(request.args.get("next")) or url_for("main.index"))
        else:
            if user:
                user.failed_logins += 1
                if user.failed_logins >= current_app.config["MAX_FAILED_LOGINS"]:
                    user.locked_until = now + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
                    user.failed_logins = 0
                audit("login", "user", user.id, {"result": "failed"}, user_id=user.id)
            else:
                check_password_hash(_DUMMY_HASH, form.password.data)
                audit("login", "user", None, {"result": "failed_unknown_user"})
            db.session.commit()
            flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    audit("logout", "user", current_user.id)
    db.session.commit()
    logout_user()
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Current password is incorrect.")
        else:
            current_user.set_password(form.new_password.data)
            current_user.must_change_password = False
            audit("update", "user", current_user.id, {"field": "password"})
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/change_password.html", form=form)
