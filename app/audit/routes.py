from flask import Blueprint, abort, render_template, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import AuditLog
import json
from datetime import datetime

audit_bp = Blueprint("audit", __name__, url_prefix="/audit-log")

ACTION_LABELS = {
    "create_booking":       "Created booking",
    "forced_single_book":   "Forced single booking",
    "create_series":        "Created series",
    "forced_series_book":   "Forced series booking",
    "edit_booking":         "Edited booking",
    "forced_edit":          "Forced edit",
    "delete_booking":       "Deleted booking",
    "delete_environment":   "Deleted environment",
    # …etc.
}

@audit_bp.route("/", methods=["GET"])
@login_required
def list_audit():
    if current_user.role != "admin":
        abort(403)

    action = request.args.get("action", type=str)
    search = request.args.get("search", "", type=str).strip()

    q = (
        AuditLog.query
        .filter(AuditLog.actor_id == current_user.id)
        .options(joinedload(AuditLog.actor))
        .order_by(AuditLog.timestamp.desc())
    )
    if action:
        q = q.filter(AuditLog.action == action)
    if search:
        q = q.filter(AuditLog.details.ilike(f"%{search}%"))

    logs = q.all()

    # Parse JSON details into Python objects (and ISO→datetime)
    for entry in logs:
        pd = None
        if entry.details:
            try:
                raw = json.loads(entry.details)
                pd = {}
                for k, v in raw.items():
                    if k in ("start", "end") and isinstance(v, str):
                        try:
                            pd[k] = datetime.fromisoformat(v)
                        except ValueError:
                            pd[k] = v
                    else:
                        pd[k] = v
            except json.JSONDecodeError:
                pd = None
        entry.parsed_details = pd

    return render_template(
        "audit/list.html",
        logs=logs,
        action_labels=ACTION_LABELS
    )
