"""Centralized constants for Voco cognitive engine.

All magic numbers and timeout values should be defined here for easy maintenance.
"""

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
TTS_TAIL_DELAY: float = 0.6  # Delay after TTS stream completes

# Model settings
DEFAULT_MODEL: str = "haiku_tools"  # claude-haiku-4-5 with tools (cost-safe default)
FALLBACK_MODEL: str = "haiku"  # claude-haiku-4-5

# Environment keys
ALLOWED_ENV_KEYS: set[str] = {
    "CARTESIA_API_KEY",
    "GITHUB_TOKEN",
    "TTS_VOICE",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "GOOGLE_API_KEY",
}

# Claude Code delegation
CLAUDE_CODE_TIMEOUT: float = 300.0  # 5 min max for Claude Code subprocess

# Tauri config
TAURI_APP_ID: str = "com.voco.mcp-gateway"
