import uuid

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="workshops"
    )
    source_type = models.CharField(max_length=16, choices=SourceType)
    external_reference = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=300)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True)
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
