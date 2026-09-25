import socket
from datetime import date, datetime
from unittest.mock import patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from werkblatt.integrations.pretix.client import (
    MAX_PRETIX_REQUEST_BYTES,
    MAX_PRETIX_RESPONSE_BYTES,
    PretixClient,
    PretixConfigurationError,
    PretixUnavailable,
    validate_public_https_origin,
)
from werkblatt.integrations.pretix.creation import (
    PretixCreationPreset,
    PretixEventCreator,
    PretixEventDraft,
    numbered_event_slug,
)
from werkblatt.integrations.pretix.provider import PretixWorkshopProvider
from werkblatt.integrations.pretix.types import (
    ExternalRegistration,
    ExternalWorkshop,
    ExternalWorkshopBatch,
)
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import PretixEventRule, Workshop, WorkshopRegistration

PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def batch(workshops, *, ignored=()):
    return ExternalWorkshopBatch(
        workshops=tuple(workshops),
        synchronized_event_slugs=frozenset(
            item.event_slug or item.reference.partition(":")[0] for item in workshops
        ),
        ignored_event_slugs=frozenset(ignored),
    )


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
            "https://pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        workshops = PretixWorkshopProvider(client, "example-organizer").list_workshops()
    assert len(workshops) == 1
    assert workshops[0].reference == "reihe:42"
    assert workshops[0].event_slug == "reihe"
    assert workshops[0].title == "Termin"


def test_series_can_be_excluded_before_subevents_are_requested():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "slug": "offene-werkstatt",
                            "live": True,
                            "testmode": False,
                            "has_subevents": True,
                        }
                    ],
                    "next": None,
                },
            )
        pytest.fail("Ausgeschlossene Subevents dürfen nicht abgerufen werden")

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        workshops = PretixWorkshopProvider(client, "example-organizer").list_workshops(
            excluded_event_slugs=frozenset({"offene-werkstatt"})
        )
    assert workshops == []


def test_subevent_import_cutoff_is_sent_to_pretix_and_enforced_locally():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "slug": "reihe",
                            "live": True,
                            "testmode": False,
                            "has_subevents": True,
                        }
                    ],
                    "next": None,
                },
            )
        assert request.url.params["date_from_after"] == "2026-08-25"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1,
                        "active": True,
                        "is_public": True,
                        "date_from": "2026-08-24T10:00:00+02:00",
                    },
                    {
                        "id": 2,
                        "active": True,
                        "is_public": True,
                        "date_from": "2026-08-25T10:00:00+02:00",
                    },
                ],
                "next": None,
            },
        )

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        workshops = PretixWorkshopProvider(client, "example-organizer").list_workshops(
            not_before=date(2026, 8, 25)
        )
    assert [workshop.reference for workshop in workshops] == ["reihe:2"]


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
            "https://pretix.eu", "synthetic-token", transport=httpx.MockTransport(handler)
        )
        provider = PretixWorkshopProvider(client, "example-organizer")
        assert provider.list_workshops() == []
        assert provider.list_workshops(include_testmode=True)[0].reference == "synthetic-preflight"


@pytest.mark.django_db
def test_sync_imports_only_requested_synthetic_workshop_and_active_registrations(settings):
    organization = Organization.objects.create(slug="example", name="Example Organization")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "synthetic-organizer"
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
        patch.object(PretixWorkshopProvider, "list_workshop_batch", return_value=batch([workshop])),
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
        patch.object(PretixWorkshopProvider, "list_workshop_batch", return_value=batch([workshop])),
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
    Organization.objects.create(slug="example", name="Example Organization")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "synthetic-organizer"
    settings.DEFAULT_ORGANIZATION_SLUG = "example"

    with pytest.raises(CommandError, match="erfordert"):
        call_command("sync_pretix", "--include-test-events")


@pytest.mark.django_db
def test_regular_sync_requires_valid_import_cutoff(settings):
    Organization.objects.create(slug="example", name="Example Organization")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "synthetic-organizer"
    settings.DEFAULT_ORGANIZATION_SLUG = "example"
    settings.PRETIX_IMPORT_NOT_BEFORE = ""

    with pytest.raises(CommandError, match="PRETIX_IMPORT_NOT_BEFORE"):
        call_command("sync_pretix")


