import pytest
from datetime import datetime, timedelta
from app import db
from app.models import AuditLog, Booking, Environment, User
from app.bookings.service import BookingService
from tests.utils import future_datetime, login_user, login_admin

# Utility to get environment object safely
def get_environment():
    return Environment.query.first()

def test_overlap_exists_true_false(client):
    login_user(client)
    with client.application.app_context():
        user = User.query.filter_by(email="eve@example.com").first()
        env = get_environment()
        start, end = future_datetime()
        # Create overlap booking
        db.session.add(Booking(environment_id=env.id, user_id=user.id, start=datetime.strptime(start, "%Y-%m-%dT%H:%M"), end=datetime.strptime(end, "%Y-%m-%dT%H:%M")))
        db.session.commit()

        s = datetime.strptime(start, "%Y-%m-%dT%H:%M")
        e = datetime.strptime(end, "%Y-%m-%dT%H:%M")

        assert BookingService._overlap_exists(env.id, s, e) is True
        assert BookingService._overlap_exists(env.id, s + timedelta(hours=3), e + timedelta(hours=3)) is False

def test_daily_util_seconds(client):
    login_user(client)
    with client.application.app_context():
        user = User.query.filter_by(email="eve@example.com").first()
        env = get_environment()
        today = datetime.now()
        start = today.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=2)

        db.session.add(Booking(environment_id=env.id, user_id=user.id, start=start, end=end))
        db.session.commit()

        seconds = BookingService._daily_util_seconds(env.id, today.date())
        assert seconds == 7200  # 2 hours in seconds

def test_validate_single_failures_and_success(client):
    login_user(client)
    with client.application.app_context():
        env = get_environment()

        # Fail: end before start
        start = datetime.now() + timedelta(days=1)
        end = start - timedelta(hours=1)
        ok, msg = BookingService._validate_single(env.id, start, end)
        assert not ok and "after start" in msg

        # Fail: too long
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=9)
        ok, msg = BookingService._validate_single(env.id, start, end)
        assert not ok and "exceed 8 hours" in msg

        # Pass
        end = start + timedelta(hours=1)
        ok, msg = BookingService._validate_single(env.id, start, end)
        assert ok and msg is None

def test_create_booking_and_suggestion(client):
    login_user(client)
    with client.application.app_context():
        user = User.query.filter_by(email="eve@example.com").first()
        env = get_environment()

        start = datetime.now() + timedelta(days=1, hours=9)
        end = start + timedelta(hours=1)

        # Create a booking
        ok, booking = BookingService.create_booking(user, env, start, end)
        assert ok and isinstance(booking, Booking)

        # Try overlapping booking and get suggestion
        conflict_start = start
        conflict_end = end
        sug_start, sug_end = BookingService.find_suggestion(env, conflict_start, conflict_end)
        assert sug_start is not None
        assert sug_end is not None

def test_validate_single_duration_and_util_cap(client, app_instance):

    with app_instance.app_context():
        env = Environment.query.first()

        # Create 22 hours worth of 1-hour bookings (22/24 = 91.6%)
        base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(22):
            start = base + timedelta(hours=i)
            end = start + timedelta(hours=1)
            db.session.add(Booking(environment_id=env.id, user_id=1, start=start, end=end))
        db.session.commit()

        # Now attempt another 1-hour booking (23rd hour)
        over_start = base + timedelta(hours=22)
        over_end = over_start + timedelta(hours=1)
        valid, msg = BookingService._validate_single(env.id, over_start, over_end)
        assert not valid
        assert "utilization cap" in msg

def test_build_slots_no_matching_weekdays():
    start = datetime(2025, 6, 17, 10, 0)  # Tuesday
    end = datetime(2025, 6, 18, 12, 0)    # Wednesday
    weekdays = ["5", "6"]  # Saturday, Sunday
    slots = BookingService._build_slots(start, end, weekdays)
    assert slots == []

def test_bulk_insert_with_audit(client):
    login_user(client)

    with client.application.app_context():
        user = User.query.filter_by(email="eve@example.com").first()
        env = Environment.query.first()
        now = datetime.now()
        slots = [(now + timedelta(days=1), now + timedelta(days=1, hours=1))]
        count = BookingService._bulk_insert_with_audit(user, env, slots, "test_action")
        assert count == 1

def test_find_series_suggestion_valid(monkeypatch, client):
    with client.application.app_context():
        env = Environment.query.first()
        monkeypatch.setattr(BookingService, "_overlap_exists", lambda *args, **kwargs: False)
        result = BookingService.find_series_suggestion(
            env,
            datetime(2025, 6, 17).date(),
            datetime(2025, 6, 18).date(),
            ["1"],  # Tuesday
            datetime.min.time(),
            (datetime.min + timedelta(hours=1)).time()
        )
        assert result != (None, None)

def test_attempt_single_booking_admin_force(client):

    with client.application.app_context():
        user = User.query.filter_by(email="admin@example.com").first()
        env = Environment.query.first()
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        ok, result = BookingService.attempt_single_booking(user, env, start, end, force=True)
        assert ok
        assert hasattr(result, "id")
