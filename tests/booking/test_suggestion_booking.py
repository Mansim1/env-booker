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
        # seed environment
        e = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@x")
        db.session.add(e)
        # seed user
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
        data={"environment": env_id, "start": start, "end": end},
        follow_redirects=True
    )

def accept_suggestion(client, env_id, start, end):
    return client.get(
        f"/bookings/accept_suggestion?env_id={env_id}&start={start}&end={end}",
        follow_redirects=True
    )

def test_suggested_slot_appears(client):
    # Pre-seed a clash: 12:00-14:00
    with client.application.app_context():
        db.session.add(
            Booking(
                environment_id=1,
                user_id=1,
                start=datetime(2025,6,1,12,0),
                end=datetime(2025,6,1,14,0)
            )
        )
        db.session.commit()

    # Attempt to book 13:00-15:00
    resp = post_booking(client, 1, "2025-06-01 13:00", "2025-06-01 15:00")
    # Expect a suggestion: ±3h → earliest free is 09:00-11:00
    assert b"Suggested slot: 2025-06-01 09:00\u20132025-06-01 11:00" in resp.data
    # Confirm [Accept] link is present
    assert b"?env_id=1&start=2025-06-01T09:00&end=2025-06-01T11:00" in resp.data

def test_no_suggestion_when_none_available(client):
    # Fill all ±3h windows. For two‐hour slot, that means:
    # Pre-seed bookings covering 10:00-12:00, 11:00-13:00, 12:00-14:00, 13:00-15:00, 14:00-16:00, ...
    # Simplify by seeding every 2-hour block from 10:00 to 16:00:
    with client.application.app_context():
        for hour in [10, 12, 14]:
            db.session.add(
                Booking(
                    environment_id=1,
                    user_id=1,
                    start=datetime(2025,6,1,hour,0),
                    end=datetime(2025,6,1,hour+2,0)
                )
            )
        db.session.commit()

    resp = post_booking(client, 1, "2025-06-01 12:00", "2025-06-01 14:00")
    # Should only see the generic clash message
    assert b"This slot is already booked." in resp.data
    assert b"Suggested slot:" not in resp.data

def test_accept_suggestion_creates_booking(client):
    # Pre-seed clash for 12:00-14:00 so suggestion is 09:00-11:00
    with client.application.app_context():
        db.session.add(
            Booking(
                environment_id=1,
                user_id=1,
                start=datetime(2025,6,1,12,0),
                end=datetime(2025,6,1,14,0)
            )
        )
        db.session.commit()

    # Get suggestion
    resp = post_booking(client, 1, "2025-06-01 13:00", "2025-06-01 15:00")
    assert b"Suggested slot: 2025-06-01 09:00\u20132025-06-01 11:00" in resp.data

    # Accept suggestion
    resp2 = accept_suggestion(client, 1, "2025-06-01T09:00", "2025-06-01T11:00")
    # After acceptance, booking should be created
    assert b"Booking confirmed: Sandbox1 from 2025-06-01 09:00 to 2025-06-01 11:00." in resp2.data

    # Verify in database
    b1 = Booking.query.filter_by(start=datetime(2025,6,1,9,0)).first()
    assert b1 is not None
