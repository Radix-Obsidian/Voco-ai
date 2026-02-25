"""SessionContext — per-session mutable state container.

Replaces the ``nonlocal`` closures scattered across ``voco_stream`` with a
single, explicit dataclass that every pipeline phase receives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class SessionContext:
    """All per-session mutable state for a single WebSocket connection."""

    websocket: WebSocket
    thread_id: str
    config: dict
    audio_buffer: bytearray = field(default_factory=bytearray)
    tts_active: bool = False
    auth_uid: str = "local"
    auth_token: str = ""
    metrics: dict[str, int] = field(default_factory=lambda: {
        "timeout_count": 0,
        "rpc_count": 0,
        "turn_count": 0,
    })
