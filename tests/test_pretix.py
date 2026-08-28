import socket
from unittest.mock import patch

import httpx
import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from werkblatt.integrations.pretix.client import (
    MAX_PRETIX_RESPONSE_BYTES,
    PretixClient,
    PretixConfigurationError,
    PretixUnavailable,
    validate_public_https_origin,
)
from werkblatt.integrations.pretix.provider import PretixWorkshopProvider
from werkblatt.integrations.pretix.types import ExternalRegistration, ExternalWorkshop
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import Workshop, WorkshopRegistration

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


def test_testmode_events_require_explicit_opt_in():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "slug": "synthetic-preflight",
                        "name": {"de": "Synthetischer Preflight"},
                        "live": True,
                        "testmode": True,
                        "has_subevents": False,
                        "date_from": "2026-09-01T18:00:00+02:00",
                    }
                ],
                "next": None,
            },
        )

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://www.pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        provider = PretixWorkshopProvider(client, "WERK")
        assert provider.list_workshops() == []
        assert provider.list_workshops(include_testmode=True)[0].reference == "synthetic-preflight"


@pytest.mark.django_db
def test_sync_imports_only_requested_synthetic_workshop_and_active_registrations(settings):
    organization = Organization.objects.create(slug="zircula", name="Synthetische Organisation")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    workshop = ExternalWorkshop(
        reference="preflight:42",
        title="Synthetischer Pretix-Workshop",
        starts_at=timezone.now(),
        ends_at=None,
        location="Testraum",
    )
    first_rows = [
        ExternalRegistration(reference="ORDER1:1", display_name="Erste Testperson"),
        ExternalRegistration(reference="ORDER2:2", display_name="Zweite Testperson"),
    ]
    with (
        patch.object(PretixWorkshopProvider, "list_workshops", return_value=[workshop]),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=first_rows),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix", "--include-test-events", "--workshop-reference", "preflight:42")

    stored_workshop = Workshop.objects.get(external_reference="preflight:42")
    assert list(
        stored_workshop.registrations.order_by("display_name").values_list("display_name", "active")
    ) == [("Erste Testperson", True), ("Zweite Testperson", True)]

    second_rows = [
        ExternalRegistration(reference="ORDER2:2", display_name="Zweite Testperson geändert")
    ]
    with (
        patch.object(PretixWorkshopProvider, "list_workshops", return_value=[workshop]),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=second_rows),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix", "--include-test-events", "--workshop-reference", "preflight:42")

    assert WorkshopRegistration.objects.get(external_reference="ORDER1:1").active is False
    updated = WorkshopRegistration.objects.get(external_reference="ORDER2:2")
    assert updated.active is True
    assert updated.display_name == "Zweite Testperson geändert"


@pytest.mark.django_db
def test_sync_rejects_unbounded_test_event_import(settings):
    Organization.objects.create(slug="zircula", name="Synthetische Organisation")
    settings.PRETIX_API_TOKEN = "synthetic-token"

    with pytest.raises(CommandError, match="erfordert"):
        call_command("sync_pretix", "--include-test-events")


def test_resolution_change_to_private_address_is_rejected_before_request():
    private_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with patch("socket.getaddrinfo", side_effect=[PUBLIC_DNS, private_dns]):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(lambda _request: pytest.fail("request must not run")),
        )
        with pytest.raises(PretixConfigurationError):
            client.get("/api/v1/organizers/WORK/events/")


def test_response_size_is_bounded():
    response_body = b'{"padding":"' + b"x" * MAX_PRETIX_RESPONSE_BYTES + b'"}'
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=response_body)
            ),
        )
        with pytest.raises(PretixUnavailable, match="size limit"):
            client.get("/api/v1/organizers/WORK/events/")
