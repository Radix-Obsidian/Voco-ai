"""Tests for session_memory — save/load JSONL session history."""

import json
import os
import tempfile

import pytest

from src.graph.session_memory import load_session_history, save_session_entry


def test_save_creates_jsonl_file():
    """save_session_entry creates .voco/sessions.jsonl and writes valid JSONL."""
    with tempfile.TemporaryDirectory() as tmp:
        save_session_entry(
            project_path=tmp,
            transcript="Set up GitHub secrets",
            actions=["propose_command"],
            files=["services/cognitive-engine/.env"],
            summary="Configured secrets.",
            session_id="session-test1",
            model="claude-sonnet-4-5-20250929",
        )

        path = os.path.join(tmp, ".voco", "sessions.jsonl")
        assert os.path.exists(path), ".voco/sessions.jsonl was not created"

        with open(path, encoding="utf-8") as fh:
            lines = fh.read().strip().splitlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["transcript"] == "Set up GitHub secrets"
        assert entry["actions"] == ["propose_command"]
        assert entry["files"] == ["services/cognitive-engine/.env"]
        assert entry["summary"] == "Configured secrets."
        assert entry["session_id"] == "session-test1"
        assert entry["model"] == "claude-sonnet-4-5-20250929"
        assert "ts" in entry


def test_load_returns_formatted_string():
    """load_session_history returns a formatted block from saved entries."""
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(3):
            save_session_entry(
                project_path=tmp,
                transcript=f"Task number {i}",
                actions=[f"tool_{i}"],
                summary=f"Did thing {i}.",
                session_id="session-fmt",
            )

        result = load_session_history(tmp)
        assert result.startswith("## Session Memory")
        assert "Task number 0" in result
        assert "Task number 2" in result
        assert "tool_1" in result
        assert "Did thing 2." in result


def test_load_empty_returns_empty_string():
    """load_session_history returns '' when file does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        result = load_session_history(tmp)
        assert result == ""


def test_load_no_project_path_returns_empty():
    """load_session_history returns '' when project_path is empty."""
    assert load_session_history("") == ""


def test_max_entries_cap():
    """load_session_history only returns the last max_entries entries."""
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(30):
            save_session_entry(
                project_path=tmp,
                transcript=f"Entry {i}",
                session_id="session-cap",
            )

        result = load_session_history(tmp, max_entries=20)
        # First 10 entries (0-9) should be trimmed
        assert "Entry 0" not in result
        assert "Entry 9" not in result
        # Last 20 entries (10-29) should be present
        assert "Entry 10" in result
        assert "Entry 29" in result
