"""Production readiness tests — dead code removal verification.

Proves that deprecated voice/STT code paths have been removed and
no phantom references remain in active source code.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_dead_code_removal.py -v
"""

from __future__ import annotations

import ast
import pathlib

import pytest


SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"


# ---------------------------------------------------------------------------
# 1. No voco_voice_input / voco_speak tool registrations
# ---------------------------------------------------------------------------


class TestDeadVoiceToolsRemoved:
    """ide_mcp_server.py should NOT register voco_voice_input or voco_speak as tools."""

    def test_no_voice_input_tool(self):
        source = (SRC_DIR / "ide_mcp_server.py").read_text()
        # Tool registration uses Tool(name="voco_voice_input", ...) pattern
        # Should only appear in comments, not in actual Tool() definitions
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("//"):
                continue
            if "Tool(" in line and "voco_voice_input" in line:
                pytest.fail(f"Line {i}: voco_voice_input still registered as Tool")

    def test_no_speak_tool(self):
        source = (SRC_DIR / "ide_mcp_server.py").read_text()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("//"):
                continue
            if "Tool(" in line and "voco_speak" in line:
                pytest.fail(f"Line {i}: voco_speak still registered as Tool")

    def test_no_voice_input_handler(self):
        """No if name == 'voco_voice_input' handler should exist."""
        source = (SRC_DIR / "ide_mcp_server.py").read_text()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if 'name == "voco_voice_input"' in line or "name == 'voco_voice_input'" in line:
                pytest.fail(f"Line {i}: voco_voice_input handler still present")

    def test_no_speak_handler(self):
        """No if name == 'voco_speak' handler should exist."""
        source = (SRC_DIR / "ide_mcp_server.py").read_text()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if 'name == "voco_speak"' in line or "name == 'voco_speak'" in line:
                pytest.fail(f"Line {i}: voco_speak handler still present")


# ---------------------------------------------------------------------------
# 2. Dead settings removed from VocoSettings interface
# ---------------------------------------------------------------------------


class TestDeadSettingsRemoved:
    """use-settings.ts should NOT contain STT_PROVIDER, WHISPER_MODEL, WAKE_WORD."""

    @pytest.fixture
    def settings_source(self):
        frontend_src = SRC_DIR.parent.parent / "mcp-gateway" / "src" / "hooks" / "use-settings.ts"
        if not frontend_src.exists():
            pytest.skip("Frontend source not available")
        return frontend_src.read_text()

    def test_no_stt_provider(self, settings_source):
        assert "STT_PROVIDER" not in settings_source

    def test_no_whisper_model(self, settings_source):
        assert "WHISPER_MODEL" not in settings_source

    def test_no_wake_word(self, settings_source):
        assert "WAKE_WORD" not in settings_source

    def test_has_github_token(self, settings_source):
        assert "GITHUB_TOKEN" in settings_source

    def test_has_global_hotkey(self, settings_source):
        assert "GLOBAL_HOTKEY" in settings_source


# ---------------------------------------------------------------------------
# 3. Billing rename: report_voice_turn → report_turn
# ---------------------------------------------------------------------------


class TestBillingRename:
    """billing/routes.py should export report_turn (not report_voice_turn)."""

    def test_report_turn_function_exists(self):
        from src.billing.routes import report_turn
        assert callable(report_turn)

    def test_no_report_voice_turn_function(self):
        import src.billing.routes as billing
        assert not hasattr(billing, "report_voice_turn"), \
            "report_voice_turn should be renamed to report_turn"


# ---------------------------------------------------------------------------
# 4. VocoState has orgo_computer_id
# ---------------------------------------------------------------------------


class TestVocoStateOrgoField:
    def test_orgo_computer_id_in_state(self):
        from src.graph.state import VocoState
        annotations = VocoState.__annotations__
        assert "orgo_computer_id" in annotations


# ---------------------------------------------------------------------------
# 5. Constants include Orgo values
# ---------------------------------------------------------------------------


class TestOrgoConstants:
    def test_boot_timeout(self):
        from src.constants import ORGO_BOOT_TIMEOUT
        assert ORGO_BOOT_TIMEOUT == 30.0

    def test_default_ram(self):
        from src.constants import ORGO_DEFAULT_RAM
        assert ORGO_DEFAULT_RAM == 4

    def test_default_cpu(self):
        from src.constants import ORGO_DEFAULT_CPU
        assert ORGO_DEFAULT_CPU == 2


# ---------------------------------------------------------------------------
# 6. OnboardingTour is text-first (no voice references)
# ---------------------------------------------------------------------------


class TestOnboardingTourTextFirst:
    """OnboardingTour.tsx should reference 'Text-First' not 'Voice First'."""

    @pytest.fixture
    def tour_source(self):
        frontend_src = SRC_DIR.parent.parent / "mcp-gateway" / "src" / "components" / "OnboardingTour.tsx"
        if not frontend_src.exists():
            pytest.skip("Frontend source not available")
        return frontend_src.read_text()

    def test_no_voice_first(self, tour_source):
        assert "Voice First" not in tour_source
        assert "Voice-First" not in tour_source

    def test_has_text_first(self, tour_source):
        assert "Text-First" in tour_source

    def test_no_mic_icon(self, tour_source):
        # Mic icon import should be removed
        assert "Mic," not in tour_source
        assert "Mic }" not in tour_source

    def test_has_message_square_icon(self, tour_source):
        assert "MessageSquare" in tour_source
