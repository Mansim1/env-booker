# app/audit/routes.py
from flask import Blueprint, abort, render_template
from flask_login import login_required, current_user
from app.models import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/audit-log")

@audit_bp.route("/", methods=["GET"])
@login_required
def list_audit():
    if current_user.role != "admin":
        abort(403)
    # newest first
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template("audit/list.html", logs=logs)
