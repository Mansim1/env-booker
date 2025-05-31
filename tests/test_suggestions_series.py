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
        # create environment
        e = Environment(name="Sandbox1", owner_squad="Team1", created_by_email="admin@x")
        db.session.add(e)
        # create user
        u = User(email="eve@example.com", role="regular")
        u.set_password("Reg1user!")
        db.session.add(u)
        db.session.commit()
    with app.test_client() as c:
        c.post("/auth/login", data={"email":"eve@example.com","password":"Reg1user!"})
        yield c

def post_series(client, env_id, start_dt, end_dt, weekdays):
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

def accept_series(client, env_id, start_date, end_date, weekdays, start_time, end_time):
    return client.get(
        f"/bookings/accept_series_suggestion"
        f"?env_id={env_id}"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
        f"&weekdays={','.join(weekdays)}"
        f"&start_time={start_time}"
        f"&end_time={end_time}",
        follow_redirects=True
    )

def test_series_suggestion_appears(client):
    # Pre-seed clashes for Mon-Fri 09:00-10:00 (2025-05-12 to 2025-05-16)
    with client.application.app_context():
        start_date = datetime(2025,5,12).date()
        for single_date in [start_date + timedelta(days=i) for i in range(5)]:  # Mon–Fri
            db.session.add(
                Booking(
                    environment_id=1,
                    user_id=1,
                    start=datetime.combine(single_date, datetime.strptime("09:00", "%H:%M").time()),
                    end=datetime.combine(single_date, datetime.strptime("10:00", "%H:%M").time())
                )
            )
        db.session.commit()

    weekdays = ["0","1","2","3","4"]  # Mon–Fri
    resp = post_series(client, 1, "2025-05-12T09:00", "2025-05-16T10:00", weekdays)

    text = resp.get_data(as_text=True)
    # We expect the suggestion to mention "Suggested series:"
    assert "Series failed due to clash. Suggested series:" in text
    # The earliest free offset should be 08:00–09:00
    assert "2025-05-12 08:00-09:00" in text
    # Confirm the [Accept] link is present with those parameters
    assert "/bookings/accept_series_suggestion?env_id=1&start_date=2025-05-12&end_date=2025-05-16&weekdays=0,1,2,3,4&start_time=08:00&end_time=09:00" in text

def test_no_series_suggestion_when_none_available(client):
    # Pre-seed busy slots so no 1-hour window can fit ±3h.
    # Block hourly windows from 06:00 to 16:00 each weekday
    with client.application.app_context():
        start_date = datetime(2025,5,12).date()
        for single_date in [start_date + timedelta(days=i) for i in range(5)]:
            for hr in range(6, 16):
                db.session.add(
                    Booking(
                        environment_id=1,
                        user_id=1,
                        start=datetime.combine(single_date, datetime.strptime(f"{hr:02}:00", "%H:%M").time()),
                        end=datetime.combine(single_date, datetime.strptime(f"{hr+1:02}:00", "%H:%M").time())
                    )
                )
        db.session.commit()

    weekdays = ["0","1","2","3","4"]
    resp = post_series(client, 1, "2025-05-12T09:00", "2025-05-16T10:00", weekdays)

    text = resp.get_data(as_text=True)
    # Since all windows 06–16 are blocked, no suggestion should appear
    assert "Series failed: no alternative series available within" in text
    assert "[Accept]" not in text

def test_accept_series_suggestion_creates_bookings(client):
    # Pre-seed MON-FRI 09:00–10:00 so suggestion is 08:00–09:00
    with client.application.app_context():
        start_date = datetime(2025,5,12).date()
        for single_date in [start_date + timedelta(days=i) for i in range(5)]:
            db.session.add(
                Booking(
                    environment_id=1,
                    user_id=1,
                    start=datetime.combine(single_date, datetime.strptime("09:00", "%H:%M").time()),
                    end=datetime.combine(single_date, datetime.strptime("10:00", "%H:%M").time())
                )
            )
        db.session.commit()

    weekdays = ["0","1","2","3","4"]
    # Attempt series, get suggestion
    resp = post_series(client, 1, "2025-05-12T09:00", "2025-05-16T10:00", weekdays)
    text = resp.get_data(as_text=True)
    assert "Suggested series:" in text

    # Accept suggestion of 08:00–09:00
    resp2 = accept_series(
        client,
        1,
        "2025-05-12",  # start_date
        "2025-05-16",  # end_date
        weekdays,
        "08:00",       # start_time
        "09:00"        # end_time
    )
    text2 = resp2.get_data(as_text=True)
    assert "Series booking confirmed: 5 slots for Sandbox1." in text2

    # Verify exactly one booking at 08:00–09:00 for each weekday
    with client.application.app_context():
        start_date = datetime(2025,5,12).date()
        for i in range(5):
            single_date = start_date + timedelta(days=i)
            dt_start = datetime.combine(single_date, datetime.strptime("08:00", "%H:%M").time())
            dt_end   = datetime.combine(single_date, datetime.strptime("09:00", "%H:%M").time())
            booking = Booking.query.filter_by(environment_id=1, start=dt_start, end=dt_end).first()
            assert booking is not None
