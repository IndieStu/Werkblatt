import uuid

from django.conf import settings
from django.db import models


class DocumentationQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        if organization_id is None:
            raise ValueError("organization_id ist erforderlich")
        return self.filter(organization_id=organization_id)


class Documentation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        FINALIZED = "finalized", "Abgeschlossen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="documentations",
    )
    workshop = models.OneToOneField(
        "workshops.Workshop",
        on_delete=models.CASCADE,
        related_name="documentation",
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.DRAFT)
    conducted_as_planned = models.BooleanField(default=True)
    report = models.TextField(blank=True, max_length=10_000)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documentations",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_documentations",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = DocumentationQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "workshop"],
                name="documentation_unique_workshop_per_organization",
            ),
        ]


class ParticipantEntry(models.Model):
    class Origin(models.TextChoices):
        REGISTERED = "registered", "Angemeldet"
        WALK_IN = "walk_in", "Spontan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    documentation = models.ForeignKey(
        Documentation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    registration = models.ForeignKey(
        "workshops.WorkshopRegistration",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentation_entries",
    )
    display_name = models.CharField(max_length=200)
    origin = models.CharField(max_length=16, choices=Origin)
    present = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["documentation", "registration"],
                condition=models.Q(registration__isnull=False),
                name="participant_unique_registration_per_documentation",
            ),
        ]


class Facilitator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    documentation = models.ForeignKey(
        Documentation,
        on_delete=models.CASCADE,
        related_name="facilitators",
    )
    display_name = models.CharField(max_length=200)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facilitated_documentations",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "display_name"]


class DocumentationRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    documentation = models.ForeignKey(
        Documentation,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    number = models.PositiveIntegerField()
    snapshot_schema_version = models.PositiveSmallIntegerField(default=1)
    snapshot = models.JSONField()
    snapshot_sha256 = models.CharField(max_length=64)
    optional_change_reason = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documentation_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["documentation", "number"],
                name="documentation_revision_unique_number",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Dokumentationsrevisionen sind unveränderlich")
        return super().save(*args, **kwargs)
