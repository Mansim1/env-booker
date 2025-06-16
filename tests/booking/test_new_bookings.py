import pytest
from datetime import datetime, timedelta
from app.models import Booking
from app import db
from tests.utils import future_datetime, login_user, post_series_booking, post_single_booking

# --- Single Booking Tests ---

def test_successful_single_booking(client):
    login_user(client)
    start, end = future_datetime()
    resp = post_single_booking(client, 1, start, end)
    assert b"Booking confirmed" in resp.data
    assert Booking.query.count() == 1


def test_single_booking_end_before_start(client):
    login_user(client)
    start, end = future_datetime()
    resp = post_single_booking(client, 1, end, start)
    assert b"End time must be after start time." in resp.data
    assert Booking.query.count() == 0


def test_single_booking_overlap(client):
    login_user(client)
    start, end = future_datetime()
    post_single_booking(client, 1, start, end)
    overlap_start = (datetime.strptime(start, "%Y-%m-%dT%H:%M") + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    overlap_end = (datetime.strptime(end, "%Y-%m-%dT%H:%M") + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    resp = post_single_booking(client, 1, overlap_start, overlap_end)
    assert b"Booking failed due to clash. Suggested slot:" in resp.data
    assert Booking.query.count() == 1


# --- Series Booking Tests ---

def test_successful_series_booking(client):
    login_user(client)
    start, end = future_datetime(offset_days=7, duration_hours=169)  # 1 week range
    weekdays = ["0", "1", "2", "3", "4"]
    resp = post_series_booking(client, 1, start, end, weekdays)
    assert b"Series booking confirmed" in resp.data
    assert Booking.query.count() >= 5


def test_series_booking_with_clash(client):
    login_user(client)
    # Add manual clash
    start, _ = future_datetime(offset_days=9)
    with client.application.app_context():
        db.session.add(Booking(
            environment_id=1, user_id=1,
            start=datetime.strptime(start, "%Y-%m-%dT%H:%M"),
            end=datetime.strptime(start, "%Y-%m-%dT%H:%M") + timedelta(hours=1)
        ))
        db.session.commit()

    series_start, series_end = future_datetime(offset_days=7, duration_hours=170)
    weekdays = ["0", "1", "2", "3", "4"]
    resp = post_series_booking(client, 1, series_start, series_end, weekdays)
    assert b"Series failed due to clash. Suggested series:" in resp.data


def test_series_booking_weekday_slot(client):
    login_user(client)
    sat = (datetime.now() + timedelta(days=(5 - datetime.now().weekday()) % 7 + 5)).replace(hour=9, minute=0)
    sun = sat + timedelta(days=1, hours=2)
    resp = post_series_booking(
        client,
        1,
        sat.strftime("%Y-%m-%dT%H:%M"),
        sun.strftime("%Y-%m-%dT%H:%M"),
        ["0", "1", "2", "3", "4"]
    )
    assert b"Series booking confirmed" in resp.data


# # --- Download ICS Tests ---

def test_ics_download_authorized(client):
    login_user(client)
    start, end = future_datetime()
    post_single_booking(client, 1, start, end)
    booking = Booking.query.first()
    resp = client.get(f"/bookings/{booking.id}/download")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "text/calendar; charset=utf-8"