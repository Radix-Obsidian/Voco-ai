"""Centralized constants for Voco cognitive engine.

All magic numbers and timeout values should be defined here for easy maintenance.
"""

# Audio processing
AUDIO_MIN_BUFFER_SIZE: int = 6400  # 200ms of audio at 16kHz mono 16-bit
SILENCE_FRAMES_FOR_TURN_END: int = 40  # 40 × 32ms = 1.28s silence before turn-end

# WebSocket timeouts (seconds)
WEBSOCKET_RECEIVE_TIMEOUT: float = 30.0  # Main receive loop timeout
WEBSOCKET_MESSAGE_TIMEOUT: float = 10.0  # Screen frames wait
WEBSOCKET_SCAN_TIMEOUT: float = 30.0  # Security scan wait

# HITL (Human-in-the-Loop) timeouts (seconds)
HITL_PROPOSAL_TIMEOUT: float = 120.0  # 2 minutes for user to approve/reject proposals
HITL_COMMAND_TIMEOUT: float = 120.0  # 2 minutes for user to approve/reject commands

# RPC timeouts (seconds)
RPC_BACKGROUND_TIMEOUT: float = 30.0  # Background job RPC wait
RPC_FUTURE_MAX_AGE: float = 300.0  # 5 minutes before stale future cleanup

# TTS timing (seconds)
TTS_GRACE_PERIOD: float = 0.5  # Delay after TTS before re-enabling mic
TTS_TAIL_DELAY: float = 0.6  # Delay before resuming mic after TTS ends

# Model settings
DEFAULT_MODEL: str = "sonnet"  # claude-sonnet-4-5
FALLBACK_MODEL: str = "haiku"  # claude-haiku-4-5

# Environment keys
ALLOWED_ENV_KEYS: set[str] = {
    "DEEPGRAM_API_KEY",
    "CARTESIA_API_KEY",
    "GITHUB_TOKEN",
    "TTS_VOICE",
    "SUPABASE_URL",
    "GOOGLE_API_KEY",
}

# Tauri config
TAURI_APP_ID: str = "com.voco.mcp-gateway"
