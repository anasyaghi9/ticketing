import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from events.models import Booking, Event, Seat
from events.services import ACTIVE, SeatNotAvailable, book_seat
from users.models import User

THREADS = 20


@pytest.mark.django_db(transaction=True)
def test_only_one_of_many_simultaneous_bookings_succeeds():
    organizer = User.objects.create_user(
        "org", "org@test.com", "pass12345", role="organizer"
    )
    event = Event.objects.create(
        organizer=organizer,
        title="Race",
        venue="Hall",
        starts_at=timezone.now() + timedelta(days=30),
    )
    seat = Seat.objects.create(event=event, label="A1", price=10)
    users = [
        User.objects.create_user(f"u{i}", f"u{i}@test.com", "pass12345")
        for i in range(THREADS)
    ]

    results = []
    barrier = threading.Barrier(THREADS)

    def worker(user):
        try:
            barrier.wait()
            book_seat(user, seat.id)
            results.append("ok")
        except SeatNotAvailable:
            results.append("rejected")
        except Exception as exc:
            results.append(f"error: {type(exc).__name__}")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 1
    assert results.count("rejected") == THREADS - 1
    assert Booking.objects.filter(seat=seat, status__in=ACTIVE).count() == 1