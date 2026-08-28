import ipaddress
import json
import socket
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import httpx


class PretixConfigurationError(ValueError):
    pass


class PretixUnavailable(RuntimeError):
    pass


MAX_PRETIX_RESPONSE_BYTES = 5 * 1024 * 1024


def validate_public_https_origin(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or parsed.port not in (None, 443)
    ):
        raise PretixConfigurationError("Pretix base URL must be a plain HTTPS origin")
    try:
        addresses = {
            row[4][0] for row in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise PretixConfigurationError("Pretix host cannot be resolved") from exc
    if not addresses:
        raise PretixConfigurationError("Pretix host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise PretixConfigurationError(
                "Pretix host must resolve exclusively to public addresses"
            )
    return value


class PretixClient:
    def __init__(self, base_url: str, token: str, *, transport: httpx.BaseTransport | None = None):
        if not token:
            raise PretixConfigurationError("Pretix API token is required")
        self.base_url = validate_public_https_origin(base_url)
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json", "Authorization": f"Token {token}"},
            timeout=httpx.Timeout(8.0, connect=5.0),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if not path.startswith("/api/v1/") or ".." in path:
            raise ValueError("Pretix requests are restricted to fixed API paths")
        validate_public_https_origin(self.base_url)
        try:
            with self._client.stream("GET", path, params=params) as response:
                response.raise_for_status()
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_PRETIX_RESPONSE_BYTES:
                        raise PretixUnavailable("Pretix response exceeds the safe size limit")
                    chunks.append(chunk)
            payload = json.loads(b"".join(chunks))
        except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PretixUnavailable("Pretix request failed") from exc
        if not isinstance(payload, dict):
            raise PretixUnavailable("Pretix returned an invalid response")
        return payload

    def pages(self, path: str, params: dict[str, str] | None = None) -> Iterator[dict[str, Any]]:
        query = dict(params or {})
        for page in range(1, 101):
            payload = self.get(path, {**query, "page": str(page)})
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise PretixUnavailable("Pretix returned an invalid result list")
            yield from (item for item in results if isinstance(item, dict))
            if not payload.get("next"):
                return
        raise PretixUnavailable("Pretix pagination limit exceeded")
