import uuid

from django.db import models
from django.db.models import Q


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUND_REQUIRED = "refund_required", "Refund required"

    booking = models.ForeignKey(
        "events.Booking", on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(status="pending"),
                name="one_pending_payment_per_booking",
            )
        ]

    def __str__(self):
        return f"Payment {self.reference} ({self.status})"


class WebhookEvent(models.Model):
    """One row per webhook we have already processed (the idempotency record)."""

    event_id = models.CharField(max_length=100, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id