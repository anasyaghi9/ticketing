from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Booking, Seat

HOLD_MINUTES = 10
ACTIVE = [Booking.Status.PENDING, Booking.Status.CONFIRMED]


class SeatNotAvailable(Exception):
    pass


@transaction.atomic
def book_seat(user, seat_id):
    # 1) lock the seat row: other requests for this seat wait here
    seat = Seat.objects.select_for_update().get(id=seat_id)
    now = timezone.now()

    # 2) free holds that already expired
    Booking.objects.filter(
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at__lt=now,
    ).update(status=Booking.Status.EXPIRED)

    # 3) is the seat taken?
    if Booking.objects.filter(seat=seat, status__in=ACTIVE).exists():
        raise SeatNotAvailable(f"Seat {seat.label} is not available")

    # 4) create a temporary hold
    return Booking.objects.create(
        user=user,
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at=now + timedelta(minutes=HOLD_MINUTES),
    )

class BookingNotCancellable(Exception):
    pass


@transaction.atomic
def cancel_booking(user, booking_id):
    # filtering by user means someone else's booking raises DoesNotExist
    booking = Booking.objects.select_for_update().get(id=booking_id, user=user)

    if booking.status not in ACTIVE:
        raise BookingNotCancellable("Booking is already closed.")

    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    return booking