import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from werkblatt.workshops.models import Workshop

from .models import (
    Documentation,
    DocumentationCustomFieldValue,
    DocumentationRevision,
    DocumentTemplate,
    Facilitator,
    ParticipantEntry,
    WorkshopTemplateAssignment,
)


def snapshot_sha256(snapshot: dict) -> str:
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class ConcurrentDocumentationUpdate(ValidationError):
    pass


@dataclass(frozen=True)
class ParticipantInput:
    entry_id: UUID | None
    display_name: str
    present: bool
    delete: bool = False


@dataclass(frozen=True)
class FacilitatorInput:
    facilitator_id: UUID | None
    display_name: str
    delete: bool = False


@transaction.atomic
def get_or_create_documentation(*, workshop: Workshop, user) -> Documentation:
    documentation, created = Documentation.objects.get_or_create(
        organization_id=workshop.organization_id,
        workshop=workshop,
        defaults={"created_by": user, "updated_by": user},
    )
    if created:
        assignment = getattr(workshop, "template_assignment", None)
        if assignment is None:
            default_template = (
                DocumentTemplate.objects.for_organization(workshop.organization_id)
                .filter(is_default=True, status=DocumentTemplate.Status.ACTIVE)
                .select_related("current_version")
                .first()
            )
            if default_template:
                assignment = WorkshopTemplateAssignment.objects.create(
                    organization_id=workshop.organization_id,
                    workshop=workshop,
                    template=default_template,
                    template_version=default_template.current_version,
                    assigned_by=user,
                )
        if assignment:
            documentation.template_assignment = assignment
            documentation.save(update_fields=["template_assignment"])
        registrations = workshop.registrations.filter(
            organization_id=workshop.organization_id
        ).order_by("display_name")
        ParticipantEntry.objects.bulk_create(
            [
                ParticipantEntry(
                    organization_id=workshop.organization_id,
                    documentation=documentation,
                    registration=registration,
                    display_name=registration.display_name,
                    origin=ParticipantEntry.Origin.REGISTERED,
                    present=True,
                    sort_order=index,
                )
                for index, registration in enumerate(registrations)
            ]
        )
        display_name = user.get_full_name()
        if display_name:
            Facilitator.objects.create(
                organization_id=workshop.organization_id,
                documentation=documentation,
                display_name=display_name,
                user=user,
            )
    return documentation


def statistics_for(documentation: Documentation) -> dict[str, int]:
    participants = list(documentation.participants.all())
    registered = sum(item.origin == ParticipantEntry.Origin.REGISTERED for item in participants)
    present_registered = sum(
        item.origin == ParticipantEntry.Origin.REGISTERED and item.present for item in participants
    )
    walk_ins = sum(
        item.origin == ParticipantEntry.Origin.WALK_IN and item.present for item in participants
    )
    return {
        "registered": registered,
        "present_registered": present_registered,
        "walk_ins": walk_ins,
        "present_total": present_registered + walk_ins,
        "no_shows": registered - present_registered,
    }


def _locked_documentation(documentation_id: UUID, organization_id: UUID) -> Documentation:
    try:
        return (
            Documentation.objects.select_for_update()
            .select_related("workshop")
            .for_organization(organization_id)
            .get(pk=documentation_id)
        )
    except Documentation.DoesNotExist as exc:
        raise PermissionDenied("Dokumentation nicht gefunden") from exc


def _check_version(documentation: Documentation, expected_version: int) -> None:
    if documentation.version != expected_version:
        raise ConcurrentDocumentationUpdate(
            "Der Entwurf wurde zwischenzeitlich geändert. Bitte Seite neu laden."
        )


def _apply_participants(documentation: Documentation, rows: list[ParticipantInput]) -> None:
    existing = {entry.id: entry for entry in documentation.participants.select_for_update()}
    next_order = len(existing)
    for row in rows:
        name = row.display_name.strip()
        if row.entry_id is not None:
            entry = existing.get(row.entry_id)
            if entry is None:
                raise PermissionDenied("Ungültiger Teilnehmereintrag")
            if row.delete:
                if entry.origin == ParticipantEntry.Origin.REGISTERED:
                    raise ValidationError("Importierte Anmeldungen können nicht gelöscht werden")
                entry.delete()
                continue
            if not name:
                raise ValidationError("Teilnehmernamen dürfen nicht leer sein")
            entry.display_name = name
            entry.present = row.present
            entry.save(update_fields=["display_name", "present"])
        elif name and not row.delete:
            ParticipantEntry.objects.create(
                organization_id=documentation.organization_id,
                documentation=documentation,
                display_name=name,
                origin=ParticipantEntry.Origin.WALK_IN,
                present=row.present,
                sort_order=next_order,
            )
            next_order += 1


