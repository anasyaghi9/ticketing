from django.test import override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import BaseThrottle


def client_ip(forwarded_for, proxies):
    with override_settings(REST_FRAMEWORK={"NUM_PROXIES": proxies}):
        request = APIRequestFactory().get(
            "/", HTTP_X_FORWARDED_FOR=forwarded_for, REMOTE_ADDR="172.18.0.1"
        )
        return BaseThrottle().get_ident(request)


def test_one_proxy_uses_the_address_nginx_appended():
    # a client can fake the first entry, but Nginx appends the real address last
    assert client_ip("6.6.6.6, 203.0.113.7", proxies=1) == "203.0.113.7"


def test_no_proxy_configured_ignores_the_forwarded_header():
    assert client_ip("6.6.6.6", proxies=0) == "172.18.0.1"