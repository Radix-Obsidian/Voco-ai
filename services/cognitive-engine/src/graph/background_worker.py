"""Background job queue for async tool execution.

Implements the Instant ACK + Background Queue pattern (Milestone 11).

When a long-running tool is called, the orchestrator immediately returns an
ACK ToolMessage to satisfy Anthropic's strict tool_call → tool_result API
contract.  The real work runs inside an ``asyncio.Task``.  On completion the
worker injects a ``SystemMessage`` into the LangGraph checkpoint so Claude
knows the result on the user's next turn.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class BackgroundJobQueue:
    """Manages async tool coroutines, firing a callback when each one finishes."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._timeout_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        job_id: str,
        coro: Coroutine[Any, Any, Any],
        on_complete: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Schedule *coro* as a background asyncio.Task.

        Args:
            job_id:      Unique identifier for this job (used in log messages
                         and the state injection notification).
            coro:        The coroutine to execute in the background.
            on_complete: Async callback invoked as ``on_complete(job_id, result_str)``
                         after *coro* finishes (or errors).  The callback is
                         responsible for injecting the result into LangGraph state.
        """
        task = asyncio.create_task(self._run(job_id, coro, on_complete))
        self._tasks[job_id] = task
        task.add_done_callback(lambda t: self._tasks.pop(job_id, None))
        logger.info(
            "[BackgroundQueue] Job %s submitted. Active jobs: %d",
            job_id,
            len(self._tasks),
        )

    def active_count(self) -> int:
        """Return the number of currently running background jobs."""
        return len(self._tasks)

    @property
    def timeout_count(self) -> int:
        """Return the total number of jobs that ended with a timeout."""
        return self._timeout_count

    def cancel_all(self) -> None:
        """Cancel every pending background job (e.g. on session shutdown)."""
        for task in list(self._tasks.values()):
            task.cancel()
        logger.info("[BackgroundQueue] All background jobs cancelled.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run(
        self,
        job_id: str,
        coro: Coroutine[Any, Any, Any],
        on_complete: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Internal runner — always fires *on_complete*, even on failure."""
        try:
            result = await coro
            result_str = str(result)
            if "timed out" in result_str.lower():
                self._timeout_count += 1
            logger.info("[BackgroundQueue] Job %s completed successfully.", job_id)
            await on_complete(job_id, result_str)
        except asyncio.CancelledError:
            logger.warning("[BackgroundQueue] Job %s was cancelled.", job_id)
            await on_complete(job_id, f"Job {job_id} was cancelled before completion.")
        except Exception as exc:
            logger.error(
                "[BackgroundQueue] Job %s failed: %s",
                job_id,
                exc,
                exc_info=True,
            )
            await on_complete(job_id, f"Background job {job_id} encountered an error: {exc}")
