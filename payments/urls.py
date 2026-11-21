from django.urls import path

from .views import PaymentWebhookView, StartPaymentView

urlpatterns = [
    path("", StartPaymentView.as_view(), name="payment-start"),
    path("webhook/", PaymentWebhookView.as_view(), name="payment-webhook"),
]