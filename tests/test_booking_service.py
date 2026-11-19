from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Booking
from events.services import (
    BookingNotCancellable,
    SeatNotAvailable,
    book_seat,
    cancel_booking,
)

pytestmark = pytest.mark.django_db


def test_book_seat_creates_a_ten_minute_hold(attendee, seat):
    booking = book_seat(attendee, seat.id)
    now = timezone.now()

    assert booking.status == Booking.Status.PENDING
    assert now + timedelta(minutes=9) < booking.hold_expires_at < now + timedelta(minutes=11)


def test_second_user_cannot_book_a_held_seat(attendee, attendee2, seat):
    book_seat(attendee, seat.id)

    with pytest.raises(SeatNotAvailable):
        book_seat(attendee2, seat.id)


def test_expired_hold_frees_the_seat(attendee, attendee2, seat):
    old = Booking.objects.create(
        user=attendee,
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at=timezone.now() - timedelta(minutes=1),
    )

    new = book_seat(attendee2, seat.id)

    old.refresh_from_db()
    assert old.status == Booking.Status.EXPIRED
    assert new.status == Booking.Status.PENDING


def test_cancel_frees_the_seat(attendee, attendee2, seat):
    booking = book_seat(attendee, seat.id)

    cancel_booking(attendee, booking.id)

    assert book_seat(attendee2, seat.id).status == Booking.Status.PENDING


def test_cannot_cancel_someone_elses_booking(attendee, attendee2, seat):
    booking = book_seat(attendee, seat.id)

    with pytest.raises(Booking.DoesNotExist):
        cancel_booking(attendee2, booking.id)


def test_cannot_cancel_twice(attendee, seat):
    booking = book_seat(attendee, seat.id)
    cancel_booking(attendee, booking.id)

    with pytest.raises(BookingNotCancellable):
        cancel_booking(attendee, booking.id)