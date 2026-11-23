import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from events.models import Booking, Event, Seat
from events.services import (
    ACTIVE,
    MAX_ACTIVE_BOOKINGS_PER_EVENT,
    BookingLimitReached,
    book_seat,
)
from users.models import User

PARALLEL_REQUESTS = 8


@pytest.mark.django_db(transaction=True)
def test_parallel_requests_from_one_user_cannot_exceed_the_limit():
    organizer = User.objects.create_user(
        "org", "org@test.com", "pass12345", role="organizer"
    )
    event = Event.objects.create(
        organizer=organizer, title="Limit", venue="Hall",
        starts_at=timezone.now() + timedelta(days=30),
    )
    seats = [
        Seat.objects.create(event=event, label=f"P{i}", price=10)
        for i in range(PARALLEL_REQUESTS)
    ]
    user = User.objects.create_user("greedy", "greedy@test.com", "pass12345")

    results = []
    barrier = threading.Barrier(PARALLEL_REQUESTS)

    def worker(seat_id):
        try:
            barrier.wait()
            book_seat(user, seat_id)
            results.append("ok")
        except BookingLimitReached:
            results.append("limit")
        except Exception as exc:
            results.append(f"error: {type(exc).__name__}")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(s.id,)) for s in seats]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == MAX_ACTIVE_BOOKINGS_PER_EVENT
    assert results.count("limit") == PARALLEL_REQUESTS - MAX_ACTIVE_BOOKINGS_PER_EVENT
    held = Booking.objects.filter(user=user, status__in=ACTIVE).count()
    assert held == MAX_ACTIVE_BOOKINGS_PER_EVENT