import socket
from unittest.mock import patch

import httpx
import pytest

from werkblatt.integrations.pretix.client import (
    PretixClient,
    PretixConfigurationError,
    validate_public_https_origin,
)
from werkblatt.integrations.pretix.provider import PretixWorkshopProvider

PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_rejects_non_https_and_private_hosts():
    with pytest.raises(PretixConfigurationError):
        validate_public_https_origin("http://pretix.example")
    private_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with (
        patch("socket.getaddrinfo", return_value=private_dns),
        pytest.raises(PretixConfigurationError),
    ):
        validate_public_https_origin("https://pretix.example")


def test_maps_event_series_and_subevent():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "slug": "reihe",
                            "name": {"de": "Workshopreihe"},
                            "live": True,
                            "testmode": False,
                            "has_subevents": True,
                        }
                    ],
                    "next": None,
                },
            )
        if request.url.path.endswith("/subevents/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 42,
                            "name": {"de": "Termin"},
                            "active": True,
                            "is_public": True,
                            "date_from": "2026-09-01T18:00:00+02:00",
                            "date_to": "2026-09-01T20:00:00+02:00",
                            "location": {"de": "Werkstatt"},
                        }
                    ],
                    "next": None,
                },
            )
        raise AssertionError(request.url)

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://www.pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        workshops = PretixWorkshopProvider(client, "WERK").list_workshops()
    assert len(workshops) == 1
    assert workshops[0].reference == "reihe:42"
    assert workshops[0].title == "Termin"
