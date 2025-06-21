from datetime import datetime
from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import Booking, Environment, AuditLog

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Redirect to /dashboard if logged in, otherwise to the login page."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    else:
        return redirect(url_for("auth.login"))
    
    
@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Show dashboard with quick links and stats + upcoming bookings."""
    now = datetime.utcnow()
    today = now.date()

    # Base upcoming‐bookings query (admin sees all, user only their own)
    base_q = Booking.query.filter(Booking.start >= now)
    if current_user.role != "admin":
        base_q = base_q.filter_by(user_id=current_user.id)

    # Fetch next 5 upcoming slots
    upcoming = base_q.order_by(Booking.start).limit(5).all()

    # Stats
    upcoming_count = base_q.count()

    if current_user.role == "admin":
        env_count = Environment.query.count()
    else:
        # distinct environments in your upcoming
        env_count = (
            base_q.with_entities(Booking.environment_id)
                  .distinct()
                  .count()
        )

    # Hours booked today
    day_start = datetime.combine(today, datetime.min.time())
    day_end   = datetime.combine(today, datetime.max.time())
    day_q = Booking.query.filter(Booking.start >= day_start,
                                 Booking.start <= day_end)
    if current_user.role != "admin":
        day_q = day_q.filter_by(user_id=current_user.id)
    secs = day_q.with_entities(
        func.coalesce(
          func.sum(
            func.strftime('%s', Booking.end) - func.strftime('%s', Booking.start)
          ), 0
        )
    ).scalar() or 0
    hours_today = round(secs / 3600, 1)

    # Next booking for banner
    next_booking = upcoming[0] if upcoming else None

    # Recent activity (admin only)
    activity_feed = None
    if current_user.role == "admin":
        activity_feed = (
            AuditLog.query
            .order_by(AuditLog.timestamp.desc())
            .limit(5)
            .all()
        )

    return render_template(
        "main/index.html",
        user=current_user,
        upcoming=upcoming,
        upcoming_count=upcoming_count,
        env_count=env_count,
        hours_today=hours_today,
        next_booking=next_booking,
        activity_feed=activity_feed,
    )
