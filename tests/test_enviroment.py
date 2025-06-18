import pytest
from app.models import Environment
from tests.utils import login_admin

def test_create_environment_success(client):
    login_admin(client)
    resp = client.post(
        "/environments/new",
        data={"name": "Sandbox X", "owner_squad": "Team X"},
        follow_redirects=True,
    )
    assert b"Environment \'Sandbox X\' created" in resp.data
    assert b"Sandbox X" in resp.data
    assert Environment.query.filter_by(name="Sandbox X").first() is not None


@pytest.mark.parametrize(
    "name,owner,message",
    [
        ("", "Team", b"Name cannot be blank."),
        ("A" * 101, "Team", b"Name must be 100 characters or fewer."),
        ("Env1", "", b"Owner Squad is required."),
        ("Env1", "Team@!", b"Owner Squad contains invalid characters."),
    ],
)
def test_environment_validation_errors(client, name, owner, message):
    login_admin(client)
    resp = client.post(
        "/environments/new",
        data={"name": name, "owner_squad": owner},
        follow_redirects=True,
    )
    assert message in resp.data


def test_unique_name_enforced(client):
    login_admin(client)
    client.post(
        "/environments/new",
        data={"name": "Unique", "owner_squad": "Team1"},
        follow_redirects=True,
    )
    resp = client.post(
        "/environments/new",
        data={"name": "Unique", "owner_squad": "Team2"},
        follow_redirects=True,
    )
    assert b"That environment name is already in use." in resp.data


def test_environment_records_creator(client):
    login_admin(client)
    resp = client.post(
        "/environments/new",
        data={"name": "Recorder", "owner_squad": "TeamRec"},
        follow_redirects=True,
    )
    env = Environment.query.filter_by(name="Recorder").first()
    assert env.created_by_email == "admin@example.com"
    assert b"Environment \'Recorder\' created by admin@example.com." in resp.data


def test_edit_environment_success(client):
    login_admin(client)
    client.post("/environments/new", data={"name": "ToEdit", "owner_squad": "One"}, follow_redirects=True)
    env = Environment.query.filter_by(name="ToEdit").first()

    resp = client.post(
        f"/environments/{env.id}/edit",
        data={"name": "EditedName", "owner_squad": "Two"},
        follow_redirects=True
    )
    assert b"Environment \'EditedName\' updated." in resp.data
    assert Environment.query.filter_by(name="EditedName").first() is not None


def test_delete_environment_success(client):
    login_admin(client)
    client.post("/environments/new", data={"name": "ToDelete", "owner_squad": "One"}, follow_redirects=True)
    env = Environment.query.filter_by(name="ToDelete").first()

    resp = client.post(f"/environments/{env.id}/delete", follow_redirects=True)
    assert b"Environment \'ToDelete\' deleted." in resp.data
    assert Environment.query.filter_by(name="ToDelete").first() is None
