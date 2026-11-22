from django.urls import path

from .pay_views import PayView
from .views import PaymentWebhookView, StartPaymentView

urlpatterns = [
    path("", StartPaymentView.as_view(), name="payment-start"),
    path("webhook/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path("<uuid:reference>/pay/", PayView.as_view(), name="payment-pay"),
]