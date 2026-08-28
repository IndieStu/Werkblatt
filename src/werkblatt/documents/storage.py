import ipaddress
import socket
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx
from django.conf import settings

from .models import GeneratedDocument


class WebDavConfigurationError(ValueError):
    pass


def validate_webdav_target(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
    ):
        raise WebDavConfigurationError("WebDAV benötigt eine HTTPS-URL ohne Credentials")
    mode = settings.WEBDAV_TRUST_MODE
    if mode not in {"hosted", "self_hosted"}:
        raise WebDavConfigurationError("Unbekannter WebDAV-Trust-Modus")
    if mode == "hosted" and parsed.hostname.lower() not in settings.WEBDAV_ALLOWED_HOSTS:
        try:
            addresses = {
                row[4][0]
                for row in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise WebDavConfigurationError("WebDAV-Host kann nicht aufgelöst werden") from exc
        if not addresses or any(
            not ipaddress.ip_address(address).is_global for address in addresses
        ):
            raise WebDavConfigurationError("WebDAV-Host ist im Hosted-Modus nicht erlaubt")
    return value


def _validated_root() -> PurePosixPath:
    configured = settings.WEBDAV_ROOT
    root = configured.strip("/")
    parts = PurePosixPath(root).parts
    if (
        not root
        or configured != root
        or "\\" in root
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise WebDavConfigurationError("WEBDAV_ROOT ist ungültig")
    return PurePosixPath(*parts)


def store_via_webdav(document: GeneratedDocument) -> GeneratedDocument:
    if not settings.WEBDAV_BASE_URL:
        return document
    claimed = GeneratedDocument.objects.filter(
        pk=document.pk,
        status__in=[GeneratedDocument.Status.RENDERED, GeneratedDocument.Status.STORAGE_FAILED],
    ).update(status=GeneratedDocument.Status.STORING)
    document.refresh_from_db()
    if claimed != 1:
        return document
    try:
        filename = (
            f"{document.workshop.starts_at:%Y-%m-%d}_{document.output_kind}_{document.id}.pdf"
        )
        key = PurePosixPath(
            _validated_root(),
            str(document.organization_id),
            str(document.workshop.starts_at.year),
            filename,
        )
        base_url = validate_webdav_target(settings.WEBDAV_BASE_URL)
        url = f"{base_url}/{quote(str(key))}"
        auth = (settings.WEBDAV_USERNAME, settings.WEBDAV_PASSWORD)
        parent = PurePosixPath()
        with httpx.Client(
            auth=auth,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=False,
        ) as client:
            validate_webdav_target(base_url)
            for part in key.parent.parts:
                parent /= part
                response = client.request("MKCOL", f"{base_url}/{quote(str(parent))}")
                if response.status_code not in {201, 405}:
                    response.raise_for_status()
            with document.pdf_file.open("rb") as stream:
                response = client.put(
                    url,
                    content=stream.read(),
                    headers={"Content-Type": "application/pdf", "If-None-Match": "*"},
                )
        if response.status_code != 412:
            response.raise_for_status()
    except Exception as exc:
        document.status = GeneratedDocument.Status.STORAGE_FAILED
        document.attempt_count += 1
        document.last_error_class = type(exc).__name__
        document.save(update_fields=["status", "attempt_count", "last_error_class", "updated_at"])
        return document
    document.status = GeneratedDocument.Status.STORED
    document.storage_key = str(key)
    document.attempt_count += 1
    document.last_error_class = ""
    document.save(
        update_fields=[
            "status",
            "storage_key",
            "attempt_count",
            "last_error_class",
            "updated_at",
        ]
    )
    return document
