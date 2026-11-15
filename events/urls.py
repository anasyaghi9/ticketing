from django.urls import path

from .views import (
    BookSeatView,
    EventDetailView,
    EventListView,
    MyBookingsView,
)

urlpatterns = [
    path("", EventListView.as_view(), name="event-list"),
    path("<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("seats/<int:seat_id>/book/", BookSeatView.as_view(), name="seat-book"),
    path("my-bookings/", MyBookingsView.as_view(), name="my-bookings"),
]