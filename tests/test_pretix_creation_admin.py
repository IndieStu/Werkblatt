from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from werkblatt.identities.models import Membership
from werkblatt.integrations.pretix.creation import PretixTemplateInspection
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import PretixEventCreationPreset, PretixFundingText


@pytest.fixture
def admin_setup(settings):
    organization = Organization.objects.create(slug="example", name="Example")
    other = Organization.objects.create(slug="other", name="Other")
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    users = {}
    for role in Membership.Role:
        user = get_user_model().objects.create_user(username=role.value)
        Membership.objects.create(organization=organization, user=user, role=role)
        users[role] = user
    return organization, other, users


@pytest.mark.django_db
def test_pretix_creation_settings_are_admin_only(admin_setup):
    _, _, users = admin_setup
    client = Client()
    for role in (Membership.Role.WORKSHOP_USER, Membership.Role.EDITOR):
        client.force_login(users[role])
        assert client.get(reverse("pretix-creation-settings")).status_code == 403
    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    response = client.get(reverse("pretix-creation-settings"))
    assert response.status_code == 200
    assert 'href="https://pretix.eu/control"' in response.content.decode()
    assert "Verpflichtende Fragen" in response.content.decode()


@pytest.mark.django_db
def test_admin_can_create_tenant_scoped_preset_and_funding_text(admin_setup):
    organization, _, users = admin_setup
    client = Client()
    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    response = client.post(
        reverse("pretix-creation-preset-create"),
        {
            "display_name": "Standardworkshop",
            "template_event_slug": "blanko",
            "primary_item_internal_name": "werkblatt_standard",
            "child_item_internal_name": "werkblatt_child",
            "active": "on",
        },
    )
    assert response.status_code == 302
    preset = PretixEventCreationPreset.objects.get()
    assert preset.organization == organization
    assert preset.created_by == users[Membership.Role.ORGANIZATION_ADMIN]

    response = client.post(
        reverse("pretix-funding-text-create"),
        {
            "display_name": "Klimaschutz im Alltag",
            "text": "Gefördert durch ein synthetisches Förderprogramm.",
            "active": "on",
        },
    )
    assert response.status_code == 302
    funding_text = PretixFundingText.objects.get()
    assert funding_text.organization == organization
    assert funding_text.created_by == users[Membership.Role.ORGANIZATION_ADMIN]


@pytest.mark.django_db
def test_admin_cannot_access_foreign_preset_or_funding_text(admin_setup):
    _, other, users = admin_setup
    admin = users[Membership.Role.ORGANIZATION_ADMIN]
    foreign_preset = PretixEventCreationPreset.objects.create(
        organization=other,
        display_name="Fremd",
        template_event_slug="foreign",
        primary_item_internal_name="standard",
        child_item_internal_name="child",
        created_by=admin,
        updated_by=admin,
    )
    foreign_text = PretixFundingText.objects.create(
        organization=other,
        display_name="Fremd",
        text="Fremder Text",
        created_by=admin,
        updated_by=admin,
    )
    client = Client()
    client.force_login(admin)
    assert (
        client.get(reverse("pretix-creation-preset-edit", args=[foreign_preset.id])).status_code
        == 404
    )
    assert (
        client.post(reverse("pretix-creation-preset-check", args=[foreign_preset.id])).status_code
        == 404
    )
    assert (
        client.get(reverse("pretix-funding-text-edit", args=[foreign_text.id])).status_code == 404
    )


@pytest.mark.django_db
def test_template_check_is_read_only_and_reports_sanitized_result(admin_setup, settings):
    organization, _, users = admin_setup
    admin = users[Membership.Role.ORGANIZATION_ADMIN]
    preset = PretixEventCreationPreset.objects.create(
        organization=organization,
        display_name="Standard",
        template_event_slug="blanko",
        primary_item_internal_name="werkblatt_standard",
        child_item_internal_name="werkblatt_child",
        created_by=admin,
        updated_by=admin,
    )
    settings.PRETIX_API_TOKEN = "synthetic-token"
    settings.PRETIX_ORGANIZER = "WORK"
    client = Client()
    client.force_login(admin)
    with (
        patch("werkblatt.workshops.views.PretixClient.__init__", return_value=None),
        patch("werkblatt.workshops.views.PretixClient.close"),
        patch(
            "werkblatt.workshops.views.PretixEventCreator.inspect_template",
            return_value=PretixTemplateInspection(
                event_slug="blanko",
                primary_item_internal_name="werkblatt_standard",
                child_item_internal_name="werkblatt_child",
                capacity=10,
            ),
        ) as inspect,
    ):
        response = client.post(
            reverse("pretix-creation-preset-check", args=[preset.id]), follow=True
        )

    assert response.status_code == 200
    assert "Vorlage bestätigt" in response.content.decode()
    inspect.assert_called_once()
    assert PretixEventCreationPreset.objects.count() == 1


@pytest.mark.django_db
def test_preset_form_rejects_visible_names_as_ambiguous_identifiers(admin_setup):
    _, _, users = admin_setup
    client = Client()
    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    response = client.post(
        reverse("pretix-creation-preset-create"),
        {
            "display_name": "Ungültig",
            "template_event_slug": "blanko",
            "primary_item_internal_name": "Normales Ticket",
            "child_item_internal_name": "Anmeldung für Kinder",
            "active": "on",
        },
    )
    assert response.status_code == 200
    assert "Nur ASCII-Buchstaben" in response.content.decode()
    assert not PretixEventCreationPreset.objects.exists()
