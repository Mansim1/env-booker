from datetime import timedelta
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
