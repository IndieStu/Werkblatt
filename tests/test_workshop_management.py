from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from werkblatt.documentation.models import Documentation
from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import PretixEventRule, Workshop


@pytest.fixture
def workshop_management(db, settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "tenant"
    organization = Organization.objects.create(slug="tenant", name="Tenant")
    other = Organization.objects.create(slug="other", name="Other")
    users = {}
    for role in Membership.Role:
        user = get_user_model().objects.create_user(username=f"user-{role}")
        Membership.objects.create(organization=organization, user=user, role=role)
        users[role] = user
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="series:1",
        parent_external_reference="series",
        title="Filterbarer Workshop",
        starts_at=timezone.now(),
    )
    foreign = Workshop.objects.create(
        organization=other,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="foreign:1",
        title="Fremder Workshop",
        starts_at=timezone.now(),
    )
    return organization, users, workshop, foreign


@pytest.mark.django_db
def test_visibility_is_reversible_for_editor_but_not_workshop_user(workshop_management):
    organization, users, workshop, _ = workshop_management
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    assert (
        client.post(
            reverse("workshop-visibility", args=[workshop.id]), {"visibility": "hidden"}
        ).status_code
        == 403
    )

    client.force_login(users[Membership.Role.EDITOR])
    response = client.post(
        reverse("workshop-visibility", args=[workshop.id]), {"visibility": "hidden"}
    )
    assert response.status_code == 302
    workshop.refresh_from_db()
    assert workshop.visibility == Workshop.Visibility.HIDDEN
    assert workshop.visibility_changed_by == users[Membership.Role.EDITOR]
    assert "Filterbarer Workshop" not in client.get(reverse("workshop-list")).content.decode()
    assert (
        "Filterbarer Workshop"
        in client.get(reverse("workshop-list") + "?visibility=hidden").content.decode()
    )

    client.post(reverse("workshop-visibility", args=[workshop.id]), {"visibility": "active"})
    workshop.refresh_from_db()
    assert workshop.visibility == Workshop.Visibility.ACTIVE
    assert workshop.organization == organization


@pytest.mark.django_db
def test_only_admin_can_waive_requirement_with_reason_and_direct_open_is_blocked(
    workshop_management,
):
    _, users, workshop, _ = workshop_management
    client = Client()
    client.force_login(users[Membership.Role.EDITOR])
    assert client.get(reverse("workshop-requirement", args=[workshop.id])).status_code == 403

    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    url = reverse("workshop-requirement", args=[workshop.id])
    response = client.post(
        url,
        {"documentation_requirement": Workshop.DocumentationRequirement.NOT_REQUIRED, "reason": ""},
    )
    assert response.status_code == 200
    workshop.refresh_from_db()
    assert workshop.documentation_requirement == Workshop.DocumentationRequirement.REQUIRED

    response = client.post(
        url,
        {
            "documentation_requirement": Workshop.DocumentationRequirement.NOT_REQUIRED,
            "reason": "Offenes Angebot ohne Nachweispflicht",
        },
    )
    assert response.status_code == 302
    workshop.refresh_from_db()
    assert workshop.requirement_source == Workshop.RequirementSource.INDIVIDUAL
    assert workshop.requirement_decided_by == users[Membership.Role.ORGANIZATION_ADMIN]
    assert client.get(reverse("documentation-detail", args=[workshop.id])).status_code == 403
    assert not Documentation.objects.filter(workshop=workshop).exists()


@pytest.mark.django_db
def test_management_actions_are_tenant_scoped(workshop_management):
    _, users, _, foreign = workshop_management
    client = Client()
    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    assert (
        client.post(
            reverse("workshop-visibility", args=[foreign.id]), {"visibility": "hidden"}
        ).status_code
        == 404
    )
    assert client.get(reverse("workshop-requirement", args=[foreign.id])).status_code == 404


@pytest.mark.django_db
def test_pretix_rules_are_admin_only_tenant_scoped_and_apply_to_existing_workshops(
    workshop_management,
):
    organization, users, workshop, _ = workshop_management
    client = Client()
    client.force_login(users[Membership.Role.EDITOR])
    assert client.get(reverse("pretix-rule-list")).status_code == 403

    client.force_login(users[Membership.Role.ORGANIZATION_ADMIN])
    response = client.post(
        reverse("pretix-rule-create"),
        {
            "event_slug": "series",
            "display_name": "Offene Reihe",
            "import_enabled": "on",
            "documentation_requirement": Workshop.DocumentationRequirement.NOT_REQUIRED,
            "reason": "Offene Werkstatt",
        },
    )
    assert response.status_code == 302
    rule = PretixEventRule.objects.get(organization=organization, event_slug="series")
    assert rule.decided_by == users[Membership.Role.ORGANIZATION_ADMIN]
    workshop.refresh_from_db()
    assert workshop.documentation_requirement == Workshop.DocumentationRequirement.NOT_REQUIRED
    assert workshop.requirement_source == Workshop.RequirementSource.EVENT_RULE


@pytest.mark.django_db
def test_workshop_list_filters_status_search_dates_and_paginates(workshop_management):
    organization, users, workshop, _ = workshop_management
    for number in range(26):
        Workshop.objects.create(
            organization=organization,
            source_type=Workshop.SourceType.NATIVE,
            title=f"Weiterer Termin {number:02d}",
            starts_at=timezone.now() + timedelta(days=number),
        )
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    response = client.get(reverse("workshop-list") + "?visibility=active&q=Filterbarer")
    assert workshop.title in response.content.decode()
    response = client.get(reverse("workshop-list") + "?visibility=active")
    assert response.context["page"].paginator.num_pages == 2

    workshop.visibility = Workshop.Visibility.HIDDEN
    workshop.save(update_fields=["visibility"])
    response = client.get(reverse("workshop-list") + "?visibility=invalid")
    assert workshop.title not in response.content.decode()
