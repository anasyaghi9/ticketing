from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event
from .permissions import IsOrganizer
from .serializers import SeatBulkCreateSerializer
from .services import create_seats


class CreateSeatsView(APIView):
    permission_classes = [IsOrganizer]

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if event.organizer_id != request.user.id:
            return Response(
                {"detail": "You do not own this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SeatBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            created = create_seats(event, **serializer.validated_data)
        except IntegrityError:
            return Response(
                {"detail": "Some of these seats already exist."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"created": created}, status=status.HTTP_201_CREATED)