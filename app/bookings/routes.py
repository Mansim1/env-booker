# Flask Blueprint for handling all booking-related routes
from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, request
)
from flask_login import login_required, current_user
from markupsafe import Markup
from datetime import datetime
from app import db
from app.environment.forms import DeleteForm
from app.models import AuditLog, Environment, Booking
from app.bookings.forms import BookingForm, SeriesBookingForm
from app.bookings.service import BookingService
import logging

logger = logging.getLogger(__name__)

# Registering Blueprint for /bookings routes
bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


@bookings_bp.route("/")
@login_required
def list_bookings():
    """Displays bookings list for current user or all bookings if admin"""
    logger.debug("Fetching bookings for user: %s", current_user.email)
    q = Booking.query.order_by(Booking.start)
    if current_user.role != "admin":
        q = q.filter_by(user_id=current_user.id)
    return render_template("bookings/list.html", bookings=q.all(), delete_form=DeleteForm())


@bookings_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_booking():
    """Handles creation of single bookings with conflict checking and admin override"""
    form = BookingForm()
    force_flag = (request.args.get("force") == "true")
    is_admin   = (current_user.role == "admin")

    if request.method == "GET":
        logger.debug("Rendering booking form for user: %s", current_user.email)

    if form.validate_on_submit():
        env   = db.session.get(Environment, form.environment.data) or abort(404)
        start = form.start.data
        end   = form.end.data

        # Prevent bookings in the past
        if start < datetime.now():
            flash("Cannot book a time in the past.", "danger")
            return render_template("bookings/form.html", form=form)

        logger.info("Booking attempt by %s: %s from %s to %s", current_user.email, env.name, start, end)

        # Attempt to create the booking with clash and force handling
        ok, result = BookingService.attempt_single_booking(
            user=current_user,
            environment=env,
            start=start,
            end=end,
            accept_suggestion=False,
            force=force_flag
        )

        # Handle booking failures and display suggestions or errors
        if not ok:
            logger.warning("Booking failed for user %s on env %s: %s", current_user.email, env.name, result)
            if result == "clash":
                flash(Markup(BookingService.single_suggestion_flash(env, start, end)), "info")
            else:
                flash(result, "danger")

            # Admins can force the booking if there's a clash
            if is_admin and not force_flag and result == "clash":
                orig_start = start.strftime("%Y-%m-%dT%H:%M")
                orig_end   = end.strftime("%Y-%m-%dT%H:%M")
                return render_template(
                    "bookings/form.html",
                    form=form,
                    clash=True,
                    can_force=True,
                    orig_start=orig_start,
                    orig_end=orig_end
                )

            return render_template("bookings/form.html", form=form)

        # Booking successful
        b = result
        logger.info("Booking successful: user %s booked %s (%s to %s)", current_user.email, b.environment.name, b.start, b.end)
        flash(
            f"Booking confirmed: {b.environment.name} from "
            f"{b.start.strftime('%Y-%m-%d %H:%M')} to {b.end.strftime('%Y-%m-%d %H:%M')}.",
            "success"
        )
        return redirect(url_for("bookings.list_bookings"))

    # GET request or validation failure
    return render_template("bookings/form.html", form=form)


@bookings_bp.route("/accept_suggestion")
@login_required
def accept_suggestion():
    """Accept a suggested booking time if original slot was unavailable"""
    env_id    = request.args.get("env_id", type=int)
    start_str = request.args.get("start")
    end_str   = request.args.get("end")
    logger.debug("Suggestion accepted by %s for env_id=%s", current_user.email, env_id)

    if not start_str or not end_str:
        logger.error("Missing query params for suggestion: start=%s, end=%s", start_str, end_str)
        abort(400)

    env = db.session.get(Environment, env_id) or abort(404)

    try:
        start = datetime.fromisoformat(start_str)
        end   = datetime.fromisoformat(end_str)
    except ValueError:
        logger.error("Invalid datetime format in suggestion accept URL")
        abort(400)

    ok, res = BookingService.attempt_single_booking(
        user=current_user,
        environment=env,
        start=start,
        end=end,
        accept_suggestion=True
    )
    if not ok:
        logger.warning("Suggestion booking failed for user %s", current_user.email)
        flash("Could not create suggested booking", "danger")
        return redirect(url_for("bookings.create_booking"))

    b = res
    logger.info("Suggested booking confirmed for user %s: %s (%s to %s)", current_user.email, b.environment.name, b.start, b.end)
    flash(f"Booking confirmed: {b.environment.name} from {b.start.strftime('%Y-%m-%d %H:%M')} to {b.end.strftime('%Y-%m-%d %H:%M')}.", "success")
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/series", methods=["GET", "POST"])
@login_required
def create_series_booking():
    """Creates a recurring (series) booking across selected weekdays"""
    form = SeriesBookingForm()
    force = (request.args.get("force") == "true")

    if request.method == "GET":
        logger.debug("Rendering series booking form for user: %s", current_user.email)

    if form.validate_on_submit():
        env = db.session.get(Environment, form.environment.data) or abort(404)

        # Prevent bookings in the past
        if form.start_dt.data < datetime.now():
            flash("Cannot book a time in the past.", "danger")
            return render_template("bookings/series_form.html", form=form)

        logger.info("Series booking attempt by %s for %s (%s to %s)", current_user.email, env.name, form.start_dt.data, form.end_dt.data)

        ok, res = BookingService.attempt_series_booking(
            user=current_user,
            environment=env,
            start_dt=form.start_dt.data,
            end_dt=form.end_dt.data,
            weekdays=form.days_of_week.data,
            force=force
        )

        if not ok:
            logger.warning("Series booking failed for user %s: %s", current_user.email, res)
            if res == "clash":
                ctx = BookingService.series_suggestion_context(form, env, form.start_dt.data, form.end_dt.data)
                return render_template("bookings/series_form.html", **ctx)
            flash(res, "danger")
            return render_template("bookings/series_form.html", form=form)

        count, forced = res
        logger.info("Series booking successful: %d slots booked for %s by %s (forced=%s)", count, env.name, current_user.email, forced)
        verb = " (forced)" if forced else ""
        flash(f"Series booking{verb} confirmed: {count} slots for {env.name}.", "success")
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/series_form.html", form=form)


