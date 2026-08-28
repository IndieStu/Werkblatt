import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    display_name = models.CharField(max_length=200, blank=True)

    def get_full_name(self) -> str:
        return self.display_name or super().get_full_name() or self.username


class Identity(models.Model):
    class Kind(models.TextChoices):
        OIDC = "oidc", "OIDC"
        LOCAL = "local", "Lokales Konto"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="identities")
    kind = models.CharField(max_length=16, choices=Kind)
    issuer = models.URLField(max_length=500, blank=True)
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "issuer", "subject"], name="identity_unique_external_subject"
            ),
        ]


class Membership(models.Model):
    class Role(models.TextChoices):
        ORGANIZATION_ADMIN = "organization_admin", "Organization Admin"
        WORKSHOP_USER = "workshop_user", "Workshop User"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        DISABLED = "disabled", "Deaktiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, choices=Role)
    status = models.CharField(max_length=16, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="membership_unique_organization_user"
            ),
        ]
