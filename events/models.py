from django.conf import settings
from django.db import models
from django.db.models import Q


class Event(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["starts_at"])]

    def __str__(self):
        return self.title


class Seat(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="seats"
    )
    label = models.CharField(max_length=10)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "label"],
                name="unique_seat_label_per_event",
            )
        ]

    def __str__(self):
        return f"{self.event.title} - {self.label}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    seat = models.ForeignKey(
        Seat, on_delete=models.PROTECT, related_name="bookings"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "hold_expires_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["seat"],
                condition=Q(status__in=["pending", "confirmed"]),
                name="unique_active_booking_per_seat",
            )
        ]

    def __str__(self):
        return f"{self.user} -> {self.seat} ({self.status})"