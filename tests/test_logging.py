
import json
import logging
import sys
from datetime import timedelta

import pytest
from django.utils import timezone

from config.logs import JsonFormatter
from events.models import Booking
from events.services import book_seat, cancel_booking, expire_holds


pytestmark = pytest.mark.django_db


def format_record(message, fields=None, exc_info=None):
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        message,
        None,
        exc_info,
    )

    if fields is not None:
        record.fields = fields

    return json.loads(JsonFormatter().format(record))


def test_json_formatter_outputs_one_valid_object_with_the_fields():
    data = format_record("booking_created", {"booking_id": 7})

    assert data["message"] == "booking_created"
    assert data["level"] == "INFO"
    assert data["booking_id"] == 7
    assert "time" in data


def test_fields_cannot_overwrite_the_core_keys():
    data = format_record("x", {"level": "FAKE", "message": "FAKE"})

    assert data["level"] == "INFO"
    assert data["message"] == "x"


def test_exceptions_are_included():
    try:
        raise ValueError("boom")
    except ValueError:
        data = format_record("failed", exc_info=sys.exc_info())

    assert "ValueError: boom" in data["exception"]


def records(caplog, name):
    return {
        r.getMessage(): r
        for r in caplog.records
        if r.name == name
    }


def test_booking_and_cancel_are_logged(caplog, attendee, seat):
    with caplog.at_level(logging.INFO, logger="events.services"):
        booking = book_seat(attendee, seat.id)
        cancel_booking(attendee, booking.id)

    logged = records(caplog, "events.services")

    assert logged["booking_created"].fields == {
        "booking_id": booking.id,
        "seat_id": seat.id,
        "user_id": attendee.id,
    }

    assert logged["booking_cancelled"].fields["booking_id"] == booking.id


def test_expired_holds_are_logged_only_when_something_expired(
    caplog,
    attendee,
    seat,
):
    with caplog.at_level(logging.INFO, logger="events.services"):
        expire_holds()

    assert "holds_expired" not in records(caplog, "events.services")

    Booking.objects.create(
        user=attendee,
        seat=seat,
        status=Booking.Status.PENDING,
        hold_expires_at=timezone.now() - timedelta(minutes=1),
    )

    with caplog.at_level(logging.INFO, logger="events.services"):
        expire_holds()

    assert records(caplog, "events.services")["holds_expired"].fields == {
        "count": 1,
    }


def test_invalid_webhook_signature_is_logged_without_the_signature(
    api_client,
    caplog,
):
    with caplog.at_level(logging.WARNING, logger="payments.views"):
        response = api_client.post(
            "/api/payments/webhook/",
            data="{}",
            content_type="application/json",
            HTTP_X_SIGNATURE="secret-looking-value",
        )

    logged = records(caplog, "payments.views")

    assert response.status_code == 401
    assert "ip" in logged["webhook_invalid_signature"].fields
    assert "secret-looking-value" not in str(
        [r.__dict__ for r in caplog.records]
    )