def _apply_facilitators(documentation: Documentation, rows: list[FacilitatorInput]) -> None:
    existing = {entry.id: entry for entry in documentation.facilitators.select_for_update()}
    next_order = len(existing)
    for row in rows:
        name = row.display_name.strip()
        if row.facilitator_id is not None:
            facilitator = existing.get(row.facilitator_id)
            if facilitator is None:
                raise PermissionDenied("Ungültiger Eintrag für Durchführende")
            if row.delete:
                facilitator.delete()
                continue
            if not name:
                raise ValidationError("Namen von Durchführenden dürfen nicht leer sein")
            facilitator.display_name = name
            facilitator.save(update_fields=["display_name"])
        elif name and not row.delete:
            Facilitator.objects.create(
                organization_id=documentation.organization_id,
                documentation=documentation,
                display_name=name,
                sort_order=next_order,
            )
            next_order += 1


@transaction.atomic
def save_draft(
    *,
    documentation_id: UUID,
    organization_id: UUID,
    user,
    expected_version: int,
    conducted_as_planned: bool,
    report: str,
    participants: list[ParticipantInput],
    facilitators: list[FacilitatorInput],
    custom_values: dict[str, object] | None = None,
) -> Documentation:
    documentation = _locked_documentation(documentation_id, organization_id)
    _check_version(documentation, expected_version)
    if documentation.status != Documentation.Status.DRAFT:
        raise ValidationError("Abgeschlossene Dokumentation zuerst wieder öffnen")
    _apply_participants(documentation, participants)
    _apply_facilitators(documentation, facilitators)
    if custom_values is not None:
        for stable_key, value in custom_values.items():
            DocumentationCustomFieldValue.objects.update_or_create(
                organization_id=documentation.organization_id,
                documentation=documentation,
                field_stable_key=stable_key,
                defaults={"value": value, "updated_by": user},
            )
    documentation.conducted_as_planned = conducted_as_planned
    documentation.report = report.strip()
    documentation.updated_by = user
    documentation.version += 1
    documentation.save(
        update_fields=[
            "conducted_as_planned",
            "report",
            "updated_by",
            "version",
            "updated_at",
        ]
    )
    return documentation


def build_snapshot(documentation: Documentation) -> dict:
    workshop = documentation.workshop
    snapshot = {
        "schema_version": 2,
        "workshop": {
            "id": str(workshop.id),
            "title": workshop.title,
            "starts_at": workshop.starts_at.isoformat(),
            "ends_at": workshop.ends_at.isoformat() if workshop.ends_at else None,
            "location": workshop.location,
            "source_type": workshop.source_type,
            "external_reference": workshop.external_reference,
        },
        "documentation": {
            "conducted_as_planned": documentation.conducted_as_planned,
            "report": documentation.report,
        },
        "facilitators": [
            {"display_name": item.display_name} for item in documentation.facilitators.all()
        ],
        "participants": [
            {
                "display_name": item.display_name,
                "origin": item.origin,
                "present": item.present,
                "registration_reference": (
                    item.registration.external_reference if item.registration_id else None
                ),
            }
            for item in documentation.participants.select_related("registration")
        ],
        "statistics": statistics_for(documentation),
    }
    assignment = documentation.template_assignment
    if assignment:
        version = assignment.template_version
        values = {
            str(value.field_stable_key): value.value
            for value in documentation.custom_field_values.all()
        }
        outputs = [
            {
                "id": str(output.id),
                "kind": output.kind,
                "display_name": output.display_name,
                "include_participant_names": output.include_participant_names,
                "include_signature_column": output.include_signature_column,
                "include_statistics": output.include_statistics,
                "include_report": output.include_report,
                "include_facilitators": output.include_facilitators,
            }
            for output in version.outputs.filter(enabled=True)
        ]
        fields = []
        for field in version.custom_fields.filter(active=True):
            fields.append(
                {
                    "stable_key": str(field.stable_key),
                    "label": field.label,
                    "help_text": field.help_text,
                    "field_type": field.field_type,
                    "required": field.required,
                    "presentation": field.presentation,
                    "include_in_output_kinds": field.include_in_output_kinds,
                    "choice_options": field.choice_options,
                    "value": values.get(str(field.stable_key)),
                }
            )
        assets = [
            {
                "asset_name": placement.asset_version.asset.display_name,
                "asset_version_id": str(placement.asset_version_id),
                "version": placement.asset_version.number,
                "media_type": placement.asset_version.media_type,
                "sha256": placement.asset_version.sha256,
                "role": placement.role,
                "zone": placement.zone,
                "sort_order": placement.sort_order,
                "show_funded_by_label": placement.show_funded_by_label,
            }
            for placement in version.asset_placements.select_related("asset_version__asset")
            if placement.enabled
        ]
        snapshot["template"] = {
            "id": str(assignment.template_id),
            "name": assignment.template.name,
            "version_id": str(version.id),
            "version": version.number,
            "schema_version": version.configuration_schema_version,
            "project_title": version.project_title,
            "subtitle": version.subtitle,
            "funding_text": version.funding_text,
            "attendance_text": version.attendance_text,
            "outputs": outputs,
            "assets": assets,
            "custom_fields": fields,
        }
    return snapshot


