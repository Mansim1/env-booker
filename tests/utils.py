from datetime import datetime, timedelta
from app.models import Environment

# ──────── AUTH HELPERS ─────────

def post_login(client, email, pw):
    """Log in any user."""
    return client.post("/auth/login", data={"email": email, "password": pw}, follow_redirects=True)

def login_user(client):
    """Log in as regular user."""
    return post_login(client, "eve@example.com", "RegUser123!")

def login_admin(client):
    """Log in as admin user."""
    return post_login(client, "admin@example.com", "AdminPass123!")

def logout_user(client):
    """Logout the user."""
    return client.get("/auth/logout", follow_redirects=True)


# ──────── BOOKING HELPERS ─────────

def post_single_booking(client, env_id, start, end):
    """Create a single booking."""
    return client.post(
        "/bookings/new",
        data={"environment": env_id, "start": start, "end": end},
        follow_redirects=True
    )

def post_series_booking(client, env_id, start_dt, end_dt, weekdays):
    """Create a series booking."""
    return client.post(
        "/bookings/series",
        data={
            "environment": env_id,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "days_of_week": weekdays,
        },
        follow_redirects=True
    )

# ──────── DATETIME HELPERS ─────────

def future_datetime(offset_days=7, hour=9, duration_hours=1):
    """Generate future datetime strings for form inputs."""
    start = (datetime.now() + timedelta(days=offset_days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=duration_hours)
    return start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")


# ──────── ENVIRONMENT HELPERS ─────────

def get_environment():
    """Get the seeded test environment from the DB."""
    return Environment.query.filter_by(name="Env1").first()
