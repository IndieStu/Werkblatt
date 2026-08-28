import pytest
from django.db import connection
from django.test import Client


def test_liveness_does_not_touch_database(monkeypatch):
    def fail_if_used():
        raise AssertionError("Liveness darf die Datenbank nicht verwenden")

    monkeypatch.setattr(connection, "cursor", fail_if_used)
    response = Client().get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_readiness_checks_database():
    response = Client().get("/ready/")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["Cache-Control"] == "no-store"
