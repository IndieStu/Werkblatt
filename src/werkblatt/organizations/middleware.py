from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied

from .models import Organization


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: UUID
    slug: str


class OrganizationContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.organization_context = None
        if request.user.is_authenticated:
            membership = (
                request.user.memberships.select_related("organization")
                .filter(
                    organization__slug=settings.DEFAULT_ORGANIZATION_SLUG,
                    organization__status=Organization.Status.ACTIVE,
                    status="active",
                )
                .first()
            )
            if membership is None:
                raise PermissionDenied("Keine aktive Organisationszugehörigkeit")
            request.organization = membership.organization
            request.organization_context = OrganizationContext(
                organization_id=membership.organization_id,
                slug=membership.organization.slug,
            )
        return self.get_response(request)
