import pytest
from app import create_app, db
from app.models import User

@pytest.fixture
def client(tmp_path):
    """Creates a test client and in-memory test DB with one test user."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"

    with app.app_context():
        db.create_all()
        # Add a regular user
        user = User(email="eve@example.com")
        user.set_password("RegUser123!")
        db.session.add(user)
        db.session.commit()

    with app.test_client() as client:
        yield client
