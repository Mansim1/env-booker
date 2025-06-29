from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import AuditLog

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

ACTION_LABELS = {
    "create_booking":       "Created booking",
    "accept_suggestion":    "Created suggested booking",
    "forced_single_book":   "Forced single booking",
    "create_series":        "Created series booking",
    "create_series_summary":"New Series summary",
    "forced_series_book":   "Forced series booking",
    "forced_series_booking_summary": "Forced series summary",
    "edit_booking":         "Edited booking",
    "forced_edit":          "Forced edit",
    "delete_booking":       "Deleted booking",
    "create_environment":   "Created new environment",
    "update_environment":   "Updated enviroment",
    "delete_environment":   "Deleted environment",
}

@audit_bp.route("/", methods=["GET"])
@login_required
def list_audit():

    action = request.args.get("action", type=str)

    q = (
        AuditLog.query
        .options(joinedload(AuditLog.actor))
        .filter(AuditLog.actor_id == current_user.id)
        .order_by(AuditLog.timestamp.desc())
    )
    if action:
        q = q.filter(AuditLog.action == action)

    logs = q.all()

    return render_template(
        "audit/list.html",
        logs=logs,
        action_labels=ACTION_LABELS
    )
