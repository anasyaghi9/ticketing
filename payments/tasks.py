import hashlib
import hmac
import json
import urllib.request

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from events.models import Booking


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_booking_confirmation(booking_id):
    booking = Booking.objects.select_related("user", "seat__event").get(id=booking_id)
    event = booking.seat.event
    send_mail(
        subject=f"Booking confirmed: {event.title}",
        message=(
            f"Hi {booking.user.username},\n\n"
            f"Your seat {booking.seat.label} for {event.title} "
            f"at {event.venue} is confirmed.\n\nSee you there!"
        ),
        from_email=None,
        recipient_list=[booking.user.email],
    )
    return f"sent to {booking.user.email}"


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def deliver_fake_webhook(reference, outcome, event_id):
    """Play the payment gateway: call our own webhook with a signed request."""
    body = json.dumps(
        {"event_id": event_id, "reference": reference, "outcome": outcome}
    ).encode()
    signature = hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    request = urllib.request.Request(
        settings.PAYMENT_WEBHOOK_URL,
        data=body,
        headers={"Content-Type": "application/json", "X-Signature": signature},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return f"webhook answered {response.status}"