@bookings_bp.route("/accept_series_suggestion")
@login_required
def accept_series_suggestion():
    """Accept a series booking suggestion from the system"""
    params = request.args.to_dict()
    logger.debug("Series suggestion accepted by %s with params: %s", current_user.email, params)

    ok, res = BookingService.accept_series_suggestion(current_user, **params)
    if not ok:
        logger.warning("Series suggestion booking failed for user %s", current_user.email)
        flash("Could not create suggested series booking.", "danger")
        return redirect(url_for("bookings.create_series_booking"))
    count = res
    flash(f"Series booking confirmed: {count} slots for {params['env_name']}.", "success")
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/<int:booking_id>/download")
@login_required
def download_ics(booking_id):
    """Download .ics calendar file for the booking"""
    booking = db.session.get(Booking, booking_id)

    if not booking:
        logger.error("Booking not found for ID: %s", booking_id)
        abort(404)

    # Only allow download for booking owner or admin
    if current_user.role != "admin" and booking.user_id != current_user.id:
        logger.warning("Unauthorized .ics download attempt by %s for booking %d", current_user.email, booking_id)
        abort(403)
    logger.debug("Generating .ics file for booking %d by %s", booking_id, current_user.email)
    return BookingService.generate_ics_response(booking)


@bookings_bp.route("/<int:booking_id>/edit", methods=["GET", "POST"])
@login_required
def edit_booking(booking_id):
    booking = db.session.get(Booking, booking_id) or abort(404)
    if current_user.role != "admin" and booking.user_id != current_user.id:
        abort(403)

    form = BookingForm(obj=booking)
    force_flag = (request.args.get("force") == "true")
    is_admin   = (current_user.role == "admin")

    if form.validate_on_submit():
        env   = db.session.get(Environment, form.environment.data) or abort(404)
        start = form.start.data
        end   = form.end.data

        if start < datetime.now():
            flash("Cannot set booking to a time in the past.", "danger")
            return render_template("bookings/form.html", form=form, edit=True, booking=booking)

        logger.info("Edit attempt by %s for booking %d to %s (%s–%s)", current_user.email, booking.id, env.name, start, end)

        ok, result = BookingService.attempt_edit_booking(
            booking=booking,
            user=current_user,
            environment=env,
            start=start,
            end=end,
            force=force_flag
        )

        if not ok:
            logger.warning("Booking edit failed for %s: %s", current_user.email, result)

            if result == "clash":
                flash(Markup(BookingService.single_suggestion_flash(env, start, end)), "info")

                if is_admin and not force_flag:
                    orig_start = start.strftime("%Y-%m-%dT%H:%M")
                    orig_end   = end.strftime("%Y-%m-%dT%H:%M")
                    return render_template(
                        "bookings/form.html",
                        form=form,
                        clash=True,
                        can_force=True,
                        orig_start=orig_start,
                        orig_end=orig_end,
                        edit=True,
                        booking=booking
                    )
            else:
                flash(result, "danger")

            return render_template("bookings/form.html", form=form, edit=True, booking=booking)

        flash("Booking updated successfully.", "success")
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/form.html", form=form, edit=True, booking=booking)


@bookings_bp.route("/<int:booking_id>/delete", methods=["POST"])
@login_required
def delete_booking(booking_id):
    """Allow for Deleting enviroment bookings"""
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role != "admin" and booking.user_id != current_user.id:
        abort(403)

    db.session.delete(booking)
    db.session.add(AuditLog(
        action="delete_booking",
        actor_id=current_user.id,
        booking_id=booking.id,
        details=f"Deleted booking {booking.id}"
    ))
    db.session.commit()
    flash("Booking deleted.", "success")
    return redirect(url_for("bookings.list_bookings"))
