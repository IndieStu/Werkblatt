from django.conf import settings

from werkblatt.identities.policies import Capability, capabilities_for


def organization(request):
    organization = getattr(request, "organization", None)
    capabilities = capabilities_for(request.user, getattr(organization, "id", None))
    can_manage_templates = Capability.MANAGE_DOCUMENT_TEMPLATES in capabilities
    can_manage_assets = Capability.MANAGE_DOCUMENT_ASSETS in capabilities
    can_manage_organization = Capability.MANAGE_ORGANIZATION_PROFILE in capabilities
    can_manage_integrations = Capability.MANAGE_INTEGRATIONS in capabilities
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
        "is_org_admin": can_manage_organization,
        "can_manage_templates": can_manage_templates,
        "can_manage_assets": can_manage_assets,
        "can_manage_organization": can_manage_organization,
        "can_manage_integrations": can_manage_integrations,
        "can_access_administration": bool(
            can_manage_templates
            or can_manage_assets
            or can_manage_organization
            or can_manage_integrations
        ),
        "user_theme": request.user.theme if request.user.is_authenticated else "system",
    }
