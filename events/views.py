from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Event, Seat
from .serializers import BookingSerializer, EventDetailSerializer, EventSerializer
from .services import (
    BookingNotCancellable,
    SeatNotAvailable,
    book_seat,
    cancel_booking,
)


class EventListView(generics.ListAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventDetailSerializer

    def get_queryset(self):
        now = timezone.now()
        active_booking = Booking.objects.filter(seat=OuterRef("pk")).filter(
            Q(status=Booking.Status.CONFIRMED)
            | Q(status=Booking.Status.PENDING, hold_expires_at__gt=now)
        )
        seats = Seat.objects.annotate(is_taken=Exists(active_booking))
        return Event.objects.prefetch_related(Prefetch("seats", queryset=seats))


class BookSeatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, seat_id):
        try:
            booking = book_seat(request.user, seat_id)
        except Seat.DoesNotExist:
            return Response(
                {"detail": "Seat not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (SeatNotAvailable, IntegrityError):
            return Response(
                {"detail": "Seat is not available."}, status=status.HTTP_409_CONFLICT
            )
        return Response(
            BookingSerializer(booking).data, status=status.HTTP_201_CREATED
        )


class CancelBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = cancel_booking(request.user, booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except BookingNotCancellable:
            return Response(
                {"detail": "Booking cannot be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(BookingSerializer(booking).data)


class MyBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related("seat__event")
            .order_by("-created_at")
        )