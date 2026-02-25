"""Centralized ID generation utilities for Voco."""

import uuid


def generate_call_id(prefix: str = "") -> str:
    """Generate a unique call ID with optional prefix.

    Args:
        prefix: Optional prefix for the ID (e.g., 'voco', 'screen', 'scan')

    Returns:
        A short 8-character hex string, optionally prefixed with hyphen separator.
    """
    unique_part = uuid.uuid4().hex[:8]
    if prefix:
        return f"{prefix}-{unique_part}"
    return unique_part


def generate_job_id() -> str:
    """Generate a unique background job ID.

    Returns:
        A short 8-character hex string.
    """
    return uuid.uuid4().hex[:8]


def generate_thread_id() -> str:
    """Generate a unique thread/session ID.

    Returns:
        A 16-character hex string for longer uniqueness.
    """
    return uuid.uuid4().hex[:16]
