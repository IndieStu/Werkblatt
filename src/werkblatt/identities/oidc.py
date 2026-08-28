from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied


@dataclass(frozen=True)
class OidcClaims:
    issuer: str
    subject: str
    display_name: str
    email: str
    groups: frozenset[str]


def validate_oidc_settings() -> None:
    values = {
        "OIDC_DISCOVERY_URL": settings.OIDC_DISCOVERY_URL,
        "OIDC_CLIENT_ID": settings.OIDC_CLIENT_ID,
        "OIDC_CLIENT_SECRET": settings.OIDC_CLIENT_SECRET,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ImproperlyConfigured(f"OIDC ist nicht vollständig konfiguriert: {', '.join(missing)}")
    parsed = urlparse(settings.OIDC_DISCOVERY_URL)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ImproperlyConfigured("OIDC_DISCOVERY_URL muss eine HTTPS-URL sein")


def oauth_client():
    validate_oidc_settings()
    oauth = OAuth()
    oauth.register(
        name="authentik",
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET,
        server_metadata_url=settings.OIDC_DISCOVERY_URL,
        client_kwargs={"scope": "openid email profile groups", "code_challenge_method": "S256"},
    )
    return oauth.authentik


def normalized_claims(payload: dict[str, Any]) -> OidcClaims:
    issuer = str(payload.get("iss", ""))
    subject = str(payload.get("sub", ""))
    if not issuer or not subject:
        raise PermissionDenied("OIDC-Antwort ohne stabile Identität")
    raw_groups = payload.get("groups", [])
    groups = (
        frozenset(str(value) for value in raw_groups if isinstance(value, str))
        if isinstance(raw_groups, list)
        else frozenset()
    )
    allowed = settings.OIDC_ALLOWED_GROUPS
    if allowed and groups.isdisjoint(allowed):
        raise PermissionDenied("Keine Werkblatt-Berechtigung")
    return OidcClaims(
        issuer=issuer,
        subject=subject,
        display_name=str(payload.get("name") or payload.get("preferred_username") or ""),
        email=str(payload.get("email") or ""),
        groups=groups,
    )
