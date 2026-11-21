import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Booking

from .models import Payment
from .serializers import PaymentSerializer
from .services import BookingNotPayable, process_webhook, start_payment


class StartPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get("booking_id")
        if not isinstance(booking_id, int) or isinstance(booking_id, bool):
            return Response(
                {"booking_id": ["An integer is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = start_payment(request.user, booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except BookingNotPayable:
            return Response(
                {"detail": "Booking cannot be paid."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentWebhookView(APIView):
    # the gateway has no JWT: it proves itself with a signature instead
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw = request.body  # must be read before request.data is touched
        signature = request.headers.get("X-Signature", "")
        expected = hmac.new(
            settings.PAYMENT_WEBHOOK_SECRET.encode(), raw, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature.encode(), expected.encode()):
            return Response(
                {"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            data = json.loads(raw)
            event_id = data["event_id"]
            reference = data["reference"]
            outcome = data["outcome"]
        except (ValueError, KeyError, TypeError):
            return Response(
                {"detail": "Malformed payload."}, status=status.HTTP_400_BAD_REQUEST
            )

        valid = (
            isinstance(event_id, str)
            and 0 < len(event_id) <= 100
            and isinstance(reference, str)
            and outcome in ("succeeded", "failed")
        )
        if not valid:
            return Response(
                {"detail": "Malformed payload."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = process_webhook(event_id, reference, outcome)
        except (Payment.DoesNotExist, DjangoValidationError):
            return Response(
                {"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response({"status": result})