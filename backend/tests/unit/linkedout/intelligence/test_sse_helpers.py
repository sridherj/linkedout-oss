# SPDX-License-Identifier: Apache-2.0
"""Tests for SSE helper utilities — stream_with_heartbeat and sse_line."""
from __future__ import annotations

import asyncio
import json

import pytest

from linkedout.intelligence.controllers._sse_helpers import sse_line, stream_with_heartbeat


# ---------------------------------------------------------------------------
# 1. test_heartbeat_emitted_after_interval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_emitted_after_interval():
    """When the source generator is slower than the heartbeat interval, heartbeats appear."""

    async def slow_generator():
        yield "event1"
        await asyncio.sleep(0.2)  # longer than heartbeat interval
        yield "event2"

    chunks: list[str] = []
    async for chunk in stream_with_heartbeat(slow_generator(), interval=0.05):
        chunks.append(chunk)

    heartbeats = [c for c in chunks if "heartbeat" in c]
    assert len(heartbeats) >= 1, f"Expected at least 1 heartbeat, got {chunks}"

    # Real events should still be present
    assert "event1" in chunks
    assert "event2" in chunks


# ---------------------------------------------------------------------------
# 2. test_no_heartbeat_when_events_are_fast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_heartbeat_when_events_are_fast():
    """When events arrive faster than the heartbeat interval, no heartbeats are emitted."""

    async def fast_generator():
        for i in range(5):
            yield f"event{i}"
            # No sleep — much faster than any heartbeat interval

    chunks: list[str] = []
    async for chunk in stream_with_heartbeat(fast_generator(), interval=10):
        chunks.append(chunk)

    heartbeats = [c for c in chunks if "heartbeat" in c]
    assert heartbeats == [], f"Expected no heartbeats, got {heartbeats}"
    assert len(chunks) == 5


# ---------------------------------------------------------------------------
# 3. test_stream_cleanup_on_client_disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_cleanup_on_client_disconnect():
    """Cancelling the consumer mid-stream triggers cleanup (finally block runs)."""

    cleanup_ran = False

    async def long_generator():
        nonlocal cleanup_ran
        try:
            for i in range(100):
                yield f"event{i}"
                await asyncio.sleep(0.1)
        finally:
            cleanup_ran = True

    async def consume():
        count = 0
        async for _chunk in stream_with_heartbeat(long_generator(), interval=0.05):
            count += 1
            if count >= 2:
                break  # simulate client disconnect

    await consume()
    # Allow a tick for finally blocks to execute
    await asyncio.sleep(0.05)
    assert cleanup_ran, "Generator finally block should have executed on disconnect"


# ---------------------------------------------------------------------------
# 4. test_heartbeat_format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_format():
    """Heartbeat output matches SSE format: 'data: {"type": "heartbeat"}\\n\\n'."""

    async def slow_generator():
        await asyncio.sleep(0.15)
        yield "done"

    chunks: list[str] = []
    async for chunk in stream_with_heartbeat(slow_generator(), interval=0.05):
        chunks.append(chunk)

    heartbeats = [c for c in chunks if "heartbeat" in c]
    assert len(heartbeats) >= 1

    for hb in heartbeats:
        parsed = json.loads(hb.strip().removeprefix("data: "))
        assert parsed == {"type": "heartbeat"}
        assert hb.endswith("\n\n")


# ---------------------------------------------------------------------------
# 5. test_sse_line_format
# ---------------------------------------------------------------------------


def test_sse_line_format():
    """sse_line() produces valid SSE: 'data: <json>\\n\\n'."""
    event = {"type": "results", "payload": [1, 2, 3]}
    line = sse_line(event)

    assert line.startswith("data: ")
    assert line.endswith("\n\n")

    payload = json.loads(line[len("data: "):].strip())
    assert payload == event
