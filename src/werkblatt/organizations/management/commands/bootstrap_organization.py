from django.conf import settings
from django.core.management.base import BaseCommand

from werkblatt.organizations.models import Organization


class Command(BaseCommand):
    help = "Legt die konfigurierte Pilotorganisation idempotent an."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        organization, created = Organization.objects.get_or_create(
            slug=settings.DEFAULT_ORGANIZATION_SLUG,
            defaults={"name": options["name"]},
        )
        action = "angelegt" if created else "bereits vorhanden"
        self.stdout.write(self.style.SUCCESS(f"Organisation {organization.slug}: {action}"))
