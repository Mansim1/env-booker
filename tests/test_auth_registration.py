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
        with app.test_client() as c:
            yield c

def post_register(client, email, pw, confirm):
    return client.post(
        "/auth/register",
        data={"email": email, "password": pw, "confirm": confirm},
        follow_redirects=True,
    )

def test_missing_fields(client):
    resp = post_register(client, "", "", "")
    assert b"Email is required." in resp.data
    assert b"Password is required." in resp.data
    assert b"Please confirm your password." in resp.data

def test_invalid_email_format(client):
    resp = post_register(client, "not-an-email", "SecurePass1!", "SecurePass1!")
    assert b"Enter a valid email address." in resp.data

def test_email_whitespace_stripped(client):
    resp = post_register(client, "   alice@example.com   ", "SecurePass1!", "SecurePass1!")
    # Should treat as valid and create user
    assert b"Registration complete! Please log in." in resp.data
    user = User.query.filter_by(email="alice@example.com").first()
    assert user is not None

def test_sql_injection_in_email(client):
    malicious = "test; DROP TABLE users;"
    resp = post_register(client, malicious, "SecurePass1!", "SecurePass1!")
    assert b"Invalid characters in field." in resp.data

def test_password_invalid_chars(client):
    resp = post_register(client, "eve@example.com", "Bad Space!", "Bad Space!")
    assert b"Password contains invalid characters." in resp.data

def test_xss_injection_in_email(client):
    xss = "<script>alert(1)</script>@example.com"
    resp = post_register(client, xss, "SecurePass1!", "SecurePass1!")
    assert b"Enter a valid email address." in resp.data

def test_password_confirmation_mismatch(client):
    resp = post_register(client, "bob@example.com", "SecurePass1!", "SecurePass2!")
    assert b"Passwords do not match." in resp.data

def test_successful_registration_creates_user(client):
    resp = post_register(client, "carol@example.com", "SecurePass1!", "SecurePass1!")
    assert b"Registration complete! Please log in." in resp.data
    user = User.query.filter_by(email="carol@example.com").first()
    assert user is not None
