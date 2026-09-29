import ipaddress
import json
import socket
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlparse

import httpx


class PretixConfigurationError(ValueError):
    pass


class PretixUnavailable(RuntimeError):
    pass


MAX_PRETIX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_PRETIX_REQUEST_BYTES = 256 * 1024
MAX_PRETIX_RATE_LIMIT_RETRIES = 2
MAX_PRETIX_RETRY_AFTER_SECONDS = 60
PRETIX_REQUEST_INTERVAL_SECONDS = 0.2


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
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        request_interval_seconds: float | None = None,
    ):
        if not token:
            raise PretixConfigurationError("Pretix API token is required")
        self.base_url = validate_public_https_origin(base_url)
        self._sleep = sleeper
        self._monotonic = monotonic
        self._last_request_started: float | None = None
        self._request_interval_seconds = (
            PRETIX_REQUEST_INTERVAL_SECONDS
            if request_interval_seconds is None and transport is None
            else (request_interval_seconds or 0.0)
        )
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

    def _wait_for_request_slot(self) -> None:
        if self._last_request_started is not None:
            elapsed = self._monotonic() - self._last_request_started
            remaining = self._request_interval_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_started = self._monotonic()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After", "").strip()
        if not value.isdigit():
            return None
        seconds = int(value)
        if seconds > MAX_PRETIX_RETRY_AFTER_SECONDS:
            return None
        return seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method not in {"GET", "POST", "PATCH"}:
            raise ValueError("Unsupported Pretix request method")
        if not path.startswith("/api/v1/") or ".." in path:
            raise ValueError("Pretix requests are restricted to fixed API paths")
        if json_body is not None:
            encoded_body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            if len(encoded_body) > MAX_PRETIX_REQUEST_BYTES:
                raise PretixConfigurationError("Pretix request exceeds the safe size limit")
        validate_public_https_origin(self.base_url)
        payload = None
        for attempt in range(MAX_PRETIX_RATE_LIMIT_RETRIES + 1):
            try:
                self._wait_for_request_slot()
                retry_after = None
                with self._client.stream(method, path, params=params, json=json_body) as response:
                    if response.status_code == 429 and method == "GET":
                        retry_after = self._retry_after_seconds(response)
                    if retry_after is None or attempt == MAX_PRETIX_RATE_LIMIT_RETRIES:
                        response.raise_for_status()
                    if retry_after is None:
                        chunks = []
                        size = 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > MAX_PRETIX_RESPONSE_BYTES:
                                raise PretixUnavailable(
                                    "Pretix response exceeds the safe size limit"
                                )
                            chunks.append(chunk)
                if retry_after is not None:
                    self._sleep(retry_after)
                    continue
                response_body = b"".join(chunks)
                if not response_body and response.status_code == 204:
                    return {}
                payload = json.loads(response_body)
                break
            except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PretixUnavailable("Pretix request failed") from exc
        if not isinstance(payload, dict):
            raise PretixUnavailable("Pretix returned an invalid response")
        return payload

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", path, params=params, json_body=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", path, json_body=payload)

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
