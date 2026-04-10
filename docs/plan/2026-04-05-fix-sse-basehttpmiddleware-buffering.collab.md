# Plan: Fix SSE stream buffering caused by BaseHTTPMiddleware

## Root Cause

`RequestLoggingMiddleware` in `main.py:176` extends Starlette's `BaseHTTPMiddleware`, which **buffers streaming responses**. When `call_next()` returns a `StreamingResponse`, the middleware wraps the body in an internal `anyio.MemoryObjectStream` that doesn't flush chunks immediately. Heartbeats are yielded by the generator but buffered inside the middleware — they never reach the client until the full response completes or enough data accumulates.

This is a well-known Starlette limitation: `BaseHTTPMiddleware` is incompatible with SSE/streaming.

**Why `time.sleep` worked:** The total response was still short enough that the buffered chunks were flushed before Chrome's timeout. With real LLM calls taking >30s, the buffer holds the heartbeats too long.

**Why DevTools masked it:** Chrome's network inspector changes connection management behavior, keeping connections alive longer.

## Fix

Replace `BaseHTTPMiddleware` with a pure ASGI middleware that passes the response through without buffering.

### File: `shared/utilities/request_logging_middleware.py`

Replace the current implementation:

```python
"""Request/response logging middleware for FastAPI."""
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from shared.utilities.logger import get_logger

logger = get_logger('http.access')


class RequestLoggingMiddleware:
    """Log method, path, status code, and duration for every request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            '%s %s %d %.1fms',
            scope.get('method', ''),
            scope.get('path', ''),
            status_code,
            duration_ms,
        )
```

### File: `main.py` — no changes needed

`app.add_middleware(RequestLoggingMiddleware)` works the same way with pure ASGI middleware.

### Cleanup

- Remove debug logs from `_sse_helpers.py` (the `[heartbeat]` INFO logs)

## Verification

1. Restart backend
2. Trigger best-hop on a profile with many mutual connections (slow LLM response)
3. **Without** DevTools open, confirm the UI transitions to "Analyzing" and results appear
4. Confirm request logging still works for normal (non-streaming) endpoints
