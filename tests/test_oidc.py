import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from werkblatt.identities.models import Membership
from werkblatt.identities.oidc import normalized_claims
from werkblatt.identities.services import provision_oidc_user
from werkblatt.organizations.models import Organization


def test_normalizes_oidc_claims(settings):
    settings.OIDC_ISSUER = "https://auth.zircula.org/application/o/werkblatt/"
    settings.OIDC_CLIENT_ID = "werkblatt"
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users"}
    claims = normalized_claims(
        {
            "iss": "https://auth.zircula.org/application/o/werkblatt/",
            "sub": "stable-user-id",
            "name": "Erika Beispiel",
            "email": "erika@example.invalid",
            "groups": ["Werkblatt Users"],
            "aud": "werkblatt",
        }
    )
    assert claims.subject == "stable-user-id"
    assert claims.display_name == "Erika Beispiel"


def test_rejects_user_without_allowed_group(settings):
    settings.OIDC_ISSUER = "https://issuer.invalid"
    settings.OIDC_CLIENT_ID = "werkblatt"
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users"}
    with pytest.raises(PermissionDenied):
        normalized_claims({"iss": "https://issuer.invalid", "sub": "id", "groups": ["Unrelated"]})


@pytest.mark.parametrize(
    "payload",
    [
        {"iss": "https://wrong.invalid", "sub": "id", "groups": ["Werkblatt Users"]},
        {
            "iss": "https://issuer.invalid",
            "sub": "id",
            "aud": "other-client",
            "groups": ["Werkblatt Users"],
        },
        {
            "iss": "https://issuer.invalid",
            "sub": "id",
            "aud": 123,
            "groups": ["Werkblatt Users"],
        },
        {"iss": "https://issuer.invalid", "groups": ["Werkblatt Users"]},
    ],
)
def test_rejects_invalid_identity_binding(settings, payload):
    settings.OIDC_ISSUER = "https://issuer.invalid"
    settings.OIDC_CLIENT_ID = "werkblatt"
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users"}
    with pytest.raises(PermissionDenied):
        normalized_claims(payload)


@pytest.mark.django_db
def test_group_changes_update_only_configured_organization_role(settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "zircula"
    settings.OIDC_ISSUER = "https://issuer.invalid"
    settings.OIDC_CLIENT_ID = "werkblatt"
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users", "Werkblatt Admins"}
    settings.OIDC_ADMIN_GROUPS = {"Werkblatt Admins"}
    organization = Organization.objects.create(slug="zircula", name="Zircula")
    other = Organization.objects.create(slug="other", name="Andere")
    admin_claims = normalized_claims(
        {
            "iss": settings.OIDC_ISSUER,
            "sub": "stable-subject",
            "aud": settings.OIDC_CLIENT_ID,
            "groups": ["Werkblatt Admins"],
        }
    )
    user = provision_oidc_user(admin_claims)
    assert (
        user.memberships.get(organization=organization).role == Membership.Role.ORGANIZATION_ADMIN
    )
    Membership.objects.create(
        organization=other,
        user=user,
        role=Membership.Role.WORKSHOP_USER,
    )

    user_claims = normalized_claims(
        {
            "iss": settings.OIDC_ISSUER,
            "sub": "stable-subject",
            "aud": settings.OIDC_CLIENT_ID,
            "groups": ["Werkblatt Users"],
        }
    )
    provision_oidc_user(user_claims)
    assert user.memberships.get(organization=organization).role == Membership.Role.WORKSHOP_USER
    assert user.memberships.get(organization=other).role == Membership.Role.WORKSHOP_USER
    assert get_user_model().objects.count() == 1
