import logging
from django.db import transaction
from django.utils import timezone

from events.models import Booking

from .models import Payment, WebhookEvent
from .tasks import send_booking_confirmation
logger = logging.getLogger(__name__)


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
        booking=booking,
        status=Payment.Status.PENDING,
    ).first()
    if existing:
        return existing
        
    payment = Payment.objects.create(
        booking=booking,
        amount=booking.seat.price,
    )

    logger.info(
        "payment_started",
        extra={
            "fields": {
                "payment_id": payment.id,
                "booking_id": booking.id,
                "user_id": user.id,
            }
        },
    )
    return payment


@transaction.atomic
def process_webhook(event_id, reference, outcome):
    # 1) idempotency: have we seen this event_id before?
    _, created = WebhookEvent.objects.get_or_create(event_id=event_id)
    if not created:
        logger.info(
            "webhook_duplicate",
            extra={"fields": {"event_id": event_id}},
        )
        return "duplicate"

    # 2) lock the payment so concurrent webhooks queue up
    payment = Payment.objects.select_for_update().get(reference=reference)

    if payment.status != Payment.Status.PENDING:
        result = "ignored"

    elif outcome == "failed":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        result = "failed"

    else:
        booking = Booking.objects.select_for_update().get(
            pk=payment.booking_id
        )

        if booking.status == Booking.Status.PENDING:
            booking.status = Booking.Status.CONFIRMED
            booking.hold_expires_at = None
            booking.save(update_fields=["status", "hold_expires_at"])

            payment.status = Payment.Status.SUCCEEDED

            # queue the email only after the transaction really committed
            transaction.on_commit(
                lambda: send_booking_confirmation.delay(booking.id)
            )

            result = "confirmed"

        else:
            # money arrived but the seat is no longer ours
            payment.status = Payment.Status.REFUND_REQUIRED
            result = "refund_required"

        payment.save(update_fields=["status"])

    level = (
        logging.WARNING
        if result == "refund_required"
        else logging.INFO
    )

    logger.log(
        level,
        "webhook_processed",
        extra={
            "fields": {
                "event_id": event_id,
                "payment_id": payment.id,
                "booking_id": payment.booking_id,
                "result": result,
            }
        },
    )

    return result