from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from werkblatt.integrations.pretix import PretixClient, PretixWorkshopProvider
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import PretixEventRule, Workshop, WorkshopRegistration


class Command(BaseCommand):
    help = "Synchronisiert Workshops aus dem konfigurierten Pretix-Organizer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workshop-reference",
            action="append",
            dest="workshop_references",
            help="Import auf eine explizite Pretix-Workshopreferenz begrenzen.",
        )
        parser.add_argument(
            "--include-test-events",
            action="store_true",
            help="Pretix-Testevents zulassen; nur mit --workshop-reference erlaubt.",
        )

    def handle(self, *args, **options):
        if not settings.PRETIX_API_TOKEN:
            raise CommandError("PRETIX_API_TOKEN ist nicht gesetzt")
        if not settings.PRETIX_ORGANIZER:
            raise CommandError("PRETIX_ORGANIZER ist nicht gesetzt")
        try:
            organization = Organization.objects.get(
                slug=settings.DEFAULT_ORGANIZATION_SLUG,
                status=Organization.Status.ACTIVE,
            )
        except Organization.DoesNotExist as exc:
            raise CommandError("Die konfigurierte Organisation fehlt oder ist deaktiviert") from exc

        requested_references = set(options.get("workshop_references") or [])
        include_test_events = options.get("include_test_events", False)
        if include_test_events and not requested_references:
            raise CommandError("--include-test-events erfordert --workshop-reference")
        not_before = None
        if not requested_references:
            try:
                not_before = date.fromisoformat(settings.PRETIX_IMPORT_NOT_BEFORE)
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    "PRETIX_IMPORT_NOT_BEFORE muss für einen regulären Sync "
                    "als YYYY-MM-DD gesetzt sein"
                ) from exc

        rules = {
            rule.event_slug: rule
            for rule in PretixEventRule.objects.filter(organization=organization)
        }
        excluded_event_slugs = frozenset(
            rule.event_slug for rule in rules.values() if not rule.import_enabled
        )
        client = PretixClient(settings.PRETIX_BASE_URL, settings.PRETIX_API_TOKEN)
        try:
            # Externe HTTP-Arbeit findet bewusst außerhalb einer DB-Transaktion statt.
            provider = PretixWorkshopProvider(client, settings.PRETIX_ORGANIZER)
            imported = provider.list_workshops(
                include_testmode=include_test_events,
                not_before=not_before,
                excluded_event_slugs=excluded_event_slugs,
            )
            if requested_references:
                imported = [item for item in imported if item.reference in requested_references]
                missing = requested_references - {item.reference for item in imported}
                if missing:
                    raise CommandError(
                        "Pretix-Workshopreferenz nicht gefunden: " + ", ".join(sorted(missing))
                    )
            event_slugs = {
                item.reference: item.event_slug or item.reference.partition(":")[0]
                for item in imported
            }
            imported = [
                item
                for item in imported
                if rules.get(event_slugs[item.reference]) is None
                or rules[event_slugs[item.reference]].import_enabled
            ]
            registrations_by_reference = {}
            for item in imported:
                event_slug, separator, subevent = item.reference.rpartition(":")
                if separator and subevent.isdigit():
                    registrations = provider.list_registrations(event_slug, int(subevent))
                else:
                    registrations = provider.list_registrations(item.reference)
                registrations_by_reference[item.reference] = registrations
        finally:
            client.close()

        with transaction.atomic():
            for item in imported:
                event_slug = event_slugs[item.reference]
                rule = rules.get(event_slug)
                requirement = (
                    rule.documentation_requirement
                    if rule
                    else Workshop.DocumentationRequirement.REQUIRED
                )
                workshop, created = Workshop.objects.update_or_create(
                    organization=organization,
                    source_type=Workshop.SourceType.PRETIX,
                    external_reference=item.reference,
                    defaults={
                        "title": item.title,
                        "parent_external_reference": event_slug,
                        "starts_at": item.starts_at,
                        "ends_at": item.ends_at,
                        "location": item.location,
                    },
                )
                if created or workshop.requirement_source != Workshop.RequirementSource.INDIVIDUAL:
                    workshop.documentation_requirement = requirement
                    workshop.requirement_source = (
                        Workshop.RequirementSource.EVENT_RULE
                        if rule
                        else Workshop.RequirementSource.DEFAULT
                    )
                    workshop.requirement_reason = rule.reason if rule else ""
                    workshop.requirement_decided_by = rule.decided_by if rule else None
                    workshop.requirement_decided_at = rule.updated_at if rule else None
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
                WorkshopRegistration.objects.filter(
                    organization=organization,
                    workshop=workshop,
                ).update(active=False)
                for registration in registrations_by_reference[item.reference]:
                    WorkshopRegistration.objects.update_or_create(
                        organization=organization,
                        workshop=workshop,
                        external_reference=registration.reference,
                        defaults={"display_name": registration.display_name, "active": True},
                    )
        registration_count = sum(len(rows) for rows in registrations_by_reference.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(imported)} Workshops und {registration_count} Anmeldungen synchronisiert"
            )
        )
