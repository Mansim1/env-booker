import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Environment, Booking

@pytest.fixture
def client(tmp_path):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    with app.app_context():
        db.create_all()
        e = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@x")
        db.session.add(e)
        u = User(email="eve@example.com", role="regular")
        u.set_password("Reg1user!")
        db.session.add(u)
        db.session.commit()
    with app.test_client() as c:
        c.post("/auth/login", data={"email":"eve@example.com","password":"Reg1user!"})
        yield c

def post_booking(client, env_id, start, end):
    return client.post(
        "/bookings/new",
        data={
            "environment": env_id,
            "start": start,
            "end": end
        },
        follow_redirects=True
    )

def test_successful_booking(client):
    # Use ISO "T" format so WTForms DateTimeLocalField parses correctly
    resp = post_booking(client, 1, "2025-06-01T10:00", "2025-06-01T12:00")
    assert b"Booking confirmed: Sandbox1 from 2025-06-01 10:00 to 2025-06-01 12:00" in resp.data

    with client.application.app_context():
        bkg = Booking.query.first()
        assert bkg.environment_id == 1

def test_end_before_start(client):
    resp = post_booking(client, 1, "2025-06-01T12:00", "2025-06-01T10:00")
    assert b"End time must be after start time." in resp.data

def test_exceeds_max_duration(client):
    resp = post_booking(client, 1, "2025-06-01T00:00", "2025-06-01T09:00")
    assert b"Booking cannot exceed 8 hours." in resp.data

def test_overlapping_booking_suggests_alternative(client):
    # Pre‐seed one booking from 09:00–11:00
    with client.application.app_context():
        db.session.add(
            Booking(
                environment_id=1,
                user_id=1,
                start=datetime(2025,6,1,9,0),
                end=datetime(2025,6,1,11,0)
            )
        )
        db.session.commit()

    # Attempt 10:00–12:00 → clash → service suggests a free slot
    resp = post_booking(client, 1, "2025-06-01T10:00", "2025-06-01T12:00")
    data = resp.get_data(as_text=True)

    # Check that “Suggested slot:” banner appears
    assert "Suggested slot:" in data

    # Verify the [Accept] link has the correct params (env_id=1 and ISO times)
    assert "/bookings/accept_suggestion?env_id=1&start=2025-06-01T11:00&end=2025-06-01T13:00" in data

def test_reject_when_daily_utilization_exceeds_cap(client):
    # Pre‐seed bookings so total = 23 hours for 2025-06-01
    with client.application.app_context():
        env = Environment.query.first()
        user = User.query.first()
        current_start = datetime(2025, 6, 1, 0, 0)
        for i in range(23):
            b = Booking(
                environment_id=env.id,
                user_id=user.id,
                start=current_start + timedelta(hours=i),
                end=current_start + timedelta(hours=i+1)
            )
            db.session.add(b)
        db.session.commit()

    # Attempt 23:00–00:00 (one more hour) → exceeds 90 % cap
    resp = client.post(
        "/bookings/new",
        data={
            "environment": 1,
            "start": "2025-06-01T23:00",
            "end":   "2025-06-02T00:00"
        },
        follow_redirects=True
    )
    assert b"Cannot book: daily utilization cap" in resp.data

    with client.application.app_context():
        total_bookings = Booking.query.filter(
            Booking.start >= datetime(2025,6,1,0,0),
            Booking.start <  datetime(2025,6,2,0,0)
        ).count()
        assert total_bookings == 23  # no new booking added

def test_allow_when_daily_utilization_within_cap(client):
    # Pre‐seed 20 hours (under 90 % = 21.6 h) for 2025-06-01
    with client.application.app_context():
        env = Environment.query.first()
        user = User.query.first()
        current_start = datetime(2025, 6, 1, 0, 0)
        for i in range(20):
            b = Booking(
                environment_id=env.id,
                user_id=user.id,
                start=current_start + timedelta(hours=i),
                end=current_start + timedelta(hours=i+1)
            )
            db.session.add(b)
        db.session.commit()

    # Attempt 20:00–21:30 (1.5 h) → total will be 21.5h < 21.6h cap
    resp = client.post(
        "/bookings/new",
        data={
            "environment": 1,
            "start": "2025-06-01T20:00",
            "end":   "2025-06-01T21:30"
        },
        follow_redirects=True
    )
    assert b"Booking confirmed: Sandbox1 from 2025-06-01 20:00 to 2025-06-01 21:30" in resp.data

    with client.application.app_context():
        count = Booking.query.filter(
            Booking.start == datetime(2025,6,1,20,0),
            Booking.end   == datetime(2025,6,1,21,30)
        ).count()
        assert count == 1
