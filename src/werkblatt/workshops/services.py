from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from werkblatt.identities.policies import Capability, require_capability

from .models import PretixEventRule, Workshop


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
