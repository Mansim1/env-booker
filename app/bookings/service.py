from datetime import datetime, timedelta
from app import db
from app.models import Booking

class BookingService:
    MAX_DURATION = timedelta(hours=8)

    @staticmethod
    def create_booking(user, environment, start, end):
        # 1. End must be after start
        if end <= start:
            return False, "End time must be after start time."
        # 2. Duration limit
        if end - start > BookingService.MAX_DURATION:
            return False, "Booking cannot exceed 8 hours."
        # 3. Overlap check
        overlap = (
            Booking.query
            .filter(Booking.environment_id == environment.id)
            .filter(Booking.end > start, Booking.start < end)
            .first()
        )
        if overlap:
            return False, "This slot is already booked."

        # 4. Create and commit
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
