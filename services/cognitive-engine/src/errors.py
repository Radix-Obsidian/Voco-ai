"""VocoError envelope — structured error reporting over WebSocket.

Every error sent to the frontend follows a consistent JSON shape so the
Tauri UI can render toasts with actionable information and the backend
logs remain machine-parseable.

Error codes
-----------
E_STT_FAILED       Deepgram transcription error.
E_TTS_FAILED       Cartesia synthesis error.
E_RPC_TIMEOUT      Tauri JSON-RPC call exceeded its deadline.
E_GRAPH_FAILED     LangGraph invocation raised.
E_AUTH_EXPIRED      Supabase / LiteLLM token no longer valid.
E_MODEL_OVERLOADED  Upstream model returned 529 / rate-limit.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ErrorCode(str, enum.Enum):
    E_STT_FAILED = "E_STT_FAILED"
    E_TTS_FAILED = "E_TTS_FAILED"
    E_RPC_TIMEOUT = "E_RPC_TIMEOUT"
    E_GRAPH_FAILED = "E_GRAPH_FAILED"
    E_AUTH_EXPIRED = "E_AUTH_EXPIRED"
    E_MODEL_OVERLOADED = "E_MODEL_OVERLOADED"


@dataclass
class VocoError:
    code: str
    message: str
    recoverable: bool = True
    session_id: str = ""
    details: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": "error",
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "session_id": self.session_id,
        }
        if self.details:
            d["details"] = self.details
        return d


async def send_error(websocket: WebSocket, error: VocoError) -> None:
    """Serialize *error* and send it as a JSON message on *websocket*.

    Silently catches send failures (the socket may already be closed).
    """
    try:
        await websocket.send_json(error.to_dict())
        logger.warning(
            "[VocoError] Sent %s to client: %s (session=%s)",
            error.code,
            error.message,
            error.session_id,
        )
    except Exception as exc:
        logger.debug("[VocoError] Failed to send error to client: %s", exc)
