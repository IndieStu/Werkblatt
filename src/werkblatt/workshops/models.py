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
