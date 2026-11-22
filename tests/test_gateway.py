from unittest.mock import patch

import pytest
from django.conf import settings

from events.services import book_seat
from payments.gateways import FakeGateway
from payments.models import Payment
from payments.services import start_payment
from payments.tasks import deliver_fake_webhook

pytestmark = pytest.mark.django_db


@pytest.fixture
def payment(attendee, seat):
    booking = book_seat(attendee, seat.id)
    return start_payment(attendee, booking.id)


def pay_url(payment):
    return f"/api/payments/{payment.reference}/pay/"


def queued_args(task):
    return task.apply_async.call_args.kwargs["args"]


def test_success_card_queues_a_succeeded_callback(auth, attendee, payment):
    with patch("payments.gateways.deliver_fake_webhook") as task:
        response = auth(attendee).post(
            pay_url(payment), {"card_number": FakeGateway.SUCCESS}, format="json"
        )

    assert response.status_code == 202
    assert response.json() == {"status": "processing"}
    args = queued_args(task)
    assert args[0] == str(payment.reference)
    assert args[1] == "succeeded"


def test_any_other_card_is_declined(auth, attendee, payment):
    with patch("payments.gateways.deliver_fake_webhook") as task:
        auth(attendee).post(
            pay_url(payment), {"card_number": "4000000000000002"}, format="json"
        )

    assert queued_args(task)[1] == "failed"


def test_cannot_pay_someone_elses_payment(auth, attendee2, payment):
    with patch("payments.gateways.deliver_fake_webhook") as task:
        response = auth(attendee2).post(
            pay_url(payment), {"card_number": FakeGateway.SUCCESS}, format="json"
        )

    assert response.status_code == 404
    task.apply_async.assert_not_called()


def test_cannot_pay_a_payment_that_is_not_pending(auth, attendee, payment):
    Payment.objects.filter(id=payment.id).update(status=Payment.Status.SUCCEEDED)

    response = auth(attendee).post(
        pay_url(payment), {"card_number": FakeGateway.SUCCESS}, format="json"
    )

    assert response.status_code == 409


def test_invalid_card_number_is_rejected(auth, attendee, payment):
    response = auth(attendee).post(
        pay_url(payment), {"card_number": "abc"}, format="json"
    )

    assert response.status_code == 400


def test_pay_requires_login(api_client, payment):
    response = api_client.post(
        pay_url(payment), {"card_number": FakeGateway.SUCCESS}, format="json"
    )

    assert response.status_code == 401


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_request_built_by_the_task_is_accepted_by_the_webhook(
    api_client, payment, django_capture_on_commit_callbacks
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse()

    with patch("payments.tasks.urllib.request.urlopen", fake_urlopen):
        deliver_fake_webhook(str(payment.reference), "succeeded", "fake_evt_1")

    request = captured["request"]
    assert request.full_url == settings.PAYMENT_WEBHOOK_URL

    with patch("payments.services.send_booking_confirmation"):
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                "/api/payments/webhook/",
                data=request.data,
                content_type="application/json",
                HTTP_X_SIGNATURE=request.get_header("X-signature"),
            )

    payment.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {"status": "confirmed"}
    assert payment.status == Payment.Status.SUCCEEDED