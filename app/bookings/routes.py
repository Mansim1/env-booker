from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.bookings.forms import BookingForm
from app.bookings.service import BookingService
from app.models import Environment, Booking

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")

@bookings_bp.route("/", methods=["GET"])
@login_required
def list_bookings():
    if current_user.role == "admin":
        bookings = Booking.query.order_by(Booking.start).all()
    else:
        bookings = (
            Booking.query
            .filter_by(user_id=current_user.id)
            .order_by(Booking.start)
            .all()
        )
    return render_template("bookings/list.html", bookings=bookings)


@bookings_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_booking():
    form = BookingForm()
    if form.validate_on_submit():
        env = db.session.get(Environment, form.environment.data)
        if env is None:
            abort(404)

        ok, result = BookingService.create_booking(
            user=current_user,
            environment=env,
            start=form.start.data,
            end=form.end.data
        )
        if not ok:
            flash(result, "danger")
            return redirect(url_for("bookings.create_booking"))

        booking = result
        flash(
            f"Booking confirmed: {env.name} from "
            f"{booking.start.strftime('%Y-%m-%d %H:%M')} to "
            f"{booking.end.strftime('%Y-%m-%d %H:%M')}.",
            "success"
        )
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/form.html", form=form)
