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


@pytest.mark.django_db
def test_workshop_calendar_is_tenant_scoped_filterable_and_links_documentation(
    workshop_management,
):
    organization, users, workshop, foreign = workshop_management
    cancelled = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="cancelled:1",
        parent_external_reference="cancelled",
        title="Abgesagter Kalendereintrag",
        starts_at=workshop.starts_at + timedelta(hours=1),
        lifecycle_status=Workshop.LifecycleStatus.CANCELLED,
    )
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    month = timezone.localtime(workshop.starts_at).strftime("%Y-%m")

    response = client.get(reverse("workshop-calendar"), {"month": month})
    content = response.content.decode()
    assert response.status_code == 200
    assert workshop.title in content
    assert reverse("documentation-detail", args=[workshop.id]) in content
    assert cancelled.title in content
    assert reverse("documentation-detail", args=[cancelled.id]) not in content
    assert foreign.title not in content

    response = client.get(
        reverse("workshop-calendar"),
        {"month": month, "state": "cancelled", "visibility": "active"},
    )
    content = response.content.decode()
    assert cancelled.title in content
    assert workshop.title not in content


@pytest.mark.django_db
def test_workshop_calendar_rejects_invalid_month_without_error(workshop_management):
    _, users, _, _ = workshop_management
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    response = client.get(reverse("workshop-calendar"), {"month": "../../bad"})
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("role", list(Membership.Role))
def test_all_workshop_roles_can_create_tenant_bound_native_workshop(workshop_management, role):
    organization, users, _, other_workshop = workshop_management
    client = Client()
    client.force_login(users[role])
    list_response = client.get(reverse("workshop-list"))
    assert reverse("workshop-create") in list_response.content.decode()

    starts_at = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
        second=0, microsecond=0
    )
    ends_at = starts_at + timedelta(hours=3)
    response = client.post(
        reverse("workshop-create"),
        {
            "title": "Manueller Klimaworkshop",
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": ends_at.strftime("%Y-%m-%dT%H:%M"),
            "location": "Werkraum",
            "organization": str(other_workshop.organization_id),
            "source_type": Workshop.SourceType.PRETIX,
            "documentation_requirement": Workshop.DocumentationRequirement.NOT_REQUIRED,
        },
    )

    workshop = Workshop.objects.get(title="Manueller Klimaworkshop")
    assert response.status_code == 302
    assert response.url == reverse("documentation-detail", args=[workshop.id])
    assert workshop.organization == organization
    assert workshop.source_type == Workshop.SourceType.NATIVE
    assert workshop.external_reference == ""
    assert workshop.documentation_requirement == Workshop.DocumentationRequirement.REQUIRED
    assert workshop.location == "Werkraum"


@pytest.mark.django_db
def test_native_workshop_form_validates_dates_and_requires_membership(workshop_management):
    _, users, _, _ = workshop_management
    client = Client()
    outsider = get_user_model().objects.create_user(username="outsider")
    client.force_login(outsider)
    assert client.get(reverse("workshop-create")).status_code == 403

    client.force_login(users[Membership.Role.WORKSHOP_USER])
    starts_at = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
        second=0, microsecond=0
    )
    response = client.post(
        reverse("workshop-create"),
        {
            "title": "Ungültige Zeit",
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (starts_at - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": "",
        },
    )
    assert response.status_code == 200
    assert "Das Ende muss nach dem Beginn liegen." in response.content.decode()
    assert not Workshop.objects.filter(title="Ungültige Zeit").exists()


@pytest.mark.django_db
def test_native_workshop_edit_is_tenant_scoped_and_rejects_pretix(workshop_management):
    organization, users, pretix_workshop, _ = workshop_management
    native = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Manuell",
        starts_at=timezone.now() + timedelta(days=1),
    )
    other = Organization.objects.get(slug="other")
    foreign_native = Workshop.objects.create(
        organization=other,
        source_type=Workshop.SourceType.NATIVE,
        title="Fremd manuell",
        starts_at=timezone.now() + timedelta(days=1),
    )
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])

    assert client.get(reverse("workshop-edit", args=[pretix_workshop.id])).status_code == 404
    assert client.get(reverse("workshop-edit", args=[foreign_native.id])).status_code == 404

    starts_at = timezone.localtime(timezone.now() + timedelta(days=4)).replace(
        second=0, microsecond=0
    )
    response = client.post(
        reverse("workshop-edit", args=[native.id]),
        {
            "title": "Manuell korrigiert",
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": "",
            "location": "Neuer Ort",
            "source_type": Workshop.SourceType.PRETIX,
        },
    )
    assert response.status_code == 302
    native.refresh_from_db()
    assert native.title == "Manuell korrigiert"
    assert native.location == "Neuer Ort"
    assert native.source_type == Workshop.SourceType.NATIVE
    assert native.organization == organization
