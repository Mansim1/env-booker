import pytest
from app import create_app, db
from app.models import User

@pytest.fixture
def client(tmp_path):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    with app.app_context():
        db.create_all()
        u = User(email="eve@example.com")
        u.set_password("RegUser123!")
        db.session.add(u)
        db.session.commit()
    with app.test_client() as c:
        yield c

def post_login(client, email, pw):
    return client.post(
        "/auth/login",
        data={"email": email, "password": pw},
        follow_redirects=True,
    )

def test_successful_login(client):
    resp = post_login(client, "eve@example.com", "RegUser123!")
    assert b"Welcome, eve@example.com" in resp.data
    assert resp.request.path == "/"

def test_missing_login_fields(client):
    resp = post_login(client, "", "")
    assert b"Email is required." in resp.data
    assert b"Password is required." in resp.data

def test_invalid_credentials(client):
    resp = post_login(client, "eve@example.com", "WrongPass!")
    assert b"Invalid email or password." in resp.data

def test_sql_injection_in_login_email(client):
    resp = post_login(client, "test'; DROP TABLE bookings;--", "whatever")
    print(resp.data)
    assert b"Invalid characters in field." in resp.data

def test_xss_injection_in_login_email(client):
    resp = post_login(client, "<img src=x onerror=alert(1)>@ex.com", "whatever")
    assert b"Enter a valid email address." in resp.data

def test_email_max_length_login(client):
    long_email = "a" * 121 + "@x.com"
    resp = post_login(client, long_email, "RegUser123!")
    print(resp.data)
    assert b"Email must be 120 characters or fewer." in resp.data

def test_password_min_length_login(client):
    resp = post_login(client, "eve@example.com", "short")
    assert b"Password must be at least 8 characters." in resp.data

def test_protected_route_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
