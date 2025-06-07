# tests/test_audit_log.py

import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Environment, Booking, AuditLog

@pytest.fixture
def client(tmp_path):
    # Set up a fresh app and database
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"

    with app.app_context():
        db.create_all()
        # Create environment
        env = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@corp")
        db.session.add(env)
        # Create users
        regular = User(email="regular@example.com", role="regular")
        regular.set_password("Password123!")
        db.session.add(regular)
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()

    with app.test_client() as client:
        yield client

def login(client, email, password):
    return client.post("/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True
    )

def force_single_booking(client, env_id, force_flag=True):
    # Attempt to book a slot that will clash, forcing via URL param
    # First seed a clash
    with client.application.app_context():
        env = Environment.query.get(env_id)
        user = User.query.filter_by(email="regular@example.com").first()
        # Create a blocking booking 09:00–10:00 on 2025-06-01
        start = datetime(2025,6,1,9,0)
        Booking(environment_id=env.id, user_id=user.id, start=start, end=start+timedelta(hours=1))
        db.session.commit()

    # Now that clash exists, admin forces
    url = "/bookings/new"
    if force_flag:
        url += "?force=true"
    return client.post(url, data={
        "environment": env_id,
        "start": "2025-06-01T09:00",
        "end":   "2025-06-01T10:00"
    }, follow_redirects=True)

def force_series_booking(client, env_id, force_flag=True):
    # Pre-seed clashes on Mon–Wed 2025-06-02⋯04 09:00–10:00
    with client.application.app_context():
        env = Environment.query.get(env_id)
        user = User.query.filter_by(email="regular@example.com").first()
        for d_offset in range(3):
            d = datetime(2025,6,2).date() + timedelta(days=d_offset)
            start = datetime.combine(d, datetime.strptime("09:00","%H:%M").time())
            db.session.add(Booking(environment_id=env.id, user_id=user.id,
                                   start=start, end=start+timedelta(hours=1)))
        db.session.commit()

    # Admin forces series Mon–Fri 09:00–10:00
    url = "/bookings/series?force=true"
    data = {
        "environment": env_id,
        "start_dt":   "2025-06-02T09:00",
        "end_dt":     "2025-06-06T10:00",
        "days_of_week": ["0","1","2","3","4"]
    }
    return client.post(url, data=data, follow_redirects=True)

def test_force_single_booking_creates_audit_entry(client):
    # Admin logs in and forces a single booking
    login(client, "admin@example.com", "AdminPass123!")
    resp = force_single_booking(client, env_id=1)
    assert b"Series booking" not in resp.data  # sanity check

    # Check that exactly one booking exists and one audit row
    with client.application.app_context():
        booking = Booking.query.first()
        assert booking is not None

        logs = AuditLog.query.all()
        assert len(logs) == 1

        log = logs[0]
        assert log.actor.email == "admin@example.com"
        assert log.booking_id == booking.id
        assert log.action == "Forced single booking"
        # Timestamp should be very recent (within 5 seconds)
        assert (datetime.utcnow() - log.timestamp).total_seconds() < 5

def test_force_series_booking_creates_multiple_audit_entries(client):
    # Admin logs in and forces a series booking
    login(client, "admin@example.com", "AdminPass123!")
    resp = force_series_booking(client, env_id=1)
    assert b"Series booking (forced) confirmed" in resp.data

    # Series span 5 days → expect 5 new bookings and 5 audit entries
    with client.application.app_context():
        bookings = Booking.query.filter_by(environment_id=1).all()
        # 3 preseeded + 5 forced = 8
        assert len(bookings) == 8

        logs = AuditLog.query.filter_by(action="Forced series booking").all()
        assert len(logs) == 5

        # Each log refers to one of the forced bookings
        forced_ids = {log.booking_id for log in logs}
        booking_ids = {b.id for b in bookings if b.user.email=="admin@example.com"}
        assert forced_ids.issubset(booking_ids)

def test_audit_log_page_shows_entries_and_is_admin_only(client):
    # Seed one audit entry manually
    with client.application.app_context():
        admin = User.query.filter_by(role="admin").first()
        b = Booking(environment_id=1, user_id=admin.id,
                    start=datetime(2025,6,5,9,0), end=datetime(2025,6,5,10,0))
        db.session.add(b); db.session.commit()

        db.session.add(AuditLog(
            action="Forced single booking",
            actor_id=admin.id,
            booking_id=b.id,
            timestamp=datetime(2025,6,5,9,0)
        ))
        db.session.commit()

    # Regular user may not view
    login(client, "regular@example.com", "Password123!")
    resp = client.get("/admin/audit-log")
    assert resp.status_code == 403

    # Admin user can view
    login(client, "admin@example.com", "AdminPass123!")
    resp = client.get("/admin/audit-log")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    # Table row contains the admin email, booking id, action, and timestamp
    assert "admin@example.com" in text
    assert "Forced single booking" in text
    assert "2025-06-05 09:00:00" in text  # or formatted however you display it
