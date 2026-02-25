"""Tests for turn_archive — prompt hashing and JSON archival.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_turn_archive.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from src.graph.turn_archive import compute_prompt_hash, archive_turn


# ---------------------------------------------------------------------------
# 1. compute_prompt_hash → 12-char hex
# ---------------------------------------------------------------------------


class TestComputePromptHash:
    def test_returns_12_char_hex(self):
        h = compute_prompt_hash("You are Voco, an AI coding assistant.")
        assert len(h) == 12
        # Must be valid hex
        int(h, 16)

    def test_deterministic(self):
        prompt = "Hello world"
        assert compute_prompt_hash(prompt) == compute_prompt_hash(prompt)


# ---------------------------------------------------------------------------
# 2. archive_turn → writes JSON to expected path
# ---------------------------------------------------------------------------


class TestArchiveTurn:
    def test_writes_json_file(self, tmp_path: Path):
        with patch("src.graph.turn_archive._get_app_data_dir", return_value=tmp_path):
            prompt_hash = archive_turn(
                session_id="test-session-001",
                turn_number=1,
                system_prompt="You are Voco.",
                model_name="claude-sonnet-4-5-20250929",
                messages=[HumanMessage(content="Hello")],
                tool_calls=None,
            )

        expected_path = tmp_path / "sessions" / "test-session-001" / "turn_1.json"
        assert expected_path.exists()
        assert len(prompt_hash) == 12

    def test_archived_json_contains_required_fields(self, tmp_path: Path):
        with patch("src.graph.turn_archive._get_app_data_dir", return_value=tmp_path):
            archive_turn(
                session_id="test-session-002",
                turn_number=3,
                system_prompt="You are Voco.",
                model_name="claude-haiku-4-5-20251001",
                messages=[
                    HumanMessage(content="Fix the bug"),
                    AIMessage(content="I'll fix it."),
                ],
                tool_calls=[{"name": "search_codebase", "args": {"pattern": "bug"}, "id": "tc-1"}],
            )

        archive_path = tmp_path / "sessions" / "test-session-002" / "turn_3.json"
        data = json.loads(archive_path.read_text(encoding="utf-8"))

        assert data["session_id"] == "test-session-002"
        assert data["turn_number"] == 3
        assert data["model_name"] == "claude-haiku-4-5-20251001"
        assert len(data["prompt_hash"]) == 12
        assert data["system_prompt"] == "You are Voco."
        assert len(data["messages"]) == 2
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "search_codebase"


# ---------------------------------------------------------------------------
# 3. Different prompts → different hashes
# ---------------------------------------------------------------------------


class TestPromptHashUniqueness:
    def test_different_prompts_different_hashes(self):
        h1 = compute_prompt_hash("You are Voco v1.")
        h2 = compute_prompt_hash("You are Voco v2.")
        assert h1 != h2

    def test_empty_prompt_still_hashes(self):
        h = compute_prompt_hash("")
        assert len(h) == 12
        int(h, 16)
