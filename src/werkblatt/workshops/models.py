import uuid

from django.conf import settings
from django.db import models


class WorkshopQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        if organization_id is None:
            raise ValueError("organization_id ist erforderlich")
        return self.filter(organization_id=organization_id)


class Workshop(models.Model):
    class SourceType(models.TextChoices):
        PRETIX = "pretix", "Pretix"
        NATIVE = "native", "Werkblatt"

    class DocumentationRequirement(models.TextChoices):
        REQUIRED = "required", "Dokumentation erforderlich"
        NOT_REQUIRED = "not_required", "Keine Dokumentation erforderlich"

    class RequirementSource(models.TextChoices):
        DEFAULT = "default", "Standard"
        EVENT_RULE = "event_rule", "Pretix-Veranstaltungsregel"
        INDIVIDUAL = "individual", "Einzelentscheidung"

    class Visibility(models.TextChoices):
        ACTIVE = "active", "Sichtbar"
        HIDDEN = "hidden", "Ausgeblendet"

    class LifecycleStatus(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        CANCELLED = "cancelled", "Abgesagt"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="workshops"
    )
    source_type = models.CharField(max_length=16, choices=SourceType)
    external_reference = models.CharField(max_length=255, blank=True)
    parent_external_reference = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=300)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=LifecycleStatus,
        default=LifecycleStatus.ACTIVE,
    )
    documentation_requirement = models.CharField(
        max_length=16,
        choices=DocumentationRequirement,
        default=DocumentationRequirement.REQUIRED,
    )
    requirement_source = models.CharField(
        max_length=16,
        choices=RequirementSource,
        default=RequirementSource.DEFAULT,
    )
    requirement_reason = models.CharField(max_length=500, blank=True)
    requirement_decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workshop_requirement_decisions",
    )
    requirement_decided_at = models.DateTimeField(null=True, blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=Visibility,
        default=Visibility.ACTIVE,
    )
    visibility_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workshop_visibility_changes",
    )
    visibility_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = WorkshopQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_type", "external_reference"],
                condition=~models.Q(external_reference=""),
                name="workshop_unique_external_reference_per_organization",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class PretixEventRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="pretix_event_rules"
    )
    event_slug = models.CharField(max_length=255)
    display_name = models.CharField(max_length=300, blank=True)
    import_enabled = models.BooleanField(default=True)
    documentation_requirement = models.CharField(
        max_length=16,
        choices=Workshop.DocumentationRequirement,
        default=Workshop.DocumentationRequirement.REQUIRED,
    )
    reason = models.CharField(max_length=500, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pretix_event_rule_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "event_slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "event_slug"],
                name="pretix_event_rule_unique_slug_per_organization",
            )
        ]

    def __str__(self) -> str:
        return self.display_name or self.event_slug


class WorkshopRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="registrations")
    external_reference = models.CharField(max_length=255)
    display_name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "workshop", "external_reference"],
                name="registration_unique_external_reference",
            ),
        ]


class PretixEventCreationPreset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="pretix_creation_presets",
    )
    display_name = models.CharField(max_length=200)
    template_event_slug = models.CharField(max_length=255)
    primary_item_internal_name = models.CharField(max_length=200)
    child_item_internal_name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pretix_event_presets",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_pretix_event_presets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "display_name"],
                name="pretix_creation_preset_unique_name_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "template_event_slug"],
                name="pretix_creation_preset_unique_template_per_org",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    primary_item_internal_name=models.F("child_item_internal_name")
                ),
                name="pretix_creation_preset_distinct_items",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name


class PretixFundingText(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="pretix_funding_texts",
    )
    display_name = models.CharField(max_length=200)
    text = models.TextField(max_length=5000)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pretix_funding_texts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_pretix_funding_texts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "display_name"],
                name="pretix_funding_text_unique_name_per_org",
            )
        ]

    def __str__(self) -> str:
        return self.display_name


class PretixEventCreation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        CREATING = "creating", "Wird erstellt"
        CREATED = "created", "Erstellt"
        FAILED = "failed", "Fehlgeschlagen"

    class FailureCode(models.TextChoices):
        TEMPLATE_INVALID = "template_invalid", "Vorlage ungültig"
        SLUG_CONFLICT = "slug_conflict", "Slug bereits vergeben"
        PRETIX_UNAVAILABLE = "pretix_unavailable", "Pretix nicht erreichbar"
        PRETIX_REJECTED = "pretix_rejected", "Pretix hat die Anfrage abgewiesen"
        VERIFICATION_FAILED = "verification_failed", "Ergebnisprüfung fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="pretix_event_creations",
    )
    preset = models.ForeignKey(
        PretixEventCreationPreset,
        on_delete=models.PROTECT,
        related_name="event_creations",
    )
    funding_text = models.ForeignKey(
        PretixFundingText,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="event_creations",
    )
    title = models.CharField(max_length=300)
    description = models.TextField(max_length=10000, blank=True)
    funding_text_snapshot = models.TextField(max_length=5000, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True)
    capacity = models.PositiveIntegerField()
    child_registration_enabled = models.BooleanField(default=False)
    external_slug = models.CharField(max_length=255)
    external_url = models.URLField(blank=True, max_length=500)
    status = models.CharField(max_length=16, choices=Status, default=Status.DRAFT)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    failure_code = models.CharField(max_length=80, choices=FailureCode, blank=True)
    preset_snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pretix_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attempt_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "external_slug"],
                name="pretix_event_creation_unique_slug_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gte=1),
                name="pretix_event_creation_positive_capacity",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.external_slug})"
