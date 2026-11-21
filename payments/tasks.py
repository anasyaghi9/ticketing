from celery import shared_task
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