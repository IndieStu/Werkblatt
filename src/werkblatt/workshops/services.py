from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from werkblatt.identities.policies import Capability, require_capability
from werkblatt.integrations.pretix.creation import numbered_event_slug

from .models import (
    PretixEventCreation,
    PretixEventCreationPreset,
    PretixEventRule,
    PretixFundingText,
    Workshop,
)


@transaction.atomic
def save_native_workshop(*, form, organization, user, workshop=None):
    require_capability(
        user,
        organization.id,
        Capability.DOCUMENT_WORKSHOPS,
        "Keine Berechtigung zum Anlegen oder Bearbeiten von Workshops.",
    )
    values = {
        field: form.cleaned_data[field] for field in ("title", "starts_at", "ends_at", "location")
    }
    if workshop is None:
        return Workshop.objects.create(
            organization=organization,
            source_type=Workshop.SourceType.NATIVE,
            documentation_requirement=Workshop.DocumentationRequirement.REQUIRED,
            requirement_source=Workshop.RequirementSource.DEFAULT,
            **values,
        )
    try:
        locked = Workshop.objects.select_for_update().get(
            pk=workshop.pk,
            organization=organization,
            source_type=Workshop.SourceType.NATIVE,
        )
    except Workshop.DoesNotExist as exc:
        raise PermissionDenied from exc
    for field, value in values.items():
        setattr(locked, field, value)
    locked.save(update_fields=[*values, "updated_at"])
    return locked


@transaction.atomic
def set_workshop_visibility(*, workshop, organization, user, visibility):
    require_capability(
        user,
        organization.id,
        Capability.MANAGE_WORKSHOP_VISIBILITY,
        "Keine Berechtigung zum Ausblenden von Workshops.",
    )
    try:
        workshop = Workshop.objects.select_for_update().get(
            pk=workshop.pk, organization=organization
        )
    except Workshop.DoesNotExist as exc:
        raise PermissionDenied from exc
    if visibility not in Workshop.Visibility.values:
        raise ValueError("Ungültige Sichtbarkeit")
    workshop.visibility = visibility
    workshop.visibility_changed_by = user
    workshop.visibility_changed_at = timezone.now()
    workshop.save(
        update_fields=["visibility", "visibility_changed_by", "visibility_changed_at", "updated_at"]
    )
    return workshop


@transaction.atomic
def set_documentation_requirement(*, workshop, organization, user, requirement, reason):
    require_capability(
        user,
        organization.id,
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen die Dokumentationspflicht ändern.",
    )
    try:
        workshop = Workshop.objects.select_for_update().get(
            pk=workshop.pk, organization=organization
        )
    except Workshop.DoesNotExist as exc:
        raise PermissionDenied from exc
    reason = reason.strip()
    if requirement == Workshop.DocumentationRequirement.NOT_REQUIRED and not reason:
        raise ValueError("Eine Begründung ist erforderlich")
    workshop.documentation_requirement = requirement
    workshop.requirement_source = Workshop.RequirementSource.INDIVIDUAL
    workshop.requirement_reason = (
        reason if requirement == Workshop.DocumentationRequirement.NOT_REQUIRED else ""
    )
    workshop.requirement_decided_by = user
    workshop.requirement_decided_at = timezone.now()
    workshop.save(
        update_fields=[
            "documentation_requirement",
            "requirement_source",
            "requirement_reason",
            "requirement_decided_by",
            "requirement_decided_at",
            "updated_at",
        ]
    )
    return workshop


@transaction.atomic
def save_pretix_event_rule(*, form, organization, user):
    require_capability(
        user,
        organization.id,
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Regeln verwalten.",
    )
    rule = form.save(commit=False)
    if (
        not rule._state.adding
        and not PretixEventRule.objects.filter(pk=rule.pk, organization=organization).exists()
    ):
        raise PermissionDenied
    rule.organization = organization
    rule.decided_by = user
    rule.save()
    Workshop.objects.filter(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        parent_external_reference=rule.event_slug,
    ).exclude(requirement_source=Workshop.RequirementSource.INDIVIDUAL).update(
        documentation_requirement=rule.documentation_requirement,
        requirement_source=Workshop.RequirementSource.EVENT_RULE,
        requirement_reason=rule.reason,
        requirement_decided_by=user,
        requirement_decided_at=timezone.now(),
    )
    return rule


@transaction.atomic
def save_pretix_creation_preset(*, form, organization, user):
    require_capability(
        user,
        organization.id,
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Erstellungsstandards verwalten.",
    )
    preset = form.save(commit=False)
    if (
        not preset._state.adding
        and not PretixEventCreationPreset.objects.filter(
            pk=preset.pk,
            organization=organization,
        ).exists()
    ):
        raise PermissionDenied
    preset.organization = organization
    preset.updated_by = user
    if preset._state.adding:
        preset.created_by = user
    preset.save()
    return preset


@transaction.atomic
def save_pretix_funding_text(*, form, organization, user):
    require_capability(
        user,
        organization.id,
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Fördertexte verwalten.",
    )
    funding_text = form.save(commit=False)
    if (
        not funding_text._state.adding
        and not PretixFundingText.objects.filter(
            pk=funding_text.pk,
            organization=organization,
        ).exists()
    ):
        raise PermissionDenied
    funding_text.organization = organization
    funding_text.updated_by = user
    if funding_text._state.adding:
        funding_text.created_by = user
    funding_text.save()
    return funding_text


