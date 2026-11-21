from django.db import transaction
from django.utils import timezone

from events.models import Booking

from .models import Payment, WebhookEvent
from .tasks import send_booking_confirmation


class BookingNotPayable(Exception):
    pass


@transaction.atomic
def start_payment(user, booking_id):
    booking = (
        Booking.objects.select_for_update()
        .select_related("seat")
        .get(id=booking_id, user=user)
    )

    hold_is_alive = (
        booking.hold_expires_at is not None
        and booking.hold_expires_at > timezone.now()
    )
    if booking.status != Booking.Status.PENDING or not hold_is_alive:
        raise BookingNotPayable("Booking cannot be paid.")

    existing = Payment.objects.filter(
        booking=booking, status=Payment.Status.PENDING
    ).first()
    if existing:
        return existing

    return Payment.objects.create(booking=booking, amount=booking.seat.price)


@transaction.atomic
def process_webhook(event_id, reference, outcome):
    # 1) idempotency: have we seen this event_id before?
    _, created = WebhookEvent.objects.get_or_create(event_id=event_id)
    if not created:
        return "duplicate"

    # 2) lock the payment so concurrent webhooks queue up
    payment = Payment.objects.select_for_update().get(reference=reference)

    if payment.status != Payment.Status.PENDING:
        return "ignored"

    if outcome == "failed":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        return "failed"

    # 3) outcome == "succeeded"
    booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

    if booking.status == Booking.Status.PENDING:
        booking.status = Booking.Status.CONFIRMED
        booking.hold_expires_at = None
        booking.save(update_fields=["status", "hold_expires_at"])
        payment.status = Payment.Status.SUCCEEDED
        # queue the email only after the transaction really committed
        transaction.on_commit(lambda: send_booking_confirmation.delay(booking.id))
        result = "confirmed"
    else:
        # money arrived but the seat is no longer ours
        payment.status = Payment.Status.REFUND_REQUIRED
        result = "refund_required"

    payment.save(update_fields=["status"])
    return result