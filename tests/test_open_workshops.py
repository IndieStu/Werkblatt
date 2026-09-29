from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import OpenWorkshopAttendance, OpenWorkshopSeries


@pytest.fixture
def open_workshop_setup(settings):
    organization = Organization.objects.create(slug="tenant-a", name="Tenant A")
    other = Organization.objects.create(slug="tenant-b", name="Tenant B")
    settings.DEFAULT_ORGANIZATION_SLUG = organization.slug
    users = {}
    for role in Membership.Role:
        user = get_user_model().objects.create_user(username=role.value)
        Membership.objects.create(organization=organization, user=user, role=role)
        users[role] = user
    foreign_series = OpenWorkshopSeries.objects.create(
        organization=other,
        name="Fremde Reihe",
        active=True,
    )
    return organization, other, users, foreign_series


@pytest.mark.django_db
def test_only_editor_and_admin_can_configure_series(open_workshop_setup):
    organization, _, users, _ = open_workshop_setup
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    assert client.get(reverse("open-workshop-series-list")).status_code == 403
    create_response = client.post(reverse("open-workshop-series-create"), {"name": "Nähwerk"})
    assert create_response.status_code == 403

    client.force_login(users[Membership.Role.EDITOR])
    response = client.post(
        reverse("open-workshop-series-create"),
        {
            "name": "Nähwerk",
            "location": "WERK",
            "schedule_description": "Dienstags, 15 bis 18 Uhr",
            "active": "on",
        },
    )
    assert response.status_code == 302
    assert OpenWorkshopSeries.objects.filter(
        organization=organization,
        name="Nähwerk",
    ).exists()


@pytest.mark.django_db
def test_workshop_user_records_consistent_aggregate_attendance(open_workshop_setup):
    organization, _, users, _ = open_workshop_setup
    series = OpenWorkshopSeries.objects.create(organization=organization, name="Nähwerk")
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    response = client.post(
        reverse("open-workshop-attendance-create"),
        {
            "series": str(series.id),
            "occurred_on": "2026-09-28",
            "total": "9",
            "female": "5",
            "male": "2",
            "diverse": "1",
            "unspecified": "1",
            "note": "Synthetischer Testeintrag",
        },
    )
    assert response.status_code == 302
    attendance = OpenWorkshopAttendance.objects.get()
    assert attendance.organization == organization
    assert attendance.recorded_by == users[Membership.Role.WORKSHOP_USER]
    assert attendance.total == 9


@pytest.mark.django_db
def test_attendance_rejects_inconsistent_breakdown_and_cross_tenant_series(
    open_workshop_setup,
):
    organization, _, users, foreign_series = open_workshop_setup
    series = OpenWorkshopSeries.objects.create(organization=organization, name="Nähwerk")
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    common = {
        "occurred_on": "2026-09-28",
        "total": "9",
        "female": "2",
        "male": "2",
        "diverse": "1",
        "unspecified": "1",
    }
    response = client.post(
        reverse("open-workshop-attendance-create"),
        {**common, "series": str(series.id)},
    )
    assert response.status_code == 200
    assert "müssen zusammen der Gesamtzahl entsprechen" in response.content.decode()

    response = client.post(
        reverse("open-workshop-attendance-create"),
        {**common, "series": str(foreign_series.id), "total": "6"},
    )
    assert response.status_code == 200
    assert not OpenWorkshopAttendance.objects.exists()


@pytest.mark.django_db
def test_dashboard_and_csv_are_tenant_bound_and_aggregate(open_workshop_setup):
    organization, other, users, foreign_series = open_workshop_setup
    series = OpenWorkshopSeries.objects.create(organization=organization, name="=Nähwerk")
    OpenWorkshopAttendance.objects.create(
        organization=organization,
        series=series,
        occurred_on=date(2026, 9, 28),
        total=8,
        female=4,
        male=2,
        diverse=1,
        unspecified=1,
        recorded_by=users[Membership.Role.WORKSHOP_USER],
    )
    foreign_user = get_user_model().objects.create_user(username="foreign")
    OpenWorkshopAttendance.objects.create(
        organization=other,
        series=foreign_series,
        occurred_on=date(2026, 9, 28),
        total=99,
        female=99,
        recorded_by=foreign_user,
    )
    client = Client()
    client.force_login(users[Membership.Role.WORKSHOP_USER])
    dashboard = client.get(reverse("open-workshop-dashboard"))
    exported = client.get(reverse("open-workshop-statistics-csv"))
    assert dashboard.status_code == 200
    assert dashboard.context["totals"]["total"] == 8
    assert b"99" not in exported.content
    assert "'=Nähwerk" in exported.content.decode("utf-8-sig")
    assert "Fremde Reihe" not in exported.content.decode("utf-8-sig")
