from tests.utils import post_login

# Test a successful login with correct credentials
def test_successful_login(client):
    resp = post_login(client, "eve@example.com", "RegUser123!")
    assert b"Welcome, eve@example.com" in resp.data
    assert resp.request.path == "/dashboard"

# Test error messages when both fields are left blank
def test_missing_login_fields(client):
    resp = post_login(client, "", "")
    assert b"Email is required." in resp.data
    assert b"Password is required." in resp.data

# Test login with incorrect password
def test_invalid_credentials(client):
    resp = post_login(client, "eve@example.com", "WrongPass!")
    assert b"Invalid email or password." in resp.data

# Test that SQL injection attempts are caught in the login form
def test_sql_injection_in_login_email(client):
    resp = post_login(client, "test'; DROP TABLE bookings;--", "whatever")
    assert b"Invalid characters in field." in resp.data

# Test that XSS injection is blocked by email validator
def test_xss_injection_in_login_email(client):
    resp = post_login(client, "<img src=x onerror=alert(1)>@ex.com", "whatever")
    assert b"Enter a valid email address." in resp.data

# Test that login fails for emails exceeding 120 characters
def test_email_max_length_login(client):
    long_email = "a" * 121 + "@x.com"
    resp = post_login(client, long_email, "RegUser123!")
    assert b"Email must be 120 characters or fewer." in resp.data

# Test that login fails for passwords shorter than 8 characters
def test_password_min_length_login(client):
    resp = post_login(client, "eve@example.com", "short")
    assert b"Password must be at least 8 characters." in resp.data

# Test that unauthenticated users are redirected to login when accessing protected routes
def test_protected_route_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]

# Test that already logged-in users are redirected from the login page
def test_logged_in_user_redirected_from_login(client):
    post_login(client, "eve@example.com", "RegUser123!")
    resp = client.get("/auth/login", follow_redirects=True)
    assert resp.request.path == "/dashboard"

# Test that already logged-in users are redirected from the register page
def test_logged_in_user_redirected_from_register(client):
    post_login(client, "eve@example.com", "RegUser123!")
    resp = client.get("/auth/register", follow_redirects=True)
    assert resp.request.path == "/dashboard"

# Test that a non-admin user cannot access an admin-only route
def test_admin_required_blocks_non_admin(client):
    post_login(client, "eve@example.com", "RegUser123!")
    resp = client.get("/environments/new", follow_redirects=False)
    assert resp.status_code == 403
    assert b"Forbidden" in resp.data

# Test redirection logic for authenticated users trying to visit login page
def test_authenticated_user_redirected_from_login(client):
    post_login(client, "eve@example.com", "RegUser123!")
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")

# Test that a logged-in user can log out successfully
def test_logout_flow(client):
    post_login(client, "eve@example.com", "RegUser123!")
    resp = client.get("/auth/logout", follow_redirects=True)
    assert b"You have been logged out." in resp.data
    assert resp.request.path == "/auth/login"
