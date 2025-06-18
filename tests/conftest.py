import pytest
from app import create_app, db
from app.models import User, Environment

@pytest.fixture(scope="session")
def app_instance(tmp_path_factory):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path_factory.mktemp('data')}/test.db"
    app.config["TESTING"] = True
    return app

@pytest.fixture
def client(app_instance):
    with app_instance.app_context():
        db.create_all()
        # Add test data
        user = User(email="eve@example.com", role="user")
        user.set_password("RegUser123!")
        db.session.add(user)

        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)

        db.session.add(Environment(name="Env1", owner_squad="team 1", created_by_email="admin@example.com"))
        db.session.commit()

    with app_instance.test_client() as client:
        yield client

    # cleanup
    with app_instance.app_context():
        db.session.remove()
        db.drop_all()
