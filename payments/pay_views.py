import re

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateways import get_gateway
from .models import Payment


class PayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, reference):
        card_number = request.data.get("card_number")
        if not isinstance(card_number, str) or not re.fullmatch(r"\d{13,19}", card_number):
            return Response(
                {"card_number": ["Enter 13 to 19 digits."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.get(reference=reference, booking__user=request.user)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if payment.status != Payment.Status.PENDING:
            return Response(
                {"detail": "Payment is not pending."}, status=status.HTTP_409_CONFLICT
            )

        get_gateway().charge(payment, card_number)
        return Response({"status": "processing"}, status=status.HTTP_202_ACCEPTED)