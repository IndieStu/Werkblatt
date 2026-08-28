import hashlib

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from werkblatt.organizations.models import Organization

from .models import Identity, Membership, User
from .oidc import OidcClaims


@transaction.atomic
def provision_oidc_user(claims: OidcClaims) -> User:
    identity = (
        Identity.objects.select_for_update()
        .select_related("user")
        .filter(
            kind=Identity.Kind.OIDC,
            issuer=claims.issuer,
            subject=claims.subject,
        )
        .first()
    )
    if identity is None:
        stable = hashlib.sha256(f"{claims.issuer}\0{claims.subject}".encode()).hexdigest()[:24]
        user = User.objects.create_user(
            username=f"oidc-{stable}",
            email=claims.email,
            display_name=claims.display_name,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        identity = Identity.objects.create(
            user=user,
            kind=Identity.Kind.OIDC,
            issuer=claims.issuer,
            subject=claims.subject,
        )
    else:
        user = identity.user
        user.display_name = claims.display_name
        user.email = claims.email
        user.save(update_fields=["display_name", "email"])

    organization = Organization.objects.get(
        slug=settings.DEFAULT_ORGANIZATION_SLUG, status=Organization.Status.ACTIVE
    )
    role = (
        Membership.Role.ORGANIZATION_ADMIN
        if not claims.groups.isdisjoint(settings.OIDC_ADMIN_GROUPS)
        else Membership.Role.WORKSHOP_USER
    )
    Membership.objects.update_or_create(
        organization=organization,
        user=user,
        defaults={"role": role, "status": Membership.Status.ACTIVE},
    )
    identity.last_seen_at = timezone.now()
    identity.save(update_fields=["last_seen_at"])
    return user
