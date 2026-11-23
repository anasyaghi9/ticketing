from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from events.cache import event_list_key
from events.models import Event

pytestmark = pytest.mark.django_db


# ---------- cache ----------

def test_event_list_is_cached_after_the_first_request(api_client, event):
    assert cache.get(event_list_key(1, 20)) is None

    api_client.get("/api/events/")

    assert cache.get(event_list_key(1, 20)) is not None


def test_second_request_never_touches_the_database(
    api_client, event, django_assert_num_queries
):
    first = api_client.get("/api/events/")  # fills the cache

    with django_assert_num_queries(0):
        second = api_client.get("/api/events/")

    assert second.status_code == 200
    assert second.json() == first.json()


def test_creating_an_event_clears_the_cache(
    api_client, organizer, event, django_capture_on_commit_callbacks
):
    api_client.get("/api/events/")

    with django_capture_on_commit_callbacks(execute=True):
        Event.objects.create(
            organizer=organizer, title="New", venue="Hall",
            starts_at=timezone.now() + timedelta(days=5),
        )

    assert api_client.get("/api/events/").json()["count"] == 2


def test_editing_an_event_is_visible_after_invalidation(
    api_client, event, django_capture_on_commit_callbacks
):
    api_client.get("/api/events/")

    with django_capture_on_commit_callbacks(execute=True):
        event.title = "Renamed"
        event.save()

    assert api_client.get("/api/events/").json()["results"][0]["title"] == "Renamed"


# ---------- rate limiting ----------

def test_login_is_rate_limited(api_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "login", "2/min")
    body = {"username": "nobody", "password": "wrong"}

    codes = [
        api_client.post("/api/auth/login/", body, format="json").status_code
        for _ in range(3)
    ]

    assert codes == [401, 401, 429]


def test_booking_is_rate_limited_per_user(auth, attendee, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "booking", "2/min")
    client = auth(attendee)

    codes = [client.post("/api/events/seats/99999/book/").status_code for _ in range(3)]

    assert codes == [404, 404, 429]