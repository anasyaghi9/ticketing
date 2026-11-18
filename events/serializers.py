from django.utils import timezone
from rest_framework import serializers

from .models import Booking, Event, Seat


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "description", "venue", "starts_at"]

    def validate_starts_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Event must start in the future.")
        return value


class SeatSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Seat
        fields = ["id", "label", "price", "is_available"]

    def get_is_available(self, obj):
        return not obj.is_taken


class EventDetailSerializer(EventSerializer):
    seats = SeatSerializer(many=True, read_only=True)

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + ["seats"]


class BookingSerializer(serializers.ModelSerializer):
    seat_label = serializers.CharField(source="seat.label", read_only=True)
    event_title = serializers.CharField(source="seat.event.title", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "seat", "seat_label", "event_title",
            "status", "hold_expires_at", "created_at",
        ]

class SeatBulkCreateSerializer(serializers.Serializer):
    rows = serializers.ListField(
        child=serializers.RegexField(r"^[A-Za-z]{1,2}$"),
        min_length=1,
        max_length=26,
    )
    per_row = serializers.IntegerField(min_value=1, max_value=100)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)

    def validate(self, attrs):
        attrs["rows"] = [r.upper() for r in attrs["rows"]]
        if len(set(attrs["rows"])) != len(attrs["rows"]):
            raise serializers.ValidationError("Duplicate rows.")
        if len(attrs["rows"]) * attrs["per_row"] > 1000:
            raise serializers.ValidationError("Too many seats in one request (max 1000).")
        return attrs