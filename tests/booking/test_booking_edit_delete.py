import pytest
from app.models import Booking
from tests.utils import login_user, login_admin, future_datetime

@pytest.fixture
def create_booking(client):
    login_user(client)
    start, end = future_datetime()
    client.post("/bookings/new", data={"environment": 1, "start": start, "end": end}, follow_redirects=True)
    return Booking.query.first()

def test_user_can_edit_own_booking(client, create_booking):
    booking = create_booking
    new_start, new_end = future_datetime(offset_days=8)
    resp = client.post(
        f"/bookings/{booking.id}/edit",
        data={"environment": 1, "start": new_start, "end": new_end, "booking_id": booking.id},
        follow_redirects=True
    )
    assert b"Booking updated successfully" in resp.data

def test_user_cannot_edit_others_booking(client, create_booking):
    login_admin(client)
    resp = client.get(f"/bookings/{create_booking.id}/edit")
    assert resp.status_code == 403

def test_admin_can_edit_any_booking(client, create_booking):
    login_admin(client)
    new_start, new_end = future_datetime(offset_days=9)
    resp = client.post(
        f"/bookings/{create_booking.id}/edit",
        data={"environment": 1, "start": new_start, "end": new_end, "booking_id": create_booking.id},
        follow_redirects=True
    )
    assert b"Booking updated successfully" in resp.data

def test_user_can_delete_own_booking(client, create_booking):
    resp = client.post(f"/bookings/{create_booking.id}/delete", follow_redirects=True)
    assert b"Booking deleted" in resp.data

def test_admin_can_delete_any_booking(client, create_booking):
    login_admin(client)
    resp = client.post(f"/bookings/{create_booking.id}/delete", follow_redirects=True)
    assert b"Booking deleted" in resp.data
