"""Home routing and root-scope PWA files."""
from flask import Blueprint, current_app, redirect, render_template, send_from_directory, url_for
from flask_login import current_user, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    if current_user.role == "approver":
        return redirect(url_for("approvals.pending"))
    if current_user.role == "field_staff":
        clients = current_user.accessible_clients()
        if clients:
            return redirect(url_for("invoices.upload", client_id=clients[0].id))
        return render_template("error.html", code=200, title="No client assigned",
                               message="Ask your administrator to assign you to a client.")
    return redirect(url_for("clients.list_clients"))


@bp.route("/manifest.json")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.json", mimetype="application/manifest+json")


@bp.route("/service-worker.js")
def service_worker():
    # Served from the root so the worker's scope covers the whole app.
    response = send_from_directory(current_app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "icons/favicon.ico")


@bp.route("/offline")
def offline():
    """Data-free shell, cached by the service worker. Its data lives in the device's IndexedDB."""
    return render_template("offline.html")
