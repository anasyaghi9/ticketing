from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def test_health_ok(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_a_database_failure(api_client):
    with patch("config.health.connection") as connection:
        connection.cursor.side_effect = Exception("db down")
        response = api_client.get("/api/health/")

    assert response.status_code == 503