from django.conf import settings


def organization(request):
    return {
        "current_organization": getattr(request, "organization", None),
        "software_author_url": settings.SOFTWARE_AUTHOR_URL,
        "hosting_provider_label": settings.HOSTING_PROVIDER_LABEL,
    }
