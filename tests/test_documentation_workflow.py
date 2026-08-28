from copy import deepcopy

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from werkblatt.documentation.models import Documentation, ParticipantEntry
from werkblatt.documentation.services import (
    ConcurrentDocumentationUpdate,
    FacilitatorInput,
    ParticipantInput,
    finalize_documentation,
    get_or_create_documentation,
    reopen_documentation,
    save_draft,
    statistics_for,
)
from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import Workshop, WorkshopRegistration


@pytest.fixture
def documentation_setup(db):
    organization = Organization.objects.create(slug="example", name="Example Organization")
    user = get_user_model().objects.create_user(
        username="workshop-user",
        display_name="Alex Beispiel",
    )
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.WORKSHOP_USER,
    )
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="event:42",
        title="Fermentieren",
        starts_at=timezone.now(),
        location="Werkstatt",
    )
    registration_present = WorkshopRegistration.objects.create(
        organization=organization,
        workshop=workshop,
        external_reference="ORDER1:1",
        display_name="Anna Beispiel",
    )
    registration_absent = WorkshopRegistration.objects.create(
        organization=organization,
        workshop=workshop,
        external_reference="ORDER2:1",
        display_name="Max Muster",
    )
    documentation = get_or_create_documentation(workshop=workshop, user=user)
    return {
        "organization": organization,
        "user": user,
        "workshop": workshop,
        "documentation": documentation,
        "registration_present": registration_present,
        "registration_absent": registration_absent,
    }


def _participant_rows(documentation, absent_registration_id=None, walk_in_name="Lisa Spontan"):
    rows = []
    for entry in documentation.participants.all():
        rows.append(
            ParticipantInput(
                entry_id=entry.id,
                display_name=entry.display_name,
                present=entry.registration_id != absent_registration_id,
            )
        )
    if walk_in_name:
        rows.append(
            ParticipantInput(
                entry_id=None,
                display_name=walk_in_name,
                present=True,
            )
        )
    return rows


@pytest.mark.django_db
def test_new_documentation_imports_registrations_and_proposes_current_user(documentation_setup):
    documentation = documentation_setup["documentation"]
    assert documentation.participants.count() == 2
    assert set(documentation.participants.values_list("origin", flat=True)) == {
        ParticipantEntry.Origin.REGISTERED
    }
    assert documentation.facilitators.get().display_name == "Alex Beispiel"


@pytest.mark.django_db
def test_statistics_are_mathematically_consistent(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    absent_entry = documentation.participants.get(registration=data["registration_absent"])
    absent_entry.present = False
    absent_entry.save(update_fields=["present"])
    ParticipantEntry.objects.create(
        organization=data["organization"],
        documentation=documentation,
        display_name="Lisa Spontan",
        origin=ParticipantEntry.Origin.WALK_IN,
        present=True,
    )
    assert statistics_for(documentation) == {
        "registered": 2,
        "present_registered": 1,
        "walk_ins": 1,
        "present_total": 2,
        "no_shows": 1,
    }


@pytest.mark.django_db
def test_workshop_user_can_reopen_and_create_second_immutable_revision(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    save_draft(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
        conducted_as_planned=True,
        report="Erster Bericht",
        participants=_participant_rows(
            documentation,
            absent_registration_id=data["registration_absent"].id,
        ),
        facilitators=[
            FacilitatorInput(
                facilitator_id=documentation.facilitators.get().id,
                display_name="Alex Beispiel",
            )
        ],
    )
    documentation.refresh_from_db()
    first = finalize_documentation(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
    )
    assert first.number == 1
    assert first.snapshot["documentation"]["report"] == "Erster Bericht"
    assert first.snapshot["statistics"]["present_total"] == 2
    first_snapshot = deepcopy(first.snapshot)
    first_hash = first.snapshot_sha256

    documentation.refresh_from_db()
    reopen_documentation(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
    )
    documentation.refresh_from_db()
    save_draft(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
        conducted_as_planned=False,
        report="Korrigierter Bericht",
        participants=_participant_rows(documentation, walk_in_name=""),
        facilitators=[
            FacilitatorInput(
                facilitator_id=documentation.facilitators.get().id,
                display_name="Alex Beispiel",
            )
        ],
    )
    documentation.refresh_from_db()
    second = finalize_documentation(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
    )

    first.refresh_from_db()
    assert second.number == 2
    assert second.snapshot["documentation"]["report"] == "Korrigierter Bericht"
    assert first.snapshot == first_snapshot
    assert first.snapshot_sha256 == first_hash
    assert second.snapshot_sha256 != first_hash
    assert documentation.revisions.count() == 2
    with pytest.raises(ValueError):
        first.save()


@pytest.mark.django_db
def test_cross_tenant_reopen_is_denied(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    other = Organization.objects.create(slug="other", name="Andere Organisation")
    documentation.status = Documentation.Status.FINALIZED
    documentation.save(update_fields=["status"])
    with pytest.raises(PermissionDenied):
        reopen_documentation(
            documentation_id=documentation.id,
            organization_id=other.id,
            user=data["user"],
            expected_version=documentation.version,
        )


@pytest.mark.django_db
def test_stale_version_cannot_overwrite_newer_draft(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    stale_version = documentation.version
    save_draft(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=stale_version,
        conducted_as_planned=True,
        report="Aktueller Stand",
        participants=_participant_rows(documentation, walk_in_name=""),
        facilitators=[
            FacilitatorInput(
                facilitator_id=documentation.facilitators.get().id,
                display_name="Alex Beispiel",
            )
        ],
    )
    with pytest.raises(ConcurrentDocumentationUpdate):
        save_draft(
            documentation_id=documentation.id,
            organization_id=data["organization"].id,
            user=data["user"],
            expected_version=stale_version,
            conducted_as_planned=True,
            report="Veraltet",
            participants=[],
            facilitators=[],
        )
    documentation.refresh_from_db()
    assert documentation.report == "Aktueller Stand"


@pytest.mark.django_db
def test_finalize_twice_without_reopen_is_rejected(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    first = finalize_documentation(
        documentation_id=documentation.id,
        organization_id=data["organization"].id,
        user=data["user"],
        expected_version=documentation.version,
    )
    documentation.refresh_from_db()

    with pytest.raises(ValidationError, match="bereits abgeschlossen"):
        finalize_documentation(
            documentation_id=documentation.id,
            organization_id=data["organization"].id,
            user=data["user"],
            expected_version=documentation.version,
        )

    assert documentation.revisions.count() == 1
    assert documentation.revisions.get().id == first.id


@pytest.mark.django_db
def test_reopen_draft_is_rejected(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]

    with pytest.raises(ValidationError, match="Nur abgeschlossene"):
        reopen_documentation(
            documentation_id=documentation.id,
            organization_id=data["organization"].id,
            user=data["user"],
            expected_version=documentation.version,
        )

    documentation.refresh_from_db()
    assert documentation.status == Documentation.Status.DRAFT
    assert documentation.revisions.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["save", "finalize"])
def test_cross_tenant_save_and_finalize_are_denied(documentation_setup, operation):
    data = documentation_setup
    documentation = data["documentation"]
    other = Organization.objects.create(slug=f"other-{operation}", name="Andere Organisation")
    common = {
        "documentation_id": documentation.id,
        "organization_id": other.id,
        "user": data["user"],
        "expected_version": documentation.version,
    }

    with pytest.raises(PermissionDenied):
        if operation == "save":
            save_draft(
                **common,
                conducted_as_planned=True,
                report="Mandantenfremd",
                participants=[],
                facilitators=[],
            )
        else:
            finalize_documentation(**common)

    documentation.refresh_from_db()
    assert documentation.status == Documentation.Status.DRAFT
    assert documentation.report == ""
    assert documentation.revisions.count() == 0


@pytest.mark.django_db
def test_registered_participant_cannot_be_deleted(documentation_setup):
    data = documentation_setup
    documentation = data["documentation"]
    registered = documentation.participants.first()
    with pytest.raises(ValidationError):
        save_draft(
            documentation_id=documentation.id,
            organization_id=data["organization"].id,
            user=data["user"],
            expected_version=documentation.version,
            conducted_as_planned=True,
            report="",
            participants=[
                ParticipantInput(
                    entry_id=registered.id,
                    display_name=registered.display_name,
                    present=True,
                    delete=True,
                )
            ],
            facilitators=[],
        )


@pytest.mark.django_db
def test_workshop_user_can_reopen_finalized_documentation_via_view(documentation_setup, settings):
    data = documentation_setup
    settings.DEFAULT_ORGANIZATION_SLUG = data["organization"].slug
    documentation = data["documentation"]
    documentation.status = Documentation.Status.FINALIZED
    documentation.save(update_fields=["status"])

    client = Client()
    client.force_login(data["user"])
    response = client.post(
        reverse("documentation-detail", args=[data["workshop"].id]),
        {"action": "reopen", "expected_version": documentation.version},
    )

    assert response.status_code == 302
    documentation.refresh_from_db()
    assert documentation.status == Documentation.Status.DRAFT


@pytest.mark.django_db
def test_foreign_workshop_documentation_returns_404(documentation_setup, settings):
    data = documentation_setup
    other = Organization.objects.create(slug="other-view", name="Andere Organisation")
    foreign_workshop = Workshop.objects.create(
        organization=other,
        source_type=Workshop.SourceType.NATIVE,
        title="Fremder Workshop",
        starts_at=timezone.now(),
    )
    settings.DEFAULT_ORGANIZATION_SLUG = data["organization"].slug
    client = Client()
    client.force_login(data["user"])

    response = client.get(reverse("documentation-detail", args=[foreign_workshop.id]))

    assert response.status_code == 404
    assert not Documentation.objects.filter(workshop=foreign_workshop).exists()
