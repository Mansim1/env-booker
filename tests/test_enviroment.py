import pytest
from app import create_app, db
from app.models import Environment, User


@pytest.fixture
def client(tmp_path):
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    with app.app_context():
        db.create_all()
        # create admin user
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()
    with app.test_client() as c:
        # login as admin
        c.post(
            "/auth/login",
            data={"email": "admin@example.com", "password": "AdminPass123!"},
        )
        yield c


def test_create_environment_success(client):
    resp = client.post(
        "/environments/new",
        data={"name": "Sandbox X", "owner_squad": "Team X"},
        follow_redirects=True,
    )
    assert b"Environment &#39;Sandbox X&#39; created" in resp.data
    assert b"Sandbox X" in resp.data
    assert Environment.query.filter_by(name="Sandbox X").first() is not None


@pytest.mark.parametrize(
    "name,owner,message",
    [
        ("", "Team", b"Name cannot be blank."),
        ("A" * 101, "Team", b"Name must be 100 characters or fewer."),
        ("Sandbox X", "", b"Owner Squad is required."),
        ("Sandbox X", "Team@!", b"Owner Squad contains invalid characters."),
    ],
)
def test_environment_validation_errors(client, name, owner, message):
    resp = client.post(
        "/environments/new",
        data={"name": name, "owner_squad": owner},
        follow_redirects=True,
    )
    assert message in resp.data


def test_unique_name_enforced(client):
    # create first
    client.post(
        "/environments/new",
        data={"name": "Unique", "owner_squad": "Team1"},
        follow_redirects=True,
    )
    # attempt duplicate
    resp = client.post(
        "/environments/new",
        data={"name": "Unique", "owner_squad": "Team2"},
        follow_redirects=True,
    )
    assert b"That environment name is already in use." in resp.data


def test_environment_records_creator(client):
    resp = client.post(
        "/environments/new",
        data={"name": "Recorder", "owner_squad": "TeamRec"},
        follow_redirects=True,
    )
    print(resp.data)
    env = Environment.query.filter_by(name="Recorder").first()
    assert env.created_by_email == "admin@example.com"
    assert b"Environment &#39;Recorder&#39; created by admin@example.com." in resp.data

def test_edit_environment_success(client):
    # seed one
    client.post("/environments/new", data={"name":"ToEdit","owner_squad":"One"}, follow_redirects=True)
    env = Environment.query.filter_by(name="ToEdit").first()
    # edit it
    resp = client.post(
        f"/environments/{env.id}/edit",
        data={"name":"EditedName","owner_squad":"Two"},
        follow_redirects=True
    )
    assert b"Environment &#39;EditedName&#39; updated." in resp.data
    assert Environment.query.filter_by(name="EditedName").first() is not None

def test_delete_environment_success(client):
    client.post("/environments/new", data={"name":"ToDelete","owner_squad":"One"}, follow_redirects=True)
    env = Environment.query.filter_by(name="ToDelete").first()
    resp = client.post(
        f"/environments/{env.id}/delete",
        follow_redirects=True
    )
    assert b"Environment &#39;ToDelete&#39; deleted." in resp.data
    assert Environment.query.filter_by(name="ToDelete").first() is None
