from datetime import datetime
from flask import (
    Blueprint, Response, render_template, redirect, url_for, flash, abort, request
)
from flask_login import login_required, current_user
from markupsafe import Markup
from app import db
from app.bookings.forms import BookingForm, SeriesBookingForm
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

        desired_start = form.start.data
        desired_end = form.end.data

        ok, result = BookingService.create_booking(
            user=current_user,
            environment=env,
            start=desired_start,
            end=desired_end
        )
        if not ok:
            # Check if this is the clash‐specific message
            if result == "This slot is already booked.":
                # Look for suggestion
                sug_start, sug_end = BookingService.find_suggestion(
                    env, desired_start, desired_end
                )
                if sug_start and sug_end:
                    # Format times
                    start_str = sug_start.strftime("%Y-%m-%d %H:%M")
                    end_str = sug_end.strftime("%Y-%m-%d %H:%M")
                    # Build Accept link with GET parameters (ISO format)
                    link = url_for(
                        "bookings.accept_suggestion",
                        env_id=env.id,
                        start=sug_start.strftime("%Y-%m-%dT%H:%M"),
                        end=sug_end.strftime("%Y-%m-%dT%H:%M")
                    )
                    msg = Markup(
                        f"Suggested slot: {start_str}–{end_str} "
                        f"<a href='{link}' class='alert-link'>[Accept]</a>"
                    )
                    flash(msg, "info")
                else:
                    flash(result, "danger")
            else:
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


@bookings_bp.route("/accept_suggestion", methods=["GET"])
@login_required
def accept_suggestion():
    """
    Accept the suggested slot passed via query params:
      ?env_id=<int>&start=<ISO datetime>&end=<ISO datetime>
    """
    env_id = request.args.get("env_id", type=int)
    start_str = request.args.get("start")  # e.g. "2025-06-01T09:00"
    end_str = request.args.get("end")

    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)

    try:
        # Parse "YYYY-MM-DDTHH:MM"
        from datetime import datetime
        start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        end_dt   = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
    except Exception:
        abort(400, description="Invalid suggestion parameters.")

    ok, result = BookingService.create_booking(
        user=current_user,
        environment=env,
        start=start_dt,
        end=end_dt
    )
    if not ok:
        flash("Could not create suggested booking.", "danger")
        return redirect(url_for("bookings.create_booking"))

    flash(
        f"Booking confirmed: {env.name} from "
        f"{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}.",
        "success"
    )
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/series", methods=["GET", "POST"])
@login_required
def create_series_booking():
    form = SeriesBookingForm()
    if form.validate_on_submit():
        env = db.session.get(Environment, form.environment.data)
        if env is None:
            abort(404)

        start_dt = form.start_dt.data
        end_dt   = form.end_dt.data

        start_date = start_dt.date()
        end_date   = end_dt.date()
        start_time = start_dt.time()
        end_time   = end_dt.time()

        ok, result = BookingService.create_series(
            user=current_user,
            environment=env,
            start_date=start_date,
            end_date=end_date,
            weekdays=form.days_of_week.data,
            start_time=start_time,
            end_time=end_time
        )
        print(ok, result)
        if not ok:
            if result.startswith("Series failed: clash"):
                # Suggest an alternative series
                sug_start_time, sug_end_time = BookingService.find_series_suggestion(
                    env, start_date, end_date, form.days_of_week.data,
                    start_time, end_time
                )
                if sug_start_time and sug_end_time:
                    # Build flush message
                    weekdays_str = ", ".join([dict(form.days_of_week.choices)[d] for d in form.days_of_week.data])
                    link = url_for(
                        "bookings.accept_series_suggestion",
                        env_id=env.id,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        weekdays=",".join(form.days_of_week.data),
                        start_time=sug_start_time.strftime("%H:%M"),
                        end_time=sug_end_time.strftime("%H:%M")
                    )
                    msg = Markup(
                        f"Series failed due to clash. Suggested series: weekdays {weekdays_str} "
                        f"from {start_date.isoformat()} {sug_start_time.strftime('%H:%M')}-{sug_end_time.strftime('%H:%M')} "
                        f"<a href='{link}' class='alert-link'>[Accept]</a>"
                    )
                    flash(msg, "info")
                else:
                    flash("Series failed: no alternative series available within ±3 hours.", "danger")
            else:
                flash(result, "danger")

            return redirect(url_for("bookings.create_series_booking"))

        flash(f"Series booking confirmed: {result} slots for {env.name}.", "success")
        return redirect(url_for("bookings.list_bookings"))

    return render_template("bookings/series_form.html", form=form)


@bookings_bp.route("/accept_series_suggestion", methods=["GET"])
@login_required
def accept_series_suggestion():
    env_id       = request.args.get("env_id", type=int)
    start_date_s = request.args.get("start_date")
    end_date_s   = request.args.get("end_date")
    weekdays_csv = request.args.get("weekdays")
    start_time_s = request.args.get("start_time")
    end_time_s   = request.args.get("end_time")

    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)

    try:
        from datetime import datetime
        start_date = datetime.fromisoformat(start_date_s).date()
        end_date   = datetime.fromisoformat(end_date_s).date()
        weekdays   = weekdays_csv.split(",")
        start_time = datetime.strptime(start_time_s, "%H:%M").time()
        end_time   = datetime.strptime(end_time_s, "%H:%M").time()
    except Exception:
        abort(400, description="Invalid suggestion parameters.")

    ok, result = BookingService.create_series(
        user=current_user,
        environment=env,
        start_date=start_date,
        end_date=end_date,
        weekdays=weekdays,
        start_time=start_time,
        end_time=end_time
    )
    if not ok:
        flash("Could not create suggested series booking.", "danger")
        return redirect(url_for("bookings.create_series_booking"))

    flash(f"Series booking confirmed: {result} slots for {env.name}.", "success")
    return redirect(url_for("bookings.list_bookings"))

@bookings_bp.route("/<int:booking_id>/download", methods=["GET"])
@login_required
def download_ics(booking_id):
    """
    Generate a valid .ics file for booking_id and serve it as an attachment.
    Only the booking owner (or an admin) may download.
    """
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        abort(404)

    # Only allow the owning user or an admin to download
    if not (current_user.role == "admin" or booking.user_id == current_user.id):
        abort(403)

    # Build iCalendar content
    # UID: booking-<id>@easyenvbooker.local
    # DTSTAMP: now in UTC, formatted as YYYYMMDDTHHMMSSZ
    # DTSTART/DTEND: booking.start/end in local time, formatted as YYYYMMDDTHHMMSS
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    dtstart = booking.start.strftime("%Y%m%dT%H%M%S")
    dtend = booking.end.strftime("%Y%m%dT%H%M%S")
    env_name = booking.environment.name

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EasyEnvBooker//BookingCalendar//EN",
        "BEGIN:VEVENT",
        f"UID:booking-{booking.id}@easyenvbooker.local",
        f"DTSTAMP:{now_utc}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:Booking for {env_name}",
        "END:VEVENT",
        "END:VCALENDAR",
        ""
    ]
    ics_content = "\r\n".join(ics_lines)

    filename = f"booking-{booking.id}.ics"
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "text/calendar; charset=utf-8"
    }
    return Response(ics_content, headers=headers)
