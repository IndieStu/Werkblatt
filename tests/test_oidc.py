import pytest
from django.core.exceptions import PermissionDenied

from werkblatt.identities.oidc import normalized_claims


def test_normalizes_oidc_claims(settings):
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users"}
    claims = normalized_claims(
        {
            "iss": "https://auth.zircula.org/application/o/werkblatt/",
            "sub": "stable-user-id",
            "name": "Erika Beispiel",
            "email": "erika@example.invalid",
            "groups": ["Werkblatt Users"],
        }
    )
    assert claims.subject == "stable-user-id"
    assert claims.display_name == "Erika Beispiel"


def test_rejects_user_without_allowed_group(settings):
    settings.OIDC_ALLOWED_GROUPS = {"Werkblatt Users"}
    with pytest.raises(PermissionDenied):
        normalized_claims({"iss": "https://issuer.invalid", "sub": "id", "groups": ["Unrelated"]})
