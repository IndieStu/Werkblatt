import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        DISABLED = "disabled", "Deaktiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status, default=Status.ACTIVE)
    timezone = models.CharField(max_length=64, default="Europe/Berlin")
    default_locale = models.CharField(max_length=16, default="de")
    address = models.TextField(blank=True, max_length=500)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class BrandAssetQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        if organization_id is None:
            raise ValueError("organization_id ist erforderlich")
        return self.filter(organization_id=organization_id)


class BrandAsset(models.Model):
    class Role(models.TextChoices):
        ORGANIZATION = "organization", "Organisation"
        PROJECT_PROGRAM = "project_program", "Projekt / Programm"
        FUNDER = "funder", "Förderer"
        CLIENT = "client", "Auftraggeber"
        OTHER = "other", "Sonstiges"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        INACTIVE = "inactive", "Inaktiv"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="brand_assets"
    )
    display_name = models.CharField(max_length=200)
    default_role = models.CharField(max_length=32, choices=Role)
    status = models.CharField(max_length=16, choices=Status, default=Status.ACTIVE)
    current_version = models.ForeignKey(
        "BrandAssetVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_for_assets",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_brand_assets"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_brand_assets"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BrandAssetQuerySet.as_manager()

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "display_name"],
                name="brand_asset_unique_display_name_per_organization",
            )
        ]

    def __str__(self) -> str:
        return self.display_name


def brand_asset_original_path(instance, filename):
    suffix = ".svg" if instance.media_type == "image/svg+xml" else ".png"
    return (
        f"organizations/{instance.organization_id}/assets/{instance.asset_id}/"
        f"{instance.id}/original{suffix}"
    )


def brand_asset_preview_path(instance, _filename):
    return (
        f"organizations/{instance.organization_id}/assets/{instance.asset_id}/"
        f"{instance.id}/preview.png"
    )


class BrandAssetVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    asset = models.ForeignKey(BrandAsset, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    original_filename = models.CharField(max_length=255)
    media_type = models.CharField(max_length=32)
    byte_size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    original_file = models.FileField(upload_to=brand_asset_original_path, max_length=500)
    preview_file = models.FileField(upload_to=brand_asset_preview_path, max_length=500)
    validation_profile_version = models.PositiveSmallIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_brand_asset_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "number"], name="brand_asset_version_unique_number"
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Asset-Versionen sind unveränderlich")
        return super().save(*args, **kwargs)
