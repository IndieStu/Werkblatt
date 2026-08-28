from django.core.management.base import BaseCommand

from werkblatt.documents.models import GeneratedDocument
from werkblatt.documents.storage import store_via_webdav


class Command(BaseCommand):
    help = "Wiederholt fehlgeschlagene oder noch ausstehende WebDAV-Speicherungen."

    def handle(self, *args, **options):
        documents = GeneratedDocument.objects.filter(
            status__in=[
                GeneratedDocument.Status.RENDERED,
                GeneratedDocument.Status.STORAGE_FAILED,
            ]
        ).exclude(pdf_file="")
        stored = 0
        for document in documents.iterator():
            if store_via_webdav(document).status == GeneratedDocument.Status.STORED:
                stored += 1
        self.stdout.write(self.style.SUCCESS(f"{stored} Dokument(e) extern gespeichert."))
