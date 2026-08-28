from pathlib import PurePosixPath
from urllib.parse import quote

import httpx
from django.conf import settings

from .models import GeneratedDocument


def store_via_webdav(document: GeneratedDocument) -> GeneratedDocument:
    if not settings.WEBDAV_BASE_URL:
        return document
    filename = f"{document.workshop.starts_at:%Y-%m-%d}_{document.output_kind}_{document.id}.pdf"
    key = PurePosixPath(
        settings.WEBDAV_ROOT,
        str(document.organization_id),
        str(document.workshop.starts_at.year),
        filename,
    )
    base_url = settings.WEBDAV_BASE_URL.rstrip("/")
    url = f"{base_url}/{quote(str(key))}"
    try:
        auth = (settings.WEBDAV_USERNAME, settings.WEBDAV_PASSWORD)
        parent = PurePosixPath()
        with httpx.Client(
            auth=auth,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=False,
        ) as client:
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
