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
    # We expect the suggestion to mention "±3 hours"
    assert "Series failed due to clash. Suggested series:" in text
    assert "±3 hours" in text
    # And the accept link should be present
    assert "/bookings/accept_series_suggestion?env_id=1&start_date=2025-05-12&end_date=2025-05-16&weekdays=0,1,2,3,4&start_time=13:00&end_time=14:00" in text

def test_no_series_suggestion_when_none_available(client):
    # Pre-seed busy slots so no 1-hour window can fit ±3h.
    # e.g. fill 06-07, 07-08, 08-09, 09-10, 10-11, 11-12, 12-13, 13-14, 14-15, 15-16 each weekday
    with client.application.app_context():
        start_date = datetime(2025,5,12).date()
        for single_date in [start_date + timedelta(days=i) for i in range(5)]:
            # block all windows from 06:00 to 16:00, in 1-hour increments
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
    assert "Series failed: no alternative series available within ±3 hours." in text
    # No new bookings beyond the seeded ones
    total_seeded = 5 * 10  # 5 days × 10 hourly slots
    assert Booking.query.count() == total_seeded

def test_accept_series_suggestion_creates_bookings(client):
    # Pre-seed MON-FRI 09:00–10:00 so suggestion is 13:00–14:00
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

    # Accept suggestion of 13:00–14:00
    resp2 = accept_series(
        client,
        1,
        "2025-05-12",  # start_date
        "2025-05-16",  # end_date
        weekdays,
        "13:00",       # start_time
        "14:00"        # end_time
    )
    text2 = resp2.get_data(as_text=True)
    assert "Series booking confirmed: 5 slots for Sandbox1." in text2

    # Verify 5 new bookings at 13:00–14:00 exist
    with client.application.app_context():
        count_new = (
            Booking.query
            .filter(Booking.start >= datetime(2025,5,12,13,0))
            .filter(Booking.end <= datetime(2025,5,16,14,0))
            .count()
        )
        assert count_new == 5
