from enum import StrEnum

from django.core.exceptions import PermissionDenied

from .models import Membership


class Capability(StrEnum):
    DOCUMENT_WORKSHOPS = "document_workshops"
    MANAGE_DOCUMENT_TEMPLATES = "manage_document_templates"
    MANAGE_DOCUMENT_ASSETS = "manage_document_assets"
    MANAGE_ORGANIZATION_PROFILE = "manage_organization_profile"
    MANAGE_ORGANIZATION_BRANDING = "manage_organization_branding"
    MANAGE_INTEGRATIONS = "manage_integrations"
    MANAGE_MEMBERSHIPS = "manage_memberships"
    MANAGE_WORKSHOP_VISIBILITY = "manage_workshop_visibility"


ROLE_CAPABILITIES = {
    Membership.Role.WORKSHOP_USER: frozenset({Capability.DOCUMENT_WORKSHOPS}),
    Membership.Role.EDITOR: frozenset(
        {
            Capability.DOCUMENT_WORKSHOPS,
            Capability.MANAGE_DOCUMENT_TEMPLATES,
            Capability.MANAGE_DOCUMENT_ASSETS,
            Capability.MANAGE_WORKSHOP_VISIBILITY,
        }
    ),
    Membership.Role.ORGANIZATION_ADMIN: frozenset(Capability),
}


def capabilities_for(user, organization_id) -> frozenset[Capability]:
    if not user.is_authenticated or organization_id is None:
        return frozenset()
    role = (
        user.memberships.filter(
            organization_id=organization_id,
            status=Membership.Status.ACTIVE,
        )
        .values_list("role", flat=True)
        .first()
    )
    return ROLE_CAPABILITIES.get(role, frozenset())


def has_capability(user, organization_id, capability: Capability) -> bool:
    return capability in capabilities_for(user, organization_id)


def require_capability(user, organization_id, capability: Capability, message: str) -> None:
    if not has_capability(user, organization_id, capability):
        raise PermissionDenied(message)
