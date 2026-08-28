from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from werkblatt.integrations.pretix import PretixClient, PretixWorkshopProvider
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import Workshop


class Command(BaseCommand):
    help = "Synchronisiert Workshops aus dem konfigurierten Pretix-Organizer."

    def handle(self, *args, **options):
        if not settings.PRETIX_API_TOKEN:
            raise CommandError("PRETIX_API_TOKEN ist nicht gesetzt")
        try:
            organization = Organization.objects.get(
                slug=settings.DEFAULT_ORGANIZATION_SLUG,
                status=Organization.Status.ACTIVE,
            )
        except Organization.DoesNotExist as exc:
            raise CommandError("Die konfigurierte Organisation fehlt oder ist deaktiviert") from exc

        client = PretixClient(settings.PRETIX_BASE_URL, settings.PRETIX_API_TOKEN)
        try:
            # Externe HTTP-Arbeit findet bewusst außerhalb einer DB-Transaktion statt.
            imported = PretixWorkshopProvider(client, settings.PRETIX_ORGANIZER).list_workshops()
        finally:
            client.close()

        with transaction.atomic():
            for item in imported:
                Workshop.objects.update_or_create(
                    organization=organization,
                    source_type=Workshop.SourceType.PRETIX,
                    external_reference=item.reference,
                    defaults={
                        "title": item.title,
                        "starts_at": item.starts_at,
                        "ends_at": item.ends_at,
                        "location": item.location,
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"{len(imported)} Workshops synchronisiert"))
