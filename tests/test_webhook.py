import hashlib
import hmac
import json
import uuid
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail

from events.models import Booking
from events.services import book_seat
from payments.models import Payment, WebhookEvent
from payments.services import start_payment
from payments.tasks import send_booking_confirmation

pytestmark = pytest.mark.django_db

URL = "/api/payments/webhook/"


def sign(raw):
    return hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()


def send(client, payload, signature=None):
    raw = json.dumps(payload)
    return client.post(
        URL,
        data=raw,
        content_type="application/json",
        HTTP_X_SIGNATURE=signature or sign(raw),
    )


def payload(payment, event_id="evt_1", outcome="succeeded"):
    return {
        "event_id": event_id,
        "reference": str(payment.reference),
        "outcome": outcome,
    }


@pytest.fixture
def payment(attendee, seat):
    booking = book_seat(attendee, seat.id)
    return start_payment(attendee, booking.id)


def test_success_confirms_the_booking_and_queues_one_email(
    api_client, payment, django_capture_on_commit_callbacks
):
    with patch("payments.services.send_booking_confirmation") as task:
        with django_capture_on_commit_callbacks(execute=True):
            response = send(api_client, payload(payment))

    booking = Booking.objects.get(id=payment.booking_id)
    payment.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {"status": "confirmed"}
    assert payment.status == Payment.Status.SUCCEEDED
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.hold_expires_at is None
    task.delay.assert_called_once_with(booking.id)


def test_same_event_id_twice_is_processed_once(
    api_client, payment, django_capture_on_commit_callbacks
):
    with patch("payments.services.send_booking_confirmation") as task:
        with django_capture_on_commit_callbacks(execute=True):
            first = send(api_client, payload(payment))
            second = send(api_client, payload(payment))

    assert first.json() == {"status": "confirmed"}
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    assert WebhookEvent.objects.count() == 1
    assert task.delay.call_count == 1


def test_bad_signature_is_rejected_and_changes_nothing(api_client, payment):
    response = send(api_client, payload(payment), signature="0" * 64)

    payment.refresh_from_db()
    assert response.status_code == 401
    assert payment.status == Payment.Status.PENDING
    assert WebhookEvent.objects.count() == 0


def test_failed_outcome_marks_payment_failed_and_keeps_the_hold(api_client, payment):
    response = send(api_client, payload(payment, outcome="failed"))

    booking = Booking.objects.get(id=payment.booking_id)
    payment.refresh_from_db()
    assert response.json() == {"status": "failed"}
    assert payment.status == Payment.Status.FAILED
    assert booking.status == Booking.Status.PENDING


def test_unknown_reference_returns_404_and_leaves_no_trace(api_client):
    body = {"event_id": "evt_x", "reference": str(uuid.uuid4()), "outcome": "succeeded"}

    response = send(api_client, body)

    assert response.status_code == 404
    assert WebhookEvent.objects.count() == 0


def test_late_success_after_the_booking_expired_needs_a_refund(api_client, payment):
    Booking.objects.filter(id=payment.booking_id).update(status=Booking.Status.EXPIRED)

    response = send(api_client, payload(payment))

    booking = Booking.objects.get(id=payment.booking_id)
    payment.refresh_from_db()
    assert response.json() == {"status": "refund_required"}
    assert payment.status == Payment.Status.REFUND_REQUIRED
    assert booking.status == Booking.Status.EXPIRED


def test_a_new_event_for_an_already_final_payment_is_ignored(api_client, payment):
    send(api_client, payload(payment, event_id="evt_1", outcome="succeeded"))

    response = send(api_client, payload(payment, event_id="evt_2", outcome="failed"))

    payment.refresh_from_db()
    assert response.json() == {"status": "ignored"}
    assert payment.status == Payment.Status.SUCCEEDED


def test_confirmation_email_content(attendee, payment):
    send_booking_confirmation(payment.booking_id)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [attendee.email]
    assert "Test Event" in message.subject
    assert "A1" in message.body