from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from events.models import Event, Seat
from users.models import User


@pytest.fixture(autouse=True)
def _isolated_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "tests",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth():
    """auth(user) returns an API client logged in as that user."""

    def _auth(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _auth


@pytest.fixture
def organizer(db):
    return User.objects.create_user(
        "org", "org@test.com", "pass12345", role="organizer"
    )


@pytest.fixture
def attendee(db):
    return User.objects.create_user("sara", "sara@test.com", "pass12345")


@pytest.fixture
def attendee2(db):
    return User.objects.create_user("omar", "omar@test.com", "pass12345")


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        title="Test Event",
        venue="Hall",
        starts_at=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def seat(event):
    return Seat.objects.create(event=event, label="A1", price=20)