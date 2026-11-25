"""
Security helpers for the WebScraper API.

- URL validation / SSRF protection (blocks loopback, private, link-local,
  metadata and other non-public targets unless explicitly allowed)
- Size-limited, redirect-validated HTTP fetching
- Optional HTTP Basic / Bearer authentication (ASGI middleware, covers WebSockets)
"""

import base64
import hmac
import ipaddress
import logging
import os
import socket
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# URL validation (SSRF protection)
# ---------------------------------------------------------------------------

ALLOWED_SCHEMES = ("http", "https")
MAX_REDIRECTS = int(os.getenv("MAX_REDIRECTS", "5"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))  # 10 MB


class UnsafeURLError(ValueError):
    """Raised when a URL points to a disallowed target."""


def allow_private_urls() -> bool:
    # Read at call time so tests / operators can toggle it without re-import
    return _env_bool("ALLOW_PRIVATE_URLS", False)


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"))  # CGNAT
    )


def validate_url(url: str) -> str:
    """
    Validate that ``url`` is an http(s) URL pointing to a public host.

    Returns the URL unchanged on success, raises UnsafeURLError otherwise.
    Set ALLOW_PRIVATE_URLS=true to allow internal targets (e.g. intranet scraping).
    """
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL is required")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"URL scheme '{parsed.scheme}' is not allowed (only http/https)")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    if allow_private_urls():
        return url

    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError:
        raise UnsafeURLError("URL has an invalid port")

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeURLError(f"Host '{host}' could not be resolved")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not _is_public_ip(ip):
            raise UnsafeURLError(
                f"Access to non-public address {ip} ('{host}') is blocked. "
                "Set ALLOW_PRIVATE_URLS=true to allow internal targets."
            )
    return url


class ContentTooLargeError(ValueError):
    pass


def safe_get(
    url: str,
    session: Optional[requests.Session] = None,
    max_bytes: Optional[int] = None,
    max_redirects: Optional[int] = None,
    **kwargs,
) -> requests.Response:
    """
    Drop-in replacement for ``requests.get`` / ``session.get`` that

    * validates the initial URL and every redirect target (SSRF protection)
    * enforces a maximum response size (MAX_CONTENT_LENGTH)

    The returned Response has its body already loaded (``.content`` / ``.text`` work).
    """
    max_bytes = MAX_CONTENT_LENGTH if max_bytes is None else max_bytes
    max_redirects = MAX_REDIRECTS if max_redirects is None else max_redirects
    kwargs.pop("allow_redirects", None)
    kwargs.pop("stream", None)
    http = session or requests

    current = url
    for _ in range(max_redirects + 1):
        validate_url(current)
        response = http.get(current, allow_redirects=False, stream=True, **kwargs)

        if response.is_redirect:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise requests.TooManyRedirects("Redirect without Location header")
            current = urljoin(current, location)
            continue

        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            response.close()
            raise ContentTooLargeError(f"Response too large ({declared} bytes, limit {max_bytes})")

        chunks = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > max_bytes:
                    raise ContentTooLargeError(f"Response exceeds limit of {max_bytes} bytes")
                chunks.append(chunk)
        finally:
            response.close()

        response._content = b"".join(chunks)
        response._content_consumed = True
        return response

    raise requests.TooManyRedirects(f"Exceeded {max_redirects} redirects")


# ---------------------------------------------------------------------------
# Optional authentication
# ---------------------------------------------------------------------------

# Paths that never require auth (container health checks, static assets)
PUBLIC_PATHS = ("/api/health",)


class AuthMiddleware:
    """
    Pure-ASGI middleware enforcing HTTP Basic auth (or ``Authorization: Bearer <password>``
    / ``X-API-Key: <password>``) for all HTTP and WebSocket requests.

    Enabled only when AUTH_PASSWORD is set. AUTH_USERNAME defaults to "admin".
    Browsers show a native login prompt and then send the credentials automatically
    for fetch() and WebSocket requests, so the web UI keeps working.
    """

    def __init__(self, app, username: str, password: str, public_paths: Iterable[str] = PUBLIC_PATHS):
        self.app = app
        self.username = username.encode()
        self.password = password.encode()
        self.public_paths = tuple(public_paths)

    def _authorized(self, headers: dict) -> bool:
        api_key = headers.get(b"x-api-key")
        if api_key is not None:
            return hmac.compare_digest(api_key, self.password)

        auth = headers.get(b"authorization", b"")
        scheme, _, value = auth.partition(b" ")
        scheme = scheme.lower()
        if scheme == b"bearer":
            return hmac.compare_digest(value.strip(), self.password)
        if scheme == b"basic":
            try:
                decoded = base64.b64decode(value.strip(), validate=True)
            except Exception:
                return False
            user, sep, pwd = decoded.partition(b":")
            if not sep:
                return False
            # Evaluate both to keep timing constant
            user_ok = hmac.compare_digest(user, self.username)
            pwd_ok = hmac.compare_digest(pwd, self.password)
            return user_ok and pwd_ok
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if scope["type"] == "http" and (scope.get("method") == "OPTIONS" or path in self.public_paths):
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        if self._authorized(headers):
            return await self.app(scope, receive, send)

        if scope["type"] == "websocket":
            # Reject the handshake
            await send({"type": "websocket.close", "code": 1008})
            return

        body = b'{"detail":"Authentication required"}'
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", b'Basic realm="WebScraper API", charset="UTF-8"'),
            ],
        })
        await send({"type": "http.response.body", "body": body})