@transaction.atomic
def finalize_documentation(
    *,
    documentation_id: UUID,
    organization_id: UUID,
    user,
    expected_version: int,
    optional_change_reason: str = "",
) -> DocumentationRevision:
    documentation = _locked_documentation(documentation_id, organization_id)
    _check_version(documentation, expected_version)
    if documentation.status != Documentation.Status.DRAFT:
        raise ValidationError("Dokumentation ist bereits abgeschlossen")
    if not documentation.facilitators.exists():
        raise ValidationError("Mindestens eine durchführende Person ist erforderlich")
    if (
        not documentation.template_assignment_id
        and DocumentTemplate.objects.for_organization(organization_id)
        .filter(status=DocumentTemplate.Status.ACTIVE)
        .exists()
    ):
        raise ValidationError("Vor dem Abschluss muss eine Dokumentvorlage gewählt werden")
    definitions = (
        documentation.template_assignment.template_version.custom_fields.filter(
            active=True, required=True
        )
        if documentation.template_assignment_id
        else []
    )
    values = {
        str(value.field_stable_key): value.value
        for value in documentation.custom_field_values.all()
    }
    missing = [
        field.label for field in definitions if values.get(str(field.stable_key)) in (None, "")
    ]
    if missing:
        raise ValidationError(f"Pflichtfelder fehlen: {', '.join(missing)}")
    if documentation.template_assignment_id and not documentation.workshop.location.strip():
        raise ValidationError("Für die Dokumentausgabe muss ein Workshoport angegeben werden")
    finalized_at = timezone.now()
    snapshot = build_snapshot(documentation)
    snapshot["finalization"] = {
        "created_by_display_name": user.get_full_name(),
        "created_at": finalized_at.isoformat(),
    }
    previous_number = (
        documentation.revisions.select_for_update().aggregate(maximum=models.Max("number"))[
            "maximum"
        ]
        or 0
    )
    revision = DocumentationRevision.objects.create(
        organization_id=organization_id,
        documentation=documentation,
        number=previous_number + 1,
        snapshot=snapshot,
        snapshot_sha256=snapshot_sha256(snapshot),
        optional_change_reason=optional_change_reason.strip(),
        created_by=user,
    )
    documentation.status = Documentation.Status.FINALIZED
    documentation.finalized_at = finalized_at
    documentation.updated_by = user
    documentation.version += 1
    documentation.save(
        update_fields=["status", "finalized_at", "updated_by", "version", "updated_at"]
    )
    return revision


@transaction.atomic
def save_and_finalize(
    *,
    documentation_id: UUID,
    organization_id: UUID,
    user,
    expected_version: int,
    conducted_as_planned: bool,
    report: str,
    participants: list[ParticipantInput],
    facilitators: list[FacilitatorInput],
    optional_change_reason: str = "",
    custom_values: dict[str, object] | None = None,
) -> DocumentationRevision:
    documentation = save_draft(
        documentation_id=documentation_id,
        organization_id=organization_id,
        user=user,
        expected_version=expected_version,
        conducted_as_planned=conducted_as_planned,
        report=report,
        participants=participants,
        facilitators=facilitators,
        custom_values=custom_values,
    )
    return finalize_documentation(
        documentation_id=documentation.id,
        organization_id=organization_id,
        user=user,
        expected_version=documentation.version,
        optional_change_reason=optional_change_reason,
    )


@transaction.atomic
def reopen_documentation(
    *, documentation_id: UUID, organization_id: UUID, user, expected_version: int
) -> Documentation:
    documentation = _locked_documentation(documentation_id, organization_id)
    _check_version(documentation, expected_version)
    if documentation.status != Documentation.Status.FINALIZED:
        raise ValidationError("Nur abgeschlossene Dokumentationen können geöffnet werden")
    documentation.status = Documentation.Status.DRAFT
    documentation.updated_by = user
    documentation.version += 1
    documentation.save(update_fields=["status", "updated_by", "version", "updated_at"])
    return documentation
