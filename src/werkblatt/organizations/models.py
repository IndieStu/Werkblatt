import uuid

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
