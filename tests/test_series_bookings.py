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

def post_series(client, env_id, start_dt, end_dt, weekdays):
    """
    Send a POST to /bookings/series with the combined datetime fields.
    weekdays should be a list of strings like ["0","1","2","3","4"].
    """
    return client.post(
        "/bookings/series",
        data={
            "environment": env_id,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "days_of_week": weekdays
        },
        follow_redirects=True
    )

def test_successful_series_booking(client):
    # Request Mon-Fri 09:00-10:00 from 2025-05-12 to 2025-05-23
    weekdays = ["0","1","2","3","4"]  # Monday-Friday
    resp = post_series(
        client,
        1,
        "2025-05-12T09:00",
        "2025-05-23T10:00",
        weekdays
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
        "2025-05-12T09:00",
        "2025-05-23T10:00",
        weekdays
    )
    # Because 2025-05-15 (Thursday) clashes, no new bookings should be created beyond the original
    assert b"Series failed: clash on 2025-05-15 09:00." in resp.data
    assert Booking.query.count() == 1  # Only the pre-seeded booking remains

def test_end_before_start_date_range(client):
    # Test end datetime before start datetime triggers form validation (inline error)
    weekdays = ["0","1","2","3","4"]
    resp = post_series(
        client,
        1,
        "2025-05-20T10:00",  # start_dt
        "2025-05-20T09:00",  # end_dt (before start)
        weekdays
    )
    # The form should display an inline validation error "End must be after Start."
    assert b"End must be after Start." in resp.data
    assert Booking.query.count() == 0

def test_no_weekdays_in_range(client):
    # Request a range that covers only a weekend but select only weekdays
    weekdays = ["0","1","2","3","4"]  # Monday-Friday
    resp = post_series(
        client,
        1,
        "2025-05-17T09:00",  # Saturday
        "2025-05-18T10:00",  # Sunday
        weekdays
    )
    # Because no weekday falls between 2025-05-17 and 2025-05-18, the service
    # should return a message about no valid slots.
    assert b"No valid weekday slots in the given date range." in resp.data
    assert Booking.query.count() == 0
