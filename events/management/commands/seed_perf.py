import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from events.models import Booking, Event, Seat
from users.models import User

EVENTS = 50
SEATS_PER_EVENT = 2000
USERS = 500
BATCH = 5000


class Command(BaseCommand):
    help = "Create ~100,000 seats and bookings to measure query performance"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete and rebuild")
        parser.add_argument("--clean", action="store_true", help="delete and stop")

    def handle(self, *args, reset=False, clean=False, **options):
        perf_events = Event.objects.filter(title__startswith="PERF ")
        if perf_events.exists():
            if not (reset or clean):
                self.stdout.write("Perf data already exists. Use --reset or --clean.")
                return
            Booking.objects.filter(seat__event__in=perf_events).delete()
            perf_events.delete()
            User.objects.filter(username__startswith="perf_").delete()
            self.stdout.write("Old perf data deleted.")
        if clean:
            return

        now = timezone.now()
        password = make_password("perf-pass")
        org = User.objects.create(
            username="perf_org", email="perf_org@test.com",
            role="organizer", password=password,
        )
        users = User.objects.bulk_create(
            [
                User(username=f"perf_{i}", email=f"perf_{i}@test.com", password=password)
                for i in range(USERS)
            ],
            batch_size=BATCH,
        )
        user_ids = [u.id for u in users]

        events = Event.objects.bulk_create(
            [
                Event(organizer=org, title=f"PERF {i}", venue="Hall",
                      starts_at=now + timedelta(days=i + 1))
                for i in range(EVENTS)
            ]
        )
        seats = Seat.objects.bulk_create(
            [
                Seat(event=event, label=f"S{n}", price=25)
                for event in events
                for n in range(SEATS_PER_EVENT)
            ],
            batch_size=BATCH,
        )

        # one booking per seat, so the "one active booking per seat" rule holds
        bookings = []
        for seat in seats:
            r = random.random()
            hold = None
            if r < 0.70:
                status = Booking.Status.CONFIRMED
            elif r < 0.85:
                status = Booking.Status.CANCELLED
            elif r < 0.99:
                status = Booking.Status.EXPIRED
                hold = now - timedelta(minutes=random.randint(11, 600))
            elif r < 0.993:  # a few stale holds that the Celery task should catch
                status = Booking.Status.PENDING
                hold = now - timedelta(minutes=random.randint(1, 10))
            else:
                status = Booking.Status.PENDING
                hold = now + timedelta(minutes=random.randint(1, 10))
            bookings.append(
                Booking(user_id=random.choice(user_ids), seat_id=seat.id,
                        status=status, hold_expires_at=hold)
            )
        Booking.objects.bulk_create(bookings, batch_size=BATCH)

        with connection.cursor() as cursor:  # refresh the planner's statistics
            cursor.execute("ANALYZE events_booking")
            cursor.execute("ANALYZE events_seat")

        self.stdout.write(
            f"Created {len(users)} users, {len(events)} events, "
            f"{len(seats)} seats, {len(bookings)} bookings."
        )