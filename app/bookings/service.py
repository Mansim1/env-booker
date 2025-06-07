# app/bookings/service.py

from datetime import datetime, timedelta
from flask import Response, current_app
from sqlalchemy import func, and_
from app import db
from app.models import AuditLog, Booking
from flask import url_for
from markupsafe import escape

class BookingService:
    MAX_DURATION = timedelta(hours=8)
    DAILY_UTILIZATION_CAP = 0.90
    SUGGESTION_WINDOW = timedelta(hours=3)
    SUGGESTION_STEP = timedelta(minutes=15)

    @staticmethod
    def _overlap_exists(environment_id, start, end):
        """Return True if any booking overlaps [start, end)."""
        return db.session.query(Booking.id).filter(
            Booking.environment_id == environment_id,
            Booking.end > start,
            Booking.start < end
        ).first() is not None

    @staticmethod
    def _daily_utilization_seconds(environment_id, day):
        """Sum total booked seconds for that env on a given calendar date."""
        day_start = datetime.combine(day, datetime.min.time())
        day_end   = datetime.combine(day, datetime.max.time())
        total = db.session.query(
            func.coalesce(func.sum(func.strftime('%s', Booking.end) - func.strftime('%s', Booking.start)), 0)
        ).filter(
            Booking.environment_id == environment_id,
            Booking.start >= day_start,
            Booking.start <= day_end
        ).scalar()
        return total or 0

    @classmethod
    def _validate_single(cls, environment_id, start, end):
        """Run all validations for a single booking; return (False,msg) or (True,None)."""
        if end <= start:
            return False, "End time must be after start time."
        duration = end - start
        if duration > cls.MAX_DURATION:
            return False, "Booking cannot exceed 8 hours."

        # daily cap
        used = cls._daily_utilization_seconds(environment_id, start.date())
        if used + duration.total_seconds() > 24*3600*cls.DAILY_UTILIZATION_CAP:
            return False, "Cannot book: daily utilization cap (90 %) reached."

        # overlap
        if cls._overlap_exists(environment_id, start, end):
            return False, "This slot is already booked."

        return True, None

    @classmethod
    def create_booking(cls, user, environment, start, end):
        """Create one booking if valid, else return (False, msg)."""
        ok, err = cls._validate_single(environment.id, start, end)
        if not ok:
            return False, err

        booking = Booking(
            environment_id=environment.id,
            user_id=user.id,
            start=start,
            end=end
        )
        db.session.add(booking)
        db.session.commit()
        return True, booking

    @classmethod
    def create_series(cls, user, environment, start_date, end_date, weekdays, start_time, end_time):
        """
        Create a weekday filtered series of bookings in one atomic operation.
        Rolls back everything on the first error.
        """
        # build all slot datetimes
        slots = []
        current = start_date
        one_day = timedelta(days=1)
        while current <= end_date:
            if str(current.weekday()) in weekdays:
                slots.append((
                    datetime.combine(current, start_time),
                    datetime.combine(current, end_time)
                ))
            current += one_day

        if not slots:
            return False, "No valid weekday slots in the given date range."

        # Pre‐validate each slot with the same single checks minus overlap.
        for start_dt, end_dt in slots:
            ok, err = cls._validate_single(environment.id, start_dt, end_dt)
            # but when validating series, treat overlap separately
            if not ok and err == "This slot is already booked.":
                clash_str = start_dt.strftime("%Y-%m-%d %H:%M")
                return False, f"Series failed: clash on {clash_str}."
            if not ok:
                return False, err

        # Now transactional insert + overlap check
        session = db.session
        try:
            with session.begin_nested():
                for start_dt, end_dt in slots:
                    if cls._overlap_exists(environment.id, start_dt, end_dt):
                        clash_str = start_dt.strftime("%Y-%m-%d %H:%M")
                        raise ValueError(f"Series failed: clash on {clash_str}.")
                    session.add(Booking(
                        environment_id=environment.id,
                        user_id=user.id,
                        start=start_dt,
                        end=end_dt
                    ))
            session.commit()
            return True, len(slots)
        except ValueError as ve:
            session.rollback()
            return False, str(ve)
        except Exception:
            session.rollback()
            return False, "Series failed: unexpected error."

    @classmethod
    def find_suggestion(cls, environment, desired_start, desired_end):
        """
        For a single clash, look ±3h in 15-minute increments for a free slot
        of the same duration.
        """
        duration = desired_end - desired_start
        window = cls.SUGGESTION_WINDOW

        for step_mul in range(1, int(window/cls.SUGGESTION_STEP)+1):
            for sign in (-1, +1):
                offset = cls.SUGGESTION_STEP * step_mul * sign
                candidate_start = desired_start + offset
                candidate_end   = candidate_start + duration
                # must stay within window bounds
                if not (desired_start - window <= candidate_start <= desired_start + window):
                    continue
                if not cls._overlap_exists(environment.id, candidate_start, candidate_end):
                    return candidate_start, candidate_end

        return None, None

    @classmethod
    def find_series_suggestion(cls, environment, start_date, end_date, weekdays, start_time, end_time):
        """
        Shift the entire series window ±3h to find a clash‐free series. Returns
        (new_start_time, new_end_time) as time objects, or (None,None).
        """
        # compute slot duration
        base_start = datetime.combine(start_date, start_time)
        base_end   = datetime.combine(start_date, end_time)
        duration   = base_end - base_start
        window     = cls.SUGGESTION_WINDOW

        # generate date iterator
        dates = [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
            if str((start_date + timedelta(days=i)).weekday()) in weekdays
        ]

        for step_mul in range(1, int(window/cls.SUGGESTION_STEP)+1):
            for sign in (-1, +1):
                offset = cls.SUGGESTION_STEP * step_mul * sign

                # test entire series
                clash = False
                for day in dates:
                    cs = datetime.combine(day, start_time) + offset
                    ce = cs + duration
                    if cls._overlap_exists(environment.id, cs, ce):
                        clash = True
                        break
                if not clash:
                    new_start = (base_start + offset).time()
                    new_end   = (base_start + offset + duration).time()
                    return new_start, new_end

        return None, None

    @classmethod
    def attempt_single_booking(cls, user, environment, start, end, accept_suggestion=False):
        """
        Try to create one booking.  Returns:
          (True, booking) on success,
          (False, "clash") if overlap—and no suggestion or suggestion refused,
          (False, error_message) on any other validation failure.
        """
        ok, err = cls._validate_single(environment.id, start, end)
        if not ok:
            if err == "This slot is already booked." and not accept_suggestion:
                return False, "clash"
            return False, err

        b = Booking(environment_id=environment.id, user_id=user.id, start=start, end=end)
        db.session.add(b)
        db.session.commit()

        # audit log for forced single?
        if accept_suggestion:
            db.session.add(AuditLog(
                action="forced_single_book",
                actor_id=user.id,
                booking_id=b.id
            ))
            db.session.commit()

        return True, b

    @classmethod
    def single_suggestion_flash(cls, environment, desired_start, desired_end):
        s, e = cls.find_suggestion(environment, desired_start, desired_end)
        if not s:
            return escape("This slot is already booked.")
        start_str = s.strftime("%Y-%m-%d %H:%M")
        end_str   = e.strftime("%Y-%m-%d %H:%M")
        link = url_for("bookings.accept_suggestion",
                       env_id=environment.id,
                       start=s.isoformat(),
                       end=e.isoformat())
        return f"Suggested slot: {start_str}–{end_str} <a href='{link}' class='alert-link'>[Accept]</a>"

    @classmethod
    def attempt_series_booking(cls, user, environment, start_dt, end_dt, weekdays, force=False):
        """
        Try to create a weekday series.  If force=True and user is admin,
        bypass all checks and audit‐log each booking.  Returns:
          (True, (count, forced_flag))
          (False, "clash")  → caller should render suggestion form
          (False, errmsg)   → immediate redirect with flash
        """
        if force and user.role == "admin":
            slots = cls._build_slots(start_dt, end_dt, weekdays)
            created = cls._bulk_insert_with_audit(user, environment, slots, "forced_series_book")
            return True, (created, True)

        ok, msg = cls._prevalidate_series(environment.id, start_dt, end_dt, weekdays)
        if not ok:
            if msg.startswith("Series failed: clash"):
                return False, "clash"
            return False, msg

        count = cls._insert_series(environment, user, start_dt, end_dt, weekdays)
        return True, (count, False)

    @classmethod
    def series_suggestion_context(cls, form, env, start_dt, end_dt):
        """
        Build context dict for rendering the form with a clash‐suggestion.
        """
        sug = cls.find_series_suggestion(env,
                                         start_dt.date(),
                                         end_dt.date(),
                                         form.days_of_week.data,
                                         start_dt.time(),
                                         end_dt.time())
        weekdays_str = ", ".join(dict(form.days_of_week.choices)[d] for d in form.days_of_week.data)
        return {
            **{ "form": form, "clash": True },
            **( {
                  "suggestion": True,
                  "weekdays_str": weekdays_str,
                  "sug_start_time": sug[0].strftime("%H:%M"),
                  "sug_end_time":   sug[1].strftime("%H:%M"),
                  "orig_start_dt":  start_dt.isoformat(),
                  "orig_end_dt":    end_dt.isoformat()
                } if sug[0] else {
                  "suggestion": False,
                  "orig_start_dt": start_dt.isoformat(),
                  "orig_end_dt":   end_dt.isoformat()
                }
            )
        }
    
    @classmethod
    def generate_ics_response(cls, booking):
        """
        Return a Flask Response with a .ics attachment for this booking.
        """
        now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR","VERSION:2.0",
            "PRODID:-//EasyEnvBooker//EN",
            "BEGIN:VEVENT",
            f"UID:booking-{booking.id}@easyenvbooker.local",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{booking.start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{booking.end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:Booking for {booking.environment.name}",
            "END:VEVENT","END:VCALENDAR",""
        ]
        payload = "\r\n".join(lines)
        headers = {
            "Content-Disposition": f"attachment; filename=booking-{booking.id}.ics",
            "Content-Type": "text/calendar; charset=utf-8"
        }
        return Response(payload, headers=headers)
