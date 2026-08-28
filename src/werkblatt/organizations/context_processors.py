from django.conf import settings

from werkblatt.identities.models import Membership


def organization(request):
    is_org_admin = bool(
        request.user.is_authenticated
        and request.user.memberships.filter(
            organization=getattr(request, "organization", None),
            role=Membership.Role.ORGANIZATION_ADMIN,
            status=Membership.Status.ACTIVE,
        ).exists()
    )
    return {
        "current_organization": getattr(request, "organization", None),
        "software_author_url": settings.SOFTWARE_AUTHOR_URL,
        "hosting_provider_label": settings.HOSTING_PROVIDER_LABEL,
        "is_org_admin": is_org_admin,
    }
