from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Booking, Seat

HOLD_MINUTES = 10
ACTIVE = [Booking.Status.PENDING, Booking.Status.CONFIRMED]


class SeatNotAvailable(Exception):
    pass


class BookingNotCancellable(Exception):
    pass


@transaction.atomic
def book_seat(user, seat_id):
    seat = Seat.objects.select_for_update().get(id=seat_id)
    now = timezone.now()

    Booking.objects.filter(
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at__lt=now,
    ).update(status=Booking.Status.EXPIRED)

    if Booking.objects.filter(seat=seat, status__in=ACTIVE).exists():
        raise SeatNotAvailable(f"Seat {seat.label} is not available")

    return Booking.objects.create(
        user=user,
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at=now + timedelta(minutes=HOLD_MINUTES),
    )


@transaction.atomic
def cancel_booking(user, booking_id):
    booking = Booking.objects.select_for_update().get(id=booking_id, user=user)

    if booking.status not in ACTIVE:
        raise BookingNotCancellable("Booking is already closed.")

    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    return booking


@transaction.atomic
def create_seats(event, rows, per_row, price):
    seats = [
        Seat(event=event, label=f"{row}{n}", price=price)
        for row in rows
        for n in range(1, per_row + 1)
    ]
    Seat.objects.bulk_create(seats)
    return len(seats)