# app/bookings/routes.py

from datetime import datetime, timedelta
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
    """
    List all bookings: admin sees every booking,
    regular users see only their own.
    """
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
    """
    Single‐slot booking. If a clash occurs, regular users see an error
    or a “Suggested slot” link; admins can “Accept” the suggestion.
    """
    form = BookingForm()

    if form.validate_on_submit():
        # 1. Lookup environment
        env = db.session.get(Environment, form.environment.data)
        if env is None:
            abort(404)

        desired_start = form.start.data
        desired_end = form.end.data

        # 2. Attempt normal creation (includes clash & cap checks)
        ok, result = BookingService.create_booking(
            user=current_user,
            environment=env,
            start=desired_start,
            end=desired_end
        )

        if not ok:
            # If the failure was “This slot is already booked.” → try suggestion
            if result == "This slot is already booked.":
                sug_start, sug_end = BookingService.find_suggestion(
                    env, desired_start, desired_end
                )
                if sug_start and sug_end:
                    # Format suggestion times
                    start_str = sug_start.strftime("%Y-%m-%d %H:%M")
                    end_str = sug_end.strftime("%Y-%m-%d %H:%M")

                    # Build Accept‐link for the suggestion
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
                    # No free slot within ±3h
                    flash(result, "danger")

            else:
                # Some other validation failure (cap, end≤start, etc.)
                flash(result, "danger")

            return redirect(url_for("bookings.create_booking"))

        # 3. Success
        booking = result
        flash(
            f"Booking confirmed: {env.name} from "
            f"{booking.start.strftime('%Y-%m-%d %H:%M')} to "
            f"{booking.end.strftime('%Y-%m-%d %H:%M')}.",
            "success"
        )
        return redirect(url_for("bookings.list_bookings"))

    # GET (or form not valid) → render form
    return render_template("bookings/form.html", form=form)


@bookings_bp.route("/accept_suggestion", methods=["GET"])
@login_required
def accept_suggestion():
    """
    Endpoint for “Accept” on a suggested single‐slot reservation.
    Query string must include env_id, start, end in ISO format.
    """
    env_id = request.args.get("env_id", type=int)
    start_str = request.args.get("start")  # e.g. "2025-06-01T09:00"
    end_str = request.args.get("end")      # e.g. "2025-06-01T11:00"

    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)

    try:
        # Parse ISO‐format datetimes: "YYYY-MM-DDTHH:MM"
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
    """
    Series‐of‐slots booking. If clashes occur:
      • Regular users see a suggestion or an error.
      • Admins can append ?force=true to override both clash‐and‐cap checks.
    """
    form = SeriesBookingForm()

    # Determine if this POST should be treated as a forced series
    force_flag = request.args.get("force", "").lower() == "true"
    is_admin = (current_user.role == "admin")

    if form.validate_on_submit():
        # 1. Lookup environment
        env = db.session.get(Environment, form.environment.data)
        if env is None:
            abort(404)

        # 2. Extract date+time from form fields
        start_dt = form.start_dt.data   # datetime object (date + time)
        end_dt   = form.end_dt.data

        start_date = start_dt.date()
        end_date   = end_dt.date()
        start_time = start_dt.time()
        end_time   = end_dt.time()

        # —— A) FORCE‐OVERRIDE BRANCH for Admins ——
        if is_admin and force_flag:
            # Build all requested slots between start_date and end_date
            slots = []
            current = start_date
            one_day = timedelta(days=1)
            while current <= end_date:
                if str(current.weekday()) in form.days_of_week.data:
                    slot_start = datetime.combine(current, start_time)
                    slot_end = datetime.combine(current, end_time)
                    slots.append((slot_start, slot_end))
                current += one_day

            # Bulk‐insert all slots, ignoring any clashes or cap
            try:
                for (s_dt, e_dt) in slots:
                    booking = Booking(
                        environment_id=env.id,
                        user_id=current_user.id,
                        start=s_dt,
                        end=e_dt
                    )
                    db.session.add(booking)
                db.session.commit()

                flash(
                    f"Series booking (forced) confirmed: {len(slots)} slots for {env.name}.",
                    "success"
                )
                return redirect(url_for("bookings.list_bookings"))

            except Exception:
                db.session.rollback()
                flash("Force series failed: unexpected error.", "danger")
                # Fall through to re-render the form

        # —— B) NORMAL VALIDATION BRANCH ——
        ok, result = BookingService.create_series(
            user=current_user,
            environment=env,
            start_date=start_date,
            end_date=end_date,
            weekdays=form.days_of_week.data,
            start_time=start_time,
            end_time=end_time
        )

        if not ok:
            # If it was a “clash” error, try to find a ±3h suggestion
            if result.startswith("Series failed: clash"):
                sug_start_time, sug_end_time = BookingService.find_series_suggestion(
                    environment=env,
                    start_date=start_date,
                    end_date=end_date,
                    weekdays=form.days_of_week.data,
                    start_time=start_time,
                    end_time=end_time
                )

                if sug_start_time and sug_end_time:
                    # Build human‐friendly weekdays string (e.g. “Mon, Tue, Fri”)
                    weekdays_str = ", ".join(
                        dict(form.days_of_week.choices)[d]
                        for d in form.days_of_week.data
                    )
                    return render_template(
                        "bookings/series_form.html",
                        form=form,
                        clash=True,
                        suggestion=True,
                        weekdays_str=weekdays_str,
                        sug_start_time=sug_start_time.strftime("%H:%M"),
                        sug_end_time=sug_end_time.strftime("%H:%M"),
                        orig_start_dt=start_dt.strftime("%Y-%m-%dT%H:%M"),
                        orig_end_dt=end_dt.strftime("%Y-%m-%dT%H:%M")
                    )
                else:
                    # No suggestion found within ±3h
                    return render_template(
                        "bookings/series_form.html",
                        form=form,
                        clash=True,
                        suggestion=False,
                        orig_start_dt=start_dt.strftime("%Y-%m-%dT%H:%M"),
                        orig_end_dt=end_dt.strftime("%Y-%m-%dT%H:%M")
                    )

            # Any other failure (e.g. no valid weekdays, cap, etc.)
            flash(result, "danger")
            return redirect(url_for("bookings.create_series_booking"))

        # —— C) SUCCESS (normal series created) ——
        flash(f"Series booking confirmed: {result} slots for {env.name}.", "success")
        return redirect(url_for("bookings.list_bookings"))

    # GET (or form did not validate) → render clean form
    return render_template("bookings/series_form.html", form=form)


@bookings_bp.route("/accept_series_suggestion", methods=["GET"])
@login_required
def accept_series_suggestion():
    """
    “Accept” an alternative series suggestion. Query params:
      ?env_id=<int>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
      &weekdays=0,2,4&start_time=HH:MM&end_time=HH:MM
    """
    env_id = request.args.get("env_id", type=int)
    start_date_s = request.args.get("start_date")
    end_date_s   = request.args.get("end_date")
    weekdays_csv = request.args.get("weekdays")
    start_time_s = request.args.get("start_time")
    end_time_s   = request.args.get("end_time")

    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)

    try:
        # Parse dates/times from strings
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
    Only the booking owner (or an admin) may download it.
    """
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        abort(404)

    # Only allow the owning user or an admin to download
    if not (current_user.role == "admin" or booking.user_id == current_user.id):
        abort(403)

    # Build iCalendar content
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = booking.start.strftime("%Y%m%dT%H%M%S")
    dtend   = booking.end.strftime("%Y%m%dT%H%M%S")
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