@pytest.mark.django_db
def test_regular_sync_marks_missing_workshops_cancelled_and_reactivates_them(settings):
    organization = Organization.objects.create(slug="example", name="Example Organization")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "synthetic-organizer"
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    settings.PRETIX_IMPORT_NOT_BEFORE = "2026-08-25"
    starts_at = timezone.make_aware(datetime(2026, 9, 10, 10, 0))
    missing = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="series:2",
        parent_external_reference="series",
        title="Später gelöschter Termin",
        starts_at=starts_at,
    )
    ignored = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="test:1",
        parent_external_reference="test",
        title="Explizites Testevent",
        starts_at=starts_at,
    )
    active = ExternalWorkshop(
        reference="series:1",
        event_slug="series",
        title="Aktiver Termin",
        starts_at=starts_at,
        ends_at=None,
        location="Werkstatt",
    )
    with (
        patch.object(
            PretixWorkshopProvider,
            "list_workshop_batch",
            return_value=batch([active], ignored={"test"}),
        ),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=[]),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix")

    missing.refresh_from_db()
    ignored.refresh_from_db()
    assert missing.lifecycle_status == Workshop.LifecycleStatus.CANCELLED
    assert ignored.lifecycle_status == Workshop.LifecycleStatus.ACTIVE

    restored = ExternalWorkshop(
        reference="series:2",
        event_slug="series",
        title="Wieder aktiver Termin",
        starts_at=starts_at,
        ends_at=None,
        location="Werkstatt",
    )
    with (
        patch.object(
            PretixWorkshopProvider,
            "list_workshop_batch",
            return_value=batch([active, restored], ignored={"test"}),
        ),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=[]),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix")

    missing.refresh_from_db()
    assert missing.lifecycle_status == Workshop.LifecycleStatus.ACTIVE
    assert missing.title == "Wieder aktiver Termin"


@pytest.mark.django_db
def test_series_rule_applies_to_all_dates_but_individual_override_survives_sync(settings):
    organization = Organization.objects.create(slug="example", name="Example Organization")
    user = get_user_model().objects.create_user(username="admin")
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "synthetic-organizer"
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    settings.PRETIX_IMPORT_NOT_BEFORE = "2026-08-25"
    PretixEventRule.objects.create(
        organization=organization,
        event_slug="offene-werkstatt",
        display_name="Offene Werkstatt",
        documentation_requirement=Workshop.DocumentationRequirement.NOT_REQUIRED,
        reason="Offenes Angebot",
        decided_by=user,
    )
    workshops = [
        ExternalWorkshop(
            reference=f"offene-werkstatt:{number}",
            event_slug="offene-werkstatt",
            title=f"Termin {number}",
            starts_at=timezone.now(),
            ends_at=None,
            location="Werkstatt",
        )
        for number in (1, 2)
    ]
    with (
        patch.object(PretixWorkshopProvider, "list_workshop_batch", return_value=batch(workshops)),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=[]),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix")

    first, second = Workshop.objects.order_by("external_reference")
    assert first.documentation_requirement == Workshop.DocumentationRequirement.NOT_REQUIRED
    assert second.documentation_requirement == Workshop.DocumentationRequirement.NOT_REQUIRED
    first.documentation_requirement = Workshop.DocumentationRequirement.REQUIRED
    first.requirement_source = Workshop.RequirementSource.INDIVIDUAL
    first.save(update_fields=["documentation_requirement", "requirement_source"])

    with (
        patch.object(PretixWorkshopProvider, "list_workshop_batch", return_value=batch(workshops)),
        patch.object(PretixWorkshopProvider, "list_registrations", return_value=[]),
        patch.object(PretixClient, "__init__", return_value=None),
        patch.object(PretixClient, "close"),
    ):
        call_command("sync_pretix")

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.documentation_requirement == Workshop.DocumentationRequirement.REQUIRED
    assert second.documentation_requirement == Workshop.DocumentationRequirement.NOT_REQUIRED


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


def test_write_requests_are_json_bounded_and_do_not_follow_redirects():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"slug": "synthetic-1"})

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(handler),
        )
        assert client.post(
            "/api/v1/organizers/WORK/events/",
            {"name": {"de": "Synthetisch"}},
            params={"clone_from": "blanko"},
        ) == {"slug": "synthetic-1"}
        assert client.patch(
            "/api/v1/organizers/WORK/events/synthetic-1/",
            {"is_public": False},
        ) == {"slug": "synthetic-1"}
        with pytest.raises(PretixConfigurationError, match="size limit"):
            client.post(
                "/api/v1/organizers/WORK/events/",
                {"description": "x" * MAX_PRETIX_REQUEST_BYTES},
            )

    assert [request.method for request in requests] == ["POST", "PATCH"]
    assert requests[0].url.params["clone_from"] == "blanko"
    assert requests[0].headers["Authorization"] == "Token synthetic-token"


def test_numbered_event_slug_is_automatic_stable_and_ascii_safe():
    assert numbered_event_slug("Klimawerkstatt Gröpelingen", set()) == (
        "klimawerkstatt-gropelingen-1"
    )
    assert (
        numbered_event_slug(
            "Klimawerkstatt Gröpelingen",
            {
                "klimawerkstatt-gropelingen-1",
                "klimawerkstatt-gropelingen-2",
                "anderer-workshop-9",
            },
        )
        == "klimawerkstatt-gropelingen-3"
    )
    assert numbered_event_slug("***", set()) == "workshop-1"


