from app.models import User

# Helper function to simulate registration
def post_register(client, email, pw, confirm):
    return client.post("/auth/register", data={"email": email, "password": pw, "confirm": confirm}, follow_redirects=True)

# Test that required field errors are shown when all fields are empty
def test_missing_fields(client):
    resp = post_register(client, "", "", "")
    assert b"Email is required." in resp.data
    assert b"Password is required." in resp.data
    assert b"Please confirm your password." in resp.data

# Test that invalid email formats are caught
def test_invalid_email_format(client):
    resp = post_register(client, "not-an-email", "SecurePass1!", "SecurePass1!")
    assert b"Enter a valid email address." in resp.data

# Test that extra whitespace in email is stripped and user is created
def test_email_whitespace_stripped(client):
    resp = post_register(client, "   alice@example.com   ", "SecurePass1!", "SecurePass1!")
    assert b"Registration complete! Please log in." in resp.data
    user = User.query.filter_by(email="alice@example.com").first()
    assert user is not None

# Test that SQL injection in email is blocked
def test_sql_injection_in_email(client):
    resp = post_register(client, "test; DROP TABLE users;", "SecurePass1!", "SecurePass1!")
    assert b"Invalid characters in field." in resp.data

# Test that passwords with invalid characters are rejected
def test_password_invalid_chars(client):
    resp = post_register(client, "eve2@example.com", "Bad Space!", "Bad Space!")
    assert b"Password must include a letter, number, and special character" in resp.data

# Test that XSS payloads in email are blocked
def test_xss_injection_in_email(client):
    xss = "<script>alert(1)</script>@example.com"
    resp = post_register(client, xss, "SecurePass1!", "SecurePass1!")
    assert b"Enter a valid email address." in resp.data

# Test that password confirmation mismatch is handled correctly
def test_password_confirmation_mismatch(client):
    resp = post_register(client, "bob@example.com", "SecurePass1!", "SecurePass2!")
    assert b"Passwords do not match." in resp.data

# Test that a successful registration creates a new user
def test_successful_registration_creates_user(client):
    resp = post_register(client, "carol@example.com", "SecurePass1!", "SecurePass1!")
    assert b"Registration complete! Please log in." in resp.data
    user = User.query.filter_by(email="carol@example.com").first()
    assert user is not None

# Test that duplicate registrations are rejected
def test_duplicate_registration(client):
    resp = post_register(client, "eve@example.com", "RegUser123!", "RegUser123!")
    assert b"That email is already registered" in resp.data
