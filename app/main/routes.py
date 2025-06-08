from datetime import datetime
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Booking

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Show dashboard with quick links and upcoming bookings."""
    now = datetime.utcnow()
    # Admin sees everyone’s bookings; regular users see only their own
    if current_user.role == "admin":
        upcoming = (
            Booking.query
            .filter(Booking.start >= now)
            .order_by(Booking.start)
            .limit(5)
            .all()
        )
    else:
        upcoming = (
            Booking.query
            .filter_by(user_id=current_user.id)
            .filter(Booking.start >= now)
            .order_by(Booking.start)
            .limit(5)
            .all()
        )

    return render_template(
        "main/index.html",
        user=current_user,
        upcoming=upcoming
    )
