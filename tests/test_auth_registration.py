import pytest
from app import create_app, db
from app.models import User


@pytest.fixture
def client(tmp_path):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    with app.test_client() as c:
        with app.app_context():
            db.create_all()
        yield c


def test_successful_registration(client):
    resp = client.post(
        "/auth/register",
        data={
            "email": "alice@example.com",
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
        },
        follow_redirects=True,
    )
    assert b"Registration complete! Please log in." in resp.data
    # check user in DB
    user = User.query.filter_by(email="alice@example.com").first()
    assert user is not None


def test_password_too_short(client):
    resp = client.post(
        "/auth/register",
        data={"email": "bob@example.com", "password": "short", "confirm": "short"},
        follow_redirects=True,
    )
    assert b"Password must be at least 8 characters long." in resp.data


def test_email_already_registered(client):
    # create existing user
    from app.models import User

    u = User(email="dave@example.com")
    u.set_password("AnotherPass1!")
    db.session.add(u)
    db.session.commit()

    resp = client.post(
        "/auth/register",
        data={
            "email": "dave@example.com",
            "password": "AnotherPass1!",
            "confirm": "AnotherPass1!",
        },
        follow_redirects=True,
    )
    assert b"That email is already registered" in resp.data
