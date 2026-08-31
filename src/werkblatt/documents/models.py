import re
import unicodedata
import uuid

from django.conf import settings
from django.db import models

OUTPUT_FILENAME_LABELS = {
    "final_report": "FinalReport",
    "attendance_sheet": "AttendanceSheet",
    "anonymized_report": "AnonymizedReport",
}


def generated_document_filename(instance, *, unique=False):
    output_label = OUTPUT_FILENAME_LABELS.get(
        instance.output_kind,
        "".join(part.capitalize() for part in instance.output_kind.split("_")),
    )
    normalized_title = unicodedata.normalize("NFKC", instance.workshop.title)
    workshop_label = re.sub(r"[^\w]+", "_", normalized_title, flags=re.UNICODE)
    workshop_label = workshop_label[:120].strip("_") or "Workshop"
    parts = ["Workshop", output_label or "Document", workshop_label]
    if unique:
        parts.extend([instance.workshop.starts_at.strftime("%Y-%m-%d"), str(instance.id)[:8]])
    return "_".join(parts) + ".pdf"


def generated_document_path(instance, _filename):
    return (
        f"organizations/{instance.organization_id}/documents/{instance.workshop_id}/"
        f"{instance.id}.pdf"
    )


class GeneratedDocumentQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        if organization_id is None:
            raise ValueError("organization_id ist erforderlich")
        return self.filter(organization_id=organization_id)


class GeneratedDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        RENDERING = "rendering", "Wird erzeugt"
        RENDERED = "rendered", "Erzeugt"
        STORING = "storing", "Wird extern gespeichert"
        STORED = "stored", "Extern gespeichert"
        RENDER_FAILED = "render_failed", "PDF-Erzeugung fehlgeschlagen"
        STORAGE_FAILED = "storage_failed", "Externe Speicherung fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    workshop = models.ForeignKey(
        "workshops.Workshop", on_delete=models.PROTECT, related_name="generated_documents"
    )
    revision = models.ForeignKey(
        "documentation.DocumentationRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="generated_documents",
    )
    template_version = models.ForeignKey(
        "documentation.DocumentTemplateVersion", on_delete=models.PROTECT
    )
    output_kind = models.CharField(max_length=32)
    output_name = models.CharField(max_length=200)
    input_sha256 = models.CharField(max_length=64)
    renderer_version = models.CharField(max_length=32, default="weasyprint-69/v1")
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING)
    pdf_file = models.FileField(upload_to=generated_document_path, max_length=500, blank=True)
    pdf_sha256 = models.CharField(max_length=64, blank=True)
    byte_size = models.PositiveIntegerField(default=0)
    storage_key = models.CharField(max_length=500, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error_class = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generated_documents"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = GeneratedDocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "workshop",
                    "revision",
                    "template_version",
                    "output_kind",
                    "input_sha256",
                ],
                condition=models.Q(revision__isnull=False),
                name="generated_document_idempotent_output",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "workshop",
                    "template_version",
                    "output_kind",
                    "input_sha256",
                ],
                condition=models.Q(revision__isnull=True),
                name="generated_document_idempotent_draft_output",
            ),
        ]
