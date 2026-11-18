from django.urls import path

from .views import (
    BookSeatView,
    CancelBookingView,
    EventDetailView,
    EventListCreateView,
    MyBookingsView,
)

urlpatterns = [
    path("", EventListCreateView.as_view(), name="event-list"),
    path("<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("seats/<int:seat_id>/book/", BookSeatView.as_view(), name="seat-book"),
    path("bookings/<int:booking_id>/cancel/", CancelBookingView.as_view(), name="booking-cancel"),
    path("my-bookings/", MyBookingsView.as_view(), name="my-bookings"),
]