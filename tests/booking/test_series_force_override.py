# tests/test_series_force_override.py

import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Environment, Booking


@pytest.fixture
def client(tmp_path):
    """
    Create a fresh application and database for each test.
    We will create one environment (“Sandbox1”) and two users:
    - “regular@example.com” with role="regular"
    - “admin@example.com” with role="admin"
    """
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"

    with app.app_context():
        db.create_all()
        # Create one environment
        env = Environment(
            name="Sandbox1", owner_squad="Team1", created_by_email="admin@corp"
        )
        db.session.add(env)

        # Create a regular user
        regular = User(email="regular@example.com", role="regular")
        regular.set_password("Password123!")
        db.session.add(regular)

        # Create an admin user
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)

        db.session.commit()

    with app.test_client() as c:
        yield c


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def post_series(client, env_id, start_dt, end_dt, weekdays, force_flag=False):
    """
    POST /bookings/series with or without ?force=true.
    - start_dt, end_dt: ISO strings "YYYY-MM-DDTHH:MM"
    - weekdays: list of strings, e.g. ["0","1","2","3","4"]
    """
    url = "/bookings/series"
    if force_flag:
        url += "?force=true"

    data = {
        "environment": env_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
        # When submitting multiple days_of_week, WTForms expects multiple form entries
    }
    # Append each weekday as its own form entry:
    for d in weekdays:
        data["days_of_week"] = data.get("days_of_week", []) + [d]

    return client.post(url, data=data, follow_redirects=True)


@pytest.mark.usefixtures("client")
class TestSeriesForceOverride:
    def test_regular_user_sees_suggestion_but_cannot_force(self, client):
        """
        1. Log in as regular → pre‐seed a clash (Mon‐Wed 09:00–10:00).
        2. Regular tries to book Mon‐Fri 09:00–10:00 → sees suggestion, no Force Series button.
        3. Regular explicitly tries to force by adding ?force=true → still falls back to normal clash logic.
        """
        # 1) Log in as regular
        resp = login(client, "regular@example.com", "Password123!")
        assert b"Welcome, regular@example.com" in resp.data

        # Pre‐seed a clash: Mon–Wed 2025-06-02 to 2025-06-04, each day 09:00–10:00
        with client.application.app_context():
            env = Environment.query.first()
            user = User.query.filter_by(email="regular@example.com").first()
            for day_offset in range(3):  # 06-02, 06-03, 06-04
                d = datetime(2025, 6, 2).date() + timedelta(days=day_offset)
                slot_start = datetime.combine(d, datetime.strptime("09:00", "%H:%M").time())
                slot_end = slot_start + timedelta(hours=1)
                b = Booking(
                    environment_id=env.id,
                    user_id=user.id,
                    start=slot_start,
                    end=slot_end,
                )
                db.session.add(b)
            db.session.commit()

        # 2) Regular tries to book Mon–Fri (2025-06-02 to 2025-06-06) 09:00–10:00
        weekdays = ["0", "1", "2", "3", "4"]  # Mon–Fri
        resp2 = post_series(
            client,
            1,
            "2025-06-02T09:00",
            "2025-06-06T10:00",
            weekdays,
            force_flag=False,
        )
        text = resp2.get_data(as_text=True)

        # Should see a suggestion banner (not the “Force Series” button).
        assert "Series failed due to clash. Suggested series:" in text
        assert "[Accept Suggestion]" in text
        # But no "Force Series" button or form
        assert "Force Series" not in text

        # 3) Regular explicitly tries ?force=true
        resp3 = post_series(
            client, 1, "2025-06-02T09:00", "2025-06-06T10:00", weekdays, force_flag=True
        )
        text3 = resp3.get_data(as_text=True)
        # Because regular is not admin, they still get the clash suggestion (no override).
        assert "Series failed due to clash" in text3
        assert "[Accept Suggestion]" in text3
        assert "Force Series" not in text3

        # Confirm no new bookings beyond the 3 pre‐seeded
        with client.application.app_context():
            count = Booking.query.count()
            assert count == 3

    def test_admin_can_force_series_despite_clash(self, client):
        """
        1. Log in as admin → pre‐seed clashes (Mon–Wed 09:00–10:00).
        2. Admin POST /bookings/series?force=true for Mon–Fri 09:00–10:00.
        3. All five slots (Mon–Fri) are created, duplicating the existing three.
           We expect a total of 8 bookings (3 pre‐seeded + 5 forced).
        """
        # 1) Log in as admin
        resp = login(client, "admin@example.com", "AdminPass123!")
        assert b"Welcome, admin@example.com" in resp.data

        # Pre‐seed a clash: Mon–Wed 2025-06-02 to 2025-06-04, each day 09:00–10:00
        with client.application.app_context():
            env = Environment.query.first()
            user = User.query.filter_by(email="regular@example.com").first()
            for day_offset in range(3):  # 06-02, 06-03, 06-04
                d = datetime(2025, 6, 2).date() + timedelta(days=day_offset)
                slot_start = datetime.combine(d, datetime.strptime("09:00", "%H:%M").time())
                slot_end = slot_start + timedelta(hours=1)
                b = Booking(
                    environment_id=env.id,
                    user_id=user.id,
                    start=slot_start,
                    end=slot_end,
                )
                db.session.add(b)
            db.session.commit()

        # 2) Admin issues force‐series for Mon–Fri (2025-06-02 to 2025-06-06) 09:00–10:00
        weekdays = ["0", "1", "2", "3", "4"]  # Mon–Fri
        resp2 = post_series(
            client,
            1,
            "2025-06-02T09:00",
            "2025-06-06T10:00",
            weekdays,
            force_flag=True
        )
        text2 = resp2.get_data(as_text=True)

        # Should see a success flash indicating “forced” and 5 slots
        assert "Series booking (forced) confirmed: 5 slots for Sandbox1." in text2

        # 3) Confirm that there are exactly 8 bookings total
        with client.application.app_context():
            all_bookings = (
                Booking.query.filter(Booking.environment_id == 1)
                .order_by(Booking.start)
                .all()
            )
            # 3 pre‐seeded + 5 forced = 8
            assert len(all_bookings) == 8

            # Verify that each of the five dates (06-02 through 06-06) has at least one 09:00 booking
            expected_dates = [
                datetime(2025, 6, 2).date(),
                datetime(2025, 6, 3).date(),
                datetime(2025, 6, 4).date(),
                datetime(2025, 6, 5).date(),
                datetime(2025, 6, 6).date(),
            ]

            starts = [b.start for b in all_bookings]
            for d in expected_dates:
                # There should be at least one booking at 09:00 for this date
                matching = [b for b in starts if b.date() == d and b.hour == 9 and b.minute == 0]
                assert len(matching) >= 1

    def test_admin_can_force_when_daily_cap_exceeded(self, client):
        """
        1. Log in as admin → Pre‐seed 20 one‐hour bookings on 2025-06-10 → utilization=20h.
        2. Admin tries 09:00–18:00 (9h) for that single day (start_date=end_date=2025-06-10).
           Normal logic would reject (20 + 9 = 29h > 21.6h cap).
        3. But with force=true, Admin should create all 9 hours anyway.
        """
        # 1) Log in as admin
        login(client, "admin@example.com", "AdminPass123!")

        # Pre‐seed 20 one‐hour bookings on 2025-06-10 at 00:00–20:00
        with client.application.app_context():
            env = Environment.query.first()
            user = User.query.filter_by(email="regular@example.com").first()
            base = datetime(2025, 6, 10, 0, 0)
            for hour in range(20):
                slot_start = base + timedelta(hours=hour)
                slot_end = slot_start + timedelta(hours=1)
                b = Booking(
                    environment_id=env.id,
                    user_id=user.id,
                    start=slot_start,
                    end=slot_end,
                )
                db.session.add(b)
            db.session.commit()

        # 2) Admin tries to force a “series” from 2025-06-10T09:00 to 2025-06-10T18:00
        resp = post_series(
            client,
            1,
            "2025-06-10T09:00",
            "2025-06-19T18:00",
            weekdays=["2"],  # Wednesday (2025-06-10 is a Wednesday)
            force_flag=True
        )
        text = resp.get_data(as_text=True)
        assert "Series booking (forced) confirmed: 2 slots for Sandbox1." in text

    def test_regular_cannot_force_when_daily_cap_exceeded(self, client):
        """
        Ensure a regular user is still blocked by the cap even if they add ?force=true.
        """
        # 1) Log in as regular
        login(client, "regular@example.com", "Password123!")

        # Pre‐seed 22 one‐hour bookings on 2025-06-11 (22h)
        with client.application.app_context():
            env = Environment.query.first()
            user = User.query.filter_by(email="regular@example.com").first()
            base = datetime(2025, 6, 11, 0, 0)
            for hour in range(22):
                slot_start = base + timedelta(hours=hour)
                slot_end = slot_start + timedelta(hours=1)
                b = Booking(
                    environment_id=env.id,
                    user_id=user.id,
                    start=slot_start,
                    end=slot_end,
                )
                db.session.add(b)
            db.session.commit()

        # 2) Regular tries to “force” book 2025-06-11T09:00–16:00 (7h)
        resp = post_series(
            client,
            1,
            "2025-06-11T09:00",
            "2025-06-11T16:00",
            weekdays=["2"],  # Wednesday
            force_flag=True,
        )
        text = resp.get_data(as_text=True)

        # They should be blocked by the daily cap and see that error (no “forced” success).
        print(text)
        assert "Cannot book: daily utilization cap" in text
        assert "Force Series" not in text

        # Confirm that no additional slot was created beyond the 22
        with client.application.app_context():
            total = Booking.query.filter(
                Booking.start >= datetime(2025, 6, 11, 0, 0),
                Booking.start <  datetime(2025, 6, 12, 0, 0),
            ).count()
            assert total == 22
