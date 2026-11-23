from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Prefetch, ProtectedError, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .cache import EVENT_LIST_TTL, event_list_key
from .models import Booking, Event, Seat
from .pagination import EventPagination
from .permissions import IsEventOwner, IsOrganizer
from .serializers import BookingSerializer, EventDetailSerializer, EventSerializer
from .services import (
    MAX_ACTIVE_BOOKINGS_PER_EVENT,
    BookingLimitReached,
    BookingNotCancellable,
    EventNotBookable,
    SeatNotAvailable,
    book_seat,
    cancel_booking,
)


class EventListCreateView(generics.ListCreateAPIView):
    serializer_class = EventSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        return Event.objects.filter(starts_at__gt=timezone.now())

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOrganizer()]
        return [permissions.AllowAny()]

    def _page_params(self, request):
        """(page, size) when it is safe to cache this request, else None."""
        page = request.query_params.get("page", "1")
        size = request.query_params.get("page_size", str(EventPagination.page_size))
        for value in (page, size):
            if not (value.isascii() and value.isdecimal()):
                return None
        page, size = int(page), int(size)
        if not (1 <= page <= 100 and 1 <= size <= 100):
            return None
        return page, size

    def list(self, request, *args, **kwargs):
        params = self._page_params(request)
        if params is None:
            return super().list(request, *args, **kwargs)

        page, size = params
        key = event_list_key(page, size)
        cached = cache.get(key)

        if cached is None:
            response = super().list(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(
                    key,
                    {
                        "count": response.data["count"],
                        "results": [dict(item) for item in response.data["results"]],
                    },
                    EVENT_LIST_TTL,
                )
            return response

        next_url, previous_url = self.paginator.links(request, page, size, cached["count"])
        return Response(
            {
                "count": cached["count"],
                "next": next_url,
                "previous": previous_url,
                "results": cached["results"],
            }
        )

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsOrganizer(), IsEventOwner()]

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return EventDetailSerializer
        return EventSerializer

    def get_queryset(self):
        if self.request.method not in permissions.SAFE_METHODS:
            return Event.objects.all()
        now = timezone.now()
        active_booking = Booking.objects.filter(seat=OuterRef("pk")).filter(
            Q(status=Booking.Status.CONFIRMED)
            | Q(status=Booking.Status.PENDING, hold_expires_at__gt=now)
        )
        seats = Seat.objects.annotate(is_taken=Exists(active_booking))
        return Event.objects.prefetch_related(Prefetch("seats", queryset=seats))

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Event has bookings and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )


class BookSeatView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking"

    def post(self, request, seat_id):
        try:
            booking = book_seat(request.user, seat_id)
        except Seat.DoesNotExist:
            return Response(
                {"detail": "Seat not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except EventNotBookable:
            return Response(
                {"detail": "Event has already started."},
                status=status.HTTP_409_CONFLICT,
            )
        except BookingLimitReached:
            return Response(
                {
                    "detail": f"You can hold at most "
                    f"{MAX_ACTIVE_BOOKINGS_PER_EVENT} seats per event."
                },
                status=status.HTTP_409_CONFLICT,
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