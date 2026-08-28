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
        "OIDC_ISSUER": settings.OIDC_ISSUER,
        "OIDC_CLIENT_ID": settings.OIDC_CLIENT_ID,
        "OIDC_CLIENT_SECRET": settings.OIDC_CLIENT_SECRET,
    }
    missing = [name for name, value in values.items() if not value]
    if not settings.OIDC_ALLOWED_GROUPS:
        missing.append("OIDC_ALLOWED_GROUPS")
    if missing:
        raise ImproperlyConfigured(f"OIDC ist nicht vollständig konfiguriert: {', '.join(missing)}")
    parsed = urlparse(settings.OIDC_DISCOVERY_URL)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ImproperlyConfigured("OIDC_DISCOVERY_URL muss eine HTTPS-URL sein")
    issuer = urlparse(settings.OIDC_ISSUER)
    if (
        issuer.scheme != "https"
        or not issuer.hostname
        or issuer.username is not None
        or issuer.password is not None
    ):
        raise ImproperlyConfigured("OIDC_ISSUER muss eine HTTPS-URL ohne Credentials sein")


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
    issuer_value = payload.get("iss")
    subject_value = payload.get("sub")
    if not isinstance(issuer_value, str) or not issuer_value:
        raise PermissionDenied("OIDC-Antwort ohne stabile Identität")
    if not isinstance(subject_value, str) or not subject_value:
        raise PermissionDenied("OIDC-Antwort ohne stabile Identität")
    issuer = issuer_value
    subject = subject_value
    if issuer.rstrip("/") != settings.OIDC_ISSUER.rstrip("/"):
        raise PermissionDenied("OIDC-Antwort von unbekanntem Issuer")
    audience = payload.get("aud")
    if audience is not None:
        if isinstance(audience, str):
            audiences = {audience}
        elif isinstance(audience, list) and all(isinstance(item, str) for item in audience):
            audiences = set(audience)
        else:
            raise PermissionDenied("OIDC-Antwort mit ungültiger Audience")
        if settings.OIDC_CLIENT_ID not in audiences:
            raise PermissionDenied("OIDC-Antwort für eine andere Audience")
    raw_groups = payload.get("groups", [])
    groups = (
        frozenset(str(value) for value in raw_groups if isinstance(value, str))
        if isinstance(raw_groups, list)
        else frozenset()
    )
    allowed = settings.OIDC_ALLOWED_GROUPS
    if not allowed or groups.isdisjoint(allowed):
        raise PermissionDenied("Keine Werkblatt-Berechtigung")
    return OidcClaims(
        issuer=issuer,
        subject=subject,
        display_name=str(payload.get("name") or payload.get("preferred_username") or ""),
        email=str(payload.get("email") or ""),
        groups=groups,
    )
