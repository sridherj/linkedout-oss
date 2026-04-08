# SPDX-License-Identifier: Apache-2.0
"""Request/response logging middleware for FastAPI.

Generates a correlation ID per request, stores it in a contextvar for
downstream use, returns it as an X-Correlation-ID response header,
and logs method/path/status/duration with the correlation ID.
"""
import time
from urllib.parse import parse_qs, urlencode

from starlette.types import ASGIApp, Receive, Scope, Send

from shared.utilities.correlation import (
    generate_correlation_id,
    set_correlation_id,
)
from shared.utilities.logger import get_logger

logger = get_logger('http.access', component='backend')

# Query parameter names whose values should be redacted in logs
_SENSITIVE_PARAMS = frozenset({
    'api_key', 'apikey', 'token', 'access_token', 'refresh_token',
    'secret', 'password', 'authorization',
})


def _redact_query_string(raw: bytes) -> str:
    """Parse a query string and redact sensitive parameter values."""
    if not raw:
        return ''
    parsed = parse_qs(raw.decode('utf-8', errors='replace'), keep_blank_values=True)
    redacted = {}
    for key, values in parsed.items():
        if key.lower() in _SENSITIVE_PARAMS:
            redacted[key] = ['[REDACTED]'] * len(values)
        else:
            redacted[key] = values
    return urlencode(redacted, doseq=True)


class RequestLoggingMiddleware:
    """Log method, path, status code, and duration for every request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate and store correlation ID for this request
        cid = generate_correlation_id('req')
        set_correlation_id(cid)

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Inject X-Correlation-ID into response headers
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-correlation-id", cid.encode("utf-8"))
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.perf_counter() - start) * 1000
        method = scope.get('method', '')
        path = scope.get('path', '')
        query = _redact_query_string(scope.get('query_string', b''))
        full_path = f'{path}?{query}' if query else path
        logger.info(
            f'{method} {full_path} {status_code} {duration_ms:.1f}ms [{cid}]',
        )
