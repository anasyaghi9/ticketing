import uuid
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string

from .tasks import deliver_fake_webhook


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, payment, card_number):
        """Start charging the card. The result arrives later through the webhook."""


class FakeGateway(PaymentGateway):
    SUCCESS = "4242424242424242"

    def charge(self, payment, card_number):
        outcome = "succeeded" if card_number == self.SUCCESS else "failed"
        deliver_fake_webhook.apply_async(
            args=[str(payment.reference), outcome, f"fake_{uuid.uuid4().hex}"],
            countdown=2,
        )


def get_gateway():
    return import_string(settings.PAYMENT_GATEWAY)()