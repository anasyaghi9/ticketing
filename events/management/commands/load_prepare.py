import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from events.models import Booking, Event, Seat
from users.models import User

TITLE = "LOADTEST"
PREFIX = "lt_"


class Command(BaseCommand):
    help = "Create one event, its seats and users with 1-hour tokens for Locust"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=200)
        parser.add_argument("--seats", type=int, default=20)
        parser.add_argument("--out", default="loadtest/tokens.json")

    def handle(self, *args, users, seats, out, **options):
        old = Event.objects.filter(title=TITLE)
        Booking.objects.filter(seat__event__in=old).delete()
        old.delete()
        User.objects.filter(username__startswith=PREFIX).delete()

        password = make_password("load-pass")
        organizer = User.objects.create(
            username=f"{PREFIX}org", email=f"{PREFIX}org@test.com",
            role="organizer", password=password,
        )
        event = Event.objects.create(
            organizer=organizer, title=TITLE, venue="Arena",
            starts_at=timezone.now() + timedelta(days=30),
        )
        created_seats = Seat.objects.bulk_create(
            [Seat(event=event, label=f"L{i}", price=10) for i in range(seats)]
        )
        attendees = User.objects.bulk_create(
            [
                User(username=f"{PREFIX}{i}", email=f"{PREFIX}{i}@test.com", password=password)
                for i in range(users)
            ]
        )

        tokens = []
        for user in attendees:
            token = AccessToken.for_user(user)
            token.set_exp(lifetime=timedelta(hours=1))
            tokens.append(str(token))

        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "event_id": event.id,
                    "seat_ids": [s.id for s in created_seats],
                    "tokens": tokens,
                }
            )
        )
        self.stdout.write(f"Event {event.id}: {seats} seats, {users} users, data in {out}")