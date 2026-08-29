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
        "software_author_label": settings.SOFTWARE_AUTHOR_LABEL,
        "software_collaboration_url": settings.SOFTWARE_COLLABORATION_URL,
        "software_collaboration_label": settings.SOFTWARE_COLLABORATION_LABEL,
        "software_repository_url": settings.SOFTWARE_REPOSITORY_URL,
        "user_documentation_url": settings.USER_DOCUMENTATION_URL,
        "issue_tracker_url": settings.ISSUE_TRACKER_URL,
        "hosting_provider_label": settings.HOSTING_PROVIDER_LABEL,
        "is_org_admin": is_org_admin,
        "user_theme": request.user.theme if request.user.is_authenticated else "system",
    }
