from datetime import datetime
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from werkblatt.identities.models import Membership
from werkblatt.integrations.pretix.creation import CreatedPretixEvent
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import (
    PretixEventCreation,
    PretixEventCreationPreset,
    PretixFundingText,
    Workshop,
)


@pytest.fixture
def wizard_setup(settings):
    organization = Organization.objects.create(slug="example", name="Example")
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "WORK"
    user = get_user_model().objects.create_user(username="workshop-user")
    other_user = get_user_model().objects.create_user(username="other-user")
    admin = get_user_model().objects.create_user(username="admin")
    for member, role in (
        (user, Membership.Role.WORKSHOP_USER),
        (other_user, Membership.Role.WORKSHOP_USER),
        (admin, Membership.Role.ORGANIZATION_ADMIN),
    ):
        Membership.objects.create(organization=organization, user=member, role=role)
    preset = PretixEventCreationPreset.objects.create(
        organization=organization,
        display_name="Standardworkshop",
        template_event_slug="blanko",
        primary_item_internal_name="werkblatt_standard",
        child_item_internal_name="werkblatt_child",
        created_by=admin,
        updated_by=admin,
    )
    funding_text = PretixFundingText.objects.create(
        organization=organization,
        display_name="Förderprogramm",
        text="Gefördert durch ein synthetisches Programm.",
        created_by=admin,
        updated_by=admin,
    )
    return organization, user, other_user, preset, funding_text


@pytest.mark.django_db
def test_workshop_user_can_review_create_publish_and_open_documentation(wizard_setup):
    organization, user, _, preset, funding_text = wizard_setup
    client = Client()
    client.force_login(user)
    form_page = client.get(reverse("pretix-workshop-create"))
    assert form_page.status_code == 200
    assert "Verpflichtende Fragen" in form_page.content.decode()
    assert 'href="https://pretix.eu/control"' in form_page.content.decode()

    with (
        patch("werkblatt.workshops.views.PretixClient.__init__", return_value=None),
        patch("werkblatt.workshops.views.PretixClient.close"),
        patch(
            "werkblatt.workshops.views.PretixEventCreator.list_event_slugs",
            return_value={"klimawerkstatt-1"},
        ),
    ):
        response = client.post(
            reverse("pretix-workshop-create"),
            {
                "preset": str(preset.id),
                "title": "Klimawerkstatt",
                "starts_at": "2026-10-10T10:00",
                "ends_at": "2026-10-10T13:00",
                "location": "Werkstatt",
                "description": "Eine einfache Beschreibung.",
                "funding_text": str(funding_text.id),
                "capacity": "24",
                "child_registration_enabled": "on",
            },
        )
    creation = PretixEventCreation.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("pretix-workshop-review", args=[creation.id])
    assert creation.external_slug == "klimawerkstatt-2"
    assert creation.created_by == user

    review = client.get(response.url)
    assert review.status_code == 200
    assert "In Pretix erstellen und veröffentlichen" in review.content.decode()
    assert "Gefördert durch ein synthetisches Programm" in review.content.decode()

    with (
        patch("werkblatt.workshops.views.PretixClient.__init__", return_value=None),
        patch("werkblatt.workshops.views.PretixClient.close"),
        patch(
            "werkblatt.workshops.views.PretixEventCreator.create_from_template",
            return_value=CreatedPretixEvent(
                slug="klimawerkstatt-2",
                public_url="https://pretix.example/WORK/klimawerkstatt-2/",
                live=False,
                is_public=False,
            ),
        ),
        patch(
            "werkblatt.workshops.views.PretixEventCreator.publish_event",
            return_value=CreatedPretixEvent(
                slug="klimawerkstatt-2",
                public_url="https://pretix.example/WORK/klimawerkstatt-2/",
                live=True,
                is_public=True,
            ),
        ),
    ):
        published = client.post(reverse("pretix-workshop-publish", args=[creation.id]))

    workshop = Workshop.objects.get(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="klimawerkstatt-2",
    )
    creation.refresh_from_db()
    assert published.status_code == 302
    assert published.url == reverse("documentation-detail", args=[workshop.id])
    assert creation.status == PretixEventCreation.Status.CREATED
    assert workshop.title == "Klimawerkstatt"
    assert workshop.starts_at == timezone.make_aware(datetime(2026, 10, 10, 10, 0))


@pytest.mark.django_db
def test_creation_review_and_publish_are_limited_to_creator(wizard_setup):
    organization, user, other_user, preset, _ = wizard_setup
    creation = PretixEventCreation.objects.create(
        organization=organization,
        preset=preset,
        title="Privater Entwurf",
        starts_at=timezone.now(),
        capacity=10,
        external_slug="privater-entwurf-1",
        preset_snapshot={
            "template_event_slug": "blanko",
            "primary_item_internal_name": "werkblatt_standard",
            "child_item_internal_name": "werkblatt_child",
        },
        created_by=user,
    )
    client = Client()
    client.force_login(other_user)
    assert client.get(reverse("pretix-workshop-review", args=[creation.id])).status_code == 404
    assert client.post(reverse("pretix-workshop-publish", args=[creation.id])).status_code == 404
