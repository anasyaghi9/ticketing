from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from events.models import Booking, Seat

pytestmark = pytest.mark.django_db


def count_queries(client, url):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200
    return len(queries)


def test_my_bookings_query_count_does_not_grow_with_data(auth, attendee, event):
    def add_bookings(start, n):
        for i in range(start, start + n):
            seat = Seat.objects.create(event=event, label=f"Q{i}", price=5)
            Booking.objects.create(
                user=attendee, seat=seat, status=Booking.Status.PENDING,
                hold_expires_at=timezone.now() + timedelta(minutes=5),
            )

    client = auth(attendee)
    add_bookings(0, 2)
    few = count_queries(client, "/api/events/my-bookings/")
    add_bookings(2, 20)
    many = count_queries(client, "/api/events/my-bookings/")

    assert few == many


def test_event_detail_query_count_does_not_grow_with_seats(api_client, event):
    Seat.objects.bulk_create(
        [Seat(event=event, label=f"D{i}", price=5) for i in range(3)]
    )
    few = count_queries(api_client, f"/api/events/{event.id}/")

    Seat.objects.bulk_create(
        [Seat(event=event, label=f"E{i}", price=5) for i in range(100)]
    )
    many = count_queries(api_client, f"/api/events/{event.id}/")

    assert few == many