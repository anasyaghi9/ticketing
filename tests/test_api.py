from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Seat
from events.services import book_seat
from users.models import User

pytestmark = pytest.mark.django_db


def event_payload():
    return {
        "title": "Jazz Night",
        "venue": "Main Hall",
        "starts_at": (timezone.now() + timedelta(days=30)).isoformat(),
    }


# ---------- events ----------

def test_event_list_is_public(api_client, event):
    response = api_client.get("/api/events/")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_event_requires_login(api_client):
    response = api_client.post("/api/events/", event_payload(), format="json")

    assert response.status_code == 401


def test_attendee_cannot_create_event(auth, attendee):
    response = auth(attendee).post("/api/events/", event_payload(), format="json")

    assert response.status_code == 403


def test_organizer_can_create_event(auth, organizer):
    response = auth(organizer).post("/api/events/", event_payload(), format="json")

    assert response.status_code == 201


def test_event_in_the_past_is_rejected(auth, organizer):
    payload = event_payload()
    payload["starts_at"] = (timezone.now() - timedelta(days=1)).isoformat()

    response = auth(organizer).post("/api/events/", payload, format="json")

    assert response.status_code == 400


def test_other_organizer_cannot_edit_event(auth, event):
    other = User.objects.create_user(
        "org2", "org2@test.com", "pass12345", role="organizer"
    )

    response = auth(other).patch(
        f"/api/events/{event.id}/", {"title": "Hacked"}, format="json"
    )

    event.refresh_from_db()
    assert response.status_code == 403
    assert event.title == "Test Event"


# ---------- booking ----------

def test_book_seat_then_conflict(auth, attendee, attendee2, seat):
    url = f"/api/events/seats/{seat.id}/book/"

    assert auth(attendee).post(url).status_code == 201
    assert auth(attendee2).post(url).status_code == 409


def test_booking_requires_login(api_client, seat):
    response = api_client.post(f"/api/events/seats/{seat.id}/book/")

    assert response.status_code == 401


def test_booking_unknown_seat_returns_404(auth, attendee):
    response = auth(attendee).post("/api/events/seats/99999/book/")

    assert response.status_code == 404


def test_cannot_cancel_someone_elses_booking_via_api(auth, attendee, attendee2, seat):
    booking = book_seat(attendee, seat.id)

    response = auth(attendee2).post(f"/api/events/bookings/{booking.id}/cancel/")

    assert response.status_code == 404


def test_cancel_own_booking_then_seat_is_free(auth, attendee, attendee2, seat):
    booking = book_seat(attendee, seat.id)

    cancel = auth(attendee).post(f"/api/events/bookings/{booking.id}/cancel/")
    rebook = auth(attendee2).post(f"/api/events/seats/{seat.id}/book/")

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    assert rebook.status_code == 201


# ---------- bulk seats ----------

def test_organizer_creates_seats_in_bulk(auth, organizer, event):
    url = f"/api/events/{event.id}/seats/"
    body = {"rows": ["C", "D"], "per_row": 3, "price": "10.00"}

    first = auth(organizer).post(url, body, format="json")
    again = auth(organizer).post(url, body, format="json")

    assert first.status_code == 201
    assert first.json() == {"created": 6}
    assert Seat.objects.filter(event=event).count() == 6
    assert again.status_code == 409
    assert Seat.objects.filter(event=event).count() == 6


def test_attendee_cannot_create_seats(auth, attendee, event):
    body = {"rows": ["A"], "per_row": 2, "price": "10.00"}

    response = auth(attendee).post(f"/api/events/{event.id}/seats/", body, format="json")

    assert response.status_code == 403

def test_event_list_is_public(api_client, event):
    response = api_client.get("/api/events/")

    assert response.status_code == 200
    assert response.json()["count"] == 1