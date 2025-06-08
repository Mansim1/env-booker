# app/bookings/routes.py

from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, request
)
from flask_login import login_required, current_user
from markupsafe import Markup
from datetime import datetime
from app import db
from app.models import Environment, Booking
from app.bookings.forms import BookingForm, SeriesBookingForm
from app.bookings.service import BookingService

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


@bookings_bp.route("/")
@login_required
def list_bookings():
    q = Booking.query.order_by(Booking.start)
    if current_user.role != "admin":
        q = q.filter_by(user_id=current_user.id)
    return render_template("bookings/list.html", bookings=q.all())


@bookings_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_booking():
    form = BookingForm()
    force_flag = (request.args.get("force") == "true")
    is_admin   = (current_user.role == "admin")

    if form.validate_on_submit():
        env   = db.session.get(Environment, form.environment.data) or abort(404)
        start = form.start.data
        end   = form.end.data

        # Pass both accept_suggestion *and* force into the service:
        ok, result = BookingService.attempt_single_booking(
            user=current_user,
            environment=env,
            start=start,
            end=end,
            accept_suggestion=False,
            force=force_flag
        )

        if not ok:
            if result == "clash":
                flash(Markup(BookingService.single_suggestion_flash(env, start, end)), "info")
            else:
                flash(result, "danger")

            if is_admin and not force_flag and result == "clash":
                orig_start = start.strftime("%Y-%m-%dT%H:%M")
                orig_end   = end.strftime(  "%Y-%m-%dT%H:%M")
                return render_template(
                    "bookings/form.html",
                    form=form,
                    clash=True,
                    can_force=True,
                    orig_start=orig_start,
                    orig_end=orig_end
                )

            return redirect(url_for("bookings.create_booking"))

        b = result
        flash(
            f"Booking confirmed: {b.environment.name} from "
            f"{b.start.strftime('%Y-%m-%d %H:%M')} to {b.end.strftime('%Y-%m-%d %H:%M')}.",
            "success"
        )
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/form.html", form=form)


@bookings_bp.route("/accept_suggestion")
@login_required
def accept_suggestion():
    env_id    = request.args.get("env_id", type=int)
    start_str = request.args.get("start")
    end_str   = request.args.get("end")
    env = db.session.get(Environment, env_id) or abort(404)

    try:
        start = datetime.fromisoformat(start_str)
        end   = datetime.fromisoformat(end_str)
    except ValueError:
        abort(400)

    ok, res = BookingService.attempt_single_booking(
        user=current_user,
        environment=env,
        start=start,
        end=end,
        accept_suggestion=True
    )
    if not ok:
        flash("Could not create suggested booking", "danger")
        return redirect(url_for("bookings.create_booking"))

    b = res
    flash(f"Booking confirmed: {b.environment.name} from {b.start.strftime('%Y-%m-%d %H:%M')} to {b.end.strftime('%Y-%m-%d %H:%M')}.", "success")
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/series", methods=["GET", "POST"])
@login_required
def create_series_booking():
    form = SeriesBookingForm()
    force = (request.args.get("force") == "true")

    if form.validate_on_submit():
        env = db.session.get(Environment, form.environment.data) or abort(404)

        ok, res = BookingService.attempt_series_booking(
            user=current_user,
            environment=env,
            start_dt=form.start_dt.data,
            end_dt=form.end_dt.data,
            weekdays=form.days_of_week.data,
            force=force
        )

        if not ok:
            if res == "clash":
                ctx = BookingService.series_suggestion_context(form, env, form.start_dt.data, form.end_dt.data)
                return render_template("bookings/series_form.html", **ctx)
            flash(res, "danger")
            return redirect(url_for("bookings.create_series_booking"))

        count, forced = res
        verb = " (forced)" if forced else ""
        flash(f"Series booking{verb} confirmed: {count} slots for {env.name}.", "success")
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/series_form.html", form=form)


@bookings_bp.route("/accept_series_suggestion")
@login_required
def accept_series_suggestion():
    params = request.args.to_dict()
    ok, res = BookingService.accept_series_suggestion(current_user, **params)
    if not ok:
        flash("Could not create suggested series booking.", "danger")
        return redirect(url_for("bookings.create_series_booking"))
    count = res
    flash(f"Series booking confirmed: {count} slots for {params['env_name']}.", "success")
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/<int:booking_id>/download")
@login_required
def download_ics(booking_id):
    booking = db.session.get(Booking, booking_id) or abort(404)
    if current_user.role != "admin" and booking.user_id != current_user.id:
        abort(403)
    return BookingService.generate_ics_response(booking)
