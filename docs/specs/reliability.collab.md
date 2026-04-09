---
feature: reliability
module: src/shared/infra/reliability
linked_files:
  - src/shared/infra/reliability/retry_policy.py
  - src/shared/infra/reliability/timeout_policy.py
  - src/shared/infra/reliability/rate_limiter.py
last_verified: 2026-03-25
version: 1
---

# Reliability

**Created:** 2026-03-25 — Backfilled from existing implementation

## Intent

Provide config-driven reliability patterns for outbound calls (LLM, external APIs): retry with exponential backoff, timeout enforcement, and token-bucket rate limiting. Each pattern is a composable decorator or utility that can be applied to any function.

## Behaviors

### Retry Policy

- **Config-driven retry**: `RetryConfig` defines `max_attempts` (default 3), `min_wait_seconds` (default 1.0), `max_wait_seconds` (default 60.0), and `retryable_exceptions` (default: ConnectionError, TimeoutError). Verify retries occur the configured number of times.

- **Exponential backoff**: `retry_with_policy(config)` returns a tenacity retry decorator with exponential wait between `min_wait` and `max_wait`. Verify wait times increase exponentially.

- **Selective retry**: Only exceptions matching `retryable_exceptions` trigger retries. Other exceptions are raised immediately. Verify non-retryable exceptions propagate without retry.

- **Pre-built configs**: `LLM_RETRY_CONFIG` (3 attempts, 2-30s wait) and `EXTERNAL_API_RETRY_CONFIG` (3 attempts, 1-15s wait) are available. Verify configs have the documented values.

- **Reraise on exhaustion**: After all attempts are exhausted, the last exception is re-raised (not wrapped). Verify the original exception type is preserved.

### Timeout Policy

- **Signal-based timeout**: `timeout_with_policy(config)` uses `signal.SIGALRM` on Unix to enforce a hard timeout. Raises `TimeoutError` if the function exceeds `timeout_seconds`. Verify the function is interrupted after the timeout.

- **Platform fallback**: On platforms without `SIGALRM` or in non-main threads, the decorator is a no-op. Verify the function executes without timeout enforcement on unsupported platforms.

- **Pre-built configs**: `LLM_TIMEOUT_CONFIG` (120s) and `EXTERNAL_API_TIMEOUT_CONFIG` (30s) are available. Verify configs have the documented values.

- **Handler restoration**: After function execution (success or timeout), the original signal handler is restored. Verify no signal handler leaks.

### Rate Limiter

- **Token bucket**: `RateLimiter` implements a token-bucket algorithm. Tokens refill at `requests_per_minute / 60` per second up to the maximum. Verify tokens are consumed and refilled at the correct rate.

- **Blocking acquire**: `acquire(tokens=1)` blocks until the requested tokens are available. Verify the call blocks when tokens are exhausted and resumes after refill.

- **Thread safety**: The token bucket uses a `threading.Lock`. Verify concurrent calls do not cause race conditions.

- **Configurable limits**: `RateLimitConfig` defines `requests_per_minute` (default 60) and `tokens_per_minute` (default 100,000). Verify different configs produce different rate limits.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Retry library | Tenacity | Custom retry loop | Battle-tested, configurable, good logging support |
| 2026-03-25 | Timeout mechanism | signal.SIGALRM | threading.Timer or asyncio.wait_for | Hard interrupt for sync code; graceful fallback for unsupported platforms |
| 2026-03-25 | Rate limiter | In-process token bucket | Redis-based distributed limiter | Sufficient for single-process deployment; no external dependency |

## Not Included

- Circuit breaker pattern
- Distributed rate limiting (Redis)
- Bulkhead isolation
- Health check integration with retry policies
- Jitter in retry backoff (tenacity supports it but not configured)
