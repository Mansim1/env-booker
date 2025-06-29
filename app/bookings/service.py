import json
import logging
from datetime import datetime, timedelta, timezone, time, date
from flask import Response, url_for
from sqlalchemy import func
from markupsafe import escape
from app import db
from app.models import Booking, AuditLog, Environment

logger = logging.getLogger(__name__)

class BookingService:
    MAX_DURATION = timedelta(hours=8)
    DAILY_UTILIZATION_CAP = 0.90
    SUGGESTION_WINDOW = timedelta(hours=3)
    SUGGESTION_STEP = timedelta(minutes=15)

    @staticmethod
    def log_action(action, actor_id, details=None, commit=True):
        """
        Always record an AuditLog entry:
          - dict → JSON‐dumped
          - anything else → str()
        """
        if isinstance(details, dict):
            details = json.dumps(details, default=str)
        else:
            details = str(details) if details is not None else None

        entry = AuditLog(
            action=action,
            actor_id=actor_id,
            details=details
        )
        db.session.add(entry)
        if commit:
            db.session.commit()

        logger.debug(
            "AuditLog: action=%s actor=%s details=%s",
            action, actor_id, details
        )

    @staticmethod
    def _overlap_exists(env_id, start, end, exclude_id=None):
        q = db.session.query(Booking.id).filter(
            Booking.environment_id == env_id,
            Booking.end > start,
            Booking.start < end
        )
        if exclude_id:
            q = q.filter(Booking.id != exclude_id)
        exists = db.session.query(q.exists()).scalar()
        logger.debug("Overlap check: env=%s start=%s end=%s excl=%s → %s",
                     env_id, start, end, exclude_id, exists)
        return exists

    @staticmethod
    def _daily_util_seconds(env_id, day, exclude_id=None):
        day_start = datetime.combine(day, time.min)
        day_end   = datetime.combine(day, time.max)

        q = db.session.query(
            func.coalesce(
                func.sum(
                    func.strftime('%s', func.min(Booking.end, day_end))
                    - func.strftime('%s', func.max(Booking.start, day_start))
                ),
                0
            )
        ).filter(
            Booking.environment_id == env_id,
            Booking.end > day_start,
            Booking.start < day_end
        )
        if exclude_id:
            q = q.filter(Booking.id != exclude_id)

        secs = q.scalar() or 0
        logger.debug("Daily util for env=%s on %s excl=%s → %s sec",
                     env_id, day, exclude_id, secs)
        return secs

    @classmethod
    def _validate_single(cls, env_id, start, end, exclude_id=None):
        logger.debug("Validating: env=%s start=%s end=%s excl=%s",
                     env_id, start, end, exclude_id)
        if end <= start:
            return False, "End time must be after start time."
        duration = end - start
        if duration > cls.MAX_DURATION:
            return False, "Booking cannot exceed 8 hours."
        used = cls._daily_util_seconds(env_id, start.date(), exclude_id)
        if used + duration.total_seconds() > 24*3600*cls.DAILY_UTILIZATION_CAP:
            return False, "Cannot book: daily utilization cap (90%) reached."
        if cls._overlap_exists(env_id, start, end, exclude_id):
            return False, "Booking failed due to clash. No alternative series available within ±3 hours."
        return True, None

    @classmethod
    def delete_booking(cls, booking, user, commit=True):
        """
        Delete a Booking and emit an AuditLog entry.
        """
        # Build a human-readable message
        msg = (
            f"Deleted booking #{booking.id} in env “{booking.environment.name}” "
            f"from "
            f"{booking.start:%Y-%m-%d %H:%M} to {booking.end:%Y-%m-%d %H:%M}"
        )

        # Perform deletion
        db.session.delete(booking)

        # Audit-log it
        cls.log_action("delete_booking", user.id, details=msg, commit=False)

        # Commit if desired
        if commit:
            db.session.commit()

        logger.info("Booking %s deleted by user %s", booking.id, user.id)

    @classmethod
    def _build_slots(cls, start_dt, end_dt, weekdays):
        slots = []
        current = start_dt.date()
        one_day = timedelta(days=1)
        while current <= end_dt.date():
            if str(current.weekday()) in weekdays:
                s = datetime.combine(current, start_dt.time())
                e = datetime.combine(current, end_dt.time())
                slots.append((s, e))
            current += one_day
        logger.debug("Built %d series slots", len(slots))
        return slots

    @classmethod
    def _bulk_insert_with_audit(cls, user, environment, slots, action):
        for start, end in slots:
            b = Booking(environment_id=environment.id,
                        user_id=user.id, start=start, end=end)
            db.session.add(b)
            db.session.flush()

            msg = (
                f"booking #{b.id} in env “{environment.name}” "
                f"from {start:%Y-%m-%d %H:%M} "
                f"to {end:%Y-%m-%d %H:%M}"
            )
            cls.log_action(action, user.id, details=msg, commit=False)

        logger.info("Bulk inserted %d bookings for user %s", len(slots), user.id)
        return len(slots)

    @classmethod
    def create_series(cls, user, environment, start_date, end_date, weekdays, start_time, end_time):
        slots = cls._build_slots(
            datetime.combine(start_date, start_time),
            datetime.combine(end_date, end_time),
            weekdays
        )
        if not slots:
            return False, "No valid weekday slots in the given date range."

        for s, e in slots:
            ok, err = cls._validate_single(environment.id, s, e)
            if not ok:
                msg = f"Series failed on {s:%Y-%m-%d %H:%M}: {err}"
                logger.warning(msg)
                return False, msg

        try:
            count = cls._bulk_insert_with_audit(user, environment, slots, "create_series")
            db.session.commit()
            logger.info("Created series of %d bookings for user %s", count, user.id)

            # SUMMARY log for the whole series
            summary = (
                f"Created series of {count} bookings in env “{environment.name}” "
                f"from {start_date:%Y-%m-%d} "
                f"to {end_date:%Y-%m-%d}"
            )
            cls.log_action("create_series_summary", user.id, details=summary)

            return True, count
        except Exception:
            db.session.rollback()
            logger.exception("Unexpected error during series creation")
            return False, "Series failed: unexpected error."

    @classmethod
    def attempt_series_booking(cls, user, environment, start_dt, end_dt, weekdays, force=False):
        if force and getattr(user, "role", None) == "admin":
            logger.info("Admin %s forcing series booking %s–%s", user.id, start_dt, end_dt)
            slots = cls._build_slots(start_dt, end_dt, weekdays)
            count = cls._bulk_insert_with_audit(user, environment, slots, "forced_series_book")
            db.session.commit()

            summary = (
                f"Forced series booking: created {count} bookings in env “{environment.name}” "
                f"from {start_dt:%Y-%m-%d %H:%M} "
                f"to {end_dt:%Y-%m-%d %H:%M}"
            )
            cls.log_action("forced_series_booking_summary", user.id, details=summary)

            return True, (count, True)

        ok, result = cls.create_series(
            user, environment,
            start_dt.date(), end_dt.date(),
            weekdays, start_dt.time(), end_dt.time()
        )
        if not ok:
            if result.startswith("Series failed on"):
                return False, "clash"
            return False, result

        logger.info("Series booking succeeded for user %s", user.id)
        return True, (result, False)

    @classmethod
    def find_suggestion(cls, environment, desired_start, desired_end):
        duration = desired_end - desired_start
        for step_mul in range(1, int(cls.SUGGESTION_WINDOW / cls.SUGGESTION_STEP) + 1):
            for sign in (-1, +1):
                offset = cls.SUGGESTION_STEP * step_mul * sign
                cs = desired_start + offset
                ce = cs + duration
                if (desired_start - cls.SUGGESTION_WINDOW <= cs <= desired_start + cls.SUGGESTION_WINDOW
                    and not cls._overlap_exists(environment.id, cs, ce)):
                    logger.info("Suggestion: %s to %s", cs, ce)
                    return cs, ce
        logger.info("No single suggestion found")
        return None, None

    @classmethod
    def find_series_suggestion(cls, environment, start_date, end_date, weekdays, start_time, end_time):
        base_start = datetime.combine(start_date, start_time)
        duration = datetime.combine(start_date, end_time) - base_start
        days = [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
            if str((start_date + timedelta(days=i)).weekday()) in weekdays
        ]
        for step_mul in range(1, int(cls.SUGGESTION_WINDOW / cls.SUGGESTION_STEP) + 1):
            for sign in (-1, +1):
                offset = cls.SUGGESTION_STEP * step_mul * sign
                for d in days:
                    cs = datetime.combine(d, start_time) + offset
                    ce = cs + duration
                    if cls._overlap_exists(environment.id, cs, ce):
                        break
                else:
                    logger.info("Series suggestion offset %s", offset)
                    return (base_start + offset).time(), (base_start + offset + duration).time()
        logger.info("No series suggestion found")
        return None, None

    @classmethod
    def single_suggestion_flash(cls, environment, desired_start, desired_end):
        s, e = cls.find_suggestion(environment, desired_start, desired_end)
        if not s:
            return escape("This slot is already booked.")
        start_str = s.strftime("%Y-%m-%d %H:%M")
        end_str = e.strftime("%Y-%m-%d %H:%M")
        link = url_for("bookings.accept_suggestion",
                       env_id=environment.id,
                       start=s.isoformat(),
                       end=e.isoformat())
        return (f"Booking failed due to clash. Suggested slot: "
                f"{start_str}–{end_str} <a href='{link}' class='alert-link'>[Accept]</a>")

    @classmethod
    def attempt_single_booking(cls, user, environment, start, end,
                               accept_suggestion=False, force=False):
        if force and getattr(user, "role", None) == "admin":
            b = Booking(environment_id=environment.id, user_id=user.id,
                        start=start, end=end)
            db.session.add(b)
            db.session.flush()

            msg = (
                f"Forced booking #{b.id} in env “{environment.name}” "
                f"from {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M}"
            )
            cls.log_action("forced_single_book", user.id, details=msg, commit=False)
            db.session.commit()
            return True, b

        ok, err = cls._validate_single(environment.id, start, end)
        if not ok:
            if err.startswith("This slot") and not accept_suggestion:
                return False, "clash"
            return False, err

        b = Booking(environment_id=environment.id, user_id=user.id,
                    start=start, end=end)
        db.session.add(b)
        db.session.flush()

        action = "accept_suggestion" if accept_suggestion else "create_booking"
        msg = (
            f"{action}: booking #{b.id} in env “{environment.name}” "
            f"from {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M}, "
            f"accepted suggestion = {accept_suggestion}"
        )
        cls.log_action(action, user.id, details=msg, commit=False)
        db.session.commit()
        return True, b

    @classmethod
    def attempt_edit_booking(cls, booking, user, environment, start, end, force=False):
        original = {"start": booking.start, "end": booking.end}

        if force and getattr(user, "role", None) == "admin":
            booking.environment_id = environment.id
            booking.start = start
            booking.end = end
            db.session.flush()

            msg = (
                f"Forced edit of booking #{booking.id} in env “{environment.name}” – "
                f"from {original['start']:%Y-%m-%d %H:%M}–"
                f"{original['end']:%Y-%m-%d %H:%M} to "
                f"{start:%Y-%m-%d %H:%M}–{end:%Y-%m-%d %H:%M}"
            )
            cls.log_action("forced_edit", user.id, details=msg, commit=False)
            db.session.commit()
            return True, booking

        ok, err = cls._validate_single(environment.id, start, end, exclude_id=booking.id)
        if not ok:
            if err.startswith("This slot"):
                return False, "clash"
            return False, err

        booking.environment_id = environment.id
        booking.start = start
        booking.end = end
        db.session.flush()

        msg = (
            f"Edited booking #{booking.id} in env “{environment.name}” – "
            f"from {original['start']:%Y-%m-%d %H:%M}–"
            f"{original['end']:%Y-%m-%d %H:%M} to "
            f"{start:%Y-%m-%d %H:%M}–{end:%Y-%m-%d %H:%M}"
        )
        cls.log_action("edit_booking", user.id, details=msg, commit=False)
        db.session.commit()
        return True, booking

    @classmethod
    def series_suggestion_context(cls, form, env, start_dt, end_dt):
        s, e = cls.find_series_suggestion(
            env, start_dt.date(), end_dt.date(),
            form.days_of_week.data, start_dt.time(), end_dt.time()
        )
        weekdays_str = ", ".join(dict(form.days_of_week.choices)[d] for d in form.days_of_week.data)
        ctx = {"form": form, "clash": True, "weekdays_str": weekdays_str,
               "orig_start_dt": start_dt.isoformat(),
               "orig_end_dt": end_dt.isoformat()}
        if s:
            ctx.update({
                "suggestion": True,
                "sug_start_time": s.strftime("%H:%M"),
                "sug_end_time": e.strftime("%H:%M")
            })
        else:
            ctx["suggestion"] = False
        return ctx

    @classmethod
    def accept_series_suggestion(
        cls,
        user,
        env_id: str,
        start_date: str,
        end_date: str,
        start_time: str,
        end_time: str,
        weekdays: str,
        force: str = "false",
    ):

        # 1) Load the environment
        env = db.session.get(Environment, int(env_id))
        if env is None:
            return False, "Environment not found"

        # 2) Parse dates and times
        try:
            sd = date.fromisoformat(start_date)
            ed = date.fromisoformat(end_date)
            st = time.fromisoformat(start_time)
            et = time.fromisoformat(end_time)
        except ValueError as e:
            return False, f"Invalid date/time format: {e}"

        # 3) Parse weekdays into a list of strings
        if isinstance(weekdays, str):
            days = [d for d in weekdays.split(",") if d.strip() != ""]
        else:
            days = weekdays

        # 4) Interpret force flag
        do_force = force.lower() == "true"

        # 5) Delegate to your series booking logic
        return cls.attempt_series_booking(
            user=user,
            environment=env,
            start_dt=datetime.combine(sd, st),
            end_dt  =datetime.combine(ed, et),
            weekdays=days,
            force=do_force
        )

    @classmethod
    def generate_ics_response(cls, booking):
        now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//EasyEnvBooker//EN", "BEGIN:VEVENT",
            f"UID:booking-{booking.id}@easyenvbooker.local",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{booking.start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{booking.end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:Booking for {booking.environment.name}",
            "END:VEVENT", "END:VCALENDAR", ""
        ]
        payload = "\r\n".join(lines)
        headers = {
            "Content-Disposition": f"attachment; filename=booking-{booking.id}.ics",
            "Content-Type": "text/calendar; charset=utf-8"
        }
        logger.info("Generated ICS for booking %s", booking.id)
        return Response(payload, headers=headers)
