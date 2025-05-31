from datetime import datetime, timedelta
from app import db
from app.models import Booking

class BookingService:
    MAX_DURATION = timedelta(hours=8)
    DAILY_UTILIZATION_CAP = 0.90

    @staticmethod
    def create_booking(user, environment, start, end):
        # 1. Basic sanity checks
        if end <= start:
            return False, "End time must be after start time."
        duration = end - start
        if duration > BookingService.MAX_DURATION:
            return False, "Booking cannot exceed 8 hours."

        # 2. Daily utilization check
        #    Sum up all existing booking durations on the same calendar date
        booking_date = start.date()
        day_start = datetime.combine(booking_date, datetime.min.time())
        day_end   = datetime.combine(booking_date, datetime.max.time())

        # Query all bookings on this date for that environment
        existing_bookings = (
            Booking.query
            .filter(Booking.environment_id == environment.id)
            .filter(Booking.start >= day_start, Booking.start <= day_end)
            .all()
        )

        total_seconds = 0
        for b in existing_bookings:
            total_seconds += (b.end - b.start).total_seconds()

        # Add the proposed booking’s duration
        total_seconds += duration.total_seconds()

        # If total_seconds > 90% of 24h (i.e. 24h * 3600s * 0.90)
        cap_seconds = 24 * 3600 * BookingService.DAILY_UTILIZATION_CAP
        if total_seconds > cap_seconds:
            return False, "Cannot book: daily utilization cap (90 %) reached."

        # 3. Overlap check
        overlap = (
            Booking.query
            .filter(Booking.environment_id == environment.id)
            .filter(Booking.end > start, Booking.start < end)
            .first()
        )
        if overlap:
            return False, "This slot is already booked."

        # 4. Create the booking
        booking = Booking(
            environment_id=environment.id,
            user_id=user.id,
            start=start,
            end=end
        )
        db.session.add(booking)
        db.session.commit()
        return True, booking

    @staticmethod
    def create_series(user, environment, start_date, end_date, weekdays, start_time, end_time):
        """
        Attempt to create a series of bookings on the given weekdays between
        start_date and end_date (inclusive), each day from start_time to end_time.
        If any single day clashes, roll back all and return (False, error_message).
        Otherwise return (True, count_of_bookings).
        """
        # 1. Build a list of datetime pairs for each matching weekday
        slots = []
        current = datetime.combine(start_date, datetime.min.time())
        last = datetime.combine(end_date, datetime.min.time())
        delta_day = timedelta(days=1)
        while current.date() <= last.date():
            if str(current.weekday()) in weekdays:  # weekday() is 0=Monday … 6=Sunday
                start_dt = datetime.combine(current.date(), start_time)
                end_dt = datetime.combine(current.date(), end_time)
                # Reuse single‐booking checks (except duration check if fixed 1h)
                slots.append((start_dt, end_dt))
            current += delta_day

        if not slots:
            return False, "No valid weekday slots in the given date range."

        # 2. Begin a nested transaction—roll back entire series on first clash
        session = db.session
        try:
            # Use SAVEPOINT for nested transaction
            with session.begin_nested():
                count = 0
                for (start_dt, end_dt) in slots:
                    # Overlap check
                    overlap = (
                        Booking.query
                        .filter(Booking.environment_id == environment.id)
                        .filter(Booking.end > start_dt, Booking.start < end_dt)
                        .first()
                    )
                    if overlap:
                        clash_str = start_dt.strftime("%Y-%m-%d %H:%M")
                        raise ValueError(f"Series failed: clash on {clash_str}.")
                    # Insert child booking
                    child = Booking(
                        environment_id=environment.id,
                        user_id=user.id,
                        start=start_dt,
                        end=end_dt
                    )
                    session.add(child)
                    count += 1
            # If we reach here, no overlap was found → commit at outer level
            session.commit()
            return True, count
        except ValueError as ve:
            # Roll back to the savepoint, then outer transaction is still active
            session.rollback()
            return False, str(ve)
        except Exception as e:
            session.rollback()
            return False, "Series failed: unexpected error."

    @staticmethod
    def find_suggestion(environment, desired_start, desired_end):
        """
        Search for a free slot of the same duration within ±3 hours of desired_start.
        Returns (new_start, new_end) or (None, None) if none found.
        """
        duration = desired_end - desired_start
        window = timedelta(hours=3)
        earliest_start = desired_start - window
        latest_start = desired_start + window

        # Helper to test overlap
        def is_free(start_dt, end_dt):
            clash = (
                Booking.query
                .filter(Booking.environment_id == environment.id)
                .filter(Booking.end > start_dt, Booking.start < end_dt)
                .first()
            )
            return clash is None

        # Try offsets in 15-minute increments
        step = timedelta(minutes=15)
        offset = step
        while offset <= window:
            # Try earlier slot first
            new_start = desired_start - offset
            new_end = new_start + duration
            if new_start >= earliest_start and is_free(new_start, new_end):
                return new_start, new_end
            # Then try later slot
            new_start = desired_start + offset
            new_end = new_start + duration
            if new_end <= desired_end + window and is_free(new_start, new_end):
                return new_start, new_end

            offset += step

        return None, None
    
    @staticmethod
    def find_series_suggestion(environment, start_date, end_date, weekdays, start_time, end_time):
        """
        Search for an alternative series slot by shifting the entire daily window
        within ±3 hours of the original start_time. Returns:
           (new_start_time, new_end_time) if a full series is free,
           otherwise (None, None).
        """
        print(start_date)
        print(end_date)
        # Duration of each child slot
        duration = datetime.combine(start_date, end_time) - datetime.combine(start_date, start_time)
        window = timedelta(hours=3)

        # Generate offsets in 15-minute steps, both earlier and later
        step = timedelta(minutes=15)
        offsets = []
        offset = step
        while offset <= window:
            offsets.append(-offset)  # try earlier first
            offsets.append(offset)   # then later
            offset += step

        # Helper to iterate each relevant date
        def iter_dates():
            current = start_date
            one_day = timedelta(days=1)
            while current <= end_date:
                if str(current.weekday()) in weekdays:
                    yield current
                current += one_day

        # Test a given offset for the entire series
        def test_offset(offset_td):
            for single_date in iter_dates():
                # Use the original start_time (a time object) and offset the combined datetime
                candidate_start = datetime.combine(single_date, start_time) + offset_td
                candidate_end = candidate_start + duration
                # Overlap check
                clash = (
                    Booking.query
                    .filter(Booking.environment_id == environment.id)
                    .filter(Booking.end > candidate_start, Booking.start < candidate_end)
                    .first()
                )
                if clash:
                    return False
            return True

        for offset_td in offsets:
            if test_offset(offset_td):
                # Return the new time-only pairs for the first day
                new_start_dt = datetime.combine(start_date, start_time) + offset_td
                new_end_dt = new_start_dt + duration
                return new_start_dt.time(), new_end_dt.time()

        return None, None
