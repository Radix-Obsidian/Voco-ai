"""Tests for the BackgroundJobQueue.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_background_worker.py -v
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.graph.background_worker import BackgroundJobQueue


@pytest.mark.asyncio
async def test_submit_runs_coroutine_and_calls_on_complete():
    """submit() → coroutine runs → on_complete called with result."""
    queue = BackgroundJobQueue()
    on_complete = AsyncMock()

    async def my_coro():
        return "done"

    queue.submit("job-1", my_coro(), on_complete)
    # Give the event loop a moment to process the task
    await asyncio.sleep(0.1)

    on_complete.assert_called_once_with("job-1", "done")
    assert queue.active_count() == 0


@pytest.mark.asyncio
async def test_coroutine_raises_calls_on_complete_with_error():
    """coroutine raises → on_complete called with error string."""
    queue = BackgroundJobQueue()
    on_complete = AsyncMock()

    async def failing_coro():
        raise ValueError("boom")

    queue.submit("job-2", failing_coro(), on_complete)
    await asyncio.sleep(0.1)

    on_complete.assert_called_once()
    result_str = on_complete.call_args[0][1]
    assert "error" in result_str.lower()
    assert "boom" in result_str


@pytest.mark.asyncio
async def test_cancel_all_cancels_running_tasks():
    """cancel_all() → running tasks cancelled → on_complete called with cancel message."""
    queue = BackgroundJobQueue()
    on_complete = AsyncMock()

    async def slow_coro():
        await asyncio.sleep(999)
        return "should not reach"

    queue.submit("job-3", slow_coro(), on_complete)
    # Let the task start running
    await asyncio.sleep(0.05)
    assert queue.active_count() == 1

    queue.cancel_all()
    # Give time for the CancelledError to propagate and on_complete to fire
    await asyncio.sleep(0.3)

    on_complete.assert_called_once()
    result_str = on_complete.call_args[0][1]
    assert "cancelled" in result_str.lower()


@pytest.mark.asyncio
async def test_timeout_detection_increments_counter():
    """Timeout pattern in result string → timeout_count incremented."""
    queue = BackgroundJobQueue()
    on_complete = AsyncMock()

    async def timeout_coro():
        return "Background job abc timed out after 30 seconds."

    queue.submit("job-4", timeout_coro(), on_complete)
    await asyncio.sleep(0.1)

    assert queue.timeout_count == 1


@pytest.mark.asyncio
async def test_timeout_count_property_starts_at_zero():
    queue = BackgroundJobQueue()
    assert queue.timeout_count == 0
