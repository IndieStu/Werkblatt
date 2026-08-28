import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from werkblatt.workshops.models import Workshop

from .models import Documentation, DocumentationRevision, Facilitator, ParticipantEntry


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
) -> Documentation:
    documentation = _locked_documentation(documentation_id, organization_id)
    _check_version(documentation, expected_version)
    if documentation.status != Documentation.Status.DRAFT:
        raise ValidationError("Abgeschlossene Dokumentation zuerst wieder öffnen")
    _apply_participants(documentation, participants)
    _apply_facilitators(documentation, facilitators)
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
    return {
        "schema_version": 1,
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
    snapshot = build_snapshot(documentation)
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
        snapshot_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        optional_change_reason=optional_change_reason.strip(),
        created_by=user,
    )
    documentation.status = Documentation.Status.FINALIZED
    documentation.finalized_at = timezone.now()
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
