from datetime import datetime, timedelta, timezone
from flask import Response, url_for
from sqlalchemy import func
from markupsafe import escape
from app import db
from app.models import Booking, AuditLog
import logging

logger = logging.getLogger(__name__)

class BookingService:
    # Configuration constants for booking validation
    MAX_DURATION = timedelta(hours=8)
    DAILY_UTILIZATION_CAP = 0.90
    SUGGESTION_WINDOW = timedelta(hours=3)
    SUGGESTION_STEP = timedelta(minutes=15)

    @staticmethod
    def _overlap_exists(env_id, start, end):
        """
        Check if any existing booking overlaps with the proposed time range.
        """
        overlap = db.session.query(Booking.id).filter(
            Booking.environment_id == env_id,
            Booking.end > start,
            Booking.start < end
        ).first() is not None
        logger.debug("Overlap check for env_id=%s, start=%s, end=%s: %s", env_id, start, end, overlap)
        return overlap

    @staticmethod
    def _daily_util_seconds(env_id, day):
        """
        Calculate how many seconds of bookings already exist on a specific day
        for the given environment.
        """
        day_start = datetime.combine(day, datetime.min.time())
        day_end   = datetime.combine(day, datetime.max.time())
        seconds = db.session.query(
            func.coalesce(
                func.sum(
                    func.strftime('%s', Booking.end) - func.strftime('%s', Booking.start)
                ), 
                0
            )
        ).filter(
            Booking.environment_id == env_id,
            Booking.start >= day_start,
            Booking.start <= day_end
        ).scalar()
        logger.debug("Daily utilization for env_id=%s on %s: %s seconds", env_id, day, seconds)
        return seconds or 0

    @classmethod
    def _validate_single(cls, env_id, start, end):
        """
        Enforce all validation rules on a single booking slot:
        - End after start
        - Duration within limit
        - Daily capacity not exceeded
        - No time overlaps
        """
        logger.debug("Validating booking for env_id=%s from %s to %s", env_id, start, end)
        if end <= start:
            return False, "End time must be after start time."
        dur = end - start
        if dur > cls.MAX_DURATION:
            return False, "Booking cannot exceed 8 hours."
        used = cls._daily_util_seconds(env_id, start.date())
        if used + dur.total_seconds() > 24*3600*cls.DAILY_UTILIZATION_CAP:
            return False, "Cannot book: daily utilization cap (90 %) reached."
        if cls._overlap_exists(env_id, start, end):
            return False, "This slot is already booked."
        return True, None

    @classmethod
    def create_booking(cls, user, environment, start, end):
        """
        Create a single validated booking and commit it to the database.
        """
        ok, err = cls._validate_single(environment.id, start, end)
        if not ok:
            logger.warning("Booking validation failed for user_id=%s: %s", user.id, err)
            return False, err
        b = Booking(
            environment_id=environment.id,
            user_id=user.id,
            start=start,
            end=end
        )
        db.session.add(b)
        db.session.commit()
        logger.info("Booking created successfully for user_id=%s: env_id=%s, start=%s, end=%s", user.id, environment.id, start, end)
        return True, b

    @classmethod
    def _build_slots(cls, start_dt, end_dt, weekdays):
        """
        Generate a list of (start, end) datetime tuples for recurring bookings.
        """
        slots = []
        current = start_dt.date()
        one_day = timedelta(days=1)
        while current <= end_dt.date():
            if str(current.weekday()) in weekdays:
                s = datetime.combine(current, start_dt.time())
                e = datetime.combine(current, end_dt.time())
                slots.append((s, e))
            current += one_day
        logger.debug("Built %d slots for series booking.", len(slots))
        return slots

    @classmethod
    def _bulk_insert_with_audit(cls, user, environment, slots, action):
        """
        Insert multiple bookings and create corresponding audit log entries.
        """
        count = 0
        for s, e in slots:
            b = Booking(
                environment_id=environment.id,
                user_id=user.id,
                start=s,
                end=e
            )
            db.session.add(b)
            db.session.flush()
            db.session.add(AuditLog(
                action=action,
                actor_id=user.id,
                booking_id=b.id
            ))
            count += 1
        logger.info("Inserted %d bookings with audit for user_id=%s.", count, user.id)
        return count

    @classmethod
    def create_series(cls, user, environment, start_date, end_date, weekdays, start_time, end_time):
        # Create a list of time slots based on user input
        slots = cls._build_slots(
            datetime.combine(start_date, start_time),
            datetime.combine(end_date, end_time),
            weekdays
        )
        if not slots:
            logger.info("No valid weekday slots in the given date range.")
            return False, "No valid weekday slots in the given date range."

        # Pre-validate all slots to avoid booking conflicts
        for s, e in slots:
            ok, err = cls._validate_single(environment.id, s, e)
            if not ok and err == "This slot is already booked.":
                logger.warning(f"Series failed due to slot clash on {s}")
                return False, f"Series failed: clash on {s.strftime('%Y-%m-%d %H:%M')}."
            if not ok:
                logger.error(f"Validation failed for slot {s}-{e}: {err}")
                return False, err

        # Attempt transactional insert; rollback on error
        try:
            with db.session.begin_nested():
                for s, e in slots:
                    if cls._overlap_exists(environment.id, s, e):
                        logger.warning(f"Overlap detected during transactional insert on {s}")
                        raise ValueError(f"Series failed: clash on {s.strftime('%Y-%m-%d %H:%M')}.")
                    db.session.add(Booking(
                        environment_id=environment.id,
                        user_id=user.id,
                        start=s,
                        end=e
                    ))
            db.session.commit()
            logger.info(f"Successfully created booking series with {len(slots)} slots.")
            return True, len(slots)
        except ValueError as ve:
            db.session.rollback()
            logger.error(f"ValueError during series creation: {ve}")
            return False, str(ve)
        except Exception as e:
            db.session.rollback()
            logger.exception("Unexpected error during series creation.")
            return False, "Series failed: unexpected error."

    @classmethod
    def find_suggestion(cls, environment, desired_start, desired_end):
        duration = desired_end - desired_start
        for step_mul in range(1, int(cls.SUGGESTION_WINDOW / cls.SUGGESTION_STEP) + 1):
            for sign in (-1, +1):
                offset = cls.SUGGESTION_STEP * step_mul * sign
                cs = desired_start + offset
                ce = cs + duration
                if desired_start - cls.SUGGESTION_WINDOW <= cs <= desired_start + cls.SUGGESTION_WINDOW:
                    if not cls._overlap_exists(environment.id, cs, ce):
                        logger.info(f"Suggestion found: {cs} to {ce}")
                        return cs, ce
        logger.info("No suggestion found within suggestion window.")
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
                clash = False
                for d in days:
                    cs = datetime.combine(d, start_time) + offset
                    ce = cs + duration
                    if cls._overlap_exists(environment.id, cs, ce):
                        clash = True
                        break
                if not clash:
                    logger.info(f"Series suggestion found with offset {offset}")
                    return (base_start + offset).time(), (base_start + offset + duration).time()
        logger.info("No series suggestion found.")
        return None, None

    @classmethod
    def attempt_single_booking(cls, user, environment, start, end,
                            accept_suggestion=False, force=False):
        """
        Try to create one booking.
        Returns:
        (True, booking) on success,
        (False, "clash") if there's an overlap and suggestion not accepted,
        (False, errmsg) for other validation failures.
        """
        if force and user.role == "admin":
            logger.info(f"Admin {user.id} forcing booking from {start} to {end}")
            b = Booking(environment_id=environment.id, user_id=user.id, start=start, end=end)
            db.session.add(b)
            db.session.flush()
            db.session.add(AuditLog(action="forced_single_book", actor_id=user.id, booking_id=b.id))
            db.session.commit()
            return True, b

        ok, err = cls._validate_single(environment.id, start, end)
        if not ok:
            if err == "This slot is already booked." and not accept_suggestion:
                logger.info(f"Booking clash at {start} – no suggestion accepted.")
                return False, "clash"
            logger.warning(f"Booking validation failed: {err}")
            return False, err

        b = Booking(environment_id=environment.id, user_id=user.id, start=start, end=end)
        db.session.add(b)
        db.session.commit()

        if accept_suggestion:
            db.session.add(AuditLog(action="forced_single_book", actor_id=user.id, booking_id=b.id))
            db.session.commit()
            logger.info(f"Booking suggestion accepted by user {user.id}.")

        logger.info(f"Booking successful from {start} to {end} by user {user.id}")
        return True, b

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
        return f"Booking failed due to clash. Suggested slot: {start_str}–{end_str} <a href='{link}' class='alert-link'>[Accept]</a>"

    @classmethod
    def attempt_series_booking(cls, user, environment, start_dt, end_dt, weekdays, force=False):
        if force and user.role == "admin":
            logger.info(f"Admin {user.id} forcing series booking from {start_dt} to {end_dt}")
            slots = cls._build_slots(start_dt, end_dt, weekdays)
            count = cls._bulk_insert_with_audit(user, environment, slots, "forced_series_book")
            db.session.commit()
            return True, (count, True)

        ok, msg = cls.create_series(user, environment, start_dt.date(), end_dt.date(), weekdays, start_dt.time(), end_dt.time())
        if not ok:
            if msg.startswith("Series failed: clash"):
                logger.warning("Series booking failed due to clash.")
                return False, "clash"
            logger.error(f"Series booking failed: {msg}")
            return False, msg

        logger.info("Series booking succeeded.")
        return True, (msg, False)

    @classmethod
    def series_suggestion_context(cls, form, env, start_dt, end_dt):
        s, e = cls.find_series_suggestion(env, start_dt.date(), end_dt.date(), form.days_of_week.data, start_dt.time(), end_dt.time())
        weekdays_str = ", ".join(dict(form.days_of_week.choices)[d] for d in form.days_of_week.data)
        ctx = {"form": form, "clash": True, "weekdays_str": weekdays_str}

        if s:
            ctx.update({
                "suggestion": True,
                "sug_start_time": s.strftime("%H:%M"),
                "sug_end_time": e.strftime("%H:%M"),
                "orig_start_dt": start_dt.isoformat(),
                "orig_end_dt": end_dt.isoformat()
            })
        else:
            ctx.update({
                "suggestion": False,
                "orig_start_dt": start_dt.isoformat(),
                "orig_end_dt": end_dt.isoformat()
            })
        return ctx

    @classmethod
    def generate_ics_response(cls, booking):
        now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//EasyEnvBooker//EN",
            "BEGIN:VEVENT",
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
        logger.info(f"ICS calendar response generated for booking {booking.id}")
        return Response(payload, headers=headers)
