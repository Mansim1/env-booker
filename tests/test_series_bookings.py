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
        # create environment
        e = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@x")
        db.session.add(e)
        # create user
        u = User(email="eve@example.com", role="regular")
        u.set_password("Reg1user!")
        db.session.add(u)
        db.session.commit()
    with app.test_client() as c:
        # login
        c.post("/auth/login", data={"email":"eve@example.com","password":"Reg1user!"})
        yield c

def post_series(client, env_id, start_date, end_date, weekdays, start_time, end_time):
    return client.post(
        "/bookings/series",
        data={
            "environment": env_id,
            "start_date": start_date,
            "end_date": end_date,
            "days_of_week": weekdays,
            "start_time": start_time,
            "end_time": end_time,
        },
        follow_redirects=True
    )

def test_successful_series_booking(client):
    # Request Mon-Fri 09:00-10:00 from 2025-05-12 to 2025-05-23
    weekdays = ["0","1","2","3","4"]  # Monday-Friday
    resp = post_series(
        client,
        1,
        "2025-05-12",  # Monday
        "2025-05-23",  # Friday of next week
        weekdays,
        "09:00",
        "10:00"
    )
    # There are 2 weeks × 5 weekdays = 10 slots
    assert b"Series booking confirmed: 10 slots for Sandbox1." in resp.data
    assert Booking.query.count() == 10

def test_series_fails_on_clash(client):
    # Pre-seed a single booking on 2025-05-15 09:00-10:00
    with client.application.app_context():
        db.session.add(
            Booking(
                environment_id=1,
                user_id=1,
                start=datetime(2025,5,15,9,0),
                end=datetime(2025,5,15,10,0)
            )
        )
        db.session.commit()

    weekdays = ["0","1","2","3","4"]
    resp = post_series(
        client,
        1,
        "2025-05-12",
        "2025-05-23",
        weekdays,
        "09:00",
        "10:00"
    )
    # Because 2025-05-15 (Thursday) clashes, no bookings should be created
    assert b"Series failed: clash on 2025-05-15 09:00." in resp.data
    assert Booking.query.count() == 1  # Only the pre-seeded booking remains