@transaction.atomic
def reserve_pretix_event_creation(
    *,
    organization,
    user,
    preset,
    funding_text,
    title,
    description,
    starts_at,
    ends_at,
    location,
    capacity,
    child_registration_enabled,
    existing_external_slugs=frozenset(),
):
    require_capability(
        user,
        organization.id,
        Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
        "Keine Berechtigung zum Vorbereiten einer Pretix-Veranstaltung.",
    )
    type(organization).objects.select_for_update().get(pk=organization.pk)
    try:
        preset = PretixEventCreationPreset.objects.get(
            pk=preset.pk,
            organization=organization,
            active=True,
        )
    except PretixEventCreationPreset.DoesNotExist as exc:
        raise PermissionDenied from exc
    if funding_text is not None:
        try:
            funding_text = PretixFundingText.objects.get(
                pk=funding_text.pk,
                organization=organization,
                active=True,
            )
        except PretixFundingText.DoesNotExist as exc:
            raise PermissionDenied from exc
    occupied_slugs = set(existing_external_slugs)
    occupied_slugs.update(
        PretixEventCreation.objects.filter(organization=organization).values_list(
            "external_slug", flat=True
        )
    )
    creation = PretixEventCreation(
        organization=organization,
        preset=preset,
        funding_text=funding_text,
        title=title.strip(),
        description=description.strip(),
        funding_text_snapshot=funding_text.text if funding_text else "",
        starts_at=starts_at,
        ends_at=ends_at,
        location=location.strip(),
        capacity=capacity,
        child_registration_enabled=child_registration_enabled,
        external_slug=numbered_event_slug(title, occupied_slugs),
        preset_snapshot={
            "display_name": preset.display_name,
            "template_event_slug": preset.template_event_slug,
            "primary_item_internal_name": preset.primary_item_internal_name,
            "child_item_internal_name": preset.child_item_internal_name,
        },
        created_by=user,
    )
    creation.full_clean()
    creation.save()
    return creation


@transaction.atomic
def claim_pretix_event_creation(*, creation_id, organization, user):
    require_capability(
        user,
        organization.id,
        Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
        "Keine Berechtigung zum Erstellen einer Pretix-Veranstaltung.",
    )
    try:
        creation = PretixEventCreation.objects.select_for_update().get(
            pk=creation_id,
            organization=organization,
        )
    except PretixEventCreation.DoesNotExist as exc:
        raise PermissionDenied from exc
    if creation.status not in {
        PretixEventCreation.Status.DRAFT,
        PretixEventCreation.Status.FAILED,
    }:
        raise ValueError("Die Pretix-Erstellung kann in diesem Status nicht gestartet werden.")
    creation.status = PretixEventCreation.Status.CREATING
    creation.attempt_count += 1
    creation.failure_code = ""
    creation.attempt_started_at = timezone.now()
    creation.completed_at = None
    creation.save(
        update_fields=[
            "status",
            "attempt_count",
            "failure_code",
            "attempt_started_at",
            "completed_at",
            "updated_at",
        ]
    )
    return creation


@transaction.atomic
def complete_pretix_event_creation(*, creation_id, organization, external_url):
    try:
        creation = PretixEventCreation.objects.select_for_update().get(
            pk=creation_id,
            organization=organization,
        )
    except PretixEventCreation.DoesNotExist as exc:
        raise PermissionDenied from exc
    if creation.status != PretixEventCreation.Status.CREATING:
        raise ValueError("Die Pretix-Erstellung ist nicht aktiv.")
    creation.status = PretixEventCreation.Status.CREATED
    creation.external_url = external_url
    creation.failure_code = ""
    creation.completed_at = timezone.now()
    creation.save(
        update_fields=[
            "status",
            "external_url",
            "failure_code",
            "completed_at",
            "updated_at",
        ]
    )
    return creation


@transaction.atomic
def materialize_pretix_event_creation(*, creation_id, organization):
    try:
        creation = PretixEventCreation.objects.select_for_update().get(
            pk=creation_id,
            organization=organization,
            status=PretixEventCreation.Status.CREATED,
        )
    except PretixEventCreation.DoesNotExist as exc:
        raise PermissionDenied from exc
    rule = PretixEventRule.objects.filter(
        organization=organization,
        event_slug=creation.external_slug,
    ).first()
    defaults = {
        "parent_external_reference": creation.external_slug,
        "title": creation.title,
        "starts_at": creation.starts_at,
        "ends_at": creation.ends_at,
        "location": creation.location,
        "lifecycle_status": Workshop.LifecycleStatus.ACTIVE,
    }
    if rule:
        defaults.update(
            documentation_requirement=rule.documentation_requirement,
            requirement_source=Workshop.RequirementSource.EVENT_RULE,
            requirement_reason=rule.reason,
            requirement_decided_by=rule.decided_by,
            requirement_decided_at=timezone.now(),
        )
    workshop, _ = Workshop.objects.update_or_create(
        organization=organization,
        source_type=Workshop.SourceType.PRETIX,
        external_reference=creation.external_slug,
        defaults=defaults,
    )
    return workshop


@transaction.atomic
def fail_pretix_event_creation(*, creation_id, organization, failure_code):
    try:
        creation = PretixEventCreation.objects.select_for_update().get(
            pk=creation_id,
            organization=organization,
        )
    except PretixEventCreation.DoesNotExist as exc:
        raise PermissionDenied from exc
    if creation.status != PretixEventCreation.Status.CREATING:
        raise ValueError("Die Pretix-Erstellung ist nicht aktiv.")
    if failure_code not in PretixEventCreation.FailureCode.values:
        raise ValueError("Ungültiger Fehlercode für die Pretix-Erstellung.")
    creation.status = PretixEventCreation.Status.FAILED
    creation.failure_code = failure_code
    creation.completed_at = None
    creation.save(update_fields=["status", "failure_code", "completed_at", "updated_at"])
    return creation
