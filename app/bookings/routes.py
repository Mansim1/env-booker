from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.bookings.forms import BookingForm
from app.bookings.service import BookingService
from app.models import Environment, Booking

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")

@bookings_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_booking():
    form = BookingForm()
    if form.validate_on_submit():
        env = Environment.query.get_or_404(form.environment.data)
        ok, result = BookingService.create_booking(
            user=current_user,
            environment=env,
            start=form.start.data,
            end=form.end.data
        )
        if not ok:
            flash(result, "danger")
        else:
            booking = result
            flash(
                f"Booking confirmed: {env.name} from "
                f"{booking.start.strftime('%Y-%m-%d %H:%M')} to "
                f"{booking.end.strftime('%Y-%m-%d %H:%M')}.",
                "success"
            )
            return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html", form=form)
