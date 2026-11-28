import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Booking, Seat

logger = logging.getLogger(__name__)

HOLD_MINUTES = 10
MAX_ACTIVE_BOOKINGS_PER_EVENT = 4
ACTIVE = [Booking.Status.PENDING, Booking.Status.CONFIRMED]


class SeatNotAvailable(Exception):
    pass


class EventNotBookable(Exception):
    pass


class BookingLimitReached(Exception):
    pass


class BookingNotCancellable(Exception):
    pass


@transaction.atomic
def book_seat(user, seat_id):
    get_user_model().objects.select_for_update().get(pk=user.pk)

    seat = (
        Seat.objects.select_related("event")
        .select_for_update(of=("self",))
        .get(id=seat_id)
    )
    now = timezone.now()

    if seat.event.starts_at <= now:
        raise EventNotBookable("Event has already started.")

    Booking.objects.filter(
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at__lt=now,
    ).update(status=Booking.Status.EXPIRED)

    if Booking.objects.filter(seat=seat, status__in=ACTIVE).exists():
        raise SeatNotAvailable(f"Seat {seat.label} is not available")

    holding = (
        Booking.objects.filter(user=user, seat__event=seat.event)
        .filter(
            Q(status=Booking.Status.CONFIRMED)
            | Q(status=Booking.Status.PENDING, hold_expires_at__gt=now)
        )
        .count()
    )
    if holding >= MAX_ACTIVE_BOOKINGS_PER_EVENT:
        raise BookingLimitReached("Too many seats held for this event.")

    booking = Booking.objects.create(
        user=user,
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at=now + timedelta(minutes=HOLD_MINUTES),
    )
    logger.info(
        "booking_created",
        extra={"fields": {"booking_id": booking.id, "seat_id": seat.id, "user_id": user.id}},
    )
    return booking


@transaction.atomic
def cancel_booking(user, booking_id):
    booking = Booking.objects.select_for_update().get(id=booking_id, user=user)

    if booking.status not in ACTIVE:
        raise BookingNotCancellable("Booking is already closed.")

    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    logger.info(
        "booking_cancelled",
        extra={"fields": {"booking_id": booking.id, "user_id": user.id}},
    )
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


def expire_holds():
    """Mark every pending booking whose hold has run out as expired."""
    count = Booking.objects.filter(
        status=Booking.Status.PENDING,
        hold_expires_at__lt=timezone.now(),
    ).update(status=Booking.Status.EXPIRED)
    if count:
        logger.info("holds_expired", extra={"fields": {"count": count}})
    return count