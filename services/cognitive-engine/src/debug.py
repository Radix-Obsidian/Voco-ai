import logging
import json
from datetime import datetime


class VocoDebugLogger:
    """Centralized debugging for WebSocket, auth, and system issues."""

    def __init__(self):
        self.logger = logging.getLogger("voco.debug")
        self.events = []  # In-memory event log

    def log_ws_event(self, event_type: str, session_id: str, details: dict):
        """Log WebSocket events (connect, disconnect, auth_sync, error)."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "session_id": session_id,
            "details": details,
        }
        self.events.append(entry)
        self.logger.info("[WS] %s: %s", event_type, json.dumps(entry))

    def log_auth_failure(self, session_id: str, reason: str, error: Exception = None):
        """Log authentication failures."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "auth_failure",
            "session_id": session_id,
            "reason": reason,
            "error": str(error) if error else None,
        }
        self.events.append(entry)
        self.logger.error("[AUTH] %s: %s", reason, error)

    def get_recent_events(self, limit: int = 100) -> list:
        """Return recent debug events."""
        return self.events[-limit:]


debug_logger = VocoDebugLogger()
