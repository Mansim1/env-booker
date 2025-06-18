import pytest
from datetime import datetime, timedelta, timezone
from app import create_app, db
from app.models import User, Environment, Booking, AuditLog

@pytest.fixture
def client(tmp_path):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    with app.app_context():
        db.create_all()
        env = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@corp")
        db.session.add(env)
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
    with client.application.app_context():
        env = db.session.get(Environment, env_id)
        user = User.query.filter_by(email="regular@example.com").first()
        start = datetime(2025,6,1,9,0)
        db.session.add(Booking(
            environment_id=env.id,
            user_id=user.id,
            start=start,
            end=start+timedelta(hours=1)
        ))
        db.session.commit()
    url = "/bookings/new"
    if force_flag:
        url += "?force=true"
    return client.post(url, data={
        "environment": env_id,
        "start": "2025-06-01T09:00",
        "end":   "2025-06-01T10:00"
    }, follow_redirects=True)

def force_series_booking(client, env_id, force_flag=True):
    with client.application.app_context():
        env = db.session.get(Environment, env_id)
        user = User.query.filter_by(email="regular@example.com").first()
        for d_offset in range(3):
            d = datetime(2025,6,2).date() + timedelta(days=d_offset)
            start = datetime.combine(d, datetime.strptime("09:00","%H:%M").time())
            db.session.add(Booking(
                environment_id=env.id,
                user_id=user.id,
                start=start,
                end=start+timedelta(hours=1)
            ))
        db.session.commit()
    url = "/bookings/series?force=true"
    data = {
        "environment": env_id,
        "start_dt":   "2025-06-02T09:00",
        "end_dt":     "2025-06-06T10:00",
        "days_of_week": ["0","1","2","3","4"]
    }
    return client.post(url, data=data, follow_redirects=True)

def test_force_single_booking_creates_audit_entry(client):
    login(client, "admin@example.com", "AdminPass123!")
    resp = force_single_booking(client, env_id=1)
    assert b"Booking confirmed" in resp.data

    with client.application.app_context():
        logs = AuditLog.query.filter_by(action="forced_single_book").all()
        assert len(logs) == 1
        log = logs[0]

        # Now fetch the booking that log.booking_id points to
        forced_booking = db.session.get(Booking, log.booking_id)
        assert forced_booking is not None
        assert forced_booking.user.email == "admin@example.com"

        # Check timestamp freshness
        assert (datetime.utcnow() - log.timestamp).total_seconds() < 5

def test_force_series_booking_creates_multiple_audit_entries(client):
    login(client, "admin@example.com", "AdminPass123!")
    resp = force_series_booking(client, env_id=1)
    assert b"Series booking (forced) confirmed" in resp.data

    with client.application.app_context():
        bookings = Booking.query.filter_by(environment_id=1).all()
        assert len(bookings) == 8  # 3 preseeded + 5 forced

        logs = AuditLog.query.filter_by(action="forced_series_book").all()
        assert len(logs) == 5

        forced_ids = {log.booking_id for log in logs}
        admin_booking_ids = {
            b.id for b in bookings if b.user.email == "admin@example.com"
        }
        assert forced_ids.issubset(admin_booking_ids)

def test_audit_log_page_shows_entries_and_is_admin_only(client):
    # Seed manual entry
    with client.application.app_context():
        admin = User.query.filter_by(role="admin").first()
        b = Booking(
            environment_id=1,
            user_id=admin.id,
            start=datetime(2025,6,5,9,0),
            end=datetime(2025,6,5,10,0)
        )
        db.session.add(b)
        db.session.commit()
        db.session.add(AuditLog(
            action="forced_single_book",
            actor_id=admin.id,
            booking_id=b.id,
            timestamp=datetime(2025,6,5,9,0)
        ))
        db.session.commit()

    login(client, "regular@example.com", "Password123!")
    resp = client.get("/audit-log/")
    assert resp.status_code == 403

    login(client, "admin@example.com", "AdminPass123!")
    resp = client.get("/audit-log/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "admin@example.com" in text
    assert "Forced single booking" in text
    assert "2025-06-05 09:00:00" in text
