from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Event

pytestmark = pytest.mark.django_db


@pytest.fixture
def many_events(organizer):
    return Event.objects.bulk_create(
        [
            Event(
                organizer=organizer, title=f"E{i}", venue="Hall",
                starts_at=timezone.now() + timedelta(days=i + 1),
            )
            for i in range(25)
        ]
    )


def test_first_page_has_twenty_items_and_a_next_link(api_client, many_events):
    body = api_client.get("/api/events/").json()

    assert body["count"] == 25
    assert len(body["results"]) == 20
    assert "page=2" in body["next"]
    assert body["previous"] is None


def test_second_page_has_the_rest(api_client, many_events):
    body = api_client.get("/api/events/?page=2").json()

    assert len(body["results"]) == 5
    assert body["next"] is None
    assert body["previous"] is not None


def test_page_size_can_be_changed(api_client, many_events):
    body = api_client.get("/api/events/?page_size=5").json()

    assert body["count"] == 25
    assert len(body["results"]) == 5


def test_page_out_of_range_is_404(api_client, many_events):
    assert api_client.get("/api/events/?page=99").status_code == 404
    assert api_client.get("/api/events/?page=abc").status_code == 404


def test_events_that_already_started_are_hidden(api_client, organizer, event):
    Event.objects.create(
        organizer=organizer, title="Old", venue="Hall",
        starts_at=timezone.now() - timedelta(days=1),
    )

    body = api_client.get("/api/events/").json()

    assert body["count"] == 1
    assert body["results"][0]["title"] == "Test Event"


def test_cached_page_is_identical_to_the_fresh_one(api_client, many_events):
    fresh = api_client.get("/api/events/?page=2&page_size=10").json()
    cached = api_client.get("/api/events/?page=2&page_size=10").json()

    assert cached == fresh