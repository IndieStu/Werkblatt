from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import (
    PretixEventCreation,
    PretixEventCreationPreset,
    PretixFundingText,
)
from werkblatt.workshops.services import (
    claim_pretix_event_creation,
    complete_pretix_event_creation,
    fail_pretix_event_creation,
    reserve_pretix_event_creation,
)


@pytest.fixture
def creation_setup():
    organization = Organization.objects.create(slug="example", name="Example")
    other = Organization.objects.create(slug="other", name="Other")
    user = get_user_model().objects.create_user(username="workshop-user")
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.WORKSHOP_USER,
    )
    preset = PretixEventCreationPreset.objects.create(
        organization=organization,
        display_name="Standardworkshop",
        template_event_slug="blanko",
        primary_item_internal_name="werkblatt_standard",
        child_item_internal_name="werkblatt_child",
        created_by=user,
        updated_by=user,
    )
    funding_text = PretixFundingText.objects.create(
        organization=organization,
        display_name="Klimaschutz im Alltag",
        text="Gefördert durch ein synthetisches Förderprogramm.",
        created_by=user,
        updated_by=user,
    )
    return organization, other, user, preset, funding_text


@pytest.mark.django_db
def test_reservation_numbers_slug_and_freezes_preset_and_funding_text(creation_setup):
    organization, _, user, preset, funding_text = creation_setup
    starts_at = timezone.make_aware(datetime(2026, 10, 10, 10, 0))
    creation = reserve_pretix_event_creation(
        organization=organization,
        user=user,
        preset=preset,
        funding_text=funding_text,
        title="Klimawerkstatt Gröpelingen",
        description="Eine synthetische Beschreibung.",
        starts_at=starts_at,
        ends_at=None,
        location="Werkstatt",
        capacity=18,
        child_registration_enabled=True,
        existing_external_slugs={"klimawerkstatt-gropelingen-3"},
    )

    assert creation.external_slug == "klimawerkstatt-gropelingen-4"
    assert creation.status == PretixEventCreation.Status.DRAFT
    assert creation.funding_text_snapshot == funding_text.text
    assert creation.preset_snapshot == {
        "display_name": "Standardworkshop",
        "template_event_slug": "blanko",
        "primary_item_internal_name": "werkblatt_standard",
        "child_item_internal_name": "werkblatt_child",
    }

    funding_text.text = "Später geänderter Fördertext"
    funding_text.save(update_fields=["text", "updated_at"])
    preset.template_event_slug = "neue-vorlage"
    preset.save(update_fields=["template_event_slug", "updated_at"])
    creation.refresh_from_db()
    assert creation.funding_text_snapshot == "Gefördert durch ein synthetisches Förderprogramm."
    assert creation.preset_snapshot["template_event_slug"] == "blanko"

    second = reserve_pretix_event_creation(
        organization=organization,
        user=user,
        preset=preset,
        funding_text=None,
        title="Klimawerkstatt Gröpelingen",
        description="",
        starts_at=starts_at,
        ends_at=None,
        location="",
        capacity=10,
        child_registration_enabled=False,
    )
    assert second.external_slug == "klimawerkstatt-gropelingen-5"


@pytest.mark.django_db
def test_reservation_rejects_cross_tenant_preset_and_funding_text(creation_setup):
    organization, other, user, preset, funding_text = creation_setup
    foreign_preset = PretixEventCreationPreset.objects.create(
        organization=other,
        display_name="Fremde Vorlage",
        template_event_slug="foreign-template",
        primary_item_internal_name="foreign_standard",
        child_item_internal_name="foreign_child",
        created_by=user,
        updated_by=user,
    )
    starts_at = timezone.make_aware(datetime(2026, 10, 10, 10, 0))
    common = {
        "organization": organization,
        "user": user,
        "title": "Workshop",
        "description": "",
        "starts_at": starts_at,
        "ends_at": None,
        "location": "",
        "capacity": 10,
        "child_registration_enabled": False,
    }
    with pytest.raises(PermissionDenied):
        reserve_pretix_event_creation(
            **common,
            preset=foreign_preset,
            funding_text=None,
        )

    foreign_funding_text = PretixFundingText.objects.create(
        organization=other,
        display_name="Fremder Text",
        text="Fremd",
        created_by=user,
        updated_by=user,
    )
    with pytest.raises(PermissionDenied):
        reserve_pretix_event_creation(
            **common,
            preset=preset,
            funding_text=foreign_funding_text,
        )
    assert not PretixEventCreation.objects.exists()
    assert funding_text.organization == organization


@pytest.mark.django_db
def test_creation_status_transitions_are_retryable_and_tenant_scoped(creation_setup):
    organization, other, user, preset, funding_text = creation_setup
    creation = reserve_pretix_event_creation(
        organization=organization,
        user=user,
        preset=preset,
        funding_text=funding_text,
        title="Workshop",
        description="",
        starts_at=timezone.make_aware(datetime(2026, 10, 10, 10, 0)),
        ends_at=None,
        location="",
        capacity=10,
        child_registration_enabled=False,
    )

    claimed = claim_pretix_event_creation(
        creation_id=creation.id,
        organization=organization,
        user=user,
    )
    assert claimed.status == PretixEventCreation.Status.CREATING
    assert claimed.attempt_count == 1
    assert claimed.attempt_started_at is not None
    with pytest.raises(ValueError, match="Status"):
        claim_pretix_event_creation(
            creation_id=creation.id,
            organization=organization,
            user=user,
        )
    with pytest.raises(PermissionDenied):
        fail_pretix_event_creation(
            creation_id=creation.id,
            organization=other,
            failure_code=PretixEventCreation.FailureCode.PRETIX_UNAVAILABLE,
        )

    with pytest.raises(ValueError, match="Fehlercode"):
        fail_pretix_event_creation(
            creation_id=creation.id,
            organization=organization,
            failure_code="raw-error-must-not-be-stored",
        )

    failed = fail_pretix_event_creation(
        creation_id=creation.id,
        organization=organization,
        failure_code=PretixEventCreation.FailureCode.PRETIX_UNAVAILABLE,
    )
    assert failed.status == PretixEventCreation.Status.FAILED
    assert failed.failure_code == "pretix_unavailable"

    retried = claim_pretix_event_creation(
        creation_id=creation.id,
        organization=organization,
        user=user,
    )
    assert retried.attempt_count == 2
    completed = complete_pretix_event_creation(
        creation_id=creation.id,
        organization=organization,
        external_url="https://pretix.example/WORK/workshop-1/",
    )
    assert completed.status == PretixEventCreation.Status.CREATED
    assert completed.completed_at is not None
    assert completed.failure_code == ""

    with pytest.raises(ValueError, match="Status"):
        claim_pretix_event_creation(
            creation_id=creation.id,
            organization=organization,
            user=user,
        )


@pytest.mark.django_db
def test_user_without_membership_cannot_reserve_creation(creation_setup):
    organization, _, _, preset, funding_text = creation_setup
    outsider = get_user_model().objects.create_user(username="outsider")
    with pytest.raises(PermissionDenied):
        reserve_pretix_event_creation(
            organization=organization,
            user=outsider,
            preset=preset,
            funding_text=funding_text,
            title="Workshop",
            description="",
            starts_at=timezone.make_aware(datetime(2026, 10, 10, 10, 0)),
            ends_at=None,
            location="",
            capacity=10,
            child_registration_enabled=False,
        )
