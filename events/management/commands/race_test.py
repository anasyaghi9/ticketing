import threading
import time
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import IntegrityError, connection
from django.utils import timezone

from events.models import Booking, Event, Seat
from events.services import ACTIVE, SeatNotAvailable, book_seat
from users.models import User

THREADS = 20


def unsafe_book(user, seat_id):
    seat = Seat.objects.get(id=seat_id)
    if Booking.objects.filter(seat=seat, status__in=ACTIVE).exists():
        raise SeatNotAvailable()
    time.sleep(0.05)
    return Booking.objects.create(user=user, seat=seat)


def run_race(book_fn, users, seat_id):
    results = []
    barrier = threading.Barrier(len(users))

    def worker(user):
        try:
            barrier.wait()
            book_fn(user, seat_id)
            results.append("ok")
        except SeatNotAvailable:
            results.append("SeatNotAvailable (clean)")
        except IntegrityError:
            results.append("IntegrityError (caught by DB)")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return Counter(results)


class Command(BaseCommand):
    help = "Race test: many users try to book the same seat at once"

    def handle(self, *args, **options):
        organizer, _ = User.objects.get_or_create(
            username="race_org", defaults={"email": "race_org@test.com"}
        )
        users = [
            User.objects.get_or_create(
                username=f"race{i}", defaults={"email": f"race{i}@test.com"}
            )[0]
            for i in range(THREADS)
        ]

        for name, fn in [("WITHOUT lock", unsafe_book), ("WITH lock", book_seat)]:
            event = Event.objects.create(
                organizer=organizer, title="Race", venue="Hall",
                starts_at=timezone.now(),
            )
            seat = Seat.objects.create(event=event, label="A1", price=10)

            counts = run_race(fn, users, seat.id)
            active = Booking.objects.filter(seat=seat, status__in=ACTIVE).count()

            self.stdout.write(f"\n=== {name} ({THREADS} threads) ===")
            for k, v in counts.items():
                self.stdout.write(f"  {k}: {v}")
            self.stdout.write(f"  active bookings in DB: {active}")

            Booking.objects.filter(seat=seat).delete()
            event.delete()