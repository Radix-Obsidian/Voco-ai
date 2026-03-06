"""Production readiness tests — Orgo tool signal dicts.

Validates all 6 Orgo tools return correct signal-dict shapes
that main.py intercepts can match on.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_orgo_tools.py -v
"""

from __future__ import annotations

import pytest

from src.graph.tools import (
    orgo_create_sandbox,
    orgo_run_command,
    orgo_run_python,
    orgo_screenshot,
    orgo_upload_file,
    orgo_stop_sandbox,
)


# ---------------------------------------------------------------------------
# 1. orgo_create_sandbox
# ---------------------------------------------------------------------------


class TestOrgoCreateSandbox:
    def test_signal_dict_shape(self):
        result = orgo_create_sandbox.invoke({"project_name": "my-app"})
        assert result["method"] == "orgo/create_sandbox"
        assert result["params"]["project_name"] == "my-app"
        assert result["params"]["setup_commands"] == ""

    def test_with_setup_commands(self):
        result = orgo_create_sandbox.invoke({
            "project_name": "react-app",
            "setup_commands": "npm init -y && npm install react",
        })
        assert result["params"]["setup_commands"] == "npm init -y && npm install react"


# ---------------------------------------------------------------------------
# 2. orgo_run_command
# ---------------------------------------------------------------------------


class TestOrgoRunCommand:
    def test_signal_dict_shape(self):
        result = orgo_run_command.invoke({"command": "npm test"})
        assert result["method"] == "orgo/run_command"
        assert result["params"]["command"] == "npm test"
        assert result["params"]["timeout"] == 30

    def test_custom_timeout(self):
        result = orgo_run_command.invoke({"command": "npm install", "timeout": 120})
        assert result["params"]["timeout"] == 120


# ---------------------------------------------------------------------------
# 3. orgo_run_python
# ---------------------------------------------------------------------------


class TestOrgoRunPython:
    def test_signal_dict_shape(self):
        result = orgo_run_python.invoke({"code": "print('hello')"})
        assert result["method"] == "orgo/run_python"
        assert result["params"]["code"] == "print('hello')"
        assert result["params"]["timeout"] == 10


# ---------------------------------------------------------------------------
# 4. orgo_screenshot
# ---------------------------------------------------------------------------


class TestOrgoScreenshot:
    def test_signal_dict_shape(self):
        result = orgo_screenshot.invoke({})
        assert result["method"] == "orgo/screenshot"
        assert result["params"] == {}


# ---------------------------------------------------------------------------
# 5. orgo_upload_file
# ---------------------------------------------------------------------------


class TestOrgoUploadFile:
    def test_signal_dict_shape(self):
        result = orgo_upload_file.invoke({
            "file_path": "/home/user/app/index.js",
            "content": "console.log('hello');",
        })
        assert result["method"] == "orgo/upload_file"
        assert result["params"]["file_path"] == "/home/user/app/index.js"
        assert result["params"]["content"] == "console.log('hello');"


# ---------------------------------------------------------------------------
# 6. orgo_stop_sandbox
# ---------------------------------------------------------------------------


class TestOrgoStopSandbox:
    def test_signal_dict_shape(self):
        result = orgo_stop_sandbox.invoke({})
        assert result["method"] == "orgo/stop_sandbox"
        assert result["params"] == {}


# ---------------------------------------------------------------------------
# 7. All orgo tools in get_all_tools()
# ---------------------------------------------------------------------------


class TestOrgoToolsRegistered:
    def test_all_orgo_tools_in_registry(self):
        from unittest.mock import MagicMock, patch

        mock_tool = MagicMock()
        mock_tool.name = "tavily_search"
        mock_tool.description = "Search the web."

        with patch("src.graph.tools.get_web_search", return_value=mock_tool):
            import src.graph.tools as _mod
            _mod._web_search_instance = None
            from src.graph.tools import get_all_tools
            tools = get_all_tools()
            _mod._web_search_instance = None

        tool_names = {t.name for t in tools}
        orgo_names = {
            "orgo_create_sandbox",
            "orgo_run_command",
            "orgo_run_python",
            "orgo_screenshot",
            "orgo_upload_file",
            "orgo_stop_sandbox",
        }
        missing = orgo_names - tool_names
        assert not missing, f"Orgo tools missing from registry: {missing}"

    def test_orgo_tools_have_descriptions(self):
        from unittest.mock import MagicMock, patch

        mock_tool = MagicMock()
        mock_tool.name = "tavily_search"
        mock_tool.description = "Search the web."

        with patch("src.graph.tools.get_web_search", return_value=mock_tool):
            import src.graph.tools as _mod
            _mod._web_search_instance = None
            from src.graph.tools import get_all_tools
            tools = get_all_tools()
            _mod._web_search_instance = None

        orgo_tools = [t for t in tools if t.name.startswith("orgo_")]
        assert len(orgo_tools) == 6
        for t in orgo_tools:
            assert t.description, f"Tool {t.name} missing description"
            assert len(t.description) > 20, f"Tool {t.name} description too short"