def test_creator_clones_hidden_event_and_configures_capacity_and_child_item():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "GET" and path.endswith("/blanko/"):
            return httpx.Response(
                200,
                json={"slug": "blanko", "live": False, "is_public": False},
            )
        if request.method == "GET" and path.endswith("/blanko/items/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "internal_name": "werkblatt_standard", "active": True},
                        {"id": 2, "internal_name": "werkblatt_child", "active": True},
                    ],
                    "next": None,
                },
            )
        if request.method == "GET" and path.endswith("/blanko/quotas/"):
            return httpx.Response(
                200,
                json={"results": [{"id": 3, "items": [1, 2]}], "next": None},
            )
        if request.method == "POST" and path.endswith("/events/"):
            body = request.read().decode()
            assert '"live":false' in body
            assert '"is_public":false' in body
            assert request.url.params["clone_from"] == "blanko"
            return httpx.Response(201, json={"slug": "klimawerkstatt-1"})
        if request.method == "GET" and path.endswith("/items/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 10, "internal_name": "werkblatt_standard", "active": True},
                        {"id": 11, "internal_name": "werkblatt_child", "active": True},
                    ],
                    "next": None,
                },
            )
        if request.method == "GET" and path.endswith("/quotas/"):
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 20, "name": "Kapazität", "items": [10, 11]}],
                    "next": None,
                },
            )
        if request.method == "PATCH" and path.endswith("/items/11/"):
            assert request.read() == b'{"active":false}'
            return httpx.Response(200, json={"id": 11, "active": False})
        if request.method == "PATCH" and path.endswith("/quotas/20/"):
            assert request.read() == b'{"size":24}'
            return httpx.Response(200, json={"id": 20, "size": 24})
        if request.method == "GET" and path.endswith("/klimawerkstatt-1/"):
            return httpx.Response(
                200,
                json={
                    "slug": "klimawerkstatt-1",
                    "public_url": "https://pretix.example/WORK/klimawerkstatt-1/",
                    "live": False,
                    "is_public": False,
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    starts_at = timezone.make_aware(datetime(2026, 10, 10, 10, 0))
    ends_at = timezone.make_aware(datetime(2026, 10, 10, 13, 0))
    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(handler),
        )
        created = PretixEventCreator(client, "WORK").create_from_template(
            draft=PretixEventDraft(
                slug="klimawerkstatt-1",
                title="Klimawerkstatt",
                starts_at=starts_at,
                ends_at=ends_at,
                location="Werkstatt",
                capacity=24,
                child_registration_enabled=False,
            ),
            preset=PretixCreationPreset(
                template_event_slug="blanko",
                primary_item_internal_name="werkblatt_standard",
                child_item_internal_name="werkblatt_child",
            ),
        )

    assert created.slug == "klimawerkstatt-1"
    assert created.live is False
    assert created.is_public is False
    assert [request.method for request in requests] == [
        "GET",
        "GET",
        "GET",
        "POST",
        "GET",
        "GET",
        "PATCH",
        "PATCH",
        "GET",
    ]


def test_creator_stops_when_template_item_mapping_is_not_stable():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/blanko/"):
            return httpx.Response(
                200,
                json={"slug": "blanko", "live": False, "is_public": False},
            )
        if request.url.path.endswith("/items/"):
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 10, "internal_name": None}],
                    "next": None,
                },
            )
        raise AssertionError("No further request may happen with an invalid template mapping")

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(PretixUnavailable, match="mapping"):
            PretixEventCreator(client, "WORK").create_from_template(
                draft=PretixEventDraft(
                    slug="workshop-1",
                    title="Workshop",
                    starts_at=timezone.make_aware(datetime(2026, 10, 10, 10, 0)),
                    ends_at=None,
                    location="",
                    capacity=10,
                    child_registration_enabled=True,
                ),
                preset=PretixCreationPreset(
                    template_event_slug="blanko",
                    primary_item_internal_name="werkblatt_standard",
                    child_item_internal_name="werkblatt_child",
                ),
            )
    assert [request.method for request in requests] == ["GET", "GET"]


def test_template_inspection_rejects_visible_template_before_product_requests():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"slug": "blanko", "live": False, "is_public": True},
        )

    with patch("socket.getaddrinfo", return_value=PUBLIC_DNS):
        client = PretixClient(
            "https://pretix.example",
            "synthetic-token",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(PretixUnavailable, match="hidden"):
            PretixEventCreator(client, "WORK").inspect_template(
                PretixCreationPreset(
                    template_event_slug="blanko",
                    primary_item_internal_name="werkblatt_standard",
                    child_item_internal_name="werkblatt_child",
                )
            )
    assert len(requests) == 1
