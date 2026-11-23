from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Booking, Event, Seat
from events.services import (
    MAX_ACTIVE_BOOKINGS_PER_EVENT,
    BookingLimitReached,
    EventNotBookable,
    book_seat,
    cancel_booking,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def seats(event):
    return [
        Seat.objects.create(event=event, label=f"R{i}", price=10)
        for i in range(MAX_ACTIVE_BOOKINGS_PER_EVENT + 1)
    ]


def start_in_the_past(event):
    Event.objects.filter(id=event.id).update(starts_at=timezone.now() - timedelta(hours=1))


def test_cannot_book_a_seat_for_an_event_that_started(attendee, event, seat):
    start_in_the_past(event)

    with pytest.raises(EventNotBookable):
        book_seat(attendee, seat.id)


def test_api_returns_409_for_an_event_that_started(auth, attendee, event, seat):
    start_in_the_past(event)

    response = auth(attendee).post(f"/api/events/seats/{seat.id}/book/")

    assert response.status_code == 409
    assert "started" in response.json()["detail"]


def test_user_can_hold_up_to_the_limit_but_not_more(attendee, seats):
    for seat in seats[:MAX_ACTIVE_BOOKINGS_PER_EVENT]:
        book_seat(attendee, seat.id)

    with pytest.raises(BookingLimitReached):
        book_seat(attendee, seats[-1].id)


def test_the_limit_is_per_user(attendee, attendee2, seats):
    for seat in seats[:MAX_ACTIVE_BOOKINGS_PER_EVENT]:
        book_seat(attendee, seat.id)

    assert book_seat(attendee2, seats[-1].id).status == Booking.Status.PENDING


def test_expired_holds_do_not_count_toward_the_limit(attendee, seats):
    for seat in seats[:MAX_ACTIVE_BOOKINGS_PER_EVENT]:
        Booking.objects.create(
            user=attendee, seat=seat, status=Booking.Status.PENDING,
            hold_expires_at=timezone.now() - timedelta(minutes=1),
        )

    assert book_seat(attendee, seats[-1].id).status == Booking.Status.PENDING


def test_cancelling_a_booking_frees_a_slot(attendee, seats):
    bookings = [book_seat(attendee, s.id) for s in seats[:MAX_ACTIVE_BOOKINGS_PER_EVENT]]

    cancel_booking(attendee, bookings[0].id)

    assert book_seat(attendee, seats[-1].id).status == Booking.Status.PENDING


def test_api_returns_409_when_the_limit_is_reached(auth, attendee, seats):
    for seat in seats[:MAX_ACTIVE_BOOKINGS_PER_EVENT]:
        book_seat(attendee, seat.id)

    response = auth(attendee).post(f"/api/events/seats/{seats[-1].id}/book/")

    assert response.status_code == 409
    assert "at most" in response.json()["detail"]