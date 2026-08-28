import uuid

from django.conf import settings
from django.db import models

from werkblatt.organizations.models import BrandAsset


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
    template_assignment = models.ForeignKey(
        "WorkshopTemplateAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentations",
    )
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


class DocumentTemplateQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        if organization_id is None:
            raise ValueError("organization_id ist erforderlich")
        return self.filter(organization_id=organization_id)


class DocumentTemplate(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        INACTIVE = "inactive", "Inaktiv"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="document_templates"
    )
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status, default=Status.ACTIVE)
    is_default = models.BooleanField(default=False)
    current_version = models.ForeignKey(
        "DocumentTemplateVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_for_templates",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_document_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = DocumentTemplateQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="document_template_unique_name_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_default=True, status="active"),
                name="document_template_one_active_default_per_organization",
            ),
        ]


class DocumentTemplateVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    template = models.ForeignKey(
        DocumentTemplate, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    project_title = models.CharField(max_length=300, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    funding_text = models.TextField(max_length=2000, blank=True)
    attendance_text = models.TextField(
        max_length=2000,
        default=(
            "Mit dem Eintrag auf dieser Liste bestätige ich die Teilnahme an oben "
            "aufgeführtem Workshop."
        ),
    )
    configuration_schema_version = models.PositiveSmallIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_template_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "number"], name="document_template_version_unique_number"
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Vorlagenstände sind unveränderlich")
        return super().save(*args, **kwargs)


class TemplateAssetPlacement(models.Model):
    class Zone(models.TextChoices):
        HEADER = "header", "Kopfbereich"
        PROJECT = "project", "Projektbereich"
        FUNDING_FOOTER = "funding_footer", "Förderbereich"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    template_version = models.ForeignKey(
        DocumentTemplateVersion, on_delete=models.CASCADE, related_name="asset_placements"
    )
    asset_version = models.ForeignKey(
        "organizations.BrandAssetVersion", on_delete=models.PROTECT, related_name="placements"
    )
    role = models.CharField(max_length=32, choices=BrandAsset.Role)
    zone = models.CharField(max_length=32, choices=Zone)
    sort_order = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    show_funded_by_label = models.BooleanField(default=False)
    accessible_name = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["zone", "sort_order"]


class TemplateOutputDefinition(models.Model):
    class Kind(models.TextChoices):
        FINAL_REPORT = "final_report", "Abschlussdokument"
        ATTENDANCE_SHEET = "attendance_sheet", "Teilnahmeliste"
        ANONYMIZED_REPORT = "anonymized_report", "Anonymisierte Fassung"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    template_version = models.ForeignKey(
        DocumentTemplateVersion, on_delete=models.CASCADE, related_name="outputs"
    )
    kind = models.CharField(max_length=32, choices=Kind)
    display_name = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    include_participant_names = models.BooleanField(default=False)
    include_signature_column = models.BooleanField(default=False)
    include_statistics = models.BooleanField(default=True)
    include_report = models.BooleanField(default=True)
    include_facilitators = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_version", "kind"],
                name="template_output_unique_kind_per_version",
            )
        ]


class TemplateCustomFieldDefinition(models.Model):
    class FieldType(models.TextChoices):
        SHORT_TEXT = "short_text", "Kurzer Text"
        LONG_TEXT = "long_text", "Langer Text"
        INTEGER = "integer", "Ganzzahl"
        DECIMAL = "decimal", "Dezimalzahl"
        BOOLEAN = "boolean", "Ja / Nein"
        CHOICE = "choice", "Auswahl"
        DATE = "date", "Datum"

    class Presentation(models.TextChoices):
        REGULAR = "regular", "Normal"
        AGGREGATE_STATISTIC = "aggregate_statistic", "Aggregierte Statistik"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stable_key = models.UUIDField(default=uuid.uuid4)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    template_version = models.ForeignKey(
        DocumentTemplateVersion, on_delete=models.CASCADE, related_name="custom_fields"
    )
    label = models.CharField(max_length=200)
    help_text = models.CharField(max_length=500, blank=True)
    field_type = models.CharField(max_length=24, choices=FieldType)
    required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    default_value = models.JSONField(null=True, blank=True)
    choice_options = models.JSONField(default=list, blank=True)
    presentation = models.CharField(
        max_length=24, choices=Presentation, default=Presentation.REGULAR
    )
    include_in_output_kinds = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_version", "stable_key"],
                name="template_custom_field_unique_stable_key_per_version",
            )
        ]


class WorkshopTemplateAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    workshop = models.OneToOneField(
        "workshops.Workshop", on_delete=models.CASCADE, related_name="template_assignment"
    )
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT)
    template_version = models.ForeignKey(DocumentTemplateVersion, on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="template_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DocumentationCustomFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    documentation = models.ForeignKey(
        Documentation, on_delete=models.CASCADE, related_name="custom_field_values"
    )
    field_stable_key = models.UUIDField()
    value = models.JSONField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_documentation_custom_fields",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["documentation", "field_stable_key"],
                name="documentation_custom_value_unique_field",
            )
        ]
