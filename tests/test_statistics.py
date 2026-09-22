from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from werkblatt.documentation.models import Documentation, DocumentationRevision
from werkblatt.documentation.statistics import StatisticsPeriod, organization_statistics
from werkblatt.documentation.views import _csv_cell
from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import Workshop


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 10, 0))


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1:A2)", "-2+3", "@command", "\tformula"])
def test_csv_cells_neutralize_spreadsheet_formulas(value):
    assert _csv_cell(value) == f"'{value}"


def snapshot(*, registered, present_registered, walk_ins, project="Klimaprojekt", custom=4):
    return {
        "schema_version": 2,
        "statistics": {
            "registered": registered,
            "present_registered": present_registered,
            "walk_ins": walk_ins,
            "present_total": present_registered + walk_ins,
            "no_shows": registered - present_registered,
        },
        "template": {
            "id": "template-1",
            "name": "Fördernachweis",
            "project_title": project,
            "custom_fields": [
                {
                    "label": "Weiblich",
                    "field_type": "integer",
                    "presentation": "aggregate_statistic",
                    "value": custom,
                },
                {
                    "label": "Interne Notiz",
                    "field_type": "integer",
                    "presentation": "regular",
                    "value": 999,
                },
            ],
        },
    }


def add_revision(documentation, user, number, data):
    return DocumentationRevision.objects.create(
        organization=documentation.organization,
        documentation=documentation,
        number=number,
        snapshot=data,
        snapshot_sha256=str(number) * 64,
        created_by=user,
    )


@pytest.fixture
def statistics_setup(db, settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "statistics"
    organization = Organization.objects.create(slug="statistics", name="Statistik Organisation")
    other = Organization.objects.create(slug="statistics-other", name="Andere Organisation")
    user = get_user_model().objects.create_user(username="statistics-user")
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.WORKSHOP_USER,
    )
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Workshop mit Korrektur",
        starts_at=aware(2026, 5, 10),
    )
    documentation = Documentation.objects.create(
        organization=organization,
        workshop=workshop,
        status=Documentation.Status.DRAFT,
        created_by=user,
        updated_by=user,
    )
    add_revision(documentation, user, 1, snapshot(registered=10, present_registered=7, walk_ins=1))
    add_revision(
        documentation,
        user,
        2,
        snapshot(registered=12, present_registered=9, walk_ins=2, custom=5),
    )
    Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Noch nicht abgeschlossen",
        starts_at=aware(2026, 6, 10),
    )
    foreign_workshop = Workshop.objects.create(
        organization=other,
        source_type=Workshop.SourceType.NATIVE,
        title="Fremder Workshop",
        starts_at=aware(2026, 5, 12),
    )
    foreign_documentation = Documentation.objects.create(
        organization=other,
        workshop=foreign_workshop,
        status=Documentation.Status.FINALIZED,
        created_by=user,
        updated_by=user,
    )
    add_revision(
        foreign_documentation,
        user,
        1,
        snapshot(registered=500, present_registered=500, walk_ins=0, custom=500),
    )
    return organization, user


@pytest.mark.django_db
def test_statistics_use_only_latest_revision_and_report_open_correction(statistics_setup):
    organization, _ = statistics_setup

    result = organization_statistics(
        organization_id=organization.id,
        period=StatisticsPeriod(aware(2026, 1, 1).date(), aware(2026, 12, 31).date()),
    )

    assert result["workshops"] == 2
    assert result["finalized_workshops"] == 1
    assert result["without_finalization"] == 1
    assert result["correction_pending"] == 1
    assert result["registered"] == 12
    assert result["present_registered"] == 9
    assert result["walk_ins"] == 2
    assert result["present_total"] == 11
    assert result["no_shows"] == 3
    assert result["attendance_rate"] == "75"
    assert result["custom_statistics"] == [{"label": "Weiblich", "value": "5"}]
    assert result["groups"][0]["workshops"] == 1


@pytest.mark.django_db
def test_statistics_dashboard_and_csv_are_tenant_bound_and_name_free(statistics_setup):
    _, user = statistics_setup
    client = Client()
    client.force_login(user)
    query = "?date_from=2026-01-01&date_to=2026-12-31"

    response = client.get(reverse("statistics-dashboard") + query)
    csv_response = client.get(reverse("statistics-csv") + query)

    assert response.status_code == 200
    assert response.context["statistics"]["registered"] == 12
    assert "Andere Organisation" not in response.content.decode()
    assert csv_response.status_code == 200
    assert csv_response["Content-Type"].startswith("text/csv")
    exported = csv_response.content.decode("utf-8-sig")
    assert "Klimaprojekt · Fördernachweis" in exported
    assert "Workshop mit Korrektur" not in exported
    assert "statistics-user" not in exported
    assert "500" not in exported


@pytest.mark.django_db
def test_statistics_reject_invalid_period(statistics_setup):
    _, user = statistics_setup
    client = Client()
    client.force_login(user)
    query = "?date_from=2026-12-31&date_to=2026-01-01"

    assert client.get(reverse("statistics-dashboard") + query).status_code == 200
    assert client.get(reverse("statistics-csv") + query).status_code == 400


@pytest.mark.django_db
def test_not_required_workshops_are_not_reported_as_missing_finalization(statistics_setup):
    organization, _ = statistics_setup
    workshop = Workshop.objects.get(organization=organization, title="Noch nicht abgeschlossen")
    workshop.documentation_requirement = Workshop.DocumentationRequirement.NOT_REQUIRED
    workshop.save(update_fields=["documentation_requirement"])

    result = organization_statistics(
        organization_id=organization.id,
        period=StatisticsPeriod(aware(2026, 1, 1).date(), aware(2026, 12, 31).date()),
    )

    assert result["without_finalization"] == 0
    assert result["not_required_workshops"] == 1
