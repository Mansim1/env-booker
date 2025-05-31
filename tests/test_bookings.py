import pytest
from datetime import datetime
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
    start = "2025-06-01T10:00"
    end   = "2025-06-01T12:00"
    resp = post_booking(client, 1, start, end)
    assert b"Booking confirmed: Sandbox1 from 2025-06-01 10:00 to 2025-06-01 12:00." in resp.data
    bkg = Booking.query.first()
    assert bkg.environment_id == 1

def test_end_before_start(client):
    resp = post_booking(client, 1, "2025-06-01T12:00", "2025-06-01T10:00")
    assert b"End time must be after start time." in resp.data

def test_exceeds_max_duration(client):
    resp = post_booking(client, 1, "2025-06-01T00:00", "2025-06-01T09:00")
    assert b"Booking cannot exceed 8 hours." in resp.data

def test_overlapping_booking(client):
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
    resp = post_booking(client, 1, "2025-06-01T10:00", "2025-06-01T12:00")
    assert b"This slot is already booked." in resp.data